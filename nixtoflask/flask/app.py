import os

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from database import mysql
from config import config

from blueprints.auth.routes import auth_bp
from blueprints.catalogo.routes import catalogo_bp
from blueprints.pedidos.routes import pedidos_bp
from blueprints.perfil.routes import perfil_bp
from blueprints.programaciones.routes import programaciones_bp
from blueprints.admin_productos.routes import admin_productos_bp
from blueprints.admin_clientes.routes import admin_clientes_bp
from blueprints.admin_despacho.routes import admin_despacho_bp
from blueprints.admin_inventario.routes import admin_inventario_bp
from blueprints.admin_dashboard.routes import admin_dashboard_bp


app = Flask(__name__)

# CONFIGURACION
app.config.from_mapping(config["development"])

# Mostrar acentos y ñ tal cual en las respuestas JSON
app.json.ensure_ascii = False

# MYSQL
mysql.init_app(app)

# PERMITIR CONEXION DESDE ANGULAR
# supports_credentials=True permite que viaje la cookie de la sesión (login)
CORS(app, origins=["http://localhost:4200"], supports_credentials=True)

# REGISTRAR BLUEPRINTS
app.register_blueprint(auth_bp)
app.register_blueprint(catalogo_bp)
app.register_blueprint(pedidos_bp)
app.register_blueprint(perfil_bp)
app.register_blueprint(programaciones_bp)
app.register_blueprint(admin_productos_bp)
app.register_blueprint(admin_clientes_bp)
app.register_blueprint(admin_despacho_bp)
app.register_blueprint(admin_inventario_bp)
app.register_blueprint(admin_dashboard_bp)


# FOTOS DE PRODUCTOS (públicas, para mostrarlas en el catálogo)
# Los comprobantes de pago NO se publican aquí.
@app.route('/uploads/productos/<path:archivo>')
def foto_producto(archivo):
    carpeta = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'], 'productos')
    return send_from_directory(carpeta, archivo)


@app.route('/')
def inicio():
    return "Servidor de NixtaGuiso funcionando"


# RUTA DE PRUEBA: confirma que Flask se conecta a la base nixtaguiso
@app.route('/api/salud', methods=['GET'])
def salud():
    cursor = None

    try:
        cursor = mysql.connection.cursor()

        cursor.execute("""
            SELECT COUNT(*) AS tablas
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
        """)
        tablas = cursor.fetchone()['tablas']

        cursor.execute("SELECT COUNT(*) AS productos FROM productos")
        productos = cursor.fetchone()['productos']

        return jsonify({
            'exito': True,
            'mensaje': 'Flask conectado a MySQL correctamente',
            'base_de_datos': app.config['MYSQL_DB'],
            'tablas': tablas,
            'productos': productos
        }), 200

    except Exception as e:
        print("ERROR DE CONEXION:", str(e))

        return jsonify({
            'exito': False,
            'mensaje': 'No se pudo conectar a MySQL: ' + str(e)
        }), 500

    finally:
        if cursor:
            cursor.close()


# RESPUESTAS DE ERROR EN FORMATO JSON
@app.errorhandler(404)
def no_encontrado(error):
    return jsonify({
        'exito': False,
        'mensaje': 'La ruta solicitada no existe'
    }), 404


@app.errorhandler(405)
def metodo_no_permitido(error):
    return jsonify({
        'exito': False,
        'mensaje': 'Método no permitido para esta ruta'
    }), 405


if __name__ == '__main__':
    app.run(debug=True, port=5000)
