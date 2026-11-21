import os
from uuid import uuid4
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from database import mysql
from utils.seguridad import login_requerido

admin_productos_bp = Blueprint('admin_productos', __name__)

EXTENSIONES_PERMITIDAS = {'png', 'jpg', 'jpeg', 'webp'}
CARPETA_PUBLIC_PRODUCTOS = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'public', 'productos')
)


def extension_valida(nombre_archivo):
    return '.' in nombre_archivo and nombre_archivo.rsplit('.', 1)[1].lower() in EXTENSIONES_PERMITIDAS


@admin_productos_bp.route('/api/admin/productos/<int:id_producto>/imagen', methods=['POST'])
@login_requerido
def subir_imagen_producto(id_producto):
    cursor = None
    try:
        archivo = request.files.get('imagen')
        if not archivo or not archivo.filename:
            return jsonify({'exito': False, 'mensaje': 'Selecciona una imagen'}), 400

        if not extension_valida(archivo.filename):
            return jsonify({'exito': False, 'mensaje': 'Formato no permitido (usa jpg, png o webp)'}), 400

        os.makedirs(CARPETA_PUBLIC_PRODUCTOS, exist_ok=True)
        nombre_seguro = secure_filename(archivo.filename)
        nombre_final = f"prod_{id_producto}_{uuid4().hex[:8]}_{nombre_seguro}"
        ruta_fisica = os.path.join(CARPETA_PUBLIC_PRODUCTOS, nombre_final)
        archivo.save(ruta_fisica)

        ruta_web = f"/productos/{nombre_final}"

        cursor = mysql.connection.cursor()
        cursor.execute(
            "UPDATE productos SET imagen_url = %s WHERE id_producto = %s",
            (ruta_web, id_producto)
        )
        mysql.connection.commit()

        return jsonify({'exito': True, 'imagen_url': ruta_web}), 200
    except Exception as e:
        print("ERROR AL SUBIR IMAGEN PRODUCTO:", str(e))
        try:
            mysql.connection.rollback()
        except Exception:
            pass
        return jsonify({'exito': False, 'mensaje': 'No se pudo guardar la imagen'}), 500
    finally:
        if cursor:
            cursor.close()