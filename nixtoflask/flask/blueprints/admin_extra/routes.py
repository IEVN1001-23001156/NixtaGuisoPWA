"""
Funciones del panel administrativo rediseñado:
contadores y avisos, buscador, gráficas de kilos, consumo del cliente,
edición de recetas y gastos, y anulación de compras, producciones y mermas.
Todas son exclusivas del administrador.
"""
from datetime import date, timedelta

from flask import Blueprint, request, jsonify

from database import mysql
from utils.seguridad import admin_requerido
from utils.validaciones import ErrorValidacion, texto, numero

admin_extra_bp = Blueprint('admin_extra', __name__)

# Proyección del documento (sección 14.2): mes 1 de operación = marzo de 2027
PLAN_KILOS = {'2027-03': 600, '2027-04': 1200, '2027-05': 1900,
              '2027-06': 2600, '2027-07': 3300, '2027-08': 4000}

KG_VENDIDOS = """
    SELECT COALESCE(SUM(d.cantidad * pr.kg_por_unidad), 0) AS kg
    FROM pedidos p
    JOIN detalle_pedido d ON d.id_pedido = p.id_pedido
    JOIN productos pr ON pr.id_producto = d.id_producto
    WHERE p.estado <> 'cancelado'
"""


def respuesta_error(e, mensaje):
    if isinstance(e, ErrorValidacion):
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo
    print("ERROR:", str(e))
    mysql.connection.rollback()
    return jsonify({'exito': False, 'mensaje': mensaje}), 500


# ---------------------------------------------------------------------
#  CONTADORES DEL MENÚ Y AVISOS DE LA CAMPANA
# ---------------------------------------------------------------------
@admin_extra_bp.route('/api/admin/contadores', methods=['GET'])
@admin_requerido
def contadores():
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT COUNT(*) AS n FROM insumos WHERE activo = 1 AND existencia < stock_minimo")
        por_surtir = cursor.fetchone()['n']
        cursor.execute("SELECT COUNT(*) AS n FROM pedidos WHERE estado IN ('pendiente','preparando','en_ruta')")
        activos = cursor.fetchone()['n']
        cursor.execute("""SELECT COUNT(*) AS n FROM pedidos WHERE metodo_pago = 'transferencia'
                          AND estado_pago = 'por_validar' AND estado <> 'cancelado'""")
        por_validar = cursor.fetchone()['n']

        avisos = []
        cursor.execute("""SELECT nombre, existencia, stock_minimo, unidad FROM insumos
                          WHERE activo = 1 AND existencia < stock_minimo ORDER BY nombre""")
        for i in cursor.fetchall():
            avisos.append({'tipo': 'insumo', 'ruta': '/admin/inventario',
                           'mensaje': f"Stock bajo: {i['nombre']} ({float(i['existencia']):g} de {float(i['stock_minimo']):g} {i['unidad']})"})
        cursor.execute("""SELECT nombre FROM productos WHERE activo = 1 AND es_paquete = 0
                          AND (disponible = 0 OR existencia <= 0) ORDER BY nombre""")
        for p in cursor.fetchall():
            avisos.append({'tipo': 'producto', 'ruta': '/admin/menu', 'mensaje': f"Agotado: {p['nombre']}"})
        if por_validar:
            avisos.append({'tipo': 'pago', 'ruta': '/admin/logistica',
                           'mensaje': f"{por_validar} transferencia(s) por validar"})

        return jsonify({'exito': True, 'insumos_por_surtir': por_surtir, 'pedidos_activos': activos,
                        'pagos_por_validar': por_validar, 'avisos': avisos}), 200
    except Exception as e:
        return respuesta_error(e, 'No se pudieron obtener los contadores')
    finally:
        cursor.close()


# ---------------------------------------------------------------------
#  BUSCADOR DEL PANEL
# ---------------------------------------------------------------------
@admin_extra_bp.route('/api/admin/buscar', methods=['GET'])
@admin_requerido
def buscar():
    q = (request.args.get('q') or '').strip()
    if len(q) < 2:
        return jsonify({'exito': True, 'resultados': []}), 200
    patron = f"%{q}%"
    cursor = mysql.connection.cursor()
    try:
        resultados = []
        cursor.execute("""SELECT id_producto, nombre, presentacion FROM productos
                          WHERE activo = 1 AND nombre LIKE %s ORDER BY nombre LIMIT 5""", (patron,))
        resultados += [{'tipo': 'Producto', 'id': f['id_producto'], 'texto': f"{f['nombre']} · {f['presentacion']}",
                        'ruta': '/admin/menu'} for f in cursor.fetchall()]
        cursor.execute("""SELECT c.id_cliente, u.nombre, c.nombre_negocio FROM clientes c
                          JOIN usuarios u ON u.id_usuario = c.id_usuario
                          WHERE u.nombre LIKE %s OR c.nombre_negocio LIKE %s OR u.correo LIKE %s
                          ORDER BY u.nombre LIMIT 5""", (patron, patron, patron))
        resultados += [{'tipo': 'Cliente', 'id': f['id_cliente'], 'texto': f['nombre_negocio'] or f['nombre'],
                        'ruta': '/admin/crm'} for f in cursor.fetchall()]
        numero_pedido = ''.join(ch for ch in q if ch.isdigit())
        cursor.execute("""SELECT p.id_pedido, COALESCE(c.nombre_negocio, u.nombre) AS cliente, p.estado
                          FROM pedidos p JOIN clientes c ON c.id_cliente = p.id_cliente
                          JOIN usuarios u ON u.id_usuario = c.id_usuario
                          WHERE p.id_pedido = %s OR u.nombre LIKE %s OR c.nombre_negocio LIKE %s
                          ORDER BY p.id_pedido DESC LIMIT 5""", (int(numero_pedido or 0), patron, patron))
        resultados += [{'tipo': 'Pedido', 'id': f['id_pedido'], 'texto': f"NG-{f['id_pedido']:04d} · {f['cliente']} ({f['estado']})",
                        'ruta': '/admin/logistica'} for f in cursor.fetchall()]
        return jsonify({'exito': True, 'resultados': resultados}), 200
    except Exception as e:
        return respuesta_error(e, 'No se pudo buscar')
    finally:
        cursor.close()


# ---------------------------------------------------------------------
#  KILOS POR CANAL (PANEL) Y PLAN CONTRA REAL (REPORTES)
# ---------------------------------------------------------------------
@admin_extra_bp.route('/api/admin/kilos-canal', methods=['GET'])
@admin_requerido
def kilos_canal():
    dias = min(max(request.args.get('dias', default=6, type=int), 3), 14)
    cursor = mysql.connection.cursor()
    try:
        hoy = date.today()
        try:
            fin = date.fromisoformat(request.args.get('fecha')) if request.args.get('fecha') else hoy
        except ValueError:
            fin = hoy
        inicio = fin - timedelta(days=dias - 1)
        cursor.execute(f"""
            SELECT DATE(p.fecha_pedido) AS dia, p.tipo_cliente, SUM(d.cantidad * pr.kg_por_unidad) AS kg
            FROM pedidos p JOIN detalle_pedido d ON d.id_pedido = p.id_pedido
            JOIN productos pr ON pr.id_producto = d.id_producto
            WHERE p.estado <> 'cancelado' AND DATE(p.fecha_pedido) BETWEEN %s AND %s
            GROUP BY DATE(p.fecha_pedido), p.tipo_cliente
        """, (inicio, fin))
        datos = {(f['dia'], f['tipo_cliente']): float(f['kg']) for f in cursor.fetchall()}
        nombres = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
        fechas = [inicio + timedelta(days=i) for i in range(dias)]

        cursor.execute(f"""
            SELECT p.tipo_cliente, SUM(d.cantidad * pr.kg_por_unidad) AS kg
            FROM pedidos p JOIN detalle_pedido d ON d.id_pedido = p.id_pedido
            JOIN productos pr ON pr.id_producto = d.id_producto
            WHERE p.estado <> 'cancelado' AND DATE(p.fecha_pedido) BETWEEN %s AND %s
            GROUP BY p.tipo_cliente
        """, (fin.replace(day=1), fin))
        mes = {f['tipo_cliente']: float(f['kg']) for f in cursor.fetchall()}
        total_mes = mes.get('B2B', 0) + mes.get('B2C', 0)

        return jsonify({
            'exito': True,
            'etiquetas': ['Hoy' if d == hoy else f"{nombres[d.weekday()]} {d.day}" for d in fechas],
            'b2b': [round(datos.get((d, 'B2B'), 0), 2) for d in fechas],
            'b2c': [round(datos.get((d, 'B2C'), 0), 2) for d in fechas],
            'mezcla_mes': {'b2b': round(mes.get('B2B', 0) / total_mes * 100, 1) if total_mes else None,
                           'b2c': round(mes.get('B2C', 0) / total_mes * 100, 1) if total_mes else None,
                           'meta_b2b': 75, 'meta_b2c': 25}
        }), 200
    except Exception as e:
        return respuesta_error(e, 'No se pudo calcular la gráfica')
    finally:
        cursor.close()


@admin_extra_bp.route('/api/admin/plan-kilos', methods=['GET'])
@admin_requerido
def plan_kilos():
    cursor = mysql.connection.cursor()
    try:
        meses = list(PLAN_KILOS.keys())
        real = []
        for mes in meses:
            cursor.execute(KG_VENDIDOS + " AND DATE_FORMAT(p.fecha_pedido, '%%Y-%%m') = %s", (mes,))
            real.append(round(float(cursor.fetchone()['kg']), 1))
        etiquetas = [f"Mes {i + 1}" for i in range(len(meses))]
        return jsonify({'exito': True, 'meses': meses, 'etiquetas': etiquetas,
                        'plan': list(PLAN_KILOS.values()), 'real': real}), 200
    except Exception as e:
        return respuesta_error(e, 'No se pudo calcular el plan')
    finally:
        cursor.close()


# ---------------------------------------------------------------------
#  CRM: CONSUMO DEL CLIENTE Y NIVEL RECOMENDADO
# ---------------------------------------------------------------------
@admin_extra_bp.route('/api/admin/clientes/<int:id_cliente>/consumo', methods=['GET'])
@admin_requerido
def consumo_cliente(id_cliente):
    cursor = mysql.connection.cursor()
    try:
        desde = date.today() - timedelta(days=30)
        cursor.execute("""
            SELECT COUNT(DISTINCT DATE(p.fecha_pedido)) AS dias,
                   COALESCE(SUM(CASE WHEN pr.id_categoria = 1 AND pr.presentacion = '1 kg' THEN d.cantidad END), 0) AS kg
            FROM pedidos p JOIN detalle_pedido d ON d.id_pedido = p.id_pedido
            JOIN productos pr ON pr.id_producto = d.id_producto
            WHERE p.id_cliente = %s AND p.estado <> 'cancelado' AND p.fecha_pedido >= %s
        """, (id_cliente, desde))
        f = cursor.fetchone()
        dias, kg = f['dias'], float(f['kg'])
        cursor.execute("""SELECT COUNT(*) AS n FROM programaciones
                          WHERE id_cliente = %s AND estado = 'activa' AND frecuencia = 'semanal'""", (id_cliente,))
        suscripcion = cursor.fetchone()['n'] > 0
        promedio = round(kg / dias, 1) if dias else 0

        # Documento, sección 7.2: nivel 2 con 15 kg diarios o más, o con suscripción semanal
        recomendado = 2 if (promedio >= 15 or suscripcion) else 1
        if suscripcion:
            motivo = 'Tiene un pedido semanal programado: corresponde el nivel 2.'
        elif dias == 0:
            motivo = 'Sin compras en los últimos 30 días: se sugiere el nivel 1.'
        else:
            motivo = f'Consume en promedio {promedio:g} kg de tortilla por día de compra: corresponde el nivel {recomendado}.'
        return jsonify({'exito': True, 'kg_promedio': promedio, 'dias_con_compra': dias,
                        'suscripcion_semanal': suscripcion, 'nivel_recomendado': recomendado, 'motivo': motivo}), 200
    except Exception as e:
        return respuesta_error(e, 'No se pudo calcular el consumo')
    finally:
        cursor.close()


# ---------------------------------------------------------------------
#  RECETAS (HOJA DE PROPORCIONES)
# ---------------------------------------------------------------------
@admin_extra_bp.route('/api/admin/recetas/<int:id_receta>', methods=['GET'])
@admin_requerido
def ver_receta(id_receta):
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("""SELECT r.*, p.nombre AS producto, p.presentacion FROM recetas r
                          JOIN productos p ON p.id_producto = r.id_producto WHERE r.id_receta = %s""", (id_receta,))
        r = cursor.fetchone()
        if not r:
            return jsonify({'exito': False, 'mensaje': 'La receta no existe'}), 404
        cursor.execute("""SELECT ri.id_insumo, i.nombre, i.unidad, ri.cantidad FROM receta_insumos ri
                          JOIN insumos i ON i.id_insumo = ri.id_insumo WHERE ri.id_receta = %s ORDER BY i.nombre""", (id_receta,))
        insumos = [{'id_insumo': i['id_insumo'], 'nombre': i['nombre'], 'unidad': i['unidad'],
                    'cantidad': float(i['cantidad'])} for i in cursor.fetchall()]
        return jsonify({'exito': True, 'receta': {
            'id_receta': r['id_receta'], 'nombre': r['nombre'], 'producto': r['producto'], 'presentacion': r['presentacion'],
            'rendimiento': float(r['rendimiento']), 'costo_lote': float(r['costo_lote']), 'insumos': insumos}}), 200
    except Exception as e:
        return respuesta_error(e, 'No se pudo obtener la receta')
    finally:
        cursor.close()


@admin_extra_bp.route('/api/admin/recetas/<int:id_receta>', methods=['PUT'])
@admin_requerido
def editar_receta(id_receta):
    cursor = mysql.connection.cursor()
    try:
        datos = request.get_json(silent=True) or {}
        nombre = texto(datos, 'nombre', 'Nombre de la receta', minimo=3, maximo=100)
        rendimiento = numero(datos, 'rendimiento', 'Rendimiento', permitir_cero=False)
        costo_lote = numero(datos, 'costo_lote', 'Costo por lote')
        insumos = datos.get('insumos')
        if not isinstance(insumos, list) or not insumos:
            raise ErrorValidacion('La receta debe tener al menos un insumo')
        limpios = {}
        for i in insumos:
            try:
                id_insumo, cantidad = int(i.get('id_insumo')), float(i.get('cantidad'))
            except (TypeError, ValueError, AttributeError):
                raise ErrorValidacion('Hay un insumo con datos incorrectos')
            if cantidad <= 0:
                raise ErrorValidacion('Las cantidades por lote deben ser mayores a cero')
            limpios[id_insumo] = cantidad

        cursor.execute("SELECT 1 FROM recetas WHERE id_receta = %s", (id_receta,))
        if not cursor.fetchone():
            raise ErrorValidacion('La receta no existe', 404)
        marcadores = ', '.join(['%s'] * len(limpios))
        cursor.execute(f"SELECT COUNT(*) AS n FROM insumos WHERE activo = 1 AND id_insumo IN ({marcadores})", tuple(limpios))
        if cursor.fetchone()['n'] != len(limpios):
            raise ErrorValidacion('Uno de los insumos no existe o está desactivado')

        cursor.execute("UPDATE recetas SET nombre = %s, rendimiento = %s, costo_lote = %s WHERE id_receta = %s",
                       (nombre, rendimiento, costo_lote, id_receta))
        cursor.execute("DELETE FROM receta_insumos WHERE id_receta = %s", (id_receta,))
        for id_insumo, cantidad in limpios.items():
            cursor.execute("INSERT INTO receta_insumos (id_receta, id_insumo, cantidad) VALUES (%s, %s, %s)",
                           (id_receta, id_insumo, cantidad))
        mysql.connection.commit()
        return jsonify({'exito': True, 'mensaje': 'Receta actualizada'}), 200
    except Exception as e:
        return respuesta_error(e, 'No se pudo actualizar la receta')
    finally:
        cursor.close()


# ---------------------------------------------------------------------
#  EDITAR GASTO DE MERCADEO
# ---------------------------------------------------------------------
@admin_extra_bp.route('/api/admin/gastos-mercadeo/<int:id_gasto>', methods=['PUT'])
@admin_requerido
def editar_gasto(id_gasto):
    cursor = mysql.connection.cursor()
    try:
        datos = request.get_json(silent=True) or {}
        categorias = ('infraestructura', 'empaque', 'publicidad_b2c', 'muestras_b2b',
                      'lead_ads_b2b', 'referidos_cupones', 'bono_primer_pedido')
        if datos.get('categoria') not in categorias:
            raise ErrorValidacion('Elige una categoría válida')
        concepto = texto(datos, 'concepto', 'Concepto', minimo=3, maximo=150)
        monto = numero(datos, 'monto', 'Monto', permitir_cero=False)
        fecha = str(datos.get('fecha') or '')[:10]
        cursor.execute("""UPDATE gastos_mercadeo SET categoria = %s, concepto = %s, monto = %s,
                          fecha = COALESCE(NULLIF(%s, ''), fecha) WHERE id_gasto = %s""",
                       (datos['categoria'], concepto, monto, fecha, id_gasto))
        cursor.execute("SELECT 1 FROM gastos_mercadeo WHERE id_gasto = %s", (id_gasto,))
        if not cursor.fetchone():
            raise ErrorValidacion('El gasto no existe', 404)
        mysql.connection.commit()
        return jsonify({'exito': True, 'mensaje': 'Gasto actualizado'}), 200
    except Exception as e:
        return respuesta_error(e, 'No se pudo actualizar el gasto')
    finally:
        cursor.close()


# ---------------------------------------------------------------------
#  ANULAR REGISTROS DE INVENTARIO (se revierte su efecto)
# ---------------------------------------------------------------------
@admin_extra_bp.route('/api/admin/compras/<int:id_compra>', methods=['DELETE'])
@admin_requerido
def anular_compra(id_compra):
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("""SELECT c.*, i.nombre, i.existencia FROM compras_insumos c
                          JOIN insumos i ON i.id_insumo = c.id_insumo WHERE c.id_compra = %s FOR UPDATE""", (id_compra,))
        c = cursor.fetchone()
        if not c:
            raise ErrorValidacion('La compra no existe', 404)
        if float(c['existencia']) < float(c['cantidad']):
            raise ErrorValidacion(f"No se puede anular: de {c['nombre']} solo quedan {float(c['existencia']):g} y la compra fue de {float(c['cantidad']):g}")
        cursor.execute("UPDATE insumos SET existencia = existencia - %s WHERE id_insumo = %s", (c['cantidad'], c['id_insumo']))
        cursor.execute("DELETE FROM compras_insumos WHERE id_compra = %s", (id_compra,))
        mysql.connection.commit()
        return jsonify({'exito': True, 'mensaje': f"Compra anulada: se restaron {float(c['cantidad']):g} de {c['nombre']}"}), 200
    except Exception as e:
        return respuesta_error(e, 'No se pudo anular la compra')
    finally:
        cursor.close()


@admin_extra_bp.route('/api/admin/producciones/<int:id_produccion>', methods=['DELETE'])
@admin_requerido
def anular_produccion(id_produccion):
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("""SELECT pr.*, r.id_producto, p.nombre, p.existencia FROM producciones pr
                          JOIN recetas r ON r.id_receta = pr.id_receta JOIN productos p ON p.id_producto = r.id_producto
                          WHERE pr.id_produccion = %s FOR UPDATE""", (id_produccion,))
        prod = cursor.fetchone()
        if not prod:
            raise ErrorValidacion('La producción no existe', 404)
        if float(prod['existencia']) < float(prod['cantidad_producida']):
            raise ErrorValidacion(f"No se puede anular: de {prod['nombre']} ya se vendió parte de ese lote")
        cursor.execute("UPDATE productos SET existencia = existencia - %s WHERE id_producto = %s",
                       (prod['cantidad_producida'], prod['id_producto']))
        cursor.execute("SELECT id_insumo, cantidad FROM receta_insumos WHERE id_receta = %s", (prod['id_receta'],))
        for i in cursor.fetchall():
            cursor.execute("UPDATE insumos SET existencia = existencia + %s WHERE id_insumo = %s",
                           (float(i['cantidad']) * float(prod['num_lotes']), i['id_insumo']))
        cursor.execute("DELETE FROM producciones WHERE id_produccion = %s", (id_produccion,))
        mysql.connection.commit()
        return jsonify({'exito': True, 'mensaje': f"Producción anulada: se regresaron los insumos y se restaron {float(prod['cantidad_producida']):g} de {prod['nombre']}"}), 200
    except Exception as e:
        return respuesta_error(e, 'No se pudo anular la producción')
    finally:
        cursor.close()


@admin_extra_bp.route('/api/admin/mermas/<int:id_merma>', methods=['DELETE'])
@admin_requerido
def anular_merma(id_merma):
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT * FROM mermas WHERE id_merma = %s FOR UPDATE", (id_merma,))
        m = cursor.fetchone()
        if not m:
            raise ErrorValidacion('La merma no existe', 404)
        if m['id_insumo']:
            cursor.execute("UPDATE insumos SET existencia = existencia + %s WHERE id_insumo = %s", (m['cantidad'], m['id_insumo']))
        else:
            cursor.execute("UPDATE productos SET existencia = existencia + %s WHERE id_producto = %s", (m['cantidad'], m['id_producto']))
        cursor.execute("DELETE FROM mermas WHERE id_merma = %s", (id_merma,))
        mysql.connection.commit()
        return jsonify({'exito': True, 'mensaje': 'Merma anulada: la existencia se regresó'}), 200
    except Exception as e:
        return respuesta_error(e, 'No se pudo anular la merma')
    finally:
        cursor.close()
