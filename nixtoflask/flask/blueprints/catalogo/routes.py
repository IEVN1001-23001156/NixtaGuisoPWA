from flask import Blueprint, request, jsonify, session

from database import mysql
from utils.precios import obtener_tipo_cliente, precio_para, nombre_tarifa

catalogo_bp = Blueprint('catalogo', __name__)


# ---------------------------------------------------------------------
#  FUNCIONES DE APOYO
# ---------------------------------------------------------------------

def armar_producto(fila, tipo, nivel):
    """Convierte una fila de la base de datos en el formato que usa Angular."""
    agotado = (not fila['disponible']) or float(fila['existencia']) <= 0

    return {
        'id_producto': fila['id_producto'],
        'id_categoria': fila['id_categoria'],
        'categoria': fila['categoria'],
        'nombre': fila['nombre'],
        'descripcion': fila['descripcion'],
        'presentacion': fila['presentacion'],
        'precio': precio_para(fila, tipo, nivel),
        'precio_b2c': float(fila['precio_b2c']),
        'imagen_url': fila['imagen_url'],
        'agotado': agotado,
        'favorito': bool(fila['favorito'])
    }


# Consulta base del catálogo. El LEFT JOIN con favoritos marca los
# productos que el cliente con sesión guardó (si no hay sesión, ninguno).
CONSULTA_PRODUCTOS = """
    SELECT p.id_producto, p.id_categoria, c.nombre AS categoria,
           p.nombre, p.descripcion, p.presentacion,
           p.precio_b2c, p.precio_b2b_n1, p.precio_b2b_n2,
           p.existencia, p.imagen_url, p.disponible,
           (f.id_producto IS NOT NULL) AS favorito
    FROM productos p
    JOIN categorias c ON c.id_categoria = p.id_categoria
    LEFT JOIN favoritos f
           ON f.id_producto = p.id_producto AND f.id_cliente = %s
    WHERE p.activo = TRUE AND p.es_paquete = FALSE
"""


# ---------------------------------------------------------------------
#  CATEGORIAS
# ---------------------------------------------------------------------

@catalogo_bp.route('/api/categorias', methods=['GET'])
def listar_categorias():
    cursor = None

    try:
        cursor = mysql.connection.cursor()

        cursor.execute("""
            SELECT c.id_categoria, c.nombre, c.descripcion,
                   COUNT(p.id_producto) AS total_productos
            FROM categorias c
            LEFT JOIN productos p
                   ON p.id_categoria = c.id_categoria
                  AND p.activo = TRUE AND p.es_paquete = FALSE
            GROUP BY c.id_categoria, c.nombre, c.descripcion, c.orden
            ORDER BY c.orden
        """)

        return jsonify({
            'exito': True,
            'categorias': cursor.fetchall()
        }), 200

    except Exception as e:
        print("ERROR AL LISTAR CATEGORIAS:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudieron obtener las categorías'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  PRODUCTOS (con filtros opcionales)
#  /api/productos?categoria=2
#  /api/productos?buscar=tortilla
# ---------------------------------------------------------------------

@catalogo_bp.route('/api/productos', methods=['GET'])
def listar_productos():
    cursor = None

    try:
        categoria = request.args.get('categoria', type=int)
        buscar = request.args.get('buscar', '').strip()

        cursor = mysql.connection.cursor()
        tipo, nivel = obtener_tipo_cliente(cursor)

        consulta = CONSULTA_PRODUCTOS
        parametros = [session.get('id_cliente')]

        if categoria:
            consulta += " AND p.id_categoria = %s"
            parametros.append(categoria)

        if buscar:
            consulta += " AND (p.nombre LIKE %s OR p.descripcion LIKE %s)"
            parametros.extend([f"%{buscar}%", f"%{buscar}%"])

        consulta += " ORDER BY c.orden, p.id_producto"

        cursor.execute(consulta, parametros)
        productos = [armar_producto(fila, tipo, nivel) for fila in cursor.fetchall()]

        return jsonify({
            'exito': True,
            'tarifa': nombre_tarifa(tipo, nivel),
            'total': len(productos),
            'productos': productos
        }), 200

    except Exception as e:
        print("ERROR AL LISTAR PRODUCTOS:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudieron obtener los productos'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  DETALLE DE UN PRODUCTO
# ---------------------------------------------------------------------

@catalogo_bp.route('/api/productos/<int:id_producto>', methods=['GET'])
def detalle_producto(id_producto):
    cursor = None

    try:
        cursor = mysql.connection.cursor()
        tipo, nivel = obtener_tipo_cliente(cursor)

        cursor.execute(
            CONSULTA_PRODUCTOS + " AND p.id_producto = %s",
            (session.get('id_cliente'), id_producto)
        )
        fila = cursor.fetchone()

        if not fila:
            return jsonify({'exito': False, 'mensaje': 'El producto no existe'}), 404

        return jsonify({
            'exito': True,
            'tarifa': nombre_tarifa(tipo, nivel),
            'producto': armar_producto(fila, tipo, nivel)
        }), 200

    except Exception as e:
        print("ERROR EN DETALLE DE PRODUCTO:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudo obtener el producto'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  PAQUETES "COMIDA COMPLETA" (solo para visitantes y cuentas Hogar)
# ---------------------------------------------------------------------

@catalogo_bp.route('/api/paquetes', methods=['GET'])
def listar_paquetes():
    cursor = None

    try:
        cursor = mysql.connection.cursor()
        tipo, nivel = obtener_tipo_cliente(cursor)

        if tipo == 'B2B':
            return jsonify({
                'exito': True,
                'mensaje': 'Los paquetes son exclusivos para cuentas Hogar',
                'paquetes': []
            }), 200

        cursor.execute("""
            SELECT id_producto, nombre, descripcion, precio_b2c, imagen_url, disponible
            FROM productos
            WHERE es_paquete = TRUE AND activo = TRUE
            ORDER BY precio_b2c
        """)
        paquetes = cursor.fetchall()

        resultado = []
        for paquete in paquetes:
            cursor.execute("""
                SELECT p.id_producto, p.nombre, p.presentacion, pc.cantidad,
                       p.precio_b2c, p.existencia, p.disponible
                FROM paquete_componentes pc
                JOIN productos p ON p.id_producto = pc.id_producto
                WHERE pc.id_paquete = %s
            """, (paquete['id_producto'],))
            componentes = cursor.fetchall()

            # El paquete está agotado si falta cualquiera de sus componentes
            agotado = (not paquete['disponible']) or any(
                (not c['disponible']) or float(c['existencia']) < float(c['cantidad'])
                for c in componentes
            )
            suma_separado = sum(float(c['precio_b2c']) * float(c['cantidad']) for c in componentes)
            precio = float(paquete['precio_b2c'])

            resultado.append({
                'id_producto': paquete['id_producto'],
                'nombre': paquete['nombre'],
                'descripcion': paquete['descripcion'],
                'precio': precio,
                'precio_por_separado': suma_separado,
                'ahorro': round(suma_separado - precio, 2),
                'imagen_url': paquete['imagen_url'],
                'agotado': agotado,
                'componentes': [
                    {
                        'id_producto': c['id_producto'],
                        'nombre': c['nombre'],
                        'presentacion': c['presentacion'],
                        'cantidad': float(c['cantidad'])
                    }
                    for c in componentes
                ]
            })

        return jsonify({'exito': True, 'paquetes': resultado}), 200

    except Exception as e:
        print("ERROR AL LISTAR PAQUETES:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudieron obtener los paquetes'}), 500

    finally:
        if cursor:
            cursor.close()
