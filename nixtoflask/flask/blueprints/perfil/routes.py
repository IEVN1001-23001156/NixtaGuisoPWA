from flask import Blueprint, request, jsonify, session

from database import mysql
from utils.seguridad import cliente_requerido, login_requerido
from utils.precios import obtener_tipo_cliente, nombre_tarifa
from utils.validaciones import ErrorValidacion
from utils.ubicacion import leer_ubicacion
from blueprints.catalogo.routes import CONSULTA_PRODUCTOS, armar_producto
from blueprints.auth.routes import obtener_usuario, PATRON_CORREO, PATRON_TELEFONO, PATRON_RFC

perfil_bp = Blueprint('perfil', __name__)


# ---------------------------------------------------------------------
#  VER PERFIL
# ---------------------------------------------------------------------

@perfil_bp.route('/api/perfil', methods=['GET'])
@cliente_requerido
def ver_perfil():
    cursor = None

    try:
        cursor = mysql.connection.cursor()
        usuario = obtener_usuario(cursor, session['id_usuario'])

        if not usuario:
            return jsonify({'exito': False, 'mensaje': 'La cuenta ya no está activa'}), 404

        # Resumen de compras
        cursor.execute("""
            SELECT COUNT(*) AS total_pedidos,
                   COALESCE(SUM(CASE WHEN estado = 'entregado' THEN total END), 0) AS total_comprado
            FROM pedidos
            WHERE id_cliente = %s AND estado <> 'cancelado'
        """, (session['id_cliente'],))
        compras = cursor.fetchone()

        # Referidos: invitados y los que ya hicieron su primer pedido entregado
        cursor.execute("""
            SELECT COUNT(*) AS invitados,
                   COALESCE(SUM(EXISTS (
                       SELECT 1 FROM pedidos p
                       WHERE p.id_cliente = c.id_cliente AND p.estado = 'entregado'
                   )), 0) AS concretados
            FROM clientes c
            WHERE c.id_referido_por = %s
        """, (session['id_cliente'],))
        referidos = cursor.fetchone()

        return jsonify({
            'exito': True,
            'usuario': usuario,
            'resumen': {
                'total_pedidos': compras['total_pedidos'],
                'total_comprado': float(compras['total_comprado']),
                'referidos_invitados': int(referidos['invitados']),
                'referidos_concretados': int(referidos['concretados'])
            }
        }), 200

    except Exception as e:
        print("ERROR AL VER PERFIL:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudo obtener el perfil'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  EDITAR PERFIL
#  El tipo de cuenta (Hogar o Negocio) y el nivel B2B no se editan aquí.
# ---------------------------------------------------------------------

@perfil_bp.route('/api/perfil', methods=['PUT'])
@cliente_requerido
def editar_perfil():
    cursor = None

    try:
        datos = request.get_json(silent=True) or {}

        nombre = str(datos.get('nombre', '')).strip()
        correo = str(datos.get('correo', '')).strip().lower()
        telefono = str(datos.get('telefono', '')).strip()
        direccion = str(datos.get('direccion', '') or '').strip()
        nombre_negocio = str(datos.get('nombre_negocio', '') or '').strip()
        rfc = str(datos.get('rfc', '') or '').strip().upper()

        if len(nombre) < 3:
            return jsonify({'exito': False, 'mensaje': 'El nombre debe tener al menos 3 caracteres'}), 400

        if not PATRON_CORREO.match(correo):
            return jsonify({'exito': False, 'mensaje': 'El correo no es válido'}), 400

        if not PATRON_TELEFONO.match(telefono):
            return jsonify({'exito': False, 'mensaje': 'El teléfono debe tener 10 dígitos'}), 400

        cursor = mysql.connection.cursor()

        cursor.execute(
            "SELECT tipo FROM clientes WHERE id_cliente = %s", (session['id_cliente'],)
        )
        tipo = cursor.fetchone()['tipo']

        if tipo == 'B2B':
            if len(nombre_negocio) < 3:
                return jsonify({'exito': False, 'mensaje': 'Escribe el nombre del negocio'}), 400
            if rfc and not PATRON_RFC.match(rfc):
                return jsonify({'exito': False, 'mensaje': 'El RFC no es válido'}), 400
        else:
            nombre_negocio = ''
            rfc = ''

        # El correo no puede ser de otra cuenta
        cursor.execute(
            "SELECT 1 FROM usuarios WHERE correo = %s AND id_usuario <> %s",
            (correo, session['id_usuario'])
        )
        if cursor.fetchone():
            return jsonify({'exito': False, 'mensaje': 'Ese correo ya está registrado en otra cuenta'}), 409

        cursor.execute("""
            UPDATE usuarios SET nombre = %s, correo = %s, telefono = %s
            WHERE id_usuario = %s
        """, (nombre, correo, telefono, session['id_usuario']))

        cursor.execute("""
            UPDATE clientes SET direccion = %s, nombre_negocio = %s, rfc = %s
            WHERE id_cliente = %s
        """, (direccion or None, nombre_negocio or None, rfc or None, session['id_cliente']))

        # Ubicación en el mapa (solo si se envió)
        if 'latitud' in datos or 'longitud' in datos:
            latitud, longitud = leer_ubicacion(datos)
            cursor.execute(
                "UPDATE clientes SET latitud = %s, longitud = %s WHERE id_cliente = %s",
                (latitud, longitud, session['id_cliente'])
            )

        mysql.connection.commit()

        return jsonify({
            'exito': True,
            'mensaje': 'Perfil actualizado',
            'usuario': obtener_usuario(cursor, session['id_usuario'])
        }), 200

    except ErrorValidacion as e:
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo

    except Exception as e:
        print("ERROR AL EDITAR PERFIL:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo actualizar el perfil'}), 500

    finally:
        if cursor:
            cursor.close()


# =====================================================================
#  FAVORITOS
# =====================================================================

@perfil_bp.route('/api/favoritos', methods=['GET'])
@cliente_requerido
def listar_favoritos():
    cursor = None

    try:
        cursor = mysql.connection.cursor()
        tipo, nivel = obtener_tipo_cliente(cursor)

        # Misma consulta del catálogo, solo con los productos marcados
        cursor.execute(
            CONSULTA_PRODUCTOS + " AND f.id_producto IS NOT NULL ORDER BY f.fecha DESC",
            (session['id_cliente'],)
        )
        favoritos = [armar_producto(fila, tipo, nivel) for fila in cursor.fetchall()]

        return jsonify({
            'exito': True,
            'tarifa': nombre_tarifa(tipo, nivel),
            'favoritos': favoritos
        }), 200

    except Exception as e:
        print("ERROR AL LISTAR FAVORITOS:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudieron obtener los favoritos'}), 500

    finally:
        if cursor:
            cursor.close()


@perfil_bp.route('/api/favoritos', methods=['POST'])
@cliente_requerido
def agregar_favorito():
    cursor = None

    try:
        datos = request.get_json(silent=True) or {}
        id_producto = datos.get('id_producto')

        if not isinstance(id_producto, int):
            return jsonify({'exito': False, 'mensaje': 'Indica el producto'}), 400

        cursor = mysql.connection.cursor()

        cursor.execute("""
            SELECT 1 FROM productos
            WHERE id_producto = %s AND activo = TRUE AND es_paquete = FALSE
        """, (id_producto,))
        if not cursor.fetchone():
            return jsonify({'exito': False, 'mensaje': 'El producto no existe'}), 404

        # INSERT IGNORE: si ya era favorito, no marca error
        cursor.execute("""
            INSERT IGNORE INTO favoritos (id_cliente, id_producto) VALUES (%s, %s)
        """, (session['id_cliente'], id_producto))
        mysql.connection.commit()

        return jsonify({'exito': True, 'mensaje': 'Agregado a favoritos'}), 201

    except Exception as e:
        print("ERROR AL AGREGAR FAVORITO:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo agregar a favoritos'}), 500

    finally:
        if cursor:
            cursor.close()


@perfil_bp.route('/api/favoritos/<int:id_producto>', methods=['DELETE'])
@cliente_requerido
def quitar_favorito(id_producto):
    cursor = None

    try:
        cursor = mysql.connection.cursor()
        cursor.execute(
            "DELETE FROM favoritos WHERE id_cliente = %s AND id_producto = %s",
            (session['id_cliente'], id_producto)
        )
        mysql.connection.commit()

        return jsonify({'exito': True, 'mensaje': 'Quitado de favoritos'}), 200

    except Exception as e:
        print("ERROR AL QUITAR FAVORITO:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo quitar de favoritos'}), 500

    finally:
        if cursor:
            cursor.close()


# =====================================================================
#  NOTIFICACIONES
# =====================================================================

@perfil_bp.route('/api/notificaciones', methods=['GET'])
@login_requerido
def listar_notificaciones():
    cursor = None

    try:
        cursor = mysql.connection.cursor()

        cursor.execute("""
            SELECT id_notificacion, titulo, mensaje, leida, fecha
            FROM notificaciones
            WHERE id_usuario = %s
            ORDER BY fecha DESC, id_notificacion DESC
            LIMIT 50
        """, (session['id_usuario'],))

        notificaciones = [{
            'id_notificacion': n['id_notificacion'],
            'titulo': n['titulo'],
            'mensaje': n['mensaje'],
            'leida': bool(n['leida']),
            'fecha': n['fecha'].strftime('%Y-%m-%d %H:%M')
        } for n in cursor.fetchall()]

        return jsonify({
            'exito': True,
            'no_leidas': sum(1 for n in notificaciones if not n['leida']),
            'notificaciones': notificaciones
        }), 200

    except Exception as e:
        print("ERROR AL LISTAR NOTIFICACIONES:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudieron obtener los avisos'}), 500

    finally:
        if cursor:
            cursor.close()


@perfil_bp.route('/api/notificaciones/<int:id_notificacion>/leida', methods=['PUT'])
@login_requerido
def marcar_leida(id_notificacion):
    cursor = None

    try:
        cursor = mysql.connection.cursor()

        # El aviso debe pertenecer al usuario con sesión
        cursor.execute(
            "SELECT 1 FROM notificaciones WHERE id_notificacion = %s AND id_usuario = %s",
            (id_notificacion, session['id_usuario'])
        )
        if not cursor.fetchone():
            return jsonify({'exito': False, 'mensaje': 'El aviso no existe'}), 404

        cursor.execute(
            "UPDATE notificaciones SET leida = TRUE WHERE id_notificacion = %s",
            (id_notificacion,)
        )
        mysql.connection.commit()

        return jsonify({'exito': True, 'mensaje': 'Aviso marcado como leído'}), 200

    except Exception as e:
        print("ERROR AL MARCAR AVISO:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo actualizar el aviso'}), 500

    finally:
        if cursor:
            cursor.close()


@perfil_bp.route('/api/notificaciones/leer-todas', methods=['PUT'])
@login_requerido
def marcar_todas_leidas():
    cursor = None

    try:
        cursor = mysql.connection.cursor()
        cursor.execute(
            "UPDATE notificaciones SET leida = TRUE WHERE id_usuario = %s AND leida = FALSE",
            (session['id_usuario'],)
        )
        mysql.connection.commit()

        return jsonify({'exito': True, 'mensaje': 'Todos los avisos marcados como leídos'}), 200

    except Exception as e:
        print("ERROR AL MARCAR AVISOS:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudieron actualizar los avisos'}), 500

    finally:
        if cursor:
            cursor.close()
