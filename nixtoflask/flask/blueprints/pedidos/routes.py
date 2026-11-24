import os
import re
from datetime import datetime

from flask import Blueprint, request, jsonify, session, current_app
from werkzeug.utils import secure_filename

from database import mysql
from utils.seguridad import cliente_requerido, login_requerido
from utils.precios import obtener_tipo_cliente
from utils.pedidos import ErrorPedido, leer_productos, calcular_pedido, insertar_pedido
from utils.validaciones import ErrorValidacion
from utils.ubicacion import leer_ubicacion, a_numero
from utils.geocodificar import geocodificar

pedidos_bp = Blueprint('pedidos', __name__)

PATRON_TELEFONO = re.compile(r'^[0-9]{10}$')
EXTENSIONES_COMPROBANTE = {'jpg', 'jpeg', 'png', 'pdf'}

# Tiempo estimado que se muestra al confirmar (maquetado del Módulo 3)
TIEMPO_ESTIMADO_B2C = 'Recibirás tu pedido en aproximadamente 40 minutos'
TIEMPO_ESTIMADO_B2B = 'Tu pedido se entregará en la ruta matutina de 6:30 a 10:00 a. m.'


# ---------------------------------------------------------------------
#  FUNCIONES DE APOYO
# ---------------------------------------------------------------------

def respuesta_calculo(calculo):
    """Quita los datos internos antes de enviar el cálculo a Angular."""
    datos = dict(calculo)
    datos.pop('requeridos', None)
    datos.pop('id_cupon', None)
    return datos


def validar_tarjeta(tarjeta):
    """Pasarela en modo de prueba: solo valida el formato. No se guarda nada."""
    if not isinstance(tarjeta, dict):
        raise ErrorPedido('Captura los datos de la tarjeta')

    numero = re.sub(r'\s|-', '', str(tarjeta.get('numero', '')))
    vencimiento = str(tarjeta.get('vencimiento', '')).strip()
    cvv = str(tarjeta.get('cvv', '')).strip()

    if not re.fullmatch(r'[0-9]{16}', numero):
        raise ErrorPedido('El número de tarjeta debe tener 16 dígitos')

    coincide = re.fullmatch(r'(0[1-9]|1[0-2])/([0-9]{2})', vencimiento)
    if not coincide:
        raise ErrorPedido('La fecha de vencimiento debe tener el formato MM/AA')

    mes, anio = int(coincide.group(1)), 2000 + int(coincide.group(2))
    hoy = datetime.now()
    if (anio, mes) < (hoy.year, hoy.month):
        raise ErrorPedido('La tarjeta está vencida')

    if not re.fullmatch(r'[0-9]{3,4}', cvv):
        raise ErrorPedido('El CVV debe tener 3 o 4 dígitos')


def obtener_pedido_propio(cursor, id_pedido):
    """Regresa el pedido solo si pertenece al cliente con sesión."""
    cursor.execute(
        "SELECT * FROM pedidos WHERE id_pedido = %s AND id_cliente = %s",
        (id_pedido, session['id_cliente'])
    )
    return cursor.fetchone()


# ---------------------------------------------------------------------
#  CALCULAR EL CARRITO (no guarda nada)
# ---------------------------------------------------------------------

@pedidos_bp.route('/api/pedidos/calcular', methods=['POST'])
@cliente_requerido
def calcular():
    cursor = None

    try:
        datos = request.get_json(silent=True) or {}
        cantidades = leer_productos(datos)

        cursor = mysql.connection.cursor()
        tipo, nivel = obtener_tipo_cliente(cursor)

        calculo = calcular_pedido(
            cursor, session['id_cliente'], tipo, nivel, cantidades,
            modalidad=datos.get('modalidad', 'domicilio'),
            codigo_cupon=datos.get('codigo_cupon', ''),
            usar_saldo=bool(datos.get('usar_saldo', False))
        )

        return jsonify({'exito': True, **respuesta_calculo(calculo)}), 200

    except ErrorPedido as e:
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo

    except Exception as e:
        print("ERROR AL CALCULAR PEDIDO:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudo calcular el pedido'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  CONFIRMAR PEDIDO
# ---------------------------------------------------------------------

def adaptar_formato_pantallas(datos):
    """
    Las pantallas del checkout envían "items" (con precios del navegador).
    Aquí se convierten al formato del backend y los precios del navegador SE IGNORAN:
    Flask vuelve a calcular todo con los precios de MySQL.
    """
    if 'items' not in datos or 'productos' in datos:
        return datos, False

    items = datos.get('items') or []
    notas_especiales = [
        f"{i.get('nombre', 'Producto')}: {str(i.get('nota_especial')).strip()}"
        for i in items if str(i.get('nota_especial') or '').strip()
    ]
    referencias = str(datos.get('referencias') or '').strip()
    notas = '; '.join(([f'Referencias: {referencias}'] if referencias else []) + notas_especiales)

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT telefono FROM usuarios WHERE id_usuario = %s", (session['id_usuario'],))
    fila = cursor.fetchone()
    cursor.close()

    convertido = {
        'productos': [{'id_producto': i.get('id_producto'), 'cantidad': i.get('cantidad'),
                       'salsa': i.get('salsa'), 'agua': i.get('agua'), 'arma': i.get('arma')} for i in items],
        'modalidad': 'domicilio',
        'direccion_entrega': datos.get('direccion_entrega', ''),
        'telefono_contacto': (fila or {}).get('telefono') or '',
        'metodo_pago': datos.get('metodo_pago', 'tarjeta'),
        'notas': notas[:500],
        'codigo_cupon': datos.get('codigo_cupon'),
        'usar_saldo': bool(datos.get('usar_saldo', False)),
        'latitud': datos.get('latitud'),
        'longitud': datos.get('longitud')
    }
    return convertido, True


@pedidos_bp.route('/api/pedidos', methods=['POST'])
@cliente_requerido
def crear_pedido():
    cursor = None

    try:
        datos = request.get_json(silent=True) or {}
        datos, desde_pantallas = adaptar_formato_pantallas(datos)
        cantidades = leer_productos(datos)

        modalidad = datos.get('modalidad', 'domicilio')
        direccion = str(datos.get('direccion_entrega') or datos.get('direccion') or '').strip()
        telefono = str(datos.get('telefono_contacto') or datos.get('telefono') or '').strip() or '0000000000'
        metodo_pago = datos.get('metodo_pago')
        notas = str(datos.get('notas', '') or '').strip()

        # VALIDACIONES DE ENTREGA Y PAGO
        if modalidad == 'domicilio' and len(direccion) < 5:
            raise ErrorPedido('Escribe la dirección de entrega')

        if metodo_pago not in ('tarjeta', 'transferencia'):
            raise ErrorPedido('Selecciona el método de pago')

        # La pantalla de pago del frontend simula la pasarela (modo de prueba) y no envía
        # los datos de la tarjeta; si sí se envían, se validan.
        if metodo_pago == 'tarjeta':
            if not (desde_pantallas and not datos.get('tarjeta')):
                validar_tarjeta(datos.get('tarjeta'))
            estado_pago = 'pagado'
        else:
            estado_pago = 'por_validar'

        cursor = mysql.connection.cursor()
        tipo, nivel = obtener_tipo_cliente(cursor)

        latitud, longitud = None, None
        if modalidad == 'domicilio':
            latitud, longitud = leer_ubicacion(datos)
            if latitud is None:
                latitud, longitud = geocodificar(direccion)
            if latitud is None:
                cursor.execute(
                    "SELECT latitud, longitud FROM clientes WHERE id_cliente = %s",
                    (session['id_cliente'],)
                )
                guardada = cursor.fetchone()
                latitud, longitud = guardada['latitud'], guardada['longitud']

        # CALCULO CON LAS FILAS APARTADAS (FOR UPDATE)
        calculo = calcular_pedido(
            cursor, session['id_cliente'], tipo, nivel, cantidades,
            modalidad=modalidad,
            codigo_cupon=datos.get('codigo_cupon', ''),
            usar_saldo=bool(datos.get('usar_saldo', False)),
            bloquear=True
        )

        if not calculo['cumple_minimo']:
            raise ErrorPedido(calculo['mensaje_minimo'])

        if calculo['faltantes']:
            nombres = ', '.join(f['nombre'] for f in calculo['faltantes'])
            raise ErrorPedido(f"No hay existencia suficiente de: {nombres}", 409)

        # GUARDAR PEDIDO, DETALLE, INVENTARIO, SALDO Y AVISO
        id_pedido = insertar_pedido(
            cursor, session['id_cliente'], session['id_usuario'], calculo,
            modalidad, direccion, telefono, metodo_pago, estado_pago, notas or None,
            latitud=latitud, longitud=longitud
        )

        mysql.connection.commit()

        return jsonify({
            'exito': True,
            'mensaje': 'Pedido registrado correctamente',
            'id_pedido': id_pedido,
            'folio': f'NG-{id_pedido:04d}',
            'estado_pago': estado_pago,
            'tiempo_estimado': TIEMPO_ESTIMADO_B2B if tipo == 'B2B' else TIEMPO_ESTIMADO_B2C,
            'total': calculo['total']
        }), 201

    except (ErrorPedido, ErrorValidacion) as e:
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo

    except Exception as e:
        print("ERROR AL CREAR PEDIDO:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo registrar el pedido'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  HISTORIAL DE PEDIDOS DEL CLIENTE
# ---------------------------------------------------------------------

@pedidos_bp.route('/api/pedidos', methods=['GET'])
@login_requerido
def mis_pedidos():
    cursor = None

    try:
        cursor = mysql.connection.cursor()
        es_admin = session.get('rol') == 'admin'
        filtro = '' if es_admin else 'WHERE p.id_cliente = %s'
        parametros = () if es_admin else (session.get('id_cliente'),)

        cursor.execute("""
            SELECT p.id_pedido, p.fecha_pedido, p.estado, p.estado_pago,
                   p.metodo_pago, p.modalidad, p.total, p.subtotal, p.costo_envio,
                   p.direccion_entrega, c.id_usuario,
                   (p.estado = 'entregado' AND cal.id_calificacion IS NULL) AS puede_calificar,
                   GROUP_CONCAT(CONCAT(TRIM(TRAILING '.' FROM TRIM(TRAILING '0' FROM d.cantidad)), ' ', pr.nombre)
                                ORDER BY d.id_detalle SEPARATOR ', ') AS resumen
            FROM pedidos p
            JOIN clientes c ON c.id_cliente = p.id_cliente
            JOIN detalle_pedido d ON d.id_pedido = p.id_pedido
            JOIN productos pr ON pr.id_producto = d.id_producto
            LEFT JOIN calificaciones cal ON cal.id_pedido = p.id_pedido
            {filtro}
            GROUP BY p.id_pedido, p.fecha_pedido, p.estado, p.estado_pago,
                     p.metodo_pago, p.modalidad, p.total, p.subtotal, p.costo_envio,
                     p.direccion_entrega, c.id_usuario, cal.id_calificacion
            ORDER BY p.fecha_pedido DESC, p.id_pedido DESC
        """.format(filtro=filtro), parametros)

        pedidos = []
        for fila in cursor.fetchall():
            motivo_cancelacion = None
            if fila['estado'] == 'cancelado':
                cursor.execute("""
                    SELECT mensaje FROM notificaciones
                    WHERE id_usuario = %s
                      AND titulo = %s
                      AND mensaje LIKE %s
                    ORDER BY id_notificacion DESC
                    LIMIT 1
                """, (fila['id_usuario'], f"Pedido #{fila['id_pedido']}", '%Motivo:%'))
                aviso = cursor.fetchone()
                if aviso and 'Motivo:' in aviso['mensaje']:
                    parte = aviso['mensaje'].split('Motivo:', 1)[1].strip()
                    motivo_cancelacion = parte.split('. Si usaste saldo', 1)[0].rstrip('.').strip()

            pedidos.append({
                'id_pedido': fila['id_pedido'],
                'folio': f"NG-{fila['id_pedido']:04d}",
                'fecha_pedido': fila['fecha_pedido'].strftime('%Y-%m-%d %H:%M'),
                'direccion_entrega': fila['direccion_entrega'] or 'Recoger en cocina',
                'subtotal': float(fila['subtotal']),
                'costo_envio': float(fila['costo_envio']),
                'estado': fila['estado'],
                'motivo_cancelacion': motivo_cancelacion,
                'estado_pago': fila['estado_pago'],
                'metodo_pago': fila['metodo_pago'],
                'modalidad': fila['modalidad'],
                'total': float(fila['total']),
                'resumen': fila['resumen'],
                'puede_calificar': bool(fila['puede_calificar'])
            })

        return jsonify({'exito': True, 'pedidos': pedidos}), 200

    except Exception as e:
        print("ERROR AL LISTAR PEDIDOS:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudieron obtener los pedidos'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  DETALLE DE UN PEDIDO
# ---------------------------------------------------------------------

@pedidos_bp.route('/api/pedidos/<int:id_pedido>', methods=['GET'])
@cliente_requerido
def detalle_pedido(id_pedido):
    cursor = None

    try:
        cursor = mysql.connection.cursor()
        pedido = obtener_pedido_propio(cursor, id_pedido)

        if not pedido:
            return jsonify({'exito': False, 'mensaje': 'El pedido no existe'}), 404

        cursor.execute("""
            SELECT d.id_producto, pr.nombre, pr.presentacion, d.cantidad,
                   d.precio_unitario, d.subtotal, d.opciones
            FROM detalle_pedido d
            JOIN productos pr ON pr.id_producto = d.id_producto
            WHERE d.id_pedido = %s
            ORDER BY d.id_detalle
        """, (id_pedido,))
        productos = [{
            'id_producto': d['id_producto'],
            'nombre': d['nombre'] + (f" ({d['opciones'].split('|')[1]})" if d['opciones'] else ''),
            'presentacion': d['presentacion'],
            'cantidad': float(d['cantidad']),
            'precio_unitario': float(d['precio_unitario']),
            'subtotal': float(d['subtotal'])
        } for d in cursor.fetchall()]

        repartidor = None
        if pedido['id_repartidor']:
            cursor.execute(
                "SELECT nombre, telefono, placas FROM repartidores WHERE id_repartidor = %s",
                (pedido['id_repartidor'],)
            )
            repartidor = cursor.fetchone()

        cursor.execute(
            "SELECT estrellas, comentario FROM calificaciones WHERE id_pedido = %s",
            (id_pedido,)
        )
        calificacion = cursor.fetchone()

        return jsonify({
            'exito': True,
            'pedido': {
                'id_pedido': pedido['id_pedido'],
                'fecha_pedido': pedido['fecha_pedido'].strftime('%Y-%m-%d %H:%M'),
                'estado': pedido['estado'],
                'modalidad': pedido['modalidad'],
                'direccion_entrega': pedido['direccion_entrega'],
                'latitud': a_numero(pedido['latitud']),
                'longitud': a_numero(pedido['longitud']),
                'telefono_contacto': pedido['telefono_contacto'],
                'metodo_pago': pedido['metodo_pago'],
                'estado_pago': pedido['estado_pago'],
                'tiene_comprobante': pedido['comprobante_url'] is not None,
                'subtotal': float(pedido['subtotal']),
                'descuento': float(pedido['descuento']),
                'costo_envio': float(pedido['costo_envio']),
                'saldo_aplicado': float(pedido['saldo_aplicado']),
                'total': float(pedido['total']),
                'notas': pedido['notas'],
                'productos': productos,
                'repartidor': repartidor,
                'calificacion': calificacion,
                'puede_calificar': pedido['estado'] == 'entregado' and calificacion is None
            }
        }), 200

    except Exception as e:
        print("ERROR EN DETALLE DE PEDIDO:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudo obtener el pedido'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  SUBIR COMPROBANTE DE TRANSFERENCIA (archivo: campo "comprobante")
# ---------------------------------------------------------------------

@pedidos_bp.route('/api/pedidos/<int:id_pedido>/comprobante', methods=['POST'])
@cliente_requerido
def subir_comprobante(id_pedido):
    cursor = None

    try:
        cursor = mysql.connection.cursor()
        pedido = obtener_pedido_propio(cursor, id_pedido)

        if not pedido:
            return jsonify({'exito': False, 'mensaje': 'El pedido no existe'}), 404

        if pedido['metodo_pago'] != 'transferencia':
            return jsonify({'exito': False, 'mensaje': 'Este pedido no se pagó por transferencia'}), 400

        if pedido['estado_pago'] == 'pagado':
            return jsonify({'exito': False, 'mensaje': 'El pago de este pedido ya fue validado'}), 400

        archivo = request.files.get('comprobante')
        if not archivo or archivo.filename == '':
            return jsonify({'exito': False, 'mensaje': 'Selecciona el archivo del comprobante'}), 400

        extension = archivo.filename.rsplit('.', 1)[-1].lower() if '.' in archivo.filename else ''
        if extension not in EXTENSIONES_COMPROBANTE:
            return jsonify({'exito': False, 'mensaje': 'El comprobante debe ser JPG, PNG o PDF'}), 400

        carpeta = os.path.join(current_app.root_path, current_app.config['UPLOAD_FOLDER'], 'comprobantes')
        os.makedirs(carpeta, exist_ok=True)

        nombre_archivo = secure_filename(
            f"pedido_{id_pedido}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{extension}"
        )
        archivo.save(os.path.join(carpeta, nombre_archivo))

        cursor.execute("""
            UPDATE pedidos SET comprobante_url = %s, estado_pago = 'por_validar'
            WHERE id_pedido = %s
        """, (f"comprobantes/{nombre_archivo}", id_pedido))
        mysql.connection.commit()

        return jsonify({
            'exito': True,
            'mensaje': 'Comprobante recibido. Validaremos tu pago en breve.'
        }), 200

    except Exception as e:
        print("ERROR AL SUBIR COMPROBANTE:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo subir el comprobante'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  CALIFICAR UN PEDIDO ENTREGADO (1 a 5 estrellas)
# ---------------------------------------------------------------------

@pedidos_bp.route('/api/pedidos/<int:id_pedido>/calificacion', methods=['POST'])
@cliente_requerido
def calificar_pedido(id_pedido):
    cursor = None

    try:
        datos = request.get_json(silent=True) or {}
        estrellas = datos.get('estrellas')
        comentario = str(datos.get('comentario', '') or '').strip()

        if not isinstance(estrellas, int) or not 1 <= estrellas <= 5:
            return jsonify({'exito': False, 'mensaje': 'La calificación debe ser de 1 a 5 estrellas'}), 400

        if len(comentario) > 500:
            return jsonify({'exito': False, 'mensaje': 'El comentario debe tener máximo 500 caracteres'}), 400

        cursor = mysql.connection.cursor()
        pedido = obtener_pedido_propio(cursor, id_pedido)

        if not pedido:
            return jsonify({'exito': False, 'mensaje': 'El pedido no existe'}), 404

        if pedido['estado'] != 'entregado':
            return jsonify({'exito': False, 'mensaje': 'Solo puedes calificar pedidos entregados'}), 400

        cursor.execute("SELECT 1 FROM calificaciones WHERE id_pedido = %s", (id_pedido,))
        if cursor.fetchone():
            return jsonify({'exito': False, 'mensaje': 'Este pedido ya fue calificado'}), 409

        cursor.execute("""
            INSERT INTO calificaciones (id_pedido, estrellas, comentario)
            VALUES (%s, %s, %s)
        """, (id_pedido, estrellas, comentario or None))
        mysql.connection.commit()

        return jsonify({'exito': True, 'mensaje': '¡Gracias por tu calificación!'}), 201

    except Exception as e:
        print("ERROR AL CALIFICAR PEDIDO:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo guardar la calificación'}), 500

    finally:
        if cursor:
            cursor.close()