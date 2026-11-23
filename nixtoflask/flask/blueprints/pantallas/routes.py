"""
Rutas que usan las pantallas del frontend del equipo (diseño de los maquetados).

Todas reutilizan las reglas del backend probado:
  - las funciones del panel solo las usa el administrador (@admin_requerido)
  - los precios y totales los calcula Flask, nunca el navegador
  - cada cliente solo ve sus propios datos
"""
from datetime import date

from flask import Blueprint, request, jsonify, session

from database import mysql
from utils.seguridad import admin_requerido, cliente_requerido, login_requerido
from utils.validaciones import ErrorValidacion, texto, numero
from utils.pedidos import notificar
from utils.geocodificar import geocodificar

pantallas_bp = Blueprint('pantallas', __name__)


# =====================================================================
#  CATÁLOGO (pantallas de inicio, buscador, detalle y gestión de menú)
# =====================================================================

CONSULTA_PRODUCTOS = """
    SELECT p.id_producto, p.id_categoria, c.nombre AS categoria,
           p.nombre, p.descripcion, p.presentacion,
           p.kg_por_unidad, p.precio_b2c, p.precio_b2b_n1, p.precio_b2b_n2,
           p.existencia, p.imagen_url, p.es_paquete, p.disponible, p.activo
    FROM productos p
    LEFT JOIN categorias c ON c.id_categoria = p.id_categoria
"""

# Las opciones del formulario del frontend y su línea de producto en MySQL
CATEGORIAS_FORMULARIO = {
    'tortillas': 1, 'derivados de maíz': 1,
    'guisados': 2,
    'salsas': 3,
    'lácteos': 4, 'lacteos': 4,
    'aguas': 5, 'aguas frescas': 5
}


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
        'agotado': (not f['disponible']) or (not f['es_paquete'] and float(f['existencia'] or 0) <= 0)
    }


def kg_por_presentacion(presentacion):
    """Equivalencia en kg para las métricas (1 L ≈ 1 kg)."""
    p = presentacion.lower().replace(' ', '')
    if '100ml' in p:
        return 0.1
    if '250' in p:
        return 0.25
    if '10' in p and ('pza' in p or 'pieza' in p):
        return 0.85
    return 1


@pantallas_bp.route('/api/catalogo', methods=['GET'])
def listar_catalogo():
    """Clientes y visitantes ven lo disponible; el administrador también ve lo pausado."""
    cursor = None
    try:
        es_admin = session.get('rol') == 'admin'
        filtro = 'WHERE p.activo = 1'   # los pausados también se muestran, marcados como agotados
        cursor = mysql.connection.cursor()
        cursor.execute(f"{CONSULTA_PRODUCTOS} {filtro} ORDER BY p.es_paquete, c.orden, p.id_producto")
        return jsonify({'exito': True, 'productos': [armar_producto(f) for f in cursor.fetchall()]}), 200
    except Exception as e:
        print("ERROR EN CATALOGO:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudo cargar el catálogo'}), 500
    finally:
        if cursor:
            cursor.close()


@pantallas_bp.route('/api/catalogo/<int:id_producto>', methods=['GET'])
def detalle_catalogo(id_producto):
    cursor = None
    try:
        cursor = mysql.connection.cursor()
        cursor.execute(f"{CONSULTA_PRODUCTOS} WHERE p.id_producto = %s AND p.activo = 1", (id_producto,))
        fila = cursor.fetchone()
        if not fila:
            return jsonify({'exito': False, 'mensaje': 'El producto no existe'}), 404
        return jsonify({'exito': True, 'producto': armar_producto(fila)}), 200
    except Exception as e:
        print("ERROR EN DETALLE:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudo cargar el producto'}), 500
    finally:
        if cursor:
            cursor.close()


def leer_formulario_producto(datos):
    """Valida el formulario de la gestión de menú (mismas reglas que /api/admin/productos)."""
    nombre = texto(datos, 'nombre', 'Nombre', minimo=3, maximo=100)
    presentacion = texto(datos, 'presentacion', 'Presentación', minimo=2, maximo=50)
    descripcion = texto(datos, 'descripcion', 'Descripción', minimo=0, maximo=500, obligatorio=False)
    categoria = str(datos.get('categoria', '')).strip().lower()
    id_categoria = CATEGORIAS_FORMULARIO.get(categoria)
    if not id_categoria:
        raise ErrorValidacion('Elige una categoría válida')

    precio_b2c = round(numero(datos, 'precio_b2c', 'Precio B2C', permitir_cero=False), 2)
    # El formulario tiene un solo precio B2B: es el nivel 1; el nivel 2 aplica el −15 % del documento
    precio_n1 = round(numero(datos, 'precio_b2b', 'Precio B2B', permitir_cero=False), 2)
    precio_n2 = round(min(precio_n1, precio_b2c * 0.85), 2)
    if precio_n1 > precio_b2c:
        raise ErrorValidacion('El precio B2B no puede ser mayor que el precio B2C')

    return {
        'nombre': nombre, 'presentacion': presentacion, 'descripcion': descripcion or None,
        'id_categoria': id_categoria, 'precio_b2c': precio_b2c,
        'precio_b2b_n1': precio_n1, 'precio_b2b_n2': precio_n2,
        'kg_por_unidad': kg_por_presentacion(presentacion)
    }


def nombre_repetido(cursor, nombre, id_producto=None):
    cursor.execute(
        "SELECT id_producto FROM productos WHERE nombre = %s AND activo = 1 AND id_producto <> %s",
        (nombre, id_producto or 0)
    )
    return cursor.fetchone() is not None


@pantallas_bp.route('/api/catalogo', methods=['POST'])
@admin_requerido
def crear_producto_menu():
    cursor = None
    try:
        p = leer_formulario_producto(request.get_json(silent=True) or {})
        cursor = mysql.connection.cursor()
        if nombre_repetido(cursor, p['nombre']):
            raise ErrorValidacion('Ya existe un producto con ese nombre')

        cursor.execute("""
            INSERT INTO productos (id_categoria, nombre, descripcion, presentacion, kg_por_unidad,
                                   precio_b2c, precio_b2b_n1, precio_b2b_n2)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (p['id_categoria'], p['nombre'], p['descripcion'], p['presentacion'], p['kg_por_unidad'],
              p['precio_b2c'], p['precio_b2b_n1'], p['precio_b2b_n2']))
        id_producto = cursor.lastrowid
        mysql.connection.commit()
        return jsonify({'exito': True, 'mensaje': 'Producto creado', 'id_producto': id_producto}), 201
    except ErrorValidacion as e:
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo
    except Exception as e:
        print("ERROR AL CREAR PRODUCTO:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo crear el producto'}), 500
    finally:
        if cursor:
            cursor.close()


@pantallas_bp.route('/api/catalogo/<int:id_producto>', methods=['PUT'])
@admin_requerido
def editar_producto_menu(id_producto):
    cursor = None
    try:
        datos = request.get_json(silent=True) or {}
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT es_paquete FROM productos WHERE id_producto = %s AND activo = 1", (id_producto,))
        actual = cursor.fetchone()
        if not actual:
            raise ErrorValidacion('El producto no existe', 404)
        if actual['es_paquete']:
            raise ErrorValidacion('Los paquetes "Comida Completa" no se editan desde este formulario')

        p = leer_formulario_producto(datos)
        if nombre_repetido(cursor, p['nombre'], id_producto):
            raise ErrorValidacion('Ya existe un producto con ese nombre')

        cursor.execute("""
            UPDATE productos SET id_categoria = %s, nombre = %s, descripcion = %s, presentacion = %s,
                   kg_por_unidad = %s, precio_b2c = %s, precio_b2b_n1 = %s, precio_b2b_n2 = %s
            WHERE id_producto = %s
        """, (p['id_categoria'], p['nombre'], p['descripcion'], p['presentacion'], p['kg_por_unidad'],
              p['precio_b2c'], p['precio_b2b_n1'], p['precio_b2b_n2'], id_producto))
        mysql.connection.commit()
        return jsonify({'exito': True, 'mensaje': 'Producto actualizado', 'id_producto': id_producto}), 200
    except ErrorValidacion as e:
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo
    except Exception as e:
        print("ERROR AL EDITAR PRODUCTO:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo actualizar el producto'}), 500
    finally:
        if cursor:
            cursor.close()


@pantallas_bp.route('/api/catalogo/<int:id_producto>/estado', methods=['PATCH'])
@admin_requerido
def cambiar_estado_menu(id_producto):
    """Activar o pausar (el producto pausado se ve como agotado; no se borra)."""
    cursor = None
    try:
        activo = bool((request.get_json(silent=True) or {}).get('activo'))
        cursor = mysql.connection.cursor()
        cursor.execute("UPDATE productos SET disponible = %s WHERE id_producto = %s AND activo = 1",
                       (activo, id_producto))
        if cursor.rowcount == 0:
            cursor.execute("SELECT 1 FROM productos WHERE id_producto = %s AND activo = 1", (id_producto,))
            if not cursor.fetchone():
                return jsonify({'exito': False, 'mensaje': 'El producto no existe'}), 404
        mysql.connection.commit()
        return jsonify({'exito': True, 'mensaje': 'Producto activado' if activo else 'Producto pausado'}), 200
    except Exception as e:
        print("ERROR AL CAMBIAR ESTADO:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo cambiar el estado'}), 500
    finally:
        if cursor:
            cursor.close()


# =====================================================================
#  PERFIL: guardar la dirección de entrega
# =====================================================================

@pantallas_bp.route('/api/perfil/direccion', methods=['PUT'])
@cliente_requerido
def guardar_direccion():
    cursor = None
    try:
        direccion = texto(request.get_json(silent=True) or {}, 'direccion', 'Dirección', minimo=5, maximo=255)
        cursor = mysql.connection.cursor()
        cursor.execute("UPDATE clientes SET direccion = %s WHERE id_cliente = %s", (direccion, session['id_cliente']))

        # También se guarda su ubicación en el mapa, si la dirección se encuentra
        latitud, longitud = geocodificar(direccion)
        if latitud is not None:
            cursor.execute("UPDATE clientes SET latitud = %s, longitud = %s WHERE id_cliente = %s",
                           (latitud, longitud, session['id_cliente']))

        mysql.connection.commit()
        return jsonify({'exito': True, 'mensaje': 'Dirección de entrega guardada', 'direccion': direccion}), 200
    except ErrorValidacion as e:
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo
    except Exception as e:
        print("ERROR AL GUARDAR DIRECCION:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo guardar la dirección'}), 500
    finally:
        if cursor:
            cursor.close()


# =====================================================================
#  INVENTARIO DE PRODUCTO TERMINADO (pantalla de control de inventario)
# =====================================================================

@pantallas_bp.route('/api/inventario/productos', methods=['GET'])
@admin_requerido
def inventario_productos():
    cursor = None
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT p.id_producto, p.nombre, p.presentacion, p.existencia, c.nombre AS categoria
            FROM productos p LEFT JOIN categorias c ON c.id_categoria = p.id_categoria
            WHERE p.activo = 1 AND p.es_paquete = 0
            ORDER BY c.orden, p.id_producto
        """)
        productos = [{
            'id_producto': f['id_producto'], 'nombre': f['nombre'], 'presentacion': f['presentacion'],
            'categoria': f['categoria'], 'existencia': round(float(f['existencia'] or 0), 3)
        } for f in cursor.fetchall()]

        inicio_mes = date.today().replace(day=1)
        cursor.execute("""
            SELECT m.id_merma, m.fecha, m.cantidad, m.motivo,
                   COALESCE(p.nombre, i.nombre) AS nombre
            FROM mermas m
            LEFT JOIN productos p ON p.id_producto = m.id_producto
            LEFT JOIN insumos i ON i.id_insumo = m.id_insumo
            WHERE m.fecha >= %s ORDER BY m.fecha DESC
        """, (inicio_mes,))
        mermas = [{
            'id_merma': m['id_merma'], 'fecha': m['fecha'].strftime('%Y-%m-%d %H:%M'),
            'cantidad': float(m['cantidad']), 'motivo': m['motivo'], 'producto': m['nombre']
        } for m in cursor.fetchall()]

        return jsonify({'exito': True, 'productos': productos, 'mermas': mermas}), 200
    except Exception as e:
        print("ERROR EN INVENTARIO:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudo cargar el inventario'}), 500
    finally:
        if cursor:
            cursor.close()


@pantallas_bp.route('/api/inventario/productos/<int:id_producto>', methods=['PUT'])
@admin_requerido
def ajustar_existencia(id_producto):
    """Ajuste manual del conteo físico (la producción por lotes está en /api/admin/producciones)."""
    cursor = None
    try:
        existencia = round(numero(request.get_json(silent=True) or {}, 'existencia', 'Existencia'), 3)
        cursor = mysql.connection.cursor()
        cursor.execute("UPDATE productos SET existencia = %s WHERE id_producto = %s AND es_paquete = 0",
                       (existencia, id_producto))
        if cursor.rowcount == 0:
            cursor.execute("SELECT 1 FROM productos WHERE id_producto = %s AND es_paquete = 0", (id_producto,))
            if not cursor.fetchone():
                return jsonify({'exito': False, 'mensaje': 'El producto no existe'}), 404
        mysql.connection.commit()
        return jsonify({'exito': True, 'existencia': existencia}), 200
    except ErrorValidacion as e:
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo
    except Exception as e:
        print("ERROR AL AJUSTAR:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo actualizar la existencia'}), 500
    finally:
        if cursor:
            cursor.close()


@pantallas_bp.route('/api/inventario/reabastecer', methods=['POST'])
@admin_requerido
def reabastecer():
    cursor = None
    try:
        datos = request.get_json(silent=True) or {}
        id_producto = int(datos.get('id_producto') or 0)
        cantidad = numero(datos, 'cantidad', 'Cantidad', permitir_cero=False)
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT existencia FROM productos WHERE id_producto = %s AND es_paquete = 0 FOR UPDATE",
                       (id_producto,))
        fila = cursor.fetchone()
        if not fila:
            return jsonify({'exito': False, 'mensaje': 'El producto no existe'}), 404
        nueva = round(float(fila['existencia']) + cantidad, 3)
        cursor.execute("UPDATE productos SET existencia = %s WHERE id_producto = %s", (nueva, id_producto))
        mysql.connection.commit()
        return jsonify({'exito': True, 'existencia': nueva}), 200
    except ErrorValidacion as e:
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo
    except Exception as e:
        print("ERROR AL REABASTECER:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo reabastecer'}), 500
    finally:
        if cursor:
            cursor.close()


@pantallas_bp.route('/api/inventario/mermas', methods=['POST'])
@admin_requerido
def registrar_merma_producto():
    """Merma de producto terminado: guarda el registro y descuenta la existencia."""
    cursor = None
    try:
        datos = request.get_json(silent=True) or {}
        id_producto = int(datos.get('id_producto') or 0)
        cantidad = numero(datos, 'cantidad', 'Cantidad', permitir_cero=False)
        motivo = texto(datos, 'motivo', 'Motivo', minimo=3, maximo=255)

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT existencia FROM productos WHERE id_producto = %s AND es_paquete = 0 FOR UPDATE",
                       (id_producto,))
        fila = cursor.fetchone()
        if not fila:
            return jsonify({'exito': False, 'mensaje': 'Elige el producto afectado'}), 400
        if cantidad > float(fila['existencia']):
            return jsonify({'exito': False, 'mensaje': f"Solo hay {float(fila['existencia']):g} en existencia"}), 400

        cursor.execute("INSERT INTO mermas (id_producto, cantidad, motivo) VALUES (%s, %s, %s)",
                       (id_producto, cantidad, motivo))
        id_merma = cursor.lastrowid
        nueva_existencia = round(float(fila['existencia']) - cantidad, 3)
        cursor.execute("UPDATE productos SET existencia = %s WHERE id_producto = %s",
                       (nueva_existencia, id_producto))
        mysql.connection.commit()
        return jsonify({'exito': True, 'mensaje': 'Merma registrada',
                        'id_merma': id_merma, 'existencia': nueva_existencia}), 201
    except ErrorValidacion as e:
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo
    except Exception as e:
        print("ERROR AL REGISTRAR MERMA:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo registrar la merma'}), 500
    finally:
        if cursor:
            cursor.close()


# =====================================================================
#  DESPACHO Y RASTREO (pantallas de logística)
# =====================================================================

BASE_ORIGEN = {'lat': 21.1221, 'lng': -101.6826}   # cocina (centro de León)
ZONAS_LEON = {                                     # aproximación si el pedido no tiene pin
    'moderno': {'lat': 21.1165, 'lng': -101.6715},
    'jardines': {'lat': 21.1458, 'lng': -101.6934},
    'centro': {'lat': 21.1221, 'lng': -101.6826},
    'del valle': {'lat': 21.1382, 'lng': -101.6789},
}
NOMBRE_ESTADO = {'pendiente': 'Pendiente', 'preparando': 'Preparando', 'en_ruta': 'En Ruta',
                 'entregado': 'Entregado', 'cancelado': 'Cancelado'}


def destino_de(pedido):
    """El pin que marcó el cliente; si no hay, una zona aproximada por la dirección."""
    if pedido.get('latitud') is not None and pedido.get('longitud') is not None:
        return {'lat': float(pedido['latitud']), 'lng': float(pedido['longitud'])}
    texto_dir = (pedido.get('direccion_entrega') or '').lower()
    for clave, coords in ZONAS_LEON.items():
        if clave in texto_dir:
            return coords
    return {'lat': 21.1290, 'lng': -101.6750}


@pantallas_bp.route('/api/admin/despacho/pedidos', methods=['GET'])
@admin_requerido
def pedidos_despacho():
    cursor = None
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT p.id_pedido, p.fecha_pedido, p.estado, p.total, p.direccion_entrega,
                   p.latitud, p.longitud, p.id_repartidor,
                   COALESCE(c.nombre_negocio, u.nombre) AS cliente
            FROM pedidos p
            JOIN clientes c ON c.id_cliente = p.id_cliente
            JOIN usuarios u ON u.id_usuario = c.id_usuario
            WHERE p.modalidad = 'domicilio' AND p.estado IN ('pendiente', 'preparando', 'en_ruta')
            ORDER BY p.fecha_pedido, p.id_pedido
        """)
        pedidos = [{
            'id': f['id_pedido'],
            'folio': f"NG-{f['id_pedido']:04d}",
            'hora': f['fecha_pedido'].strftime('%H:%M'),
            'fecha': f['fecha_pedido'].strftime('%Y-%m-%d'),
            'cliente': f['cliente'],
            'detalle': f"{f['direccion_entrega']} · ${float(f['total']):.2f} MXN",
            'estado': NOMBRE_ESTADO[f['estado']],
            'asignado': f['estado'] == 'en_ruta',
            'origen': BASE_ORIGEN,
            'destino': destino_de(f)
        } for f in cursor.fetchall()]
        return jsonify({'exito': True, 'pedidos': pedidos, 'origen': BASE_ORIGEN}), 200
    except Exception as e:
        print("ERROR AL LISTAR DESPACHO:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudieron cargar los pedidos de ruta'}), 500
    finally:
        if cursor:
            cursor.close()


@pantallas_bp.route('/api/admin/despacho/asignar/<int:id_pedido>', methods=['POST'])
@admin_requerido
def asignar_y_enviar(id_pedido):
    """
    Asigna un repartidor (el indicado o el primero activo) y pone el pedido "En ruta",
    con las mismas reglas del despacho: debe estar pagado y ser a domicilio.
    """
    cursor = None
    try:
        datos = request.get_json(silent=True) or {}
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT p.*, c.id_usuario FROM pedidos p JOIN clientes c ON c.id_cliente = p.id_cliente
            WHERE p.id_pedido = %s FOR UPDATE
        """, (id_pedido,))
        p = cursor.fetchone()
        if not p:
            return jsonify({'exito': False, 'mensaje': 'El pedido no existe'}), 404
        if p['modalidad'] != 'domicilio':
            return jsonify({'exito': False, 'mensaje': 'Los pedidos para recoger no llevan repartidor'}), 400
        if p['estado'] in ('entregado', 'cancelado'):
            return jsonify({'exito': False, 'mensaje': f"El pedido ya está {p['estado']}"}), 400
        if p['estado_pago'] != 'pagado':
            return jsonify({'exito': False, 'mensaje': 'Primero hay que validar el pago del pedido'}), 400

        if datos.get('id_repartidor'):
            cursor.execute("SELECT * FROM repartidores WHERE id_repartidor = %s AND activo = 1", (datos['id_repartidor'],))
        else:
            cursor.execute("SELECT * FROM repartidores WHERE activo = 1 ORDER BY id_repartidor LIMIT 1")
        repartidor = cursor.fetchone()
        if not repartidor:
            return jsonify({'exito': False, 'mensaje': 'No hay repartidores activos'}), 400

        cursor.execute("""
            SELECT COALESCE(MAX(orden_ruta), 0) + 1 AS siguiente FROM pedidos
            WHERE id_repartidor = %s AND DATE(fecha_pedido) = DATE(%s) AND estado <> 'cancelado'
        """, (repartidor['id_repartidor'], p['fecha_pedido']))
        orden = p['orden_ruta'] if p['id_repartidor'] == repartidor['id_repartidor'] and p['orden_ruta'] \
            else cursor.fetchone()['siguiente']

        cursor.execute("UPDATE pedidos SET id_repartidor = %s, orden_ruta = %s, estado = 'en_ruta' WHERE id_pedido = %s",
                       (repartidor['id_repartidor'], orden, id_pedido))
        notificar(cursor, p['id_usuario'], 'Tu pedido va en camino',
                  f"{repartidor['nombre']} lleva tu pedido #{id_pedido}.")
        mysql.connection.commit()
        return jsonify({'exito': True, 'estado': 'En Ruta', 'repartidor': repartidor['nombre'], 'orden_ruta': orden}), 200
    except Exception as e:
        print("ERROR AL ASIGNAR:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo asignar el pedido'}), 500
    finally:
        if cursor:
            cursor.close()


@pantallas_bp.route('/api/rastreo/actual', methods=['GET'])
@login_requerido
def rastreo_actual():
    """
    Cliente: su pedido en curso más reciente (o el que indique con ?id_pedido=, si es suyo).
    Administrador: el pedido indicado o el último en ruta.
    """
    cursor = None
    try:
        id_pedido = request.args.get('id_pedido', type=int)
        es_admin = session.get('rol') == 'admin'
        condiciones, parametros = ["p.estado <> 'cancelado'"], []
        if not es_admin:
            condiciones.append("p.id_cliente = %s"); parametros.append(session.get('id_cliente'))
        if id_pedido:
            condiciones.append("p.id_pedido = %s"); parametros.append(id_pedido)
        elif es_admin:
            condiciones.append("p.estado = 'en_ruta'")
        else:
            condiciones.append("p.estado IN ('pendiente', 'preparando', 'en_ruta')")

        cursor = mysql.connection.cursor()
        cursor.execute(f"""
            SELECT p.*, r.nombre AS rep_nombre, r.telefono AS rep_telefono, r.placas AS rep_placas
            FROM pedidos p LEFT JOIN repartidores r ON r.id_repartidor = p.id_repartidor
            WHERE {' AND '.join(condiciones)}
            ORDER BY p.fecha_pedido DESC, p.id_pedido DESC LIMIT 1
        """, tuple(parametros))
        p = cursor.fetchone()
        if not p:
            return jsonify({'exito': False, 'mensaje': 'No tienes pedidos en curso'}), 404

        paso = {'pendiente': 'Preparando', 'preparando': 'Preparando', 'en_ruta': 'En Ruta',
                'entregado': 'Entregado'}.get(p['estado'], 'Preparando')
        return jsonify({
            'exito': True,
            'id_pedido': p['id_pedido'],
            'folio': f"NG-{p['id_pedido']:04d}",
            'direccion': p['direccion_entrega'] or 'Recoger en cocina',
            'estadoPedido': paso,
            'estadoRaw': p['estado'],
            'origen': BASE_ORIGEN,
            'destino': destino_de(p),
            'repartidor': {'nombre': p['rep_nombre'], 'telefono': p['rep_telefono'], 'placa': p['rep_placas']}
                          if p['rep_nombre'] else None
        }), 200
    except Exception as e:
        print("ERROR EN RASTREO:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudo obtener el rastreo'}), 500
    finally:
        if cursor:
            cursor.close()
