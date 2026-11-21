from flask import Blueprint, jsonify
from database import mysql

catalogo_bp = Blueprint('catalogo', __name__)

CONSULTA_PRODUCTOS = """
    SELECT p.id_producto, p.id_categoria, c.nombre AS categoria,
           p.nombre, p.descripcion, p.presentacion,
           p.kg_por_unidad, p.precio_b2c, p.precio_b2b_n1, p.precio_b2b_n2,
           p.existencia, p.imagen_url, p.es_paquete, p.disponible, p.activo
    FROM productos p
    LEFT JOIN categorias c ON c.id_categoria = p.id_categoria
"""


def armar_producto(f):
    return {
        'id_producto': f['id_producto'],
        'id_categoria': f['id_categoria'],
        'categoria': f['categoria'],
        'nombre': f['nombre'],
        'descripcion': f['descripcion'],
        'presentacion': f['presentacion'],
        'kg_por_unidad': float(f['kg_por_unidad']) if f['kg_por_unidad'] is not None else 0,
        'precio_b2c': float(f['precio_b2c']),
        'precio_b2b_n1': float(f['precio_b2b_n1']),
        'precio_b2b_n2': float(f['precio_b2b_n2']),
        'existencia': float(f['existencia']) if f['existencia'] is not None else 0,
        'imagen_url': f['imagen_url'],
        'es_paquete': bool(f['es_paquete']),
        'disponible': bool(f['disponible']),
        'activo': bool(f['activo']),
    }


@catalogo_bp.route('/api/catalogo', methods=['GET'])
def listar_catalogo():
    cursor = None
    try:
        cursor = mysql.connection.cursor()
        cursor.execute(f"""
            {CONSULTA_PRODUCTOS}
            WHERE p.activo = 1 AND p.disponible = 1
            ORDER BY p.id_producto ASC
        """)
        filas = cursor.fetchall()
        productos = [armar_producto(f) for f in filas]
        return jsonify({'exito': True, 'productos': productos}), 200

    except Exception as e:
        print("ERROR EN CATALOGO:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudo cargar el catálogo'}), 500

    finally:
        if cursor:
            cursor.close()


@catalogo_bp.route('/api/catalogo/<int:id_producto>', methods=['GET'])
def detalle_producto(id_producto):
    cursor = None
    try:
        cursor = mysql.connection.cursor()
        cursor.execute(f"""
            {CONSULTA_PRODUCTOS}
            WHERE p.id_producto = %s AND p.activo = 1
        """, (id_producto,))
        f = cursor.fetchone()

        if not f:
            return jsonify({'exito': False, 'mensaje': 'Producto no encontrado'}), 404

        return jsonify({'exito': True, 'producto': armar_producto(f)}), 200

    except Exception as e:
        print("ERROR EN DETALLE PRODUCTO:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudo cargar el producto'}), 500

    finally:
        if cursor:
            cursor.close()