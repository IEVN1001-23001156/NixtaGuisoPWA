import calendar
from datetime import date, datetime, timedelta

from flask import Blueprint, request, jsonify

from database import mysql
from utils.seguridad import admin_requerido
from utils.validaciones import ErrorValidacion, texto, numero

admin_dashboard_bp = Blueprint('admin_dashboard', __name__)

# Una "venta" es un pedido no cancelado
NO_CANCELADO = "p.estado <> 'cancelado'"

CATEGORIAS_GASTO = ('infraestructura', 'empaque', 'publicidad_b2c', 'muestras_b2b',
                    'lead_ads_b2b', 'referidos_cupones', 'bono_primer_pedido')
CATEGORIAS_PUBLICIDAD = ('publicidad_b2c', 'lead_ads_b2b')


def leer_fecha(texto_fecha, por_defecto):
    if not texto_fecha:
        return por_defecto
    try:
        return datetime.strptime(texto_fecha, '%Y-%m-%d').date()
    except ValueError:
        raise ErrorValidacion('La fecha debe tener el formato AAAA-MM-DD')


def leer_mes(texto_mes):
    """Regresa (primer día, último día) del mes AAAA-MM; por defecto, el actual."""
    try:
        anio, mes = (int(x) for x in (texto_mes or date.today().strftime('%Y-%m')).split('-'))
        inicio = date(anio, mes, 1)
    except ValueError:
        raise ErrorValidacion('El mes debe tener el formato AAAA-MM')
    fin = date(anio, mes, calendar.monthrange(anio, mes)[1])
    return inicio, fin


def dividir(a, b, porcentaje=False):
    """División segura: si no hay datos, regresa None en lugar de un error."""
    if not b:
        return None
    resultado = a / b * (100 if porcentaje else 1)
    return round(resultado, 2)


# =====================================================================
#  PANEL OPERATIVO
#  /api/admin/dashboard?fecha=2026-11-17   (por defecto, hoy)
# =====================================================================

@admin_dashboard_bp.route('/api/admin/dashboard', methods=['GET'])
@admin_requerido
def dashboard():
    cursor = None

    try:
        fecha = leer_fecha(request.args.get('fecha'), date.today())
        cursor = mysql.connection.cursor()

        # ---------- TARJETAS DEL DIA ----------
        cursor.execute(f"""
            SELECT COUNT(*) AS pedidos, COALESCE(SUM(p.total), 0) AS ventas
            FROM pedidos p
            WHERE DATE(p.fecha_pedido) = %s AND {NO_CANCELADO}
        """, (fecha,))
        dia = cursor.fetchone()

        cursor.execute(f"""
            SELECT COALESCE(SUM(d.cantidad * pr.kg_por_unidad), 0) AS kg
            FROM pedidos p
            JOIN detalle_pedido d ON d.id_pedido = p.id_pedido
            JOIN productos pr ON pr.id_producto = d.id_producto
            WHERE DATE(p.fecha_pedido) = %s AND {NO_CANCELADO}
        """, (fecha,))
        kg_dia = float(cursor.fetchone()['kg'])

        cursor.execute("""
            SELECT COUNT(*) AS activos FROM pedidos
            WHERE estado IN ('pendiente', 'preparando', 'en_ruta')
        """)
        pedidos_activos = cursor.fetchone()['activos']

        cursor.execute("""
            SELECT c.tipo, COUNT(*) AS total
            FROM clientes c JOIN usuarios u ON u.id_usuario = c.id_usuario
            WHERE u.activo = TRUE AND DATE(u.fecha_registro) <= %s
            GROUP BY c.tipo
        """, (fecha,))
        registrados = {'B2C': 0, 'B2B': 0}
        for fila in cursor.fetchall():
            registrados[fila['tipo']] = fila['total']

        # ---------- GRAFICA: ULTIMOS 7 DIAS, B2B vs B2C ----------
        inicio_grafica = fecha - timedelta(days=6)
        cursor.execute(f"""
            SELECT DATE(p.fecha_pedido) AS dia, p.tipo_cliente, SUM(p.total) AS ventas
            FROM pedidos p
            WHERE DATE(p.fecha_pedido) BETWEEN %s AND %s AND {NO_CANCELADO}
            GROUP BY DATE(p.fecha_pedido), p.tipo_cliente
        """, (inicio_grafica, fecha))
        ventas_dia = {(f['dia'], f['tipo_cliente']): float(f['ventas']) for f in cursor.fetchall()}

        dias = [inicio_grafica + timedelta(days=i) for i in range(7)]
        grafica = {
            'etiquetas': [d.strftime('%d/%m') for d in dias],
            'b2c': [ventas_dia.get((d, 'B2C'), 0.0) for d in dias],
            'b2b': [ventas_dia.get((d, 'B2B'), 0.0) for d in dias]
        }
        total_b2c, total_b2b = sum(grafica['b2c']), sum(grafica['b2b'])
        grafica['participacion_b2b'] = dividir(total_b2b, total_b2b + total_b2c, porcentaje=True)

        # ---------- PRODUCTOS MAS VENDIDOS (30 DIAS) ----------
        cursor.execute(f"""
            SELECT pr.nombre, pr.presentacion,
                   SUM(d.cantidad) AS cantidad, SUM(d.subtotal) AS importe
            FROM pedidos p
            JOIN detalle_pedido d ON d.id_pedido = p.id_pedido
            JOIN productos pr ON pr.id_producto = d.id_producto
            WHERE DATE(p.fecha_pedido) BETWEEN %s AND %s AND {NO_CANCELADO}
            GROUP BY pr.id_producto, pr.nombre, pr.presentacion
            ORDER BY importe DESC
            LIMIT 5
        """, (fecha - timedelta(days=29), fecha))
        mas_vendidos = [{
            'nombre': f['nombre'],
            'presentacion': f['presentacion'],
            'cantidad': float(f['cantidad']),
            'importe': float(f['importe'])
        } for f in cursor.fetchall()]

        # ---------- ALERTAS ----------
        alertas = []

        cursor.execute("""
            SELECT nombre, unidad, existencia, stock_minimo FROM insumos
            WHERE activo = TRUE AND existencia < stock_minimo ORDER BY nombre
        """)
        for i in cursor.fetchall():
            alertas.append({
                'tipo': 'insumo',
                'mensaje': f"Stock bajo: {i['nombre']} ({float(i['existencia']):g} de "
                           f"{float(i['stock_minimo']):g} {i['unidad']} mínimo)"
            })

        cursor.execute("""
            SELECT nombre FROM productos
            WHERE activo = TRUE AND es_paquete = FALSE AND disponible = TRUE AND existencia <= 0
            ORDER BY nombre
        """)
        for p in cursor.fetchall():
            alertas.append({'tipo': 'producto', 'mensaje': f"Sin existencia: {p['nombre']}"})

        cursor.execute("""
            SELECT COUNT(*) AS total FROM pedidos
            WHERE metodo_pago = 'transferencia' AND estado_pago = 'por_validar'
              AND estado <> 'cancelado'
        """)
        por_validar = cursor.fetchone()['total']
        if por_validar:
            alertas.append({'tipo': 'pago', 'mensaje': f"Transferencias por validar: {por_validar}"})

        return jsonify({
            'exito': True,
            'fecha': fecha.isoformat(),
            'tarjetas': {
                'ventas_dia': float(dia['ventas']),
                'pedidos_dia': dia['pedidos'],
                'ticket_promedio_dia': dividir(float(dia['ventas']), dia['pedidos']),
                'kg_vendidos_dia': round(kg_dia, 2),
                'pedidos_activos': pedidos_activos,
                'usuarios_registrados': registrados['B2C'] + registrados['B2B'],
                'clientes_b2c': registrados['B2C'],
                'clientes_b2b': registrados['B2B']
            },
            'grafica': grafica,
            'mas_vendidos': mas_vendidos,
            'alertas': alertas
        }), 200

    except ErrorValidacion as e:
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo

    except Exception as e:
        print("ERROR EN DASHBOARD:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudo obtener el panel'}), 500

    finally:
        if cursor:
            cursor.close()


# =====================================================================
#  REPORTES: MÉTRICAS DE LA SECCIÓN 11 CONTRA SU META
#  /api/admin/reportes?mes=2027-04   (por defecto, el mes actual)
# =====================================================================

def meta_para(cursor, indicador, fin_mes):
    """La meta permanente, o la más próxima posterior al cierre del mes."""
    cursor.execute("""
        SELECT valor_meta, fecha_meta FROM metas
        WHERE indicador = %s
        ORDER BY (fecha_meta IS NULL) DESC,
                 (fecha_meta < %s), fecha_meta
        LIMIT 1
    """, (indicador, fin_mes))
    meta = cursor.fetchone()
    if not meta:
        return None, None
    return float(meta['valor_meta']), (meta['fecha_meta'].isoformat() if meta['fecha_meta'] else None)


def metrica(cursor, fin_mes, indicador, nombre, valor, unidad, menor_es_mejor=False):
    meta, fecha_meta = meta_para(cursor, indicador, fin_mes)
    if valor is None or meta is None:
        cumple = None
    else:
        cumple = valor <= meta if menor_es_mejor else valor >= meta
    return {
        'indicador': indicador,
        'nombre': nombre,
        'valor': valor,
        'meta': meta,
        'fecha_meta': fecha_meta,
        'unidad': unidad,
        'cumple': cumple
    }


@admin_dashboard_bp.route('/api/admin/reportes', methods=['GET'])
@admin_requerido
def reportes():
    cursor = None

    try:
        inicio, fin = leer_mes(request.args.get('mes'))
        rango = (inicio, fin)
        cursor = mysql.connection.cursor()

        # ---------- VENTAS Y VOLUMEN ----------
        cursor.execute(f"""
            SELECT COALESCE(SUM(d.cantidad * pr.kg_por_unidad), 0) AS kg
            FROM pedidos p
            JOIN detalle_pedido d ON d.id_pedido = p.id_pedido
            JOIN productos pr ON pr.id_producto = d.id_producto
            WHERE DATE(p.fecha_pedido) BETWEEN %s AND %s AND {NO_CANCELADO}
        """, rango)
        kg_mes = round(float(cursor.fetchone()['kg']), 2)

        cursor.execute(f"""
            SELECT p.tipo_cliente, COUNT(*) AS pedidos, SUM(p.total) AS ventas
            FROM pedidos p
            WHERE DATE(p.fecha_pedido) BETWEEN %s AND %s AND {NO_CANCELADO}
            GROUP BY p.tipo_cliente
        """, rango)
        por_tipo = {f['tipo_cliente']: f for f in cursor.fetchall()}

        def ventas_de(tipo):
            return float(por_tipo[tipo]['ventas']) if tipo in por_tipo else 0.0

        def pedidos_de(tipo):
            return por_tipo[tipo]['pedidos'] if tipo in por_tipo else 0

        ventas_mes = ventas_de('B2C') + ventas_de('B2B')

        # ---------- ADOPCION DIGITAL ----------
        cursor.execute("""
            SELECT COUNT(*) AS total,
                   SUM(DATE(u.fecha_registro) BETWEEN %s AND %s) AS nuevos
            FROM clientes c JOIN usuarios u ON u.id_usuario = c.id_usuario
            WHERE DATE(u.fecha_registro) <= %s
        """, (inicio, fin, fin))
        fila = cursor.fetchone()
        usuarios = fila['total']
        nuevos = int(fila['nuevos'] or 0)

        cursor.execute(f"""
            SELECT COUNT(DISTINCT p.id_cliente) AS con_pedido
            FROM pedidos p
            JOIN clientes c ON c.id_cliente = p.id_cliente
            JOIN usuarios u ON u.id_usuario = c.id_usuario
            WHERE {NO_CANCELADO} AND DATE(p.fecha_pedido) <= %s AND DATE(u.fecha_registro) <= %s
        """, (fin, fin))
        con_pedido = cursor.fetchone()['con_pedido']

        cursor.execute("""
            SELECT COUNT(*) AS negocios,
                   SUM(EXISTS (SELECT 1 FROM programaciones pg
                               WHERE pg.id_cliente = c.id_cliente AND pg.estado = 'activa')) AS automatizados
            FROM clientes c JOIN usuarios u ON u.id_usuario = c.id_usuario
            WHERE c.tipo = 'B2B' AND u.activo = TRUE
        """)
        fila = cursor.fetchone()
        automatizacion = dividir(int(fila['automatizados'] or 0), fila['negocios'], porcentaje=True)

        cursor.execute(f"""
            SELECT COUNT(*) AS total
            FROM pedidos p JOIN cupones cu ON cu.id_cupon = p.id_cupon
            WHERE cu.origen = 'qr' AND DATE(p.fecha_pedido) BETWEEN %s AND %s AND {NO_CANCELADO}
        """, rango)
        escaneos_qr = cursor.fetchone()['total']

        # ---------- CLIENTES Y RETENCION ----------
        # Negocios con pedidos recurrentes: 2 o más pedidos en el mes
        cursor.execute(f"""
            SELECT COUNT(*) AS total FROM (
                SELECT p.id_cliente FROM pedidos p
                WHERE p.tipo_cliente = 'B2B' AND DATE(p.fecha_pedido) BETWEEN %s AND %s AND {NO_CANCELADO}
                GROUP BY p.id_cliente HAVING COUNT(*) >= 2
            ) recurrentes
        """, rango)
        negocios_recurrentes = cursor.fetchone()['total']

        # Recompra: de los clientes que compraron en el mes, cuántos volvieron
        # a comprar dentro de los 15 días siguientes a alguno de sus pedidos
        cursor.execute(f"""
            SELECT COUNT(DISTINCT p.id_cliente) AS compradores,
                   COUNT(DISTINCT CASE WHEN EXISTS (
                       SELECT 1 FROM pedidos p2
                       WHERE p2.id_cliente = p.id_cliente AND p2.estado <> 'cancelado'
                         AND p2.fecha_pedido > p.fecha_pedido
                         AND p2.fecha_pedido <= p.fecha_pedido + INTERVAL 15 DAY
                   ) THEN p.id_cliente END) AS recompraron
            FROM pedidos p
            WHERE DATE(p.fecha_pedido) BETWEEN %s AND %s AND {NO_CANCELADO}
        """, rango)
        fila = cursor.fetchone()
        recompra = dividir(fila['recompraron'], fila['compradores'], porcentaje=True)

        # Referidos concretados: invitados cuyo primer pedido entregado fue en el mes
        cursor.execute("""
            SELECT COUNT(*) AS total FROM (
                SELECT c.id_cliente, MIN(p.fecha_pedido) AS primero
                FROM clientes c JOIN pedidos p ON p.id_cliente = c.id_cliente
                WHERE c.id_referido_por IS NOT NULL AND p.estado = 'entregado'
                GROUP BY c.id_cliente
            ) primeros
            WHERE DATE(primero) BETWEEN %s AND %s
        """, rango)
        referidos = cursor.fetchone()['total']

        # ---------- MARKETING Y SATISFACCION ----------
        cursor.execute("""
            SELECT COALESCE(SUM(monto), 0) AS total,
                   COALESCE(SUM(CASE WHEN categoria IN %s THEN monto END), 0) AS publicidad
            FROM gastos_mercadeo WHERE fecha BETWEEN %s AND %s
        """, (CATEGORIAS_PUBLICIDAD, inicio, fin))
        gastos = cursor.fetchone()
        gasto_total = float(gastos['total'])
        gasto_publicidad = float(gastos['publicidad'])

        cursor.execute("""
            SELECT ROUND(AVG(estrellas), 2) AS csat, COUNT(*) AS total
            FROM calificaciones WHERE DATE(fecha) BETWEEN %s AND %s
        """, rango)
        fila = cursor.fetchone()
        csat = float(fila['csat']) if fila['csat'] is not None else None

        # ---------- ARMAR LAS METRICAS ----------
        m = lambda *args, **kw: metrica(cursor, fin, *args, **kw)

        grupos = [
            {'grupo': 'Ventas y volumen', 'metricas': [
                m('kg_mensuales', 'Kilogramos vendidos en el mes', kg_mes, 'kg'),
                m('ticket_b2c', 'Ticket promedio B2C', dividir(ventas_de('B2C'), pedidos_de('B2C')), 'MXN'),
                m('ticket_b2b', 'Ticket promedio B2B por entrega', dividir(ventas_de('B2B'), pedidos_de('B2B')), 'MXN'),
            ]},
            {'grupo': 'Adopción digital', 'metricas': [
                m('usuarios_registrados', 'Usuarios registrados', usuarios, 'usuarios'),
                m('conversion', 'Conversión a primer pedido', dividir(con_pedido, usuarios, porcentaje=True), '%'),
                m('automatizacion_b2b', 'Negocios con pedido programado', automatizacion, '%'),
                m('escaneos_qr', 'Reórdenes desde el QR', escaneos_qr, 'pedidos'),
            ]},
            {'grupo': 'Clientes y retención', 'metricas': [
                m('negocios_b2b', 'Negocios con pedidos recurrentes', negocios_recurrentes, 'negocios'),
                m('recompra', 'Recompra dentro de 15 días', recompra, '%'),
                m('referidos', 'Referidos concretados', referidos, 'clientes'),
            ]},
            {'grupo': 'Marketing y satisfacción', 'metricas': [
                m('roas', 'ROAS (ventas / gasto publicitario)', dividir(ventas_mes, gasto_publicidad), 'veces'),
                m('costo_registro', 'Costo publicitario por registro', dividir(gasto_publicidad, nuevos), 'MXN',
                  menor_es_mejor=True),
                m('csat', 'Calificación promedio (CSAT)', csat, 'estrellas'),
            ]}
        ]

        evaluadas = [x for g in grupos for x in g['metricas'] if x['cumple'] is not None]

        return jsonify({
            'exito': True,
            'mes': inicio.strftime('%Y-%m'),
            'resumen': {
                'ventas_mes': round(ventas_mes, 2),
                'ventas_b2c': round(ventas_de('B2C'), 2),
                'ventas_b2b': round(ventas_de('B2B'), 2),
                'pedidos_mes': pedidos_de('B2C') + pedidos_de('B2B'),
                'nuevos_registros': nuevos,
                'gasto_mercadeo': gasto_total,
                'metas_cumplidas': sum(1 for x in evaluadas if x['cumple']),
                'metas_evaluadas': len(evaluadas)
            },
            'grupos': grupos
        }), 200

    except ErrorValidacion as e:
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo

    except Exception as e:
        print("ERROR EN REPORTES:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudieron calcular los reportes'}), 500

    finally:
        if cursor:
            cursor.close()


# =====================================================================
#  GASTOS DE MERCADEO
# =====================================================================

@admin_dashboard_bp.route('/api/admin/gastos-mercadeo', methods=['GET'])
@admin_requerido
def listar_gastos():
    cursor = None

    try:
        inicio, fin = leer_mes(request.args.get('mes'))
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT * FROM gastos_mercadeo WHERE fecha BETWEEN %s AND %s
            ORDER BY fecha DESC, id_gasto DESC
        """, (inicio, fin))

        gastos = [{
            'id_gasto': g['id_gasto'],
            'categoria': g['categoria'],
            'concepto': g['concepto'],
            'monto': float(g['monto']),
            'fecha': g['fecha'].isoformat()
        } for g in cursor.fetchall()]

        return jsonify({
            'exito': True,
            'mes': inicio.strftime('%Y-%m'),
            'total': round(sum(g['monto'] for g in gastos), 2),
            'gastos': gastos
        }), 200

    except ErrorValidacion as e:
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo

    except Exception as e:
        print("ERROR AL LISTAR GASTOS:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudieron obtener los gastos'}), 500

    finally:
        if cursor:
            cursor.close()


@admin_dashboard_bp.route('/api/admin/gastos-mercadeo', methods=['POST'])
@admin_requerido
def registrar_gasto():
    cursor = None

    try:
        datos = request.get_json(silent=True) or {}
        categoria = datos.get('categoria')
        concepto = texto(datos, 'concepto', 'Concepto', minimo=3, maximo=150)
        monto = numero(datos, 'monto', 'Monto', permitir_cero=False)
        fecha = leer_fecha(datos.get('fecha'), date.today())

        if categoria not in CATEGORIAS_GASTO:
            raise ErrorValidacion('La categoría debe ser una de: ' + ', '.join(CATEGORIAS_GASTO))

        cursor = mysql.connection.cursor()
        cursor.execute("""
            INSERT INTO gastos_mercadeo (categoria, concepto, monto, fecha)
            VALUES (%s, %s, %s, %s)
        """, (categoria, concepto, monto, fecha))
        id_gasto = cursor.lastrowid
        mysql.connection.commit()

        return jsonify({'exito': True, 'mensaje': 'Gasto registrado', 'id_gasto': id_gasto}), 201

    except ErrorValidacion as e:
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo

    except Exception as e:
        print("ERROR AL REGISTRAR GASTO:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo registrar el gasto'}), 500

    finally:
        if cursor:
            cursor.close()


@admin_dashboard_bp.route('/api/admin/gastos-mercadeo/<int:id_gasto>', methods=['DELETE'])
@admin_requerido
def eliminar_gasto(id_gasto):
    cursor = None

    try:
        cursor = mysql.connection.cursor()
        cursor.execute("DELETE FROM gastos_mercadeo WHERE id_gasto = %s", (id_gasto,))

        if cursor.rowcount == 0:
            return jsonify({'exito': False, 'mensaje': 'El gasto no existe'}), 404

        mysql.connection.commit()
        return jsonify({'exito': True, 'mensaje': 'Gasto eliminado'}), 200

    except Exception as e:
        print("ERROR AL ELIMINAR GASTO:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo eliminar el gasto'}), 500

    finally:
        if cursor:
            cursor.close()


# =====================================================================
#  METAS
# =====================================================================

@admin_dashboard_bp.route('/api/admin/metas', methods=['GET'])
@admin_requerido
def listar_metas():
    cursor = None

    try:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM metas ORDER BY indicador, fecha_meta")

        metas = [{
            'id_meta': x['id_meta'],
            'indicador': x['indicador'],
            'descripcion': x['descripcion'],
            'valor_meta': float(x['valor_meta']),
            'fecha_meta': x['fecha_meta'].isoformat() if x['fecha_meta'] else None
        } for x in cursor.fetchall()]

        return jsonify({'exito': True, 'metas': metas}), 200

    except Exception as e:
        print("ERROR AL LISTAR METAS:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudieron obtener las metas'}), 500

    finally:
        if cursor:
            cursor.close()


@admin_dashboard_bp.route('/api/admin/metas/<int:id_meta>', methods=['PUT'])
@admin_requerido
def editar_meta(id_meta):
    cursor = None

    try:
        valor = numero(request.get_json(silent=True) or {}, 'valor_meta', 'Valor de la meta',
                       permitir_cero=False)

        cursor = mysql.connection.cursor()
        cursor.execute("UPDATE metas SET valor_meta = %s WHERE id_meta = %s", (valor, id_meta))

        cursor.execute("SELECT 1 FROM metas WHERE id_meta = %s", (id_meta,))
        if not cursor.fetchone():
            return jsonify({'exito': False, 'mensaje': 'La meta no existe'}), 404

        mysql.connection.commit()
        return jsonify({'exito': True, 'mensaje': 'Meta actualizada'}), 200

    except ErrorValidacion as e:
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo

    except Exception as e:
        print("ERROR AL EDITAR META:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo actualizar la meta'}), 500

    finally:
        if cursor:
            cursor.close()
