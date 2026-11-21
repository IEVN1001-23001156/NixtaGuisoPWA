import re
import random
import unicodedata

from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash

from database import mysql
from utils.seguridad import login_requerido
from utils.validaciones import ErrorValidacion
from utils.ubicacion import leer_ubicacion, a_numero

auth_bp = Blueprint('auth', __name__)

PATRON_CORREO = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
PATRON_TELEFONO = re.compile(r'^[0-9]{10}$')
PATRON_RFC = re.compile(r'^[A-ZÑ&]{3,4}[0-9]{6}[A-Z0-9]{3}$')


# ---------------------------------------------------------------------
#  FUNCIONES DE APOYO
# ---------------------------------------------------------------------

def obtener_usuario(cursor, id_usuario):
    """Regresa los datos del usuario y, si es cliente, sus datos de compra."""
    cursor.execute("""
        SELECT u.id_usuario, u.nombre, u.correo, u.telefono, u.rol,
               c.id_cliente, c.tipo, c.nombre_negocio, c.rfc, c.nivel_b2b,
               c.direccion, c.latitud, c.longitud, c.codigo_referido, c.saldo_favor
        FROM usuarios u
        LEFT JOIN clientes c ON c.id_usuario = u.id_usuario
        WHERE u.id_usuario = %s AND u.activo = TRUE
    """, (id_usuario,))

    fila = cursor.fetchone()

    if not fila:
        return None

    usuario = {
        'id_usuario': fila['id_usuario'],
        'nombre': fila['nombre'],
        'correo': fila['correo'],
        'telefono': fila['telefono'],
        'rol': fila['rol']
    }

    if fila['id_cliente'] is not None:
        usuario['cliente'] = {
            'id_cliente': fila['id_cliente'],
            'tipo': fila['tipo'],
            'nombre_negocio': fila['nombre_negocio'],
            'rfc': fila['rfc'],
            'nivel_b2b': fila['nivel_b2b'],
            'direccion': fila['direccion'],
            'latitud': a_numero(fila['latitud']),
            'longitud': a_numero(fila['longitud']),
            'codigo_referido': fila['codigo_referido'],
            'saldo_favor': float(fila['saldo_favor'])
        }

    return usuario


def generar_codigo_referido(cursor, nombre):
    """Crea un código único con el primer nombre y 3 números. Ej: JUDITH482"""
    primer_nombre = nombre.split()[0] if nombre.split() else 'CLIENTE'
    sin_acentos = unicodedata.normalize('NFD', primer_nombre)
    letras = ''.join(c for c in sin_acentos if c.isalpha() and c.isascii()).upper()[:10] or 'CLIENTE'

    while True:
        codigo = f"{letras}{random.randint(100, 999)}"
        cursor.execute(
            "SELECT 1 FROM clientes WHERE codigo_referido = %s", (codigo,)
        )
        if not cursor.fetchone():
            return codigo


def iniciar_sesion(usuario):
    """Guarda en la sesión quién es el usuario."""
    session.clear()
    session.permanent = True
    session['id_usuario'] = usuario['id_usuario']
    session['rol'] = usuario['rol']
    if 'cliente' in usuario:
        session['id_cliente'] = usuario['cliente']['id_cliente']


# ---------------------------------------------------------------------
#  REGISTRO
# ---------------------------------------------------------------------

@auth_bp.route('/api/auth/registro', methods=['POST'])
def registro():
    cursor = None

    try:
        datos = request.get_json(silent=True) or {}

        nombre = str(datos.get('nombre', '')).strip()
        correo = str(datos.get('correo', '')).strip().lower()
        telefono = str(datos.get('telefono', '')).strip()
        contrasena = str(datos.get('contrasena', ''))
        tipo = str(datos.get('tipo', '')).strip().upper()
        nombre_negocio = str(datos.get('nombre_negocio', '') or '').strip()
        rfc = str(datos.get('rfc', '') or '').strip().upper()
        direccion = str(datos.get('direccion', '') or '').strip()
        codigo_invitacion = str(datos.get('codigo_invitacion', '') or '').strip().upper()
        latitud, longitud = leer_ubicacion(datos)

        # VALIDACIONES
        if len(nombre) < 3:
            return jsonify({'exito': False, 'mensaje': 'El nombre debe tener al menos 3 caracteres'}), 400

        if not PATRON_CORREO.match(correo):
            return jsonify({'exito': False, 'mensaje': 'El correo no es válido'}), 400

        if not PATRON_TELEFONO.match(telefono):
            return jsonify({'exito': False, 'mensaje': 'El teléfono debe tener 10 dígitos'}), 400

        if len(contrasena) < 8:
            return jsonify({'exito': False, 'mensaje': 'La contraseña debe tener al menos 8 caracteres'}), 400

        if tipo not in ('B2C', 'B2B'):
            return jsonify({'exito': False, 'mensaje': 'Selecciona si la cuenta es Hogar o Negocio'}), 400

        if tipo == 'B2B':
            if len(nombre_negocio) < 3:
                return jsonify({'exito': False, 'mensaje': 'Escribe el nombre del negocio'}), 400
            if rfc and not PATRON_RFC.match(rfc):
                return jsonify({'exito': False, 'mensaje': 'El RFC no es válido'}), 400
        else:
            # Los clientes Hogar no llevan datos de negocio
            nombre_negocio = ''
            rfc = ''

        cursor = mysql.connection.cursor()

        # CORREO REPETIDO
        cursor.execute("SELECT 1 FROM usuarios WHERE correo = %s", (correo,))
        if cursor.fetchone():
            return jsonify({'exito': False, 'mensaje': 'Ya existe una cuenta con ese correo'}), 409

        # CODIGO DE QUIEN LO INVITO (opcional)
        id_referido_por = None
        if codigo_invitacion:
            cursor.execute(
                "SELECT id_cliente FROM clientes WHERE codigo_referido = %s",
                (codigo_invitacion,)
            )
            invitador = cursor.fetchone()
            if not invitador:
                return jsonify({'exito': False, 'mensaje': 'El código de invitación no existe'}), 400
            id_referido_por = invitador['id_cliente']

        # GUARDAR USUARIO
        cursor.execute("""
            INSERT INTO usuarios (nombre, correo, telefono, contrasena_hash, rol)
            VALUES (%s, %s, %s, %s, 'cliente')
        """, (
            nombre,
            correo,
            telefono,
            generate_password_hash(contrasena, method='pbkdf2:sha256')
        ))
        id_usuario = cursor.lastrowid

        # GUARDAR DATOS DE CLIENTE
        cursor.execute("""
            INSERT INTO clientes
            (id_usuario, tipo, nombre_negocio, rfc, nivel_b2b, direccion,
             latitud, longitud, codigo_referido, id_referido_por)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            id_usuario,
            tipo,
            nombre_negocio or None,
            rfc or None,
            1 if tipo == 'B2B' else None,
            direccion or None,
            latitud,
            longitud,
            generar_codigo_referido(cursor, nombre),
            id_referido_por
        ))

        mysql.connection.commit()

        # INICIAR SESION AUTOMATICAMENTE
        usuario = obtener_usuario(cursor, id_usuario)
        iniciar_sesion(usuario)

        return jsonify({
            'exito': True,
            'mensaje': 'Cuenta creada correctamente',
            'usuario': usuario
        }), 201

    except ErrorValidacion as e:
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo

    except Exception as e:
        print("ERROR EN REGISTRO:", str(e))
        try:
            mysql.connection.rollback()
        except Exception:
            pass
        return jsonify({'exito': False, 'mensaje': 'No se pudo crear la cuenta'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  INICIAR SESION
# ---------------------------------------------------------------------

@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    cursor = None

    try:
        datos = request.get_json(silent=True) or {}

        correo = str(datos.get('correo', '')).strip().lower()
        contrasena = str(datos.get('contrasena', ''))

        if not correo or not contrasena:
            return jsonify({'exito': False, 'mensaje': 'Escribe tu correo y contraseña'}), 400

        cursor = mysql.connection.cursor()

        cursor.execute("""
            SELECT id_usuario, contrasena_hash
            FROM usuarios
            WHERE correo = %s AND activo = TRUE
        """, (correo,))
        registro_usuario = cursor.fetchone()

        # Mismo mensaje si no existe o si la contraseña es incorrecta (más seguro)
        if not registro_usuario or not check_password_hash(registro_usuario['contrasena_hash'], contrasena):
            return jsonify({'exito': False, 'mensaje': 'Correo o contraseña incorrectos'}), 401

        usuario = obtener_usuario(cursor, registro_usuario['id_usuario'])
        iniciar_sesion(usuario)

        return jsonify({
            'exito': True,
            'mensaje': f"Bienvenido, {usuario['nombre']}",
            'usuario': usuario
        }), 200

    except Exception as e:
        print("ERROR EN LOGIN:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudo iniciar sesión'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  USUARIO CON SESION ACTIVA
# ---------------------------------------------------------------------

@auth_bp.route('/api/auth/yo', methods=['GET'])
@login_requerido
def yo():
    cursor = None

    try:
        cursor = mysql.connection.cursor()
        usuario = obtener_usuario(cursor, session['id_usuario'])

        if not usuario:
            session.clear()
            return jsonify({'exito': False, 'mensaje': 'La cuenta ya no está activa'}), 401

        return jsonify({'exito': True, 'usuario': usuario}), 200

    except Exception as e:
        print("ERROR EN /yo:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudo consultar el usuario'}), 500

    finally:
        if cursor:
            cursor.close()


# ---------------------------------------------------------------------
#  CERRAR SESION
# ---------------------------------------------------------------------

@auth_bp.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'exito': True, 'mensaje': 'Sesión cerrada'}), 200
