from flask import Blueprint, request, jsonify
from database import mysql
from utils.seguridad import login_requerido

admin_clientes_bp = Blueprint('admin_clientes', __name__)


@admin_clientes_bp.route('/api/admin/clientes', methods=['GET'])
@login_requerido
def listar_clientes_crm():
    cursor = None
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT c.*, u.nombre AS usuario_nombre,
                   u.correo AS usuario_correo,
                   u.telefono AS usuario_telefono
            FROM clientes c
            LEFT JOIN usuarios u ON u.id_usuario = c.id_usuario
            ORDER BY c.id_cliente DESC
        """)
        filas = cursor.fetchall()
        clientes = []
        for f in filas:
            id_cli = f.get('id_cliente') or f.get('id')
            tipo_raw = str(f.get('tipo') or f.get('tipo_cliente') or 'B2C').upper()
            es_negocio = tipo_raw == 'B2B' or bool(
                f.get('nombre_negocio') or f.get('razon_social') or f.get('rfc')
            )

            total_ped = 0
            try:
                cursor.execute(
                    "SELECT COUNT(*) AS total FROM pedidos WHERE id_cliente = %s",
                    (id_cli,)
                )
                row_ped = cursor.fetchone()
                total_ped = int((row_ped or {}).get('total') or 0)
            except Exception:
                total_ped = 0

            if total_ped >= 5:
                frecuencia = 'Frecuente'
            elif total_ped >= 1:
                frecuencia = 'Casual'
            else:
                frecuencia = 'Ocasional'

            nombre_mostrar = (
                f.get('nombre_negocio')
                or f.get('razon_social')
                or f.get('negocio')
                or f.get('nombre')
                or f.get('usuario_nombre')
                or f"Cliente #{id_cli}"
            )

            clientes.append({
                'id': id_cli,
                'nombre': str(nombre_mostrar),
                'frecuencia': frecuencia,
                'segmento': 'negocio' if es_negocio else 'domicilio',
                'tipo_etiqueta': 'Negocio B2B' if es_negocio else 'Hogar B2C',
                'correo': str(f.get('correo') or f.get('email') or f.get('usuario_correo') or ''),
                'direccion': str(f.get('direccion') or f.get('domicilio') or ''),
                'rfc': str(f.get('rfc') or ''),
                'telefono': str(f.get('telefono') or f.get('usuario_telefono') or ''),
                'total_pedidos': total_ped,
                'colorIndicador': 'verde' if es_negocio or total_ped >= 2 else 'amarillo',
            })

        return jsonify({'exito': True, 'clientes': clientes}), 200
    except Exception as e:
        print("ERROR AL LISTAR CLIENTES CRM:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudieron cargar los clientes'}), 500
    finally:
        if cursor:
            cursor.close()


@admin_clientes_bp.route('/api/admin/clientes/<int:id_cliente>', methods=['GET'])
@login_requerido
def obtener_cliente_crm(id_cliente):
    cursor = None
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT c.*, u.nombre AS usuario_nombre,
                   u.correo AS usuario_correo,
                   u.telefono AS usuario_telefono
            FROM clientes c
            LEFT JOIN usuarios u ON u.id_usuario = c.id_usuario
            WHERE c.id_cliente = %s
        """, (id_cliente,))
        f = cursor.fetchone()
        if not f:
            return jsonify({'exito': False, 'mensaje': 'Cliente no encontrado'}), 404

        negocio_val = (
            f.get('nombre_negocio')
            or f.get('razon_social')
            or f.get('negocio')
            or f.get('nombre')
            or f.get('usuario_nombre')
            or f"Cliente #{id_cliente}"
        )
        tipo_raw = str(f.get('tipo') or f.get('tipo_cliente') or '').upper()
        es_negocio = tipo_raw == 'B2B' or bool(
            f.get('nombre_negocio') or f.get('razon_social') or f.get('rfc')
        )

        cliente = {
            'id': f.get('id_cliente') or id_cliente,
            'segmento': 'Negocio B2B' if es_negocio else 'Hogar B2C',
            'negocio': str(negocio_val),
            'correo': str(f.get('correo') or f.get('email') or f.get('usuario_correo') or 'No registrado'),
            'direccion': str(f.get('direccion') or f.get('domicilio') or 'No registrada'),
            'rfc': str(f.get('rfc') or 'No registrado'),
            'telefono': str(f.get('telefono') or f.get('usuario_telefono') or 'No registrado'),
        }

        return jsonify({'exito': True, 'cliente': cliente}), 200
    except Exception as e:
        print("ERROR AL OBTENER CLIENTE CRM:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudo cargar la ficha del cliente'}), 500
    finally:
        if cursor:
            cursor.close()