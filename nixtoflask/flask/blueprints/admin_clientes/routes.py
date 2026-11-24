from flask import Blueprint, request, jsonify

from database import mysql
from utils.seguridad import admin_requerido
from utils.validaciones import ErrorValidacion, texto, booleano
from utils.ubicacion import a_numero

admin_clientes_bp = Blueprint('admin_clientes', __name__)


def frecuencia(pedidos_30_dias):
    """Etiqueta del directorio según los pedidos de los últimos 30 días."""
    if pedidos_30_dias >= 4:
        return 'frecuente'
    if pedidos_30_dias >= 1:
        return 'ocasional'
    return 'sin compras recientes'


# ---------------------------------------------------------------------
#  DIRECTORIO DE CLIENTES
#  /api/admin/clientes?tipo=B2B&buscar=tacos
# ---------------------------------------------------------------------

@admin_clientes_bp.route('/api/admin/clientes', methods=['GET'])
@admin_requerido
def listar_clientes():
    cursor = None

    try:
        tipo = request.args.get('tipo', '').strip().upper()
        buscar = request.args.get('buscar', '').strip()

        consulta = """
            SELECT c.id_cliente, u.nombre, u.correo, u.telefono, u.activo,
                   u.fecha_registro, c.tipo, c.nombre_negocio, c.nivel_b2b,
                   COUNT(p.id_pedido) AS total_pedidos,
                   COALESCE(SUM(CASE WHEN p.estado = 'entregado' THEN p.total ELSE 0 END), 0) AS total_comprado,
                   MAX(p.fecha_pedido) AS ultimo_pedido,
                   COALESCE(SUM(CASE WHEN p.fecha_pedido >= NOW() - INTERVAL 30 DAY THEN 1 ELSE 0 END), 0) AS pedidos_30_dias
            FROM clientes c
            JOIN usuarios u ON u.id_usuario = c.id_usuario
            LEFT JOIN pedidos p ON p.id_cliente = c.id_cliente AND p.estado <> 'cancelado'
            WHERE 1 = 1
        """
        parametros = []

        if tipo in ('B2C', 'B2B'):
            consulta += " AND c.tipo = %s"
            parametros.append(tipo)

        if buscar:
            consulta += " AND (u.nombre LIKE %s OR c.nombre_negocio LIKE %s OR u.correo LIKE %s)"
            parametros.extend([f"%{buscar}%"] * 3)

        consulta += """
            GROUP BY c.id_cliente, u.nombre, u.correo, u.telefono, u.activo,
                     u.fecha_registro, c.tipo, c.nombre_negocio, c.nivel_b2b
            ORDER BY u.nombre
        """

        cursor = mysql.connection.cursor()
        cursor.execute(consulta, parametros)

        clientes = [{
            'id_cliente': f['id_cliente'],
            # Campos que usa el directorio del frontend
            'id': f['id_cliente'],
            'segmento': 'negocio' if f['tipo'] == 'B2B' else 'domicilio',
            'tipo_etiqueta': 'Negocio B2B' if f['tipo'] == 'B2B' else 'Hogar B2C',
            'contacto': f['nombre'],
            'nombre': f['nombre_negocio'] or f['nombre'],
            'nombre_negocio': f['nombre_negocio'],
            'correo': f['correo'],
            'telefono': f['telefono'],
            'tipo': f['tipo'],
            'nivel_b2b': f['nivel_b2b'],
            'activo': bool(f['activo']),
            'fecha_registro': f['fecha_registro'].strftime('%Y-%m-%d') if f['fecha_registro'] else None,
            'total_pedidos': int(f['total_pedidos'] or 0),
            'total_comprado': float(f['total_comprado'] or 0),
            'ultimo_pedido': f['ultimo_pedido'].strftime('%Y-%m-%d') if f['ultimo_pedido'] else None,
            'frecuencia': frecuencia(int(f['pedidos_30_dias'] or 0))
        } for f in cursor.fetchall()]

        return jsonify({'exito': True, 'total': len(clientes), 'clientes': clientes}), 200

    except Exception as e:
        print("ERROR AL LISTAR CLIENTES:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudieron obtener los clientes'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  FICHA DEL CLIENTE
# ---------------------------------------------------------------------

@admin_clientes_bp.route('/api/admin/clientes/<int:id_cliente>', methods=['GET'])
@admin_requerido
def ficha_cliente(id_cliente):
    cursor = None

    try:
        cursor = mysql.connection.cursor()

        cursor.execute("""
            SELECT c.*, u.nombre, u.correo, u.telefono, u.activo, u.fecha_registro,
                   ur.nombre AS referido_por
            FROM clientes c
            JOIN usuarios u ON u.id_usuario = c.id_usuario
            LEFT JOIN clientes cr ON cr.id_cliente = c.id_referido_por
            LEFT JOIN usuarios ur ON ur.id_usuario = cr.id_usuario
            WHERE c.id_cliente = %s
        """, (id_cliente,))
        c = cursor.fetchone()

        if not c:
            return jsonify({'exito': False, 'mensaje': 'El cliente no existe'}), 404

        cursor.execute("""
            SELECT id_pedido, fecha_pedido, estado, estado_pago, total
            FROM pedidos WHERE id_cliente = %s
            ORDER BY fecha_pedido DESC, id_pedido DESC LIMIT 20
        """, (id_cliente,))
        historial = [{
            'id_pedido': p['id_pedido'],
            'fecha_pedido': p['fecha_pedido'].strftime('%Y-%m-%d %H:%M') if p['fecha_pedido'] else None,
            'estado': p['estado'],
            'estado_pago': p['estado_pago'],
            'total': float(p['total'] or 0)
        } for p in cursor.fetchall()]

        cursor.execute("""
            SELECT
              (SELECT COUNT(*) FROM clientes WHERE id_referido_por = %s) AS invitados,
              (SELECT COUNT(*) FROM programaciones WHERE id_cliente = %s AND estado = 'activa') AS programaciones_activas,
              (SELECT ROUND(AVG(cal.estrellas), 1) FROM calificaciones cal
                 JOIN pedidos p ON p.id_pedido = cal.id_pedido
                WHERE p.id_cliente = %s) AS calificacion_promedio
        """, (id_cliente, id_cliente, id_cliente))
        extra = cursor.fetchone()

        return jsonify({
            'exito': True,
            'cliente': {
                'id_cliente': c['id_cliente'],
                # Campos que usa la ficha del frontend
                'id': c['id_cliente'],
                'segmento': 'Negocio B2B' if c['tipo'] == 'B2B' else 'Hogar B2C',
                'negocio': c['nombre_negocio'] or 'No aplica (Hogar)',
                'nombre': c['nombre'],
                'correo': c['correo'],
                'telefono': c['telefono'],
                'activo': bool(c['activo']),
                'fecha_registro': c['fecha_registro'].strftime('%Y-%m-%d') if c['fecha_registro'] else None,
                'tipo': c['tipo'],
                'nombre_negocio': c['nombre_negocio'],
                'rfc': c['rfc'],
                'nivel_b2b': c['nivel_b2b'],
                'direccion': c['direccion'],
                'latitud': a_numero(c['latitud']),
                'longitud': a_numero(c['longitud']),
                'preferencias': c['preferencias'],
                'saldo_favor': float(c['saldo_favor'] or 0),
                'codigo_referido': c['codigo_referido'],
                'referido_por': c['referido_por'],
                'invitados': int(extra['invitados'] or 0),
                'programaciones_activas': int(extra['programaciones_activas'] or 0),
                'calificacion_promedio': float(extra['calificacion_promedio']) if extra['calificacion_promedio'] else None,
                'historial': historial
            }
        }), 200

    except Exception as e:
        print("ERROR EN FICHA DE CLIENTE:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudo obtener el cliente'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  ACTUALIZAR CLIENTE (todos los campos son opcionales)
#  { "nivel_b2b": 2, "preferencias": "...", "activo": true }
# ---------------------------------------------------------------------

@admin_clientes_bp.route('/api/admin/clientes/<int:id_cliente>', methods=['PUT'])
@admin_requerido
def actualizar_cliente(id_cliente):
    cursor = None

    try:
        datos = request.get_json(silent=True) or {}

        cursor = mysql.connection.cursor()
        cursor.execute(
            "SELECT id_usuario, tipo, nivel_b2b FROM clientes WHERE id_cliente = %s",
            (id_cliente,)
        )
        cliente = cursor.fetchone()

        if not cliente:
            return jsonify({'exito': False, 'mensaje': 'El cliente no existe'}), 404

        cambios = []

        # NIVEL B2B
        if 'nivel_b2b' in datos:
            if cliente['tipo'] != 'B2B':
                raise ErrorValidacion('Solo los negocios tienen nivel B2B')
            if datos['nivel_b2b'] not in (1, 2):
                raise ErrorValidacion('El nivel B2B debe ser 1 o 2')

            if datos['nivel_b2b'] != cliente['nivel_b2b']:
                cursor.execute(
                    "UPDATE clientes SET nivel_b2b = %s WHERE id_cliente = %s",
                    (datos['nivel_b2b'], id_cliente)
                )
                cursor.execute("""
                    INSERT INTO notificaciones (id_usuario, titulo, mensaje)
                    VALUES (%s, 'Tu tarifa cambió', %s)
                """, (cliente['id_usuario'],
                      f"Ahora tienes precio de negocio nivel {datos['nivel_b2b']}."))
                cambios.append('nivel B2B')

        # PREFERENCIAS ESPECIALES
        if 'preferencias' in datos:
            preferencias = texto(datos, 'preferencias', 'Preferencias', maximo=1000, obligatorio=False)
            cursor.execute(
                "UPDATE clientes SET preferencias = %s WHERE id_cliente = %s",
                (preferencias, id_cliente)
            )
            cambios.append('preferencias')

        # ACTIVAR O DESACTIVAR LA CUENTA
        if 'activo' in datos:
            cursor.execute(
                "UPDATE usuarios SET activo = %s WHERE id_usuario = %s",
                (booleano(datos, 'activo'), cliente['id_usuario'])
            )
            cambios.append('estado de la cuenta')

        if not cambios:
            raise ErrorValidacion('No se indicó ningún cambio')

        mysql.connection.commit()

        return jsonify({
            'exito': True,
            'mensaje': 'Cliente actualizado: ' + ', '.join(cambios)
        }), 200

    except ErrorValidacion as e:
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo

    except Exception as e:
        print("ERROR AL ACTUALIZAR CLIENTE:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo actualizar el cliente'}), 500

    finally:
        if cursor:
            cursor.close()