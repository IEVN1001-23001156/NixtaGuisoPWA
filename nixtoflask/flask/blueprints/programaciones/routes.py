from datetime import date, datetime, timedelta

from flask import Blueprint, request, jsonify, session

from database import mysql
from utils.seguridad import cliente_requerido, login_requerido
from utils.precios import obtener_tipo_cliente, precio_para
from utils.pedidos import ErrorPedido, leer_productos, calcular_pedido

programaciones_bp = Blueprint('programaciones', __name__)


# ---------------------------------------------------------------------
#  FUNCIONES DE APOYO
# ---------------------------------------------------------------------

def formato_hora(valor):
    """MySQL regresa las horas TIME como timedelta; las convertimos a HH:MM."""
    if isinstance(valor, timedelta):
        minutos = int(valor.total_seconds()) // 60
        return f"{minutos // 60:02d}:{minutos % 60:02d}"
    return str(valor)[:5]


def proxima_entrega(programacion):
    """Fecha de la siguiente entrega (para las semanales, el mismo día de la semana)."""
    if programacion['estado'] != 'activa':
        return None

    fecha = programacion['fecha_inicio']
    hoy = date.today()

    if programacion['frecuencia'] == 'unica' or fecha >= hoy:
        return fecha.isoformat() if fecha >= hoy else None

    dias = (fecha.weekday() - hoy.weekday()) % 7
    return (hoy + timedelta(days=dias)).isoformat()


def leer_datos_programacion(cursor, datos, tipo, nivel):
    """Valida los datos del formulario. Regresa un diccionario limpio."""
    tipo_pedido = datos.get('tipo')
    frecuencia = datos.get('frecuencia', 'unica')
    direccion = str(datos.get('direccion_entrega', '') or '').strip()
    notas = str(datos.get('notas', '') or '').strip()

    if tipo_pedido not in ('evento', 'negocio'):
        raise ErrorPedido('Selecciona si es un evento o abasto de negocio')

    if tipo_pedido == 'negocio' and tipo != 'B2B':
        raise ErrorPedido('Las cuentas Hogar solo pueden programar eventos')

    if frecuencia not in ('unica', 'semanal'):
        raise ErrorPedido('La frecuencia debe ser una sola vez o semanal')

    try:
        fecha_inicio = datetime.strptime(str(datos.get('fecha_inicio', '')), '%Y-%m-%d').date()
    except ValueError:
        raise ErrorPedido('La fecha debe tener el formato AAAA-MM-DD')

    if fecha_inicio <= date.today():
        raise ErrorPedido('La fecha de entrega debe ser a partir de mañana')

    try:
        hora_desde = datetime.strptime(str(datos.get('hora_desde', '')), '%H:%M').time()
        hora_hasta = datetime.strptime(str(datos.get('hora_hasta', '')), '%H:%M').time()
    except ValueError:
        raise ErrorPedido('Las horas deben tener el formato HH:MM')

    if hora_hasta <= hora_desde:
        raise ErrorPedido('La hora final debe ser posterior a la hora inicial')

    if len(direccion) < 5:
        raise ErrorPedido('Escribe la dirección de entrega')

    cantidades = leer_productos(datos)

    # Revisa productos, precios, paquetes y pedido mínimo con las mismas reglas
    # de un pedido normal (la existencia se revisa el día de la entrega)
    calculo = calcular_pedido(cursor, session['id_cliente'], tipo, nivel, cantidades)
    if not calculo['cumple_minimo']:
        raise ErrorPedido(calculo['mensaje_minimo'])

    return {
        'tipo': tipo_pedido,
        'frecuencia': frecuencia,
        'fecha_inicio': fecha_inicio,
        'hora_desde': hora_desde,
        'hora_hasta': hora_hasta,
        'direccion': direccion,
        'notas': notas or None,
        'cantidades': cantidades
    }


def guardar_detalle(cursor, id_programacion, cantidades):
    cursor.execute(
        "DELETE FROM detalle_programacion WHERE id_programacion = %s", (id_programacion,)
    )
    for id_producto, cantidad in cantidades.items():
        cursor.execute("""
            INSERT INTO detalle_programacion (id_programacion, id_producto, cantidad)
            VALUES (%s, %s, %s)
        """, (id_programacion, id_producto, cantidad))


def obtener_programacion_propia(cursor, id_programacion):
    cursor.execute(
        "SELECT * FROM programaciones WHERE id_programacion = %s AND id_cliente = %s",
        (id_programacion, session['id_cliente'])
    )
    return cursor.fetchone()


# ---------------------------------------------------------------------
#  LISTAR MIS PROGRAMACIONES
# ---------------------------------------------------------------------

@programaciones_bp.route('/api/programaciones', methods=['GET'])
@login_requerido
def listar_programaciones():
    cursor = None

    try:
        cursor = mysql.connection.cursor()

        # El administrador (Panel Operativo) ve las programaciones activas de todos
        if session.get('rol') == 'admin':
            cursor.execute("""
                SELECT pg.*, COALESCE(c.nombre_negocio, u.nombre) AS cliente, u.telefono, c.tipo AS tipo_cliente
                FROM programaciones pg
                JOIN clientes c ON c.id_cliente = pg.id_cliente
                JOIN usuarios u ON u.id_usuario = c.id_usuario
                WHERE pg.estado = 'activa'
                ORDER BY pg.fecha_inicio
            """)
            programaciones = []
            for f in cursor.fetchall():
                cursor.execute("""
                    SELECT pr.nombre, pr.presentacion, dp.cantidad FROM detalle_programacion dp
                    JOIN productos pr ON pr.id_producto = dp.id_producto WHERE dp.id_programacion = %s
                """, (f['id_programacion'],))
                productos = [{'nombre': x['nombre'], 'presentacion': x['presentacion'], 'cantidad': float(x['cantidad'])}
                             for x in cursor.fetchall()]
                programaciones.append({
                    'id_programacion': f['id_programacion'], 'tipo': f['tipo'], 'frecuencia': f['frecuencia'],
                    'fecha_inicio': f['fecha_inicio'].isoformat(), 'estado': f['estado'], 'cliente': f['cliente'],
                    'tipo_cliente': f['tipo_cliente'], 'telefono': f['telefono'],
                    'proxima_entrega': proxima_entrega(f),
                    'hora_desde': formato_hora(f['hora_desde']), 'hora_hasta': formato_hora(f['hora_hasta']),
                    'direccion_entrega': f['direccion_entrega'], 'notas': f['notas'],
                    'productos': productos,
                    'resumen': ', '.join(f"{x['cantidad']:g} {x['nombre']}" for x in productos)
                })
            programaciones.sort(key=lambda x: x['proxima_entrega'] or '9999')
            return jsonify({'exito': True, 'programaciones': programaciones}), 200

        if session.get('rol') != 'cliente':
            return jsonify({'exito': False, 'mensaje': 'Esta función es solo para clientes'}), 403

        tipo, nivel = obtener_tipo_cliente(cursor)

        cursor.execute("""
            SELECT * FROM programaciones
            WHERE id_cliente = %s
            ORDER BY (estado = 'activa') DESC, fecha_inicio
        """, (session['id_cliente'],))
        programaciones = cursor.fetchall()

        resultado = []
        for prog in programaciones:
            cursor.execute("""
                SELECT d.id_producto, d.cantidad, p.nombre, p.presentacion,
                       p.precio_b2c, p.precio_b2b_n1, p.precio_b2b_n2
                FROM detalle_programacion d
                JOIN productos p ON p.id_producto = d.id_producto
                WHERE d.id_programacion = %s
                ORDER BY d.id_detalle
            """, (prog['id_programacion'],))
            detalle = cursor.fetchall()

            productos = []
            subtotal = 0.0
            for d in detalle:
                precio = precio_para(d, tipo, nivel)
                importe = round(precio * float(d['cantidad']), 2)
                subtotal += importe
                productos.append({
                    'id_producto': d['id_producto'],
                    'nombre': d['nombre'],
                    'presentacion': d['presentacion'],
                    'cantidad': float(d['cantidad']),
                    'precio_unitario': precio,
                    'subtotal': importe
                })

            resultado.append({
                'id_programacion': prog['id_programacion'],
                'tipo': prog['tipo'],
                'frecuencia': prog['frecuencia'],
                'fecha_inicio': prog['fecha_inicio'].isoformat(),
                'hora_desde': formato_hora(prog['hora_desde']),
                'hora_hasta': formato_hora(prog['hora_hasta']),
                'direccion_entrega': prog['direccion_entrega'],
                'notas': prog['notas'],
                'estado': prog['estado'],
                'proxima_entrega': proxima_entrega(prog),
                'subtotal_estimado': round(subtotal, 2),
                'productos': productos,
                # Campos que usan las pantallas de programados
                'fecha_programada': proxima_entrega(prog) or prog['fecha_inicio'].isoformat(),
                'hora_entrega': formato_hora(prog['hora_desde']),
                'total_estimado': round(subtotal, 2),
                'resumen': ', '.join(f"{x['cantidad']:g} {x['nombre']}" for x in productos)
            })

        return jsonify({'exito': True, 'programaciones': resultado}), 200

    except Exception as e:
        print("ERROR AL LISTAR PROGRAMACIONES:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudieron obtener las programaciones'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  CREAR PROGRAMACION
# ---------------------------------------------------------------------

def adaptar_programacion_pantallas(datos):
    """
    Las pantallas (calendario, pedido especial y cotización B2B) envían
    fecha_programada, hora_entrega e items; aquí se convierten al formato del backend.
    La ventana de entrega es de una hora a partir de la hora elegida.
    """
    if 'fecha_programada' not in datos and 'items' not in datos:
        return datos
    hora = str(datos.get('hora_entrega') or '09:00')[:5]
    try:
        h, m = (int(x) for x in hora.split(':'))
        hasta = f"{min(h + 1, 23):02d}:{m if h < 23 else 59:02d}"
    except ValueError:
        hora, hasta = '09:00', '10:00'
    notas = str(datos.get('notas') or '').strip()
    if datos.get('nombre_negocio'):
        notas = f"Evento o negocio: {str(datos['nombre_negocio']).strip()}. {notas}".strip()
    return {
        'tipo': 'automatico',   # negocio si la cuenta es B2B; evento si es Hogar
        'frecuencia': 'semanal' if datos.get('frecuencia') == 'semanal' else 'unica',
        'fecha_inicio': datos.get('fecha_programada'),
        'hora_desde': hora,
        'hora_hasta': hasta,
        'direccion_entrega': datos.get('direccion_entrega', ''),
        'notas': notas[:500],
        'productos': [{'id_producto': i.get('id_producto'), 'cantidad': i.get('cantidad')} for i in (datos.get('items') or [])]
    }


@programaciones_bp.route('/api/programaciones', methods=['POST'])
@cliente_requerido
def crear_programacion():
    cursor = None

    try:
        datos = adaptar_programacion_pantallas(request.get_json(silent=True) or {})

        cursor = mysql.connection.cursor()
        tipo, nivel = obtener_tipo_cliente(cursor)
        if datos.get('tipo') == 'automatico':
            datos['tipo'] = 'negocio' if tipo == 'B2B' else 'evento'
        prog = leer_datos_programacion(cursor, datos, tipo, nivel)

        cursor.execute("""
            INSERT INTO programaciones
            (id_cliente, tipo, fecha_inicio, hora_desde, hora_hasta,
             frecuencia, direccion_entrega, notas)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            session['id_cliente'], prog['tipo'], prog['fecha_inicio'],
            prog['hora_desde'], prog['hora_hasta'], prog['frecuencia'],
            prog['direccion'], prog['notas']
        ))
        id_programacion = cursor.lastrowid

        guardar_detalle(cursor, id_programacion, prog['cantidades'])

        cursor.execute("""
            INSERT INTO notificaciones (id_usuario, titulo, mensaje)
            VALUES (%s, %s, %s)
        """, (
            session['id_usuario'],
            'Pedido programado',
            f"Agendamos tu entrega para el {prog['fecha_inicio'].strftime('%d/%m/%Y')}."
        ))

        mysql.connection.commit()

        return jsonify({
            'exito': True,
            'mensaje': 'Pedido programado correctamente',
            'id_programacion': id_programacion
        }), 201

    except ErrorPedido as e:
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo

    except Exception as e:
        print("ERROR AL CREAR PROGRAMACION:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo programar el pedido'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  EDITAR PROGRAMACION
# ---------------------------------------------------------------------

@programaciones_bp.route('/api/programaciones/<int:id_programacion>', methods=['PUT'])
@cliente_requerido
def editar_programacion(id_programacion):
    cursor = None

    try:
        datos = request.get_json(silent=True) or {}

        cursor = mysql.connection.cursor()
        actual = obtener_programacion_propia(cursor, id_programacion)

        if not actual:
            return jsonify({'exito': False, 'mensaje': 'La programación no existe'}), 404

        if actual['estado'] != 'activa':
            return jsonify({'exito': False, 'mensaje': 'Solo se pueden editar programaciones activas'}), 400

        tipo, nivel = obtener_tipo_cliente(cursor)
        prog = leer_datos_programacion(cursor, datos, tipo, nivel)

        cursor.execute("""
            UPDATE programaciones
            SET tipo = %s, fecha_inicio = %s, hora_desde = %s, hora_hasta = %s,
                frecuencia = %s, direccion_entrega = %s, notas = %s
            WHERE id_programacion = %s
        """, (
            prog['tipo'], prog['fecha_inicio'], prog['hora_desde'], prog['hora_hasta'],
            prog['frecuencia'], prog['direccion'], prog['notas'], id_programacion
        ))

        guardar_detalle(cursor, id_programacion, prog['cantidades'])
        mysql.connection.commit()

        return jsonify({'exito': True, 'mensaje': 'Programación actualizada'}), 200

    except ErrorPedido as e:
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo

    except Exception as e:
        print("ERROR AL EDITAR PROGRAMACION:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo actualizar la programación'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  CANCELAR PROGRAMACION
# ---------------------------------------------------------------------

@programaciones_bp.route('/api/programaciones/<int:id_programacion>/cancelar', methods=['PUT'])
@cliente_requerido
def cancelar_programacion(id_programacion):
    cursor = None

    try:
        cursor = mysql.connection.cursor()
        actual = obtener_programacion_propia(cursor, id_programacion)

        if not actual:
            return jsonify({'exito': False, 'mensaje': 'La programación no existe'}), 404

        if actual['estado'] != 'activa':
            return jsonify({'exito': False, 'mensaje': 'La programación ya no está activa'}), 400

        cursor.execute(
            "UPDATE programaciones SET estado = 'cancelada' WHERE id_programacion = %s",
            (id_programacion,)
        )
        mysql.connection.commit()

        return jsonify({'exito': True, 'mensaje': 'Programación cancelada'}), 200

    except Exception as e:
        print("ERROR AL CANCELAR PROGRAMACION:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo cancelar la programación'}), 500

    finally:
        if cursor:
            cursor.close()
