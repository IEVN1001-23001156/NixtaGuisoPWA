from functools import wraps
from flask import session, jsonify


# =====================================================================
#  CANDADOS PARA LAS RUTAS
#  Se colocan arriba de una ruta, por ejemplo:
#
#     @pedidos_bp.route('/api/pedidos', methods=['GET'])
#     @cliente_requerido
#     def mis_pedidos():
#         ...
# =====================================================================


def login_requerido(funcion):
    """Permite el acceso a cualquier usuario con sesión iniciada."""
    @wraps(funcion)
    def verificar(*args, **kwargs):
        if 'id_usuario' not in session:
            return jsonify({
                'exito': False,
                'mensaje': 'Debes iniciar sesión'
            }), 401
        return funcion(*args, **kwargs)
    return verificar


def cliente_requerido(funcion):
    """Permite el acceso solo a clientes (Hogar o Negocio) con sesión."""
    @wraps(funcion)
    def verificar(*args, **kwargs):
        if 'id_usuario' not in session:
            return jsonify({
                'exito': False,
                'mensaje': 'Debes iniciar sesión'
            }), 401
        if session.get('rol') != 'cliente':
            return jsonify({
                'exito': False,
                'mensaje': 'Esta opción es solo para clientes'
            }), 403
        return funcion(*args, **kwargs)
    return verificar


def admin_requerido(funcion):
    """Permite el acceso solo al administrador."""
    @wraps(funcion)
    def verificar(*args, **kwargs):
        if 'id_usuario' not in session:
            return jsonify({
                'exito': False,
                'mensaje': 'Debes iniciar sesión'
            }), 401
        if session.get('rol') != 'admin':
            return jsonify({
                'exito': False,
                'mensaje': 'No tienes permiso para esta opción'
            }), 403
        return funcion(*args, **kwargs)
    return verificar
