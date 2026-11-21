from flask import Blueprint, request, jsonify, session
from database import mysql
from utils.seguridad import login_requerido

admin_inventario_bp = Blueprint('admin_inventario', __name__)


@admin_inventario_bp.route('/api/inventario/productos', methods=['GET'])
@login_requerido
def listar_inventario_productos():
    cursor = None
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT p.id_producto, p.nombre, p.presentacion, p.existencia,
                   p.activo, c.nombre AS categoria
            FROM productos p
            LEFT JOIN categorias c ON c.id_categoria = p.id_categoria
            ORDER BY p.id_producto ASC
        """)
        filas = cursor.fetchall()
        productos = []
        for f in filas:
            ext = float(f['existencia'] or 0)
            productos.append({
                'id_producto': f['id_producto'],
                'nombre': f['nombre'],
                'presentacion': f['presentacion'] or 'Unidad',
                'categoria': f['categoria'] or 'General',
                'existencia': round(ext, 3),
                'activo': bool(f['activo']),
            })

        mermas = []
        try:
            cursor.execute("SELECT * FROM mermas ORDER BY 1 DESC LIMIT 25")
            filas_mermas = cursor.fetchall()
            for m in filas_mermas:
                fecha_val = (
                    m.get('fecha_registro')
                    or m.get('fecha')
                    or m.get('created_at')
                    or 'Registro'
                )
                mermas.append({
                    'id_merma': m.get('id_merma') or m.get('id') or 0,
                    'fecha': str(fecha_val),
                    'cantidad': float(m.get('cantidad') or 0),
                    'motivo': str(m.get('motivo') or 'Merma operativa'),
                })
        except Exception:
            mermas = []

        return jsonify({'exito': True, 'productos': productos, 'mermas': mermas}), 200
    except Exception as e:
        print("ERROR AL LISTAR INVENTARIO:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudo cargar el inventario'}), 500
    finally:
        if cursor:
            cursor.close()


@admin_inventario_bp.route('/api/inventario/productos/<int:id_producto>', methods=['PUT'])
@login_requerido
def actualizar_existencia_producto(id_producto):
    cursor = None
    try:
        datos = request.get_json(silent=True) or {}
        nueva_existencia = max(0.0, float(datos.get('existencia', 0)))

        cursor = mysql.connection.cursor()
        cursor.execute(
            "UPDATE productos SET existencia = %s WHERE id_producto = %s",
            (round(nueva_existencia, 3), id_producto)
        )
        mysql.connection.commit()

        return jsonify({'exito': True, 'existencia': round(nueva_existencia, 3)}), 200
    except Exception as e:
        print("ERROR AL ACTUALIZAR EXISTENCIA:", str(e))
        try:
            mysql.connection.rollback()
        except Exception:
            pass
        return jsonify({'exito': False, 'mensaje': 'No se pudo actualizar la existencia'}), 500
    finally:
        if cursor:
            cursor.close()


@admin_inventario_bp.route('/api/inventario/reabastecer', methods=['POST'])
@login_requerido
def reabastecer_producto():
    cursor = None
    try:
        datos = request.get_json(silent=True) or {}
        id_producto = int(datos.get('id_producto', 0))
        cantidad = float(datos.get('cantidad', 0))
        if id_producto <= 0 or cantidad <= 0:
            return jsonify({'exito': False, 'mensaje': 'Cantidad o producto inválido'}), 400

        cursor = mysql.connection.cursor()
        cursor.execute(
            "SELECT existencia FROM productos WHERE id_producto = %s",
            (id_producto,)
        )
        fila = cursor.fetchone()
        if not fila:
            return jsonify({'exito': False, 'mensaje': 'Producto no encontrado'}), 404

        nueva_existencia = round(float(fila['existencia'] or 0) + cantidad, 3)
        cursor.execute(
            "UPDATE productos SET existencia = %s WHERE id_producto = %s",
            (nueva_existencia, id_producto)
        )
        mysql.connection.commit()

        return jsonify({'exito': True, 'existencia': nueva_existencia}), 200
    except Exception as e:
        print("ERROR AL REABASTECER:", str(e))
        try:
            mysql.connection.rollback()
        except Exception:
            pass
        return jsonify({'exito': False, 'mensaje': 'No se pudo reabastecer el producto'}), 500
    finally:
        if cursor:
            cursor.close()


@admin_inventario_bp.route('/api/inventario/mermas', methods=['POST'])
@login_requerido
def registrar_merma_bd():
    cursor = None
    try:
        datos = request.get_json(silent=True) or {}
        id_producto = datos.get('id_producto')
        cantidad = float(datos.get('cantidad', 0))
        motivo = str(datos.get('motivo', 'Merma operativa')).strip()

        if cantidad <= 0:
            return jsonify({'exito': False, 'mensaje': 'La cantidad debe ser mayor a 0'}), 400

        cursor = mysql.connection.cursor()
        existencia_actualizada = None

        if id_producto:
            cursor.execute(
                "SELECT existencia FROM productos WHERE id_producto = %s",
                (int(id_producto),)
            )
            prod = cursor.fetchone()
            if prod:
                restante = max(0.0, round(float(prod['existencia'] or 0) - cantidad, 3))
                cursor.execute(
                    "UPDATE productos SET existencia = %s WHERE id_producto = %s",
                    (restante, int(id_producto))
                )
                existencia_actualizada = restante

        cursor.execute("""
            INSERT INTO mermas (id_usuario, cantidad, motivo)
            VALUES (%s, %s, %s)
        """, (
            session.get('id_usuario'),
            round(cantidad, 3),
            motivo
        ))
        mysql.connection.commit()

        return jsonify({
            'exito': True,
            'id_merma': cursor.lastrowid,
            'existencia': existencia_actualizada,
        }), 201
    except Exception as e:
        print("ERROR AL REGISTRAR MERMA:", str(e))
        try:
            mysql.connection.rollback()
        except Exception:
            pass
        return jsonify({'exito': False, 'mensaje': 'No se pudo registrar la merma'}), 500
    finally:
        if cursor:
            cursor.close()