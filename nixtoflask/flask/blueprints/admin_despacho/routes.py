from flask import Blueprint, request, jsonify
from database import mysql
from utils.seguridad import login_requerido

admin_despacho_bp = Blueprint('admin_despacho', __name__)

BASE_ORIGEN = {'lat': 21.1221, 'lng': -101.6826}

ZONAS_LEON = {
    'moderno': {'lat': 21.1165, 'lng': -101.6715},
    'jardines': {'lat': 21.1458, 'lng': -101.6934},
    'centro': {'lat': 21.1221, 'lng': -101.6826},
    'del valle': {'lat': 21.1382, 'lng': -101.6789},
}


def resolver_destino(direccion_texto):
    texto = (direccion_texto or '').lower()
    for clave, coords in ZONAS_LEON.items():
        if clave in texto:
            return coords
    return {'lat': 21.1290, 'lng': -101.6750}


@admin_despacho_bp.route('/api/admin/despacho/pedidos', methods=['GET'])
@login_requerido
def listar_pedidos_despacho():
    cursor = None
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT p.*, c.nombre_negocio, c.direccion AS cliente_direccion,
                   u.nombre AS cliente_nombre
            FROM pedidos p
            LEFT JOIN clientes c ON c.id_cliente = p.id_cliente
            LEFT JOIN usuarios u ON u.id_usuario = c.id_usuario
            ORDER BY p.id_pedido DESC
            LIMIT 25
        """)
        filas = cursor.fetchall()
        pedidos = []
        for f in filas:
            id_ped = f.get('id_pedido') or f.get('id')
            estado_raw = str(f.get('estado') or 'Pendiente').strip()
            asignado = estado_raw.lower() in ('en ruta', 'asignado', 'en camino', 'entregado')
            cliente_nombre = (
                f.get('nombre_negocio')
                or f.get('cliente_nombre')
                or f"Pedido #{id_ped}"
            )
            direccion = str(
                f.get('direccion_entrega')
                or f.get('cliente_direccion')
                or 'Zona Centro, León, Gto.'
            )
            destino = resolver_destino(direccion)
            fecha_str = str(f.get('fecha_pedido') or f.get('fecha_entrega') or 'Hoy')

            pedidos.append({
                'id': id_ped,
                'folio': str(f.get('folio') or f"PED-{id_ped}"),
                'hora': fecha_str[11:16] if len(fecha_str) >= 16 else '09:30',
                'fecha': fecha_str[:10] if len(fecha_str) >= 10 else fecha_str,
                'cliente': str(cliente_nombre),
                'detalle': f"{direccion} · ${float(f.get('total') or 0):.2f} MXN",
                'estado': estado_raw,
                'asignado': asignado,
                'origen': BASE_ORIGEN,
                'destino': destino,
            })

        return jsonify({'exito': True, 'pedidos': pedidos, 'origen': BASE_ORIGEN}), 200
    except Exception as e:
        print("ERROR AL LISTAR DESPACHO:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudieron cargar los pedidos de ruta'}), 500
    finally:
        if cursor:
            cursor.close()


@admin_despacho_bp.route('/api/admin/despacho/asignar/<int:id_pedido>', methods=['POST'])
@login_requerido
def asignar_pedido_ruta(id_pedido):
    cursor = None
    try:
        cursor = mysql.connection.cursor()
        cursor.execute(
            "UPDATE pedidos SET estado = %s WHERE id_pedido = %s",
            ('En Ruta', id_pedido)
        )
        mysql.connection.commit()
        return jsonify({'exito': True, 'estado': 'En Ruta'}), 200
    except Exception as e:
        print("ERROR AL ASIGNAR PEDIDO:", str(e))
        try:
            mysql.connection.rollback()
        except Exception:
            pass
        return jsonify({'exito': False, 'mensaje': 'No se pudo asignar el pedido'}), 500
    finally:
        if cursor:
            cursor.close()


@admin_despacho_bp.route('/api/rastreo/actual', methods=['GET'])
@login_requerido
def obtener_rastreo_actual():
    cursor = None
    try:
        id_pedido = request.args.get('id_pedido', type=int)
        cursor = mysql.connection.cursor()

        if id_pedido:
            cursor.execute("""
                SELECT p.*, c.direccion AS cliente_direccion
                FROM pedidos p
                LEFT JOIN clientes c ON c.id_cliente = p.id_cliente
                WHERE p.id_pedido = %s
            """, (id_pedido,))
        else:
            cursor.execute("""
                SELECT p.*, c.direccion AS cliente_direccion
                FROM pedidos p
                LEFT JOIN clientes c ON c.id_cliente = p.id_cliente
                ORDER BY p.id_pedido DESC
                LIMIT 1
            """)

        pedido = cursor.fetchone()
        repartidor_data = {
            'nombre': 'Sergio Gonzales',
            'telefono': '477321998',
            'placa': 'WLU-94-69',
        }

        try:
            cursor.execute("SELECT * FROM repartidores LIMIT 1")
            rep = cursor.fetchone()
            if rep:
                repartidor_data = {
                    'nombre': str(rep.get('nombre') or repartidor_data['nombre']),
                    'telefono': str(rep.get('telefono') or repartidor_data['telefono']),
                    'placa': str(rep.get('placa') or rep.get('vehiculo_placa') or repartidor_data['placa']),
                }
        except Exception:
            pass

        estado_bd = str((pedido or {}).get('estado') or 'En Ruta').strip()
        estado_norm = estado_bd.lower()
        if 'entreg' in estado_norm:
            estado_paso = 'Entregado'
        elif 'prep' in estado_norm or 'pend' in estado_norm:
            estado_paso = 'Preparando'
        else:
            estado_paso = 'En Ruta'

        direccion = str(
            (pedido or {}).get('direccion_entrega')
            or (pedido or {}).get('cliente_direccion')
            or 'Col. León Moderno, León, Gto.'
        )
        destino = resolver_destino(direccion)

        return jsonify({
            'exito': True,
            'folio': str((pedido or {}).get('folio') or ''),
            'direccion': direccion,
            'estadoPedido': estado_paso,
            'estadoRaw': estado_bd,
            'origen': BASE_ORIGEN,
            'destino': destino,
            'repartidor': repartidor_data,
        }), 200
    except Exception as e:
        print("ERROR EN RASTREO:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudo obtener el rastreo'}), 500
    finally:
        if cursor:
            cursor.close()