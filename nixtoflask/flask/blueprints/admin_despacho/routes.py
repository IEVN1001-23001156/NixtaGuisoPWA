import os
import re
from datetime import date, datetime, timedelta

from flask import Blueprint, request, jsonify, current_app, send_from_directory

from database import mysql
from utils.seguridad import admin_requerido
from utils.validaciones import ErrorValidacion, texto, booleano
from utils.precios import tipo_de_cliente
from utils.ubicacion import leer_ubicacion, a_numero
from utils.pedidos import (calcular_pedido, insertar_pedido, reponer_inventario,
                           notificar, otorgar_bono_referido, ErrorPedido)

admin_despacho_bp = Blueprint('admin_despacho', __name__)

PATRON_TELEFONO = re.compile(r'^[0-9]{10}$')
PATRON_PLACAS = re.compile(r'^[A-Z0-9-]{5,10}$')


# =====================================================================
#  REPARTIDORES
# =====================================================================

def leer_repartidor(datos):
    nombre = texto(datos, 'nombre', 'Nombre', minimo=3, maximo=100)
    telefono = str(datos.get('telefono', '')).strip()
    placas = str(datos.get('placas', '')).strip().upper()

    if not PATRON_TELEFONO.match(telefono):
        raise ErrorValidacion('El teléfono debe tener 10 dígitos')
    if not PATRON_PLACAS.match(placas):
        raise ErrorValidacion('Las placas deben tener de 5 a 10 letras, números o guiones')

    return nombre, telefono, placas


@admin_despacho_bp.route('/api/admin/repartidores', methods=['GET'])
@admin_requerido
def listar_repartidores():
    cursor = None

    try:
        incluir_inactivos = request.args.get('incluir_inactivos', '0') == '1'

        consulta = """
            SELECT r.id_repartidor, r.nombre, r.telefono, r.placas, r.activo,
                   COUNT(p.id_pedido) AS pedidos_en_ruta
            FROM repartidores r
            LEFT JOIN pedidos p ON p.id_repartidor = r.id_repartidor AND p.estado = 'en_ruta'
        """
        if not incluir_inactivos:
            consulta += " WHERE r.activo = TRUE"
        consulta += " GROUP BY r.id_repartidor, r.nombre, r.telefono, r.placas, r.activo ORDER BY r.nombre"

        cursor = mysql.connection.cursor()
        cursor.execute(consulta)

        repartidores = [{
            'id_repartidor': r['id_repartidor'],
            'nombre': r['nombre'],
            'telefono': r['telefono'],
            'placas': r['placas'],
            'activo': bool(r['activo']),
            'pedidos_en_ruta': r['pedidos_en_ruta']
        } for r in cursor.fetchall()]

        return jsonify({'exito': True, 'repartidores': repartidores}), 200

    except Exception as e:
        print("ERROR AL LISTAR REPARTIDORES:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudieron obtener los repartidores'}), 500

    finally:
        if cursor:
            cursor.close()


@admin_despacho_bp.route('/api/admin/repartidores', methods=['POST'])
@admin_requerido
def crear_repartidor():
    cursor = None

    try:
        nombre, telefono, placas = leer_repartidor(request.get_json(silent=True) or {})

        cursor = mysql.connection.cursor()
        cursor.execute("""
            INSERT INTO repartidores (nombre, telefono, placas) VALUES (%s, %s, %s)
        """, (nombre, telefono, placas))
        id_repartidor = cursor.lastrowid
        mysql.connection.commit()

        return jsonify({
            'exito': True,
            'mensaje': 'Repartidor registrado',
            'id_repartidor': id_repartidor
        }), 201

    except ErrorValidacion as e:
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo

    except Exception as e:
        print("ERROR AL CREAR REPARTIDOR:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo registrar el repartidor'}), 500

    finally:
        if cursor:
            cursor.close()


@admin_despacho_bp.route('/api/admin/repartidores/<int:id_repartidor>', methods=['PUT'])
@admin_requerido
def editar_repartidor(id_repartidor):
    cursor = None

    try:
        datos = request.get_json(silent=True) or {}
        nombre, telefono, placas = leer_repartidor(datos)
        activo = booleano(datos, 'activo', True)

        cursor = mysql.connection.cursor()

        cursor.execute("SELECT 1 FROM repartidores WHERE id_repartidor = %s", (id_repartidor,))
        if not cursor.fetchone():
            return jsonify({'exito': False, 'mensaje': 'El repartidor no existe'}), 404

        if not activo:
            cursor.execute("""
                SELECT COUNT(*) AS total FROM pedidos
                WHERE id_repartidor = %s AND estado = 'en_ruta'
            """, (id_repartidor,))
            if cursor.fetchone()['total'] > 0:
                raise ErrorValidacion('No se puede desactivar: tiene pedidos en ruta', 409)

        cursor.execute("""
            UPDATE repartidores SET nombre = %s, telefono = %s, placas = %s, activo = %s
            WHERE id_repartidor = %s
        """, (nombre, telefono, placas, activo, id_repartidor))
        mysql.connection.commit()

        return jsonify({'exito': True, 'mensaje': 'Repartidor actualizado'}), 200

    except ErrorValidacion as e:
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo

    except Exception as e:
        print("ERROR AL EDITAR REPARTIDOR:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo actualizar el repartidor'}), 500

    finally:
        if cursor:
            cursor.close()



# =====================================================================
#  PEDIDOS (Módulo 10)
# =====================================================================

ESTADOS = ('pendiente', 'preparando', 'en_ruta', 'entregado', 'cancelado')

# A qué estados puede pasar un pedido desde cada estado
SIGUIENTES = {
    'pendiente':  ('preparando', 'cancelado'),
    'preparando': ('en_ruta', 'entregado', 'cancelado'),
    'en_ruta':    ('entregado', 'cancelado'),
    'entregado':  (),
    'cancelado':  ()
}

AVISOS = {
    'preparando': 'Estamos preparando tu pedido.',
    'en_ruta':    'Tu pedido va en camino.',
    'entregado':  'Tu pedido fue entregado. ¡Buen provecho! Califica tu experiencia.',
    'cancelado':  'Tu pedido fue cancelado. Si usaste saldo, ya se regresó a tu cuenta.'
}


def obtener_pedido(cursor, id_pedido, bloquear=False):
    cursor.execute("""
        SELECT p.*, c.id_usuario, u.nombre AS cliente, c.nombre_negocio, c.preferencias,
               r.nombre AS repartidor, r.telefono AS telefono_repartidor, r.placas
        FROM pedidos p
        JOIN clientes c ON c.id_cliente = p.id_cliente
        JOIN usuarios u ON u.id_usuario = c.id_usuario
        LEFT JOIN repartidores r ON r.id_repartidor = p.id_repartidor
        WHERE p.id_pedido = %s
    """ + (" FOR UPDATE" if bloquear else ""), (id_pedido,))
    return cursor.fetchone()


# ---------------------------------------------------------------------
#  LISTAR PEDIDOS
#  /api/admin/pedidos?estado=pendiente&fecha=2026-11-17&tipo=B2B
# ---------------------------------------------------------------------

@admin_despacho_bp.route('/api/admin/pedidos', methods=['GET'])
@admin_requerido
def listar_pedidos_admin():
    cursor = None

    try:
        estado = request.args.get('estado', '')
        fecha = request.args.get('fecha', '')
        tipo = request.args.get('tipo', '').upper()

        filtros = " WHERE 1 = 1"
        parametros = []

        if fecha:
            try:
                datetime.strptime(fecha, '%Y-%m-%d')
            except ValueError:
                return jsonify({'exito': False, 'mensaje': 'La fecha debe tener el formato AAAA-MM-DD'}), 400
            filtros += " AND DATE(p.fecha_pedido) = %s"
            parametros.append(fecha)

        if tipo in ('B2C', 'B2B'):
            filtros += " AND p.tipo_cliente = %s"
            parametros.append(tipo)

        cursor = mysql.connection.cursor()

        # Conteo por estado (para las pestañas del panel)
        cursor.execute(
            "SELECT p.estado, COUNT(*) AS total FROM pedidos p" + filtros + " GROUP BY p.estado",
            parametros
        )
        conteo = {e: 0 for e in ESTADOS}
        for fila in cursor.fetchall():
            conteo[fila['estado']] = fila['total']

        if estado in ESTADOS:
            filtros += " AND p.estado = %s"
            parametros.append(estado)

        cursor.execute("""
            SELECT p.id_pedido, p.fecha_pedido, p.estado, p.estado_pago, p.metodo_pago,
                   p.modalidad, p.tipo_cliente, p.total, p.direccion_entrega,
                   p.id_programacion, p.comprobante_url,
                   u.nombre AS cliente, c.nombre_negocio, r.nombre AS repartidor,
                   (SELECT GROUP_CONCAT(CONCAT(TRIM(TRAILING '.' FROM TRIM(TRAILING '0' FROM d.cantidad)),
                           ' ', pr.nombre) ORDER BY d.id_detalle SEPARATOR ', ')
                      FROM detalle_pedido d JOIN productos pr ON pr.id_producto = d.id_producto
                     WHERE d.id_pedido = p.id_pedido) AS resumen
            FROM pedidos p
            JOIN clientes c ON c.id_cliente = p.id_cliente
            JOIN usuarios u ON u.id_usuario = c.id_usuario
            LEFT JOIN repartidores r ON r.id_repartidor = p.id_repartidor
        """ + filtros + " ORDER BY p.fecha_pedido DESC, p.id_pedido DESC LIMIT 200", parametros)

        pedidos = [{
            'id_pedido': f['id_pedido'],
            'fecha_pedido': f['fecha_pedido'].strftime('%Y-%m-%d %H:%M'),
            'cliente': f['nombre_negocio'] or f['cliente'],
            'tipo_cliente': f['tipo_cliente'],
            'estado': f['estado'],
            'estado_pago': f['estado_pago'],
            'metodo_pago': f['metodo_pago'],
            'tiene_comprobante': f['comprobante_url'] is not None,
            'modalidad': f['modalidad'],
            'direccion_entrega': f['direccion_entrega'],
            'total': float(f['total']),
            'repartidor': f['repartidor'],
            'programado': f['id_programacion'] is not None,
            'resumen': f['resumen'],
            'siguientes_estados': list(SIGUIENTES[f['estado']])
        } for f in cursor.fetchall()]

        return jsonify({'exito': True, 'conteo': conteo, 'pedidos': pedidos}), 200

    except Exception as e:
        print("ERROR AL LISTAR PEDIDOS (ADMIN):", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudieron obtener los pedidos'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  DETALLE DE UN PEDIDO
# ---------------------------------------------------------------------

@admin_despacho_bp.route('/api/admin/pedidos/<int:id_pedido>', methods=['GET'])
@admin_requerido
def detalle_pedido_admin(id_pedido):
    cursor = None

    try:
        cursor = mysql.connection.cursor()
        p = obtener_pedido(cursor, id_pedido)

        if not p:
            return jsonify({'exito': False, 'mensaje': 'El pedido no existe'}), 404

        cursor.execute("""
            SELECT pr.nombre, pr.presentacion, d.cantidad, d.precio_unitario, d.subtotal, d.opciones
            FROM detalle_pedido d
            JOIN productos pr ON pr.id_producto = d.id_producto
            WHERE d.id_pedido = %s ORDER BY d.id_detalle
        """, (id_pedido,))
        productos = [{
            'nombre': d['nombre'] + (f" ({d['opciones'].split('|')[1]})" if d['opciones'] else ''),
            'presentacion': d['presentacion'],
            'cantidad': float(d['cantidad']),
            'precio_unitario': float(d['precio_unitario']),
            'subtotal': float(d['subtotal'])
        } for d in cursor.fetchall()]

        return jsonify({
            'exito': True,
            'pedido': {
                'id_pedido': p['id_pedido'],
                'fecha_pedido': p['fecha_pedido'].strftime('%Y-%m-%d %H:%M'),
                'cliente': p['cliente'],
                'nombre_negocio': p['nombre_negocio'],
                'tipo_cliente': p['tipo_cliente'],
                'preferencias': p['preferencias'],
                'estado': p['estado'],
                'siguientes_estados': list(SIGUIENTES[p['estado']]),
                'modalidad': p['modalidad'],
                'direccion_entrega': p['direccion_entrega'],
                'latitud': a_numero(p['latitud']),
                'longitud': a_numero(p['longitud']),
                'orden_ruta': p['orden_ruta'],
                'telefono_contacto': p['telefono_contacto'],
                'metodo_pago': p['metodo_pago'],
                'estado_pago': p['estado_pago'],
                'tiene_comprobante': p['comprobante_url'] is not None,
                'subtotal': float(p['subtotal']),
                'descuento': float(p['descuento']),
                'costo_envio': float(p['costo_envio']),
                'saldo_aplicado': float(p['saldo_aplicado']),
                'total': float(p['total']),
                'notas': p['notas'],
                'programado': p['id_programacion'] is not None,
                'repartidor': {
                    'id_repartidor': p['id_repartidor'],
                    'nombre': p['repartidor'],
                    'telefono': p['telefono_repartidor'],
                    'placas': p['placas']
                } if p['id_repartidor'] else None,
                'productos': productos
            }
        }), 200

    except Exception as e:
        print("ERROR EN DETALLE DE PEDIDO (ADMIN):", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudo obtener el pedido'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  CAMBIAR ESTADO  { "estado": "preparando" }
# ---------------------------------------------------------------------

@admin_despacho_bp.route('/api/admin/pedidos/<int:id_pedido>/estado', methods=['PUT'])
@admin_requerido
def cambiar_estado(id_pedido):
    cursor = None

    try:
        nuevo = (request.get_json(silent=True) or {}).get('estado')

        if nuevo not in ESTADOS:
            raise ErrorValidacion('El estado no es válido')

        cursor = mysql.connection.cursor()
        p = obtener_pedido(cursor, id_pedido, bloquear=True)

        if not p:
            raise ErrorValidacion('El pedido no existe', 404)

        actual = p['estado']
        if nuevo not in SIGUIENTES[actual]:
            raise ErrorValidacion(f"Un pedido '{actual}' no puede pasar a '{nuevo}'")

        # Reglas de pago: los pedidos Hogar deben estar pagados para avanzar.
        # Los negocios pueden avanzar con pago por validar (liquidan semanalmente).
        if nuevo in ('preparando', 'en_ruta', 'entregado') and \
                p['tipo_cliente'] == 'B2C' and p['estado_pago'] != 'pagado':
            raise ErrorValidacion('Primero valida el pago del pedido')

        if nuevo == 'en_ruta':
            if p['modalidad'] != 'domicilio':
                raise ErrorValidacion('Los pedidos para recoger pasan de Preparando a Entregado')
            if not p['id_repartidor']:
                raise ErrorValidacion('Asigna un repartidor antes de enviar el pedido')

        if nuevo == 'entregado' and actual == 'preparando' and p['modalidad'] == 'domicilio':
            raise ErrorValidacion('Un pedido a domicilio debe pasar primero por En ruta')

        cursor.execute(
            "UPDATE pedidos SET estado = %s WHERE id_pedido = %s", (nuevo, id_pedido)
        )

        mensaje = f"Pedido #{id_pedido}: {actual} → {nuevo}"
        bono = False

        if nuevo == 'cancelado':
            reponer_inventario(cursor, id_pedido)
            if float(p['saldo_aplicado']) > 0:
                cursor.execute(
                    "UPDATE clientes SET saldo_favor = saldo_favor + %s WHERE id_cliente = %s",
                    (p['saldo_aplicado'], p['id_cliente'])
                )
            mensaje += ". El producto regresó al inventario."

        if nuevo == 'entregado':
            bono = otorgar_bono_referido(cursor, p['id_cliente'])
            if bono:
                mensaje += ". Se otorgó el bono de referido."

        notificar(cursor, p['id_usuario'], f"Pedido #{id_pedido}", AVISOS[nuevo])

        mysql.connection.commit()

        return jsonify({
            'exito': True,
            'mensaje': mensaje,
            'estado': nuevo,
            'bono_referido': bono,
            'siguientes_estados': list(SIGUIENTES[nuevo])
        }), 200

    except ErrorValidacion as e:
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo

    except Exception as e:
        print("ERROR AL CAMBIAR ESTADO:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo cambiar el estado'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  VALIDAR O RECHAZAR TRANSFERENCIA  { "accion": "validar" | "rechazar" }
# ---------------------------------------------------------------------

@admin_despacho_bp.route('/api/admin/pedidos/<int:id_pedido>/pago', methods=['PUT'])
@admin_requerido
def validar_pago(id_pedido):
    cursor = None

    try:
        accion = (request.get_json(silent=True) or {}).get('accion')

        if accion not in ('validar', 'rechazar'):
            raise ErrorValidacion("La acción debe ser 'validar' o 'rechazar'")

        cursor = mysql.connection.cursor()
        p = obtener_pedido(cursor, id_pedido, bloquear=True)

        if not p:
            raise ErrorValidacion('El pedido no existe', 404)

        if p['metodo_pago'] != 'transferencia':
            raise ErrorValidacion('Este pedido se pagó con tarjeta')

        if p['estado'] == 'cancelado':
            raise ErrorValidacion('El pedido está cancelado')

        if p['estado_pago'] == 'pagado':
            raise ErrorValidacion('El pago ya estaba validado')

        nuevo_estado = 'pagado' if accion == 'validar' else 'rechazado'
        cursor.execute(
            "UPDATE pedidos SET estado_pago = %s WHERE id_pedido = %s", (nuevo_estado, id_pedido)
        )

        if accion == 'validar':
            notificar(cursor, p['id_usuario'], f"Pedido #{id_pedido}", 'Tu pago fue validado.')
        else:
            notificar(cursor, p['id_usuario'], f"Pedido #{id_pedido}",
                      'No pudimos validar tu transferencia. Sube un comprobante correcto.')

        mysql.connection.commit()

        return jsonify({
            'exito': True,
            'mensaje': 'Pago validado' if accion == 'validar' else 'Pago rechazado',
            'estado_pago': nuevo_estado
        }), 200

    except ErrorValidacion as e:
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo

    except Exception as e:
        print("ERROR AL VALIDAR PAGO:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo actualizar el pago'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  VER COMPROBANTE (solo el administrador)
# ---------------------------------------------------------------------

@admin_despacho_bp.route('/api/admin/pedidos/<int:id_pedido>/comprobante', methods=['GET'])
@admin_requerido
def ver_comprobante(id_pedido):
    cursor = None

    try:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT comprobante_url FROM pedidos WHERE id_pedido = %s", (id_pedido,))
        fila = cursor.fetchone()

        if not fila or not fila['comprobante_url']:
            return jsonify({'exito': False, 'mensaje': 'El pedido no tiene comprobante'}), 404

        carpeta = os.path.join(current_app.root_path, current_app.config['UPLOAD_FOLDER'], 'comprobantes')
        return send_from_directory(carpeta, os.path.basename(fila['comprobante_url']))

    except Exception as e:
        print("ERROR AL VER COMPROBANTE:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se encontró el archivo del comprobante'}), 404

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  ASIGNAR REPARTIDOR  { "id_repartidor": 1 }
# ---------------------------------------------------------------------

@admin_despacho_bp.route('/api/admin/pedidos/<int:id_pedido>/repartidor', methods=['PUT'])
@admin_requerido
def asignar_repartidor(id_pedido):
    cursor = None

    try:
        try:
            id_repartidor = int((request.get_json(silent=True) or {}).get('id_repartidor'))
        except (TypeError, ValueError):
            raise ErrorValidacion('Selecciona el repartidor')

        cursor = mysql.connection.cursor()
        p = obtener_pedido(cursor, id_pedido, bloquear=True)

        if not p:
            raise ErrorValidacion('El pedido no existe', 404)

        if p['modalidad'] != 'domicilio':
            raise ErrorValidacion('Los pedidos para recoger no llevan repartidor')

        if p['estado'] in ('entregado', 'cancelado'):
            raise ErrorValidacion(f"El pedido ya está {p['estado']}")

        cursor.execute(
            "SELECT nombre FROM repartidores WHERE id_repartidor = %s AND activo = TRUE",
            (id_repartidor,)
        )
        repartidor = cursor.fetchone()
        if not repartidor:
            raise ErrorValidacion('El repartidor no existe o está inactivo', 404)

        # El pedido se agrega como la última parada de la ruta del repartidor ese día
        if p['id_repartidor'] == id_repartidor and p['orden_ruta']:
            orden = p['orden_ruta']
        else:
            cursor.execute("""
                SELECT COALESCE(MAX(orden_ruta), 0) + 1 AS siguiente FROM pedidos
                WHERE id_repartidor = %s AND DATE(fecha_pedido) = DATE(%s)
                  AND estado <> 'cancelado'
            """, (id_repartidor, p['fecha_pedido']))
            orden = cursor.fetchone()['siguiente']

        cursor.execute(
            "UPDATE pedidos SET id_repartidor = %s, orden_ruta = %s WHERE id_pedido = %s",
            (id_repartidor, orden, id_pedido)
        )
        mysql.connection.commit()

        return jsonify({
            'exito': True,
            'mensaje': f"Pedido #{id_pedido} asignado a {repartidor['nombre']} (parada {orden})",
            'orden_ruta': orden
        }), 200

    except ErrorValidacion as e:
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo

    except Exception as e:
        print("ERROR AL ASIGNAR REPARTIDOR:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo asignar el repartidor'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  GENERAR LOS PEDIDOS PROGRAMADOS DE HOY
#  Se puede presionar varias veces: no duplica pedidos.
# ---------------------------------------------------------------------

def toca_hoy(prog, hoy):
    if prog['frecuencia'] == 'unica':
        return prog['fecha_inicio'] == hoy
    return prog['fecha_inicio'] <= hoy and prog['fecha_inicio'].weekday() == hoy.weekday()


def formato_hora(valor):
    if isinstance(valor, timedelta):
        minutos = int(valor.total_seconds()) // 60
        return f"{minutos // 60:02d}:{minutos % 60:02d}"
    return str(valor)[:5]


@admin_despacho_bp.route('/api/admin/programaciones/generar', methods=['POST'])
@admin_requerido
def generar_pedidos_programados():
    cursor = None

    try:
        hoy = date.today()
        cursor = mysql.connection.cursor()

        cursor.execute("""
            SELECT pg.*, c.id_usuario, u.telefono, u.nombre AS cliente, c.nombre_negocio,
                   c.latitud, c.longitud
            FROM programaciones pg
            JOIN clientes c ON c.id_cliente = pg.id_cliente
            JOIN usuarios u ON u.id_usuario = c.id_usuario
            WHERE pg.estado = 'activa' AND u.activo = TRUE
        """)
        programaciones = [p for p in cursor.fetchall() if toca_hoy(p, hoy)]

        generados, omitidos = [], []

        for prog in programaciones:
            nombre = prog['nombre_negocio'] or prog['cliente']

            # ¿Ya se generó hoy?
            cursor.execute("""
                SELECT id_pedido FROM pedidos
                WHERE id_programacion = %s AND DATE(fecha_pedido) = %s
            """, (prog['id_programacion'], hoy))
            if cursor.fetchone():
                omitidos.append({'id_programacion': prog['id_programacion'], 'cliente': nombre,
                                 'motivo': 'Ya se había generado hoy'})
                continue

            cursor.execute(
                "SELECT id_producto, cantidad FROM detalle_programacion WHERE id_programacion = %s",
                (prog['id_programacion'],)
            )
            cantidades = {d['id_producto']: float(d['cantidad']) for d in cursor.fetchall()}
            tipo, nivel = tipo_de_cliente(cursor, prog['id_cliente'])

            try:
                calculo = calcular_pedido(cursor, prog['id_cliente'], tipo, nivel, cantidades,
                                          modalidad='domicilio', bloquear=True)
            except ErrorPedido as e:
                omitidos.append({'id_programacion': prog['id_programacion'], 'cliente': nombre,
                                 'motivo': e.mensaje})
                continue

            if calculo['faltantes']:
                omitidos.append({
                    'id_programacion': prog['id_programacion'], 'cliente': nombre,
                    'motivo': 'Sin existencia suficiente de: ' +
                              ', '.join(f['nombre'] for f in calculo['faltantes'])
                })
                continue

            if not calculo['cumple_minimo']:
                omitidos.append({'id_programacion': prog['id_programacion'], 'cliente': nombre,
                                 'motivo': calculo['mensaje_minimo']})
                continue

            ventana = f"Entrega programada {formato_hora(prog['hora_desde'])}-{formato_hora(prog['hora_hasta'])}"
            notas = f"{ventana}. {prog['notas']}" if prog['notas'] else ventana

            id_pedido = insertar_pedido(
                cursor, prog['id_cliente'], prog['id_usuario'], calculo, 'domicilio',
                prog['direccion_entrega'], prog['telefono'], 'transferencia', 'por_validar',
                notas, prog['id_programacion'],
                latitud=prog['latitud'], longitud=prog['longitud']
            )

            if prog['frecuencia'] == 'unica':
                cursor.execute(
                    "UPDATE programaciones SET estado = 'finalizada' WHERE id_programacion = %s",
                    (prog['id_programacion'],)
                )

            generados.append({'id_pedido': id_pedido, 'id_programacion': prog['id_programacion'],
                              'cliente': nombre, 'total': calculo['total']})

        mysql.connection.commit()

        return jsonify({
            'exito': True,
            'mensaje': f"Pedidos generados: {len(generados)}. Omitidos: {len(omitidos)}.",
            'fecha': hoy.isoformat(),
            'generados': generados,
            'omitidos': omitidos
        }), 200

    except Exception as e:
        print("ERROR AL GENERAR PEDIDOS PROGRAMADOS:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudieron generar los pedidos'}), 500

    finally:
        if cursor:
            cursor.close()



# =====================================================================
#  MAPA DE RUTAS
# =====================================================================

def armar_parada(f):
    return {
        'id_pedido': f['id_pedido'],
        'orden_ruta': f['orden_ruta'],
        'cliente': f['nombre_negocio'] or f['cliente'],
        'tipo_cliente': f['tipo_cliente'],
        'direccion_entrega': f['direccion_entrega'],
        'telefono_contacto': f['telefono_contacto'],
        'latitud': a_numero(f['latitud']),
        'longitud': a_numero(f['longitud']),
        'estado': f['estado'],
        'total': float(f['total']),
        'notas': f['notas']
    }


# ---------------------------------------------------------------------
#  RUTAS DE UN DIA, POR REPARTIDOR
#  /api/admin/rutas?fecha=2026-11-19   (por defecto, hoy)
#  Sirve para planear el día y para consultar rutas guardadas.
# ---------------------------------------------------------------------

@admin_despacho_bp.route('/api/admin/rutas', methods=['GET'])
@admin_requerido
def rutas_del_dia():
    cursor = None

    try:
        texto_fecha = request.args.get('fecha', '')
        try:
            fecha = datetime.strptime(texto_fecha, '%Y-%m-%d').date() if texto_fecha else date.today()
        except ValueError:
            return jsonify({'exito': False, 'mensaje': 'La fecha debe tener el formato AAAA-MM-DD'}), 400

        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT p.id_pedido, p.id_repartidor, p.orden_ruta, p.tipo_cliente,
                   p.direccion_entrega, p.telefono_contacto, p.latitud, p.longitud,
                   p.estado, p.total, p.notas,
                   u.nombre AS cliente, c.nombre_negocio,
                   r.nombre AS repartidor, r.telefono AS telefono_repartidor, r.placas
            FROM pedidos p
            JOIN clientes c ON c.id_cliente = p.id_cliente
            JOIN usuarios u ON u.id_usuario = c.id_usuario
            LEFT JOIN repartidores r ON r.id_repartidor = p.id_repartidor
            WHERE DATE(p.fecha_pedido) = %s
              AND p.modalidad = 'domicilio' AND p.estado <> 'cancelado'
            ORDER BY p.id_repartidor, p.orden_ruta, p.id_pedido
        """, (fecha,))

        rutas = {}
        sin_asignar = []
        sin_ubicacion = 0

        for f in cursor.fetchall():
            parada = armar_parada(f)
            if parada['latitud'] is None:
                sin_ubicacion += 1

            if f['id_repartidor'] is None:
                sin_asignar.append(parada)
                continue

            if f['id_repartidor'] not in rutas:
                rutas[f['id_repartidor']] = {
                    'id_repartidor': f['id_repartidor'],
                    'repartidor': f['repartidor'],
                    'telefono': f['telefono_repartidor'],
                    'placas': f['placas'],
                    'paradas': []
                }
            rutas[f['id_repartidor']]['paradas'].append(parada)

        for ruta in rutas.values():
            ruta['total_paradas'] = len(ruta['paradas'])
            ruta['entregadas'] = sum(1 for x in ruta['paradas'] if x['estado'] == 'entregado')

        return jsonify({
            'exito': True,
            'fecha': fecha.isoformat(),
            'rutas': list(rutas.values()),
            'sin_asignar': sin_asignar,
            'pedidos_sin_ubicacion': sin_ubicacion
        }), 200

    except Exception as e:
        print("ERROR AL CONSULTAR RUTAS:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudieron obtener las rutas'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  GUARDAR EL ORDEN DE LAS PARADAS
#  { "id_repartidor": 1, "pedidos": [5, 3, 8] }   -> 5 es la parada 1
# ---------------------------------------------------------------------

@admin_despacho_bp.route('/api/admin/rutas/orden', methods=['PUT'])
@admin_requerido
def guardar_orden_ruta():
    cursor = None

    try:
        datos = request.get_json(silent=True) or {}
        pedidos = datos.get('pedidos')

        try:
            id_repartidor = int(datos.get('id_repartidor'))
        except (TypeError, ValueError):
            raise ErrorValidacion('Indica el repartidor')

        if not isinstance(pedidos, list) or not pedidos or \
                not all(isinstance(x, int) for x in pedidos):
            raise ErrorValidacion('Indica la lista de pedidos en el orden de la ruta')

        if len(set(pedidos)) != len(pedidos):
            raise ErrorValidacion('Hay pedidos repetidos en la ruta')

        cursor = mysql.connection.cursor()
        marcadores = ', '.join(['%s'] * len(pedidos))
        cursor.execute(f"""
            SELECT id_pedido FROM pedidos
            WHERE id_pedido IN ({marcadores}) AND id_repartidor = %s
              AND modalidad = 'domicilio' AND estado <> 'cancelado'
        """, (*pedidos, id_repartidor))
        encontrados = {f['id_pedido'] for f in cursor.fetchall()}

        ajenos = [x for x in pedidos if x not in encontrados]
        if ajenos:
            raise ErrorValidacion(
                f"Estos pedidos no están asignados a ese repartidor: {', '.join(map(str, ajenos))}"
            )

        for posicion, id_pedido in enumerate(pedidos, start=1):
            cursor.execute(
                "UPDATE pedidos SET orden_ruta = %s WHERE id_pedido = %s", (posicion, id_pedido)
            )

        mysql.connection.commit()

        return jsonify({
            'exito': True,
            'mensaje': f"Ruta guardada con {len(pedidos)} paradas"
        }), 200

    except ErrorValidacion as e:
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo

    except Exception as e:
        print("ERROR AL GUARDAR RUTA:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo guardar la ruta'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  CORREGIR LA UBICACION DE UN PEDIDO  { "latitud": ..., "longitud": ... }
# ---------------------------------------------------------------------

@admin_despacho_bp.route('/api/admin/pedidos/<int:id_pedido>/ubicacion', methods=['PUT'])
@admin_requerido
def corregir_ubicacion(id_pedido):
    cursor = None

    try:
        latitud, longitud = leer_ubicacion(request.get_json(silent=True) or {}, obligatorio=True)

        cursor = mysql.connection.cursor()
        p = obtener_pedido(cursor, id_pedido, bloquear=True)

        if not p:
            raise ErrorValidacion('El pedido no existe', 404)

        if p['modalidad'] != 'domicilio':
            raise ErrorValidacion('Los pedidos para recoger no llevan ubicación de entrega')

        cursor.execute(
            "UPDATE pedidos SET latitud = %s, longitud = %s WHERE id_pedido = %s",
            (latitud, longitud, id_pedido)
        )
        mysql.connection.commit()

        return jsonify({'exito': True, 'mensaje': 'Ubicación actualizada'}), 200

    except ErrorValidacion as e:
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo

    except Exception as e:
        print("ERROR AL CORREGIR UBICACION:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo actualizar la ubicación'}), 500

    finally:
        if cursor:
            cursor.close()
