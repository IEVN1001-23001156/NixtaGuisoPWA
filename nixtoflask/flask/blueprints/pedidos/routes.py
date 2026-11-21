import re
from flask import Blueprint, request, jsonify, session
from database import mysql
from utils.seguridad import login_requerido

pedidos_bp = Blueprint('pedidos', __name__)


def resolver_valor_enum(cursor, tabla, columna, valor_deseado, respaldo):
    cursor.execute("""
        SELECT COLUMN_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
    """, (tabla, columna))
    fila = cursor.fetchone()
    if not fila or not fila.get('COLUMN_TYPE'):
        return respaldo
    opciones = re.findall(r"'([^']+)'", fila['COLUMN_TYPE'])
    if not opciones:
        return respaldo
    for op in opciones:
        if op.lower() == valor_deseado.lower():
            return op
    return opciones[0]


@pedidos_bp.route('/api/pedidos', methods=['POST'])
@login_requerido
def crear_pedido():
    cursor = None
    try:
        datos = request.get_json(silent=True) or {}
        items = datos.get('items') or []
        if not items:
            return jsonify({'exito': False, 'mensaje': 'El carrito está vacío'}), 400

        direccion_entrega = str(datos.get('direccion_entrega', '')).strip()
        subtotal = float(datos.get('subtotal', 0))
        costo_envio = float(datos.get('envio', 0))
        total = float(datos.get('total', subtotal + costo_envio))

        cursor = mysql.connection.cursor()

        metodo_pago = resolver_valor_enum(cursor, 'pedidos', 'metodo_pago', 'tarjeta', 'tarjeta')
        estado_inicial = resolver_valor_enum(cursor, 'pedidos', 'estado', 'pendiente', 'pendiente')
        modalidad_inicial = resolver_valor_enum(cursor, 'pedidos', 'modalidad', 'domicilio', 'domicilio')

        cursor.execute(
            "SELECT id_cliente, tipo FROM clientes WHERE id_usuario = %s",
            (session['id_usuario'],)
        )
        cliente = cursor.fetchone()
        id_cliente = cliente['id_cliente'] if cliente else None
        tipo_cliente = cliente['tipo'] if cliente and cliente['tipo'] else 'B2C'

        cursor.execute(
            "SELECT telefono FROM usuarios WHERE id_usuario = %s",
            (session['id_usuario'],)
        )
        usuario_fila = cursor.fetchone()
        telefono_contacto = usuario_fila['telefono'] if usuario_fila else None

        cursor.execute("""
            INSERT INTO pedidos
            (id_cliente, tipo_cliente, estado, modalidad, direccion_entrega,
             telefono_contacto, subtotal, descuento, costo_envio, saldo_aplicado,
             total, metodo_pago)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 0, %s, 0, %s, %s)
        """, (
            id_cliente,
            tipo_cliente,
            estado_inicial,
            modalidad_inicial,
            direccion_entrega or None,
            telefono_contacto,
            subtotal,
            costo_envio,
            total,
            metodo_pago
        ))
        id_pedido = cursor.lastrowid

        for item in items:
            id_producto = int(item['id_producto'])
            cantidad = float(item['cantidad'])
            precio_unitario = float(item['precio_unitario'])
            subtotal_item = round(cantidad * precio_unitario, 2)

            cursor.execute("""
                INSERT INTO detalle_pedido
                (id_pedido, id_producto, cantidad, precio_unitario, subtotal)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                id_pedido,
                id_producto,
                cantidad,
                precio_unitario,
                subtotal_item
            ))

        mysql.connection.commit()
        folio = f"NG-{id_pedido:04d}"

        return jsonify({
            'exito': True,
            'mensaje': 'Pedido registrado correctamente',
            'id_pedido': id_pedido,
            'folio': folio
        }), 201

    except Exception as e:
        print("ERROR AL CREAR PEDIDO:", str(e))
        try:
            mysql.connection.rollback()
        except Exception:
            pass
        return jsonify({'exito': False, 'mensaje': 'No se pudo registrar el pedido'}), 500

    finally:
        if cursor:
            cursor.close()


@pedidos_bp.route('/api/pedidos', methods=['GET'])
@login_requerido
def listar_pedidos_usuario():
    cursor = None
    try:
        cursor = mysql.connection.cursor()
        es_admin = str(session.get('rol', '')).lower() == 'admin'

        if es_admin:
            cursor.execute("""
                SELECT p.id_pedido, p.fecha_pedido, p.estado, p.modalidad,
                       p.direccion_entrega, p.subtotal, p.costo_envio, p.total,
                       p.metodo_pago
                FROM pedidos p
                ORDER BY p.fecha_pedido DESC, p.id_pedido DESC
            """)
            filas_pedidos = cursor.fetchall()
        else:
            cursor.execute(
                "SELECT id_cliente FROM clientes WHERE id_usuario = %s",
                (session['id_usuario'],)
            )
            cliente = cursor.fetchone()
            if not cliente:
                return jsonify({'exito': True, 'pedidos': []}), 200

            id_cliente = cliente['id_cliente']
            cursor.execute("""
                SELECT p.id_pedido, p.fecha_pedido, p.estado, p.modalidad,
                       p.direccion_entrega, p.subtotal, p.costo_envio, p.total,
                       p.metodo_pago
                FROM pedidos p
                WHERE p.id_cliente = %s
                ORDER BY p.fecha_pedido DESC, p.id_pedido DESC
            """, (id_cliente,))
            filas_pedidos = cursor.fetchall()

        pedidos = []
        for p in filas_pedidos:
            cursor.execute("""
                SELECT d.cantidad, d.precio_unitario, d.subtotal,
                       pr.nombre AS nombre_producto, pr.presentacion
                FROM detalle_pedido d
                LEFT JOIN productos pr ON pr.id_producto = d.id_producto
                WHERE d.id_pedido = %s
                ORDER BY d.id_detalle ASC
            """, (p['id_pedido'],))
            detalles = cursor.fetchall()

            partes_resumen = []
            for d in detalles:
                cant = int(d['cantidad']) if float(d['cantidad']).is_integer() else float(d['cantidad'])
                nombre_prod = d['nombre_producto'] or 'Producto'
                partes_resumen.append(f"{cant}x {nombre_prod}")

            pedidos.append({
                'id_pedido': p['id_pedido'],
                'folio': f"NG-{p['id_pedido']:04d}",
                'fecha_pedido': str(p['fecha_pedido']) if p['fecha_pedido'] else '',
                'estado': p['estado'] or 'pendiente',
                'modalidad': p['modalidad'] or 'domicilio',
                'direccion_entrega': p['direccion_entrega'] or '',
                'subtotal': float(p['subtotal'] or 0),
                'costo_envio': float(p['costo_envio'] or 0),
                'total': float(p['total'] or 0),
                'metodo_pago': p['metodo_pago'] or 'tarjeta',
                'resumen': ' · '.join(partes_resumen) if partes_resumen else 'Pedido NixtaGuiso',
            })

        return jsonify({'exito': True, 'pedidos': pedidos}), 200

    except Exception as e:
        print("ERROR AL LISTAR PEDIDOS:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudo cargar el historial'}), 500

    finally:
        if cursor:
            cursor.close()