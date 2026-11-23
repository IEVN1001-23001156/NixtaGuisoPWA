import os
from datetime import datetime

from flask import Blueprint, request, jsonify, current_app

from database import mysql
from utils.seguridad import admin_requerido
from utils.validaciones import ErrorValidacion, texto, numero, booleano

admin_productos_bp = Blueprint('admin_productos', __name__)

EXTENSIONES_IMAGEN = {'jpg', 'jpeg', 'png', 'webp'}


# ---------------------------------------------------------------------
#  FUNCIONES DE APOYO
# ---------------------------------------------------------------------

def armar_producto_admin(fila):
    precio = float(fila['precio_b2c'])
    costo = float(fila['costo_unitario'])
    return {
        'id_producto': fila['id_producto'],
        'id_categoria': fila['id_categoria'],
        'categoria': fila['categoria'] or 'Paquetes',
        'nombre': fila['nombre'],
        'descripcion': fila['descripcion'],
        'presentacion': fila['presentacion'],
        'kg_por_unidad': float(fila['kg_por_unidad']),
        'precio_b2c': precio,
        'precio_b2b_n1': float(fila['precio_b2b_n1']),
        'precio_b2b_n2': float(fila['precio_b2b_n2']),
        'costo_unitario': costo,
        'margen_b2c': round((precio - costo) / precio * 100, 1) if precio > 0 else 0,
        'existencia': float(fila['existencia']),
        'imagen_url': fila['imagen_url'],
        'es_paquete': bool(fila['es_paquete']),
        'disponible': bool(fila['disponible'])
    }


CONSULTA_ADMIN = """
    SELECT p.*, c.nombre AS categoria
    FROM productos p
    LEFT JOIN categorias c ON c.id_categoria = p.id_categoria
    WHERE p.activo = TRUE
"""


def leer_precios(datos):
    """Valida los tres precios y que vayan en orden: nivel 2 <= nivel 1 <= B2C."""
    b2c = numero(datos, 'precio_b2c', 'Precio B2C', permitir_cero=False)
    n1 = numero(datos, 'precio_b2b_n1', 'Precio B2B nivel 1', permitir_cero=False)
    n2 = numero(datos, 'precio_b2b_n2', 'Precio B2B nivel 2', permitir_cero=False)
    if not (n2 <= n1 <= b2c):
        raise ErrorValidacion('Los precios deben cumplir: B2B nivel 2 ≤ B2B nivel 1 ≤ B2C')
    return b2c, n1, n2


def leer_producto(cursor, datos):
    """Valida el formulario de alta o edición de un producto normal."""
    try:
        id_categoria = int(datos.get('id_categoria'))
    except (TypeError, ValueError):
        raise ErrorValidacion('Selecciona la categoría')

    cursor.execute("SELECT 1 FROM categorias WHERE id_categoria = %s", (id_categoria,))
    if not cursor.fetchone():
        raise ErrorValidacion('La categoría no existe')

    b2c, n1, n2 = leer_precios(datos)

    return {
        'id_categoria': id_categoria,
        'nombre': texto(datos, 'nombre', 'Nombre', minimo=3, maximo=100),
        'descripcion': texto(datos, 'descripcion', 'Descripción', maximo=1000, obligatorio=False),
        'presentacion': texto(datos, 'presentacion', 'Presentación', minimo=2, maximo=50),
        'kg_por_unidad': numero(datos, 'kg_por_unidad', 'Kg por unidad', permitir_cero=False),
        'precio_b2c': b2c,
        'precio_b2b_n1': n1,
        'precio_b2b_n2': n2,
        'costo_unitario': numero(datos, 'costo_unitario', 'Costo unitario'),
        'disponible': booleano(datos, 'disponible', True)
    }


def nombre_repetido(cursor, nombre, id_excluir=0):
    cursor.execute("""
        SELECT 1 FROM productos
        WHERE nombre = %s AND activo = TRUE AND id_producto <> %s
    """, (nombre, id_excluir))
    return cursor.fetchone() is not None


def obtener_producto(cursor, id_producto):
    cursor.execute(CONSULTA_ADMIN + " AND p.id_producto = %s", (id_producto,))
    return cursor.fetchone()


# ---------------------------------------------------------------------
#  LISTAR PRODUCTOS
#  /api/admin/productos?categoria=1&buscar=salsa&estado=pausado
# ---------------------------------------------------------------------

@admin_productos_bp.route('/api/admin/productos', methods=['GET'])
@admin_requerido
def listar_productos_admin():
    cursor = None

    try:
        categoria = request.args.get('categoria', '')
        buscar = request.args.get('buscar', '').strip()
        estado = request.args.get('estado', 'todos')

        consulta = CONSULTA_ADMIN
        parametros = []

        if categoria == 'paquetes':
            consulta += " AND p.es_paquete = TRUE"
        elif categoria:
            consulta += " AND p.id_categoria = %s"
            parametros.append(int(categoria))

        if buscar:
            consulta += " AND p.nombre LIKE %s"
            parametros.append(f"%{buscar}%")

        if estado == 'activo':
            consulta += " AND p.disponible = TRUE"
        elif estado == 'pausado':
            consulta += " AND p.disponible = FALSE"

        consulta += " ORDER BY p.es_paquete, c.orden, p.id_producto"

        cursor = mysql.connection.cursor()
        cursor.execute(consulta, parametros)
        productos = [armar_producto_admin(f) for f in cursor.fetchall()]

        return jsonify({'exito': True, 'total': len(productos), 'productos': productos}), 200

    except ValueError:
        return jsonify({'exito': False, 'mensaje': 'La categoría no es válida'}), 400

    except Exception as e:
        print("ERROR AL LISTAR PRODUCTOS (ADMIN):", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudieron obtener los productos'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  DETALLE
# ---------------------------------------------------------------------

@admin_productos_bp.route('/api/admin/productos/<int:id_producto>', methods=['GET'])
@admin_requerido
def detalle_producto_admin(id_producto):
    cursor = None

    try:
        cursor = mysql.connection.cursor()
        fila = obtener_producto(cursor, id_producto)

        if not fila:
            return jsonify({'exito': False, 'mensaje': 'El producto no existe'}), 404

        producto = armar_producto_admin(fila)

        if producto['es_paquete']:
            cursor.execute("""
                SELECT p.id_producto, p.nombre, p.presentacion, pc.cantidad
                FROM paquete_componentes pc
                JOIN productos p ON p.id_producto = pc.id_producto
                WHERE pc.id_paquete = %s
            """, (id_producto,))
            producto['componentes'] = [{
                'id_producto': c['id_producto'],
                'nombre': c['nombre'],
                'presentacion': c['presentacion'],
                'cantidad': float(c['cantidad'])
            } for c in cursor.fetchall()]

        return jsonify({'exito': True, 'producto': producto}), 200

    except Exception as e:
        print("ERROR EN DETALLE DE PRODUCTO (ADMIN):", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudo obtener el producto'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  ALTA DE PRODUCTO
#  (los paquetes se definen en la base de datos; aquí se dan de alta
#   productos normales, que inician con existencia 0)
# ---------------------------------------------------------------------

@admin_productos_bp.route('/api/admin/productos', methods=['POST'])
@admin_requerido
def crear_producto():
    cursor = None

    try:
        datos = request.get_json(silent=True) or {}
        cursor = mysql.connection.cursor()
        p = leer_producto(cursor, datos)

        if nombre_repetido(cursor, p['nombre']):
            raise ErrorValidacion('Ya existe un producto con ese nombre', 409)

        cursor.execute("""
            INSERT INTO productos
            (id_categoria, nombre, descripcion, presentacion, kg_por_unidad,
             precio_b2c, precio_b2b_n1, precio_b2b_n2, costo_unitario, disponible)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            p['id_categoria'], p['nombre'], p['descripcion'], p['presentacion'],
            p['kg_por_unidad'], p['precio_b2c'], p['precio_b2b_n1'], p['precio_b2b_n2'],
            p['costo_unitario'], p['disponible']
        ))
        id_producto = cursor.lastrowid
        mysql.connection.commit()

        return jsonify({
            'exito': True,
            'mensaje': 'Producto creado. Su existencia aumentará al registrar producción.',
            'producto': armar_producto_admin(obtener_producto(cursor, id_producto))
        }), 201

    except ErrorValidacion as e:
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo

    except Exception as e:
        print("ERROR AL CREAR PRODUCTO:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo crear el producto'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  EDITAR PRODUCTO
#  En los paquetes solo se editan nombre, descripción y precio.
# ---------------------------------------------------------------------

@admin_productos_bp.route('/api/admin/productos/<int:id_producto>', methods=['PUT'])
@admin_requerido
def editar_producto(id_producto):
    cursor = None

    try:
        datos = request.get_json(silent=True) or {}
        cursor = mysql.connection.cursor()
        actual = obtener_producto(cursor, id_producto)

        if not actual:
            return jsonify({'exito': False, 'mensaje': 'El producto no existe'}), 404

        if actual['es_paquete']:
            nombre = texto(datos, 'nombre', 'Nombre', minimo=3, maximo=100)
            descripcion = texto(datos, 'descripcion', 'Descripción', maximo=1000, obligatorio=False)
            precio = numero(datos, 'precio_b2c', 'Precio', permitir_cero=False)

            if nombre_repetido(cursor, nombre, id_producto):
                raise ErrorValidacion('Ya existe un producto con ese nombre', 409)

            # Los paquetes son solo para Hogar: los tres precios son iguales
            cursor.execute("""
                UPDATE productos
                SET nombre = %s, descripcion = %s,
                    precio_b2c = %s, precio_b2b_n1 = %s, precio_b2b_n2 = %s
                WHERE id_producto = %s
            """, (nombre, descripcion, precio, precio, precio, id_producto))
        else:
            p = leer_producto(cursor, datos)

            if nombre_repetido(cursor, p['nombre'], id_producto):
                raise ErrorValidacion('Ya existe un producto con ese nombre', 409)

            cursor.execute("""
                UPDATE productos
                SET id_categoria = %s, nombre = %s, descripcion = %s, presentacion = %s,
                    kg_por_unidad = %s, precio_b2c = %s, precio_b2b_n1 = %s,
                    precio_b2b_n2 = %s, costo_unitario = %s, disponible = %s
                WHERE id_producto = %s
            """, (
                p['id_categoria'], p['nombre'], p['descripcion'], p['presentacion'],
                p['kg_por_unidad'], p['precio_b2c'], p['precio_b2b_n1'], p['precio_b2b_n2'],
                p['costo_unitario'], p['disponible'], id_producto
            ))

        mysql.connection.commit()

        return jsonify({
            'exito': True,
            'mensaje': 'Producto actualizado',
            'producto': armar_producto_admin(obtener_producto(cursor, id_producto))
        }), 200

    except ErrorValidacion as e:
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo

    except Exception as e:
        print("ERROR AL EDITAR PRODUCTO:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo actualizar el producto'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  PAUSAR O ACTIVAR  { "disponible": false }
# ---------------------------------------------------------------------

@admin_productos_bp.route('/api/admin/productos/<int:id_producto>/disponible', methods=['PATCH'])
@admin_requerido
def cambiar_disponible(id_producto):
    cursor = None

    try:
        datos = request.get_json(silent=True) or {}

        if 'disponible' not in datos:
            return jsonify({'exito': False, 'mensaje': 'Indica si el producto estará disponible'}), 400

        disponible = booleano(datos, 'disponible')

        cursor = mysql.connection.cursor()
        if not obtener_producto(cursor, id_producto):
            return jsonify({'exito': False, 'mensaje': 'El producto no existe'}), 404

        cursor.execute(
            "UPDATE productos SET disponible = %s WHERE id_producto = %s",
            (disponible, id_producto)
        )
        mysql.connection.commit()

        return jsonify({
            'exito': True,
            'mensaje': 'Producto activado' if disponible else 'Producto pausado',
            'disponible': disponible
        }), 200

    except Exception as e:
        print("ERROR AL CAMBIAR DISPONIBILIDAD:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo cambiar la disponibilidad'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  DAR DE BAJA (no se borra, para conservar el historial de pedidos)
# ---------------------------------------------------------------------

@admin_productos_bp.route('/api/admin/productos/<int:id_producto>', methods=['DELETE'])
@admin_requerido
def baja_producto(id_producto):
    cursor = None

    try:
        cursor = mysql.connection.cursor()
        if not obtener_producto(cursor, id_producto):
            return jsonify({'exito': False, 'mensaje': 'El producto no existe'}), 404

        cursor.execute("""
            SELECT pq.nombre
            FROM paquete_componentes pc
            JOIN productos pq ON pq.id_producto = pc.id_paquete
            WHERE pc.id_producto = %s AND pq.activo = TRUE
        """, (id_producto,))
        paquetes = [f['nombre'] for f in cursor.fetchall()]

        if paquetes:
            return jsonify({
                'exito': False,
                'mensaje': 'No se puede dar de baja: forma parte de ' + ', '.join(paquetes)
            }), 409

        cursor.execute(
            "UPDATE productos SET activo = FALSE, disponible = FALSE WHERE id_producto = %s",
            (id_producto,)
        )
        cursor.execute("DELETE FROM favoritos WHERE id_producto = %s", (id_producto,))
        mysql.connection.commit()

        return jsonify({'exito': True, 'mensaje': 'Producto dado de baja'}), 200

    except Exception as e:
        print("ERROR AL DAR DE BAJA PRODUCTO:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo dar de baja el producto'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  SUBIR FOTO (archivo: campo "imagen")
# ---------------------------------------------------------------------

@admin_productos_bp.route('/api/admin/productos/<int:id_producto>/imagen', methods=['POST'])
@admin_requerido
def subir_imagen(id_producto):
    cursor = None

    try:
        cursor = mysql.connection.cursor()
        actual = obtener_producto(cursor, id_producto)

        if not actual:
            return jsonify({'exito': False, 'mensaje': 'El producto no existe'}), 404

        archivo = request.files.get('imagen')
        if not archivo or archivo.filename == '':
            return jsonify({'exito': False, 'mensaje': 'Selecciona la imagen'}), 400

        extension = archivo.filename.rsplit('.', 1)[-1].lower() if '.' in archivo.filename else ''
        if extension not in EXTENSIONES_IMAGEN:
            return jsonify({'exito': False, 'mensaje': 'La imagen debe ser JPG, PNG o WEBP'}), 400

        carpeta = os.path.join(current_app.root_path, current_app.config['UPLOAD_FOLDER'], 'productos')
        os.makedirs(carpeta, exist_ok=True)

        nombre_archivo = f"producto_{id_producto}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{extension}"
        archivo.save(os.path.join(carpeta, nombre_archivo))

        # Borrar la foto anterior, si había
        if actual['imagen_url']:
            anterior = os.path.join(carpeta, os.path.basename(actual['imagen_url']))
            if os.path.exists(anterior):
                os.remove(anterior)

        imagen_url = f"/uploads/productos/{nombre_archivo}"
        cursor.execute(
            "UPDATE productos SET imagen_url = %s WHERE id_producto = %s",
            (imagen_url, id_producto)
        )
        mysql.connection.commit()

        return jsonify({'exito': True, 'mensaje': 'Imagen actualizada', 'imagen_url': imagen_url}), 200

    except Exception as e:
        print("ERROR AL SUBIR IMAGEN:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo subir la imagen'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  EDITAR CATEGORIA (las 5 líneas son fijas; se edita su información)
# ---------------------------------------------------------------------

@admin_productos_bp.route('/api/admin/categorias/<int:id_categoria>', methods=['PUT'])
@admin_requerido
def editar_categoria(id_categoria):
    cursor = None

    try:
        datos = request.get_json(silent=True) or {}
        nombre = texto(datos, 'nombre', 'Nombre', minimo=3, maximo=60)
        descripcion = texto(datos, 'descripcion', 'Descripción', maximo=255, obligatorio=False)
        orden = int(numero(datos, 'orden', 'Orden'))

        cursor = mysql.connection.cursor()

        cursor.execute("SELECT 1 FROM categorias WHERE id_categoria = %s", (id_categoria,))
        if not cursor.fetchone():
            return jsonify({'exito': False, 'mensaje': 'La categoría no existe'}), 404

        cursor.execute(
            "SELECT 1 FROM categorias WHERE nombre = %s AND id_categoria <> %s",
            (nombre, id_categoria)
        )
        if cursor.fetchone():
            raise ErrorValidacion('Ya existe una categoría con ese nombre', 409)

        cursor.execute("""
            UPDATE categorias SET nombre = %s, descripcion = %s, orden = %s
            WHERE id_categoria = %s
        """, (nombre, descripcion, orden, id_categoria))
        mysql.connection.commit()

        return jsonify({'exito': True, 'mensaje': 'Categoría actualizada'}), 200

    except ErrorValidacion as e:
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo

    except Exception as e:
        print("ERROR AL EDITAR CATEGORIA:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo actualizar la categoría'}), 500

    finally:
        if cursor:
            cursor.close()
