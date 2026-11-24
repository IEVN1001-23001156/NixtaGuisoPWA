from datetime import date

from flask import Blueprint, request, jsonify

from database import mysql
from utils.seguridad import admin_requerido
from utils.validaciones import ErrorValidacion, texto, numero, booleano
from utils.inventario import registrar_produccion

admin_inventario_bp = Blueprint('admin_inventario', __name__)

UNIDADES = ('kg', 'L', 'pieza')


def estado_insumo(existencia, minimo):
    return 'por_surtir' if existencia < minimo else 'optimo'


# =====================================================================
#  INSUMOS (Stock actual)
#  /api/admin/insumos?estado=por_surtir
# =====================================================================

@admin_inventario_bp.route('/api/admin/insumos', methods=['GET'])
@admin_requerido
def listar_insumos():
    cursor = None

    try:
        filtro = request.args.get('estado', '')

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM insumos WHERE activo = TRUE ORDER BY nombre")

        insumos = []
        for i in cursor.fetchall():
            existencia = float(i['existencia'])
            minimo = float(i['stock_minimo'])
            costo = float(i['costo_unitario']) if i['costo_unitario'] is not None else None
            estado = estado_insumo(existencia, minimo)

            if filtro in ('por_surtir', 'optimo') and estado != filtro:
                continue

            insumos.append({
                'id_insumo': i['id_insumo'],
                'nombre': i['nombre'],
                'unidad': i['unidad'],
                'existencia': existencia,
                'stock_minimo': minimo,
                'costo_unitario': costo,
                'valor_inventario': round(existencia * costo, 2) if costo is not None else None,
                'estado': estado
            })

        return jsonify({
            'exito': True,
            'por_surtir': sum(1 for i in insumos if i['estado'] == 'por_surtir'),
            'insumos': insumos
        }), 200

    except Exception as e:
        print("ERROR AL LISTAR INSUMOS:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudieron obtener los insumos'}), 500

    finally:
        if cursor:
            cursor.close()


@admin_inventario_bp.route('/api/admin/insumos', methods=['POST'])
@admin_requerido
def crear_insumo():
    cursor = None

    try:
        datos = request.get_json(silent=True) or {}
        nombre = texto(datos, 'nombre', 'Nombre', minimo=3, maximo=100)
        unidad = datos.get('unidad')
        stock_minimo = numero(datos, 'stock_minimo', 'Stock mínimo')
        costo = numero(datos, 'costo_unitario', 'Costo unitario') if datos.get('costo_unitario') not in (None, '') else None

        if unidad not in UNIDADES:
            raise ErrorValidacion('La unidad debe ser kg, L o pieza')

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT 1 FROM insumos WHERE nombre = %s", (nombre,))
        if cursor.fetchone():
            raise ErrorValidacion('Ya existe un insumo con ese nombre', 409)

        cursor.execute("""
            INSERT INTO insumos (nombre, unidad, stock_minimo, costo_unitario)
            VALUES (%s, %s, %s, %s)
        """, (nombre, unidad, stock_minimo, costo))
        id_insumo = cursor.lastrowid
        mysql.connection.commit()

        return jsonify({
            'exito': True,
            'mensaje': 'Insumo creado. Registra una compra para darle existencia.',
            'id_insumo': id_insumo
        }), 201

    except ErrorValidacion as e:
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo

    except Exception as e:
        print("ERROR AL CREAR INSUMO:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo crear el insumo'}), 500

    finally:
        if cursor:
            cursor.close()


# La unidad y la existencia no se editan aquí: la unidad la usan las recetas
# y la existencia solo cambia con compras, producción, ventas y mermas.
@admin_inventario_bp.route('/api/admin/insumos/<int:id_insumo>', methods=['PUT'])
@admin_requerido
def editar_insumo(id_insumo):
    cursor = None

    try:
        datos = request.get_json(silent=True) or {}
        nombre = texto(datos, 'nombre', 'Nombre', minimo=3, maximo=100)
        stock_minimo = numero(datos, 'stock_minimo', 'Stock mínimo')
        costo = numero(datos, 'costo_unitario', 'Costo unitario') if datos.get('costo_unitario') not in (None, '') else None
        activo = booleano(datos, 'activo', True)

        cursor = mysql.connection.cursor()

        cursor.execute("SELECT 1 FROM insumos WHERE id_insumo = %s", (id_insumo,))
        if not cursor.fetchone():
            return jsonify({'exito': False, 'mensaje': 'El insumo no existe'}), 404

        cursor.execute(
            "SELECT 1 FROM insumos WHERE nombre = %s AND id_insumo <> %s", (nombre, id_insumo)
        )
        if cursor.fetchone():
            raise ErrorValidacion('Ya existe un insumo con ese nombre', 409)

        if not activo:
            cursor.execute("SELECT COUNT(*) AS total FROM receta_insumos WHERE id_insumo = %s", (id_insumo,))
            if cursor.fetchone()['total'] > 0:
                raise ErrorValidacion('No se puede desactivar: lo usa una receta de producción', 409)

        cursor.execute("""
            UPDATE insumos SET nombre = %s, stock_minimo = %s, costo_unitario = %s, activo = %s
            WHERE id_insumo = %s
        """, (nombre, stock_minimo, costo, activo, id_insumo))
        mysql.connection.commit()

        return jsonify({'exito': True, 'mensaje': 'Insumo actualizado'}), 200

    except ErrorValidacion as e:
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo

    except Exception as e:
        print("ERROR AL EDITAR INSUMO:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo actualizar el insumo'}), 500

    finally:
        if cursor:
            cursor.close()


# =====================================================================
#  COMPRAS (entradas de insumos)
# =====================================================================

@admin_inventario_bp.route('/api/admin/compras', methods=['POST'])
@admin_requerido
def registrar_compra():
    cursor = None

    try:
        datos = request.get_json(silent=True) or {}
        cantidad = numero(datos, 'cantidad', 'Cantidad', permitir_cero=False)
        costo_total = numero(datos, 'costo_total', 'Costo total')
        proveedor = texto(datos, 'proveedor', 'Proveedor', maximo=120, obligatorio=False)

        try:
            id_insumo = int(datos.get('id_insumo'))
        except (TypeError, ValueError):
            raise ErrorValidacion('Selecciona el insumo')

        cursor = mysql.connection.cursor()
        cursor.execute(
            "SELECT nombre, unidad FROM insumos WHERE id_insumo = %s AND activo = TRUE FOR UPDATE",
            (id_insumo,)
        )
        insumo = cursor.fetchone()
        if not insumo:
            raise ErrorValidacion('El insumo no existe', 404)

        cursor.execute("""
            INSERT INTO compras_insumos (id_insumo, cantidad, costo_total, proveedor)
            VALUES (%s, %s, %s, %s)
        """, (id_insumo, cantidad, costo_total, proveedor))

        # Suma la existencia y guarda el costo de la última compra
        costo_unitario = round(costo_total / cantidad, 2)
        cursor.execute("""
            UPDATE insumos
            SET existencia = existencia + %s, costo_unitario = %s
            WHERE id_insumo = %s
        """, (cantidad, costo_unitario, id_insumo))

        mysql.connection.commit()

        return jsonify({
            'exito': True,
            'mensaje': f"Compra registrada: +{cantidad:g} {insumo['unidad']} de {insumo['nombre']}",
            'costo_unitario': costo_unitario
        }), 201

    except ErrorValidacion as e:
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo

    except Exception as e:
        print("ERROR AL REGISTRAR COMPRA:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo registrar la compra'}), 500

    finally:
        if cursor:
            cursor.close()


@admin_inventario_bp.route('/api/admin/compras', methods=['GET'])
@admin_requerido
def listar_compras():
    cursor = None

    try:
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT c.id_compra, c.fecha, i.nombre AS insumo, i.unidad,
                   c.cantidad, c.costo_total, c.proveedor
            FROM compras_insumos c
            JOIN insumos i ON i.id_insumo = c.id_insumo
            ORDER BY c.fecha DESC, c.id_compra DESC
            LIMIT 100
        """)

        compras = [{
            'id_compra': c['id_compra'],
            'fecha': c['fecha'].strftime('%Y-%m-%d %H:%M'),
            'insumo': c['insumo'],
            'unidad': c['unidad'],
            'cantidad': float(c['cantidad']),
            'costo_total': float(c['costo_total']),
            'proveedor': c['proveedor']
        } for c in cursor.fetchall()]

        return jsonify({'exito': True, 'compras': compras}), 200

    except Exception as e:
        print("ERROR AL LISTAR COMPRAS:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudieron obtener las compras'}), 500

    finally:
        if cursor:
            cursor.close()


# =====================================================================
#  RECETAS Y PRODUCCION
# =====================================================================

@admin_inventario_bp.route('/api/admin/recetas', methods=['GET'])
@admin_requerido
def listar_recetas():
    cursor = None

    try:
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT r.id_receta, r.nombre, r.rendimiento, r.costo_lote,
                   p.id_producto, p.nombre AS producto, p.presentacion, p.existencia
            FROM recetas r
            JOIN productos p ON p.id_producto = r.id_producto
            WHERE p.activo = TRUE
            ORDER BY r.id_receta
        """)
        recetas = cursor.fetchall()

        resultado = []
        for r in recetas:
            cursor.execute("""
                SELECT i.nombre, i.unidad, i.existencia, ri.cantidad
                FROM receta_insumos ri
                JOIN insumos i ON i.id_insumo = ri.id_insumo
                WHERE ri.id_receta = %s
            """, (r['id_receta'],))
            insumos = cursor.fetchall()

            # Cuántos lotes completos alcanza a producir el stock actual
            lotes_posibles = min(
                (int(float(i['existencia']) // float(i['cantidad'])) for i in insumos),
                default=0
            )

            resultado.append({
                'id_receta': r['id_receta'],
                'nombre': r['nombre'],
                'id_producto': r['id_producto'],
                'producto': r['producto'],
                'presentacion': r['presentacion'],
                'rendimiento': float(r['rendimiento']),
                'costo_lote': float(r['costo_lote']),
                'existencia_producto': float(r['existencia']),
                'lotes_posibles': lotes_posibles,
                'insumos': [{
                    'nombre': i['nombre'],
                    'unidad': i['unidad'],
                    'cantidad_por_lote': float(i['cantidad']),
                    'existencia': float(i['existencia'])
                } for i in insumos]
            })

        return jsonify({'exito': True, 'recetas': resultado}), 200

    except Exception as e:
        print("ERROR AL LISTAR RECETAS:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudieron obtener las recetas'}), 500

    finally:
        if cursor:
            cursor.close()


@admin_inventario_bp.route('/api/admin/recetas', methods=['POST'])
@admin_requerido
def crear_receta():
    cursor = None

    try:
        datos = request.get_json(silent=True) or {}
        nombre = texto(datos, 'nombre', 'Nombre de la receta', minimo=2, maximo=120)
        rendimiento = numero(datos, 'rendimiento', 'Rendimiento', permitir_cero=False)
        costo_lote = numero(datos, 'costo_lote', 'Costo por lote') if datos.get('costo_lote') not in (None, '') else 0.0
        insumos_receta = datos.get('insumos')

        try:
            id_producto = int(datos.get('id_producto'))
        except (TypeError, ValueError):
            raise ErrorValidacion('Selecciona un producto válido')

        if not isinstance(insumos_receta, list) or len(insumos_receta) == 0:
            raise ErrorValidacion('Agrega al menos un insumo a la receta')

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT 1 FROM productos WHERE id_producto = %s AND activo = TRUE", (id_producto,))
        if not cursor.fetchone():
            raise ErrorValidacion('El producto seleccionado no existe', 404)

        filas_insumos = []
        ids_vistos = set()
        for item in insumos_receta:
            if not isinstance(item, dict):
                raise ErrorValidacion('Formato de insumo inválido')
            try:
                id_insumo = int(item.get('id_insumo'))
                cantidad = float(item.get('cantidad'))
            except (TypeError, ValueError):
                raise ErrorValidacion('Verifica el insumo y la cantidad')

            if id_insumo <= 0 or cantidad <= 0:
                raise ErrorValidacion('Cada insumo debe tener cantidad mayor a cero')
            if id_insumo in ids_vistos:
                raise ErrorValidacion('No repitas el mismo insumo en la receta')
            ids_vistos.add(id_insumo)

            cursor.execute("SELECT 1 FROM insumos WHERE id_insumo = %s AND activo = TRUE", (id_insumo,))
            if not cursor.fetchone():
                raise ErrorValidacion('Uno de los insumos no existe o está inactivo', 404)

            filas_insumos.append((id_insumo, cantidad))

        cursor.execute("""
            INSERT INTO recetas (id_producto, nombre, rendimiento, costo_lote)
            VALUES (%s, %s, %s, %s)
        """, (id_producto, nombre, rendimiento, costo_lote))
        id_receta = cursor.lastrowid

        for id_insumo, cantidad in filas_insumos:
            cursor.execute("""
                INSERT INTO receta_insumos (id_receta, id_insumo, cantidad)
                VALUES (%s, %s, %s)
            """, (id_receta, id_insumo, cantidad))

        mysql.connection.commit()

        return jsonify({
            'exito': True,
            'mensaje': 'Receta creada correctamente',
            'id_receta': id_receta
        }), 201

    except ErrorValidacion as e:
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo

    except Exception as e:
        print("ERROR AL CREAR RECETA:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo crear la receta'}), 500

    finally:
        if cursor:
            cursor.close()


@admin_inventario_bp.route('/api/admin/producciones', methods=['POST'])
@admin_requerido
def crear_produccion():
    cursor = None

    try:
        datos = request.get_json(silent=True) or {}
        num_lotes = numero(datos, 'num_lotes', 'Número de lotes', permitir_cero=False)
        notas = texto(datos, 'notas', 'Notas', maximo=500, obligatorio=False)

        try:
            id_receta = int(datos.get('id_receta'))
        except (TypeError, ValueError):
            raise ErrorValidacion('Selecciona la receta')

        cursor = mysql.connection.cursor()
        resultado = registrar_produccion(cursor, id_receta, num_lotes, notas)
        mysql.connection.commit()

        return jsonify({
            'exito': True,
            'mensaje': f"Producción registrada: +{resultado['cantidad_producida']:g} "
                       f"({resultado['presentacion']}) de {resultado['producto']}",
            **resultado
        }), 201

    except ErrorValidacion as e:
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo

    except Exception as e:
        print("ERROR AL REGISTRAR PRODUCCION:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo registrar la producción'}), 500

    finally:
        if cursor:
            cursor.close()


@admin_inventario_bp.route('/api/admin/producciones', methods=['GET'])
@admin_requerido
def listar_producciones():
    cursor = None

    try:
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT pr.id_produccion, pr.fecha, pr.num_lotes, pr.cantidad_producida, pr.notas,
                   r.nombre AS receta, p.nombre AS producto, p.presentacion,
                   ROUND(pr.num_lotes * r.costo_lote, 2) AS costo
            FROM producciones pr
            JOIN recetas r ON r.id_receta = pr.id_receta
            JOIN productos p ON p.id_producto = r.id_producto
            ORDER BY pr.fecha DESC, pr.id_produccion DESC
            LIMIT 100
        """)

        producciones = [{
            'id_produccion': p['id_produccion'],
            'fecha': p['fecha'].strftime('%Y-%m-%d %H:%M'),
            'receta': p['receta'],
            'producto': p['producto'],
            'presentacion': p['presentacion'],
            'num_lotes': float(p['num_lotes']),
            'cantidad_producida': float(p['cantidad_producida']),
            'costo': float(p['costo']),
            'notas': p['notas']
        } for p in cursor.fetchall()]

        return jsonify({'exito': True, 'producciones': producciones}), 200

    except Exception as e:
        print("ERROR AL LISTAR PRODUCCIONES:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudo obtener la producción'}), 500

    finally:
        if cursor:
            cursor.close()


# =====================================================================
#  MERMAS (de un insumo O de un producto terminado)
# =====================================================================

@admin_inventario_bp.route('/api/admin/mermas', methods=['POST'])
@admin_requerido
def registrar_merma():
    cursor = None

    try:
        datos = request.get_json(silent=True) or {}
        cantidad = numero(datos, 'cantidad', 'Cantidad', permitir_cero=False)
        motivo = texto(datos, 'motivo', 'Motivo', minimo=3, maximo=255)
        id_insumo = datos.get('id_insumo')
        id_producto = datos.get('id_producto')

        if (id_insumo is None) == (id_producto is None):
            raise ErrorValidacion('Indica un insumo o un producto (solo uno)')

        cursor = mysql.connection.cursor()

        if id_insumo is not None:
            tabla, campo, valor = 'insumos', 'id_insumo', int(id_insumo)
            cursor.execute(
                "SELECT nombre, unidad, existencia FROM insumos WHERE id_insumo = %s FOR UPDATE",
                (valor,)
            )
        else:
            tabla, campo, valor = 'productos', 'id_producto', int(id_producto)
            cursor.execute("""
                SELECT nombre, presentacion AS unidad, existencia
                FROM productos WHERE id_producto = %s AND es_paquete = FALSE FOR UPDATE
            """, (valor,))

        registro = cursor.fetchone()
        if not registro:
            raise ErrorValidacion('El insumo o producto no existe', 404)

        if float(registro['existencia']) < cantidad:
            raise ErrorValidacion(
                f"La merma ({cantidad:g}) es mayor que la existencia de "
                f"{registro['nombre']} ({float(registro['existencia']):g})"
            )

        cursor.execute(
            f"UPDATE {tabla} SET existencia = existencia - %s WHERE {campo} = %s",
            (cantidad, valor)
        )
        cursor.execute(f"""
            INSERT INTO mermas ({campo}, cantidad, motivo) VALUES (%s, %s, %s)
        """, (valor, cantidad, motivo))

        mysql.connection.commit()

        return jsonify({
            'exito': True,
            'mensaje': f"Merma registrada: -{cantidad:g} de {registro['nombre']}"
        }), 201

    except (TypeError, ValueError):
        return jsonify({'exito': False, 'mensaje': 'El insumo o producto no es válido'}), 400

    except ErrorValidacion as e:
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': e.mensaje}), e.codigo

    except Exception as e:
        print("ERROR AL REGISTRAR MERMA:", str(e))
        mysql.connection.rollback()
        return jsonify({'exito': False, 'mensaje': 'No se pudo registrar la merma'}), 500

    finally:
        if cursor:
            cursor.close()


# /api/admin/mermas?mes=2026-11  (por defecto, el mes actual)
@admin_inventario_bp.route('/api/admin/mermas', methods=['GET'])
@admin_requerido
def listar_mermas():
    cursor = None

    try:
        mes = request.args.get('mes', date.today().strftime('%Y-%m'))
        try:
            anio, numero_mes = (int(x) for x in mes.split('-'))
            date(anio, numero_mes, 1)
        except ValueError:
            return jsonify({'exito': False, 'mensaje': 'El mes debe tener el formato AAAA-MM'}), 400

        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT m.id_merma, m.fecha, m.cantidad, m.motivo,
                   COALESCE(i.nombre, p.nombre) AS nombre,
                   COALESCE(i.unidad, p.presentacion) AS unidad,
                   CASE WHEN m.id_insumo IS NOT NULL THEN 'insumo' ELSE 'producto' END AS tipo,
                   ROUND(m.cantidad * COALESCE(i.costo_unitario, p.costo_unitario, 0), 2) AS costo_estimado
            FROM mermas m
            LEFT JOIN insumos i ON i.id_insumo = m.id_insumo
            LEFT JOIN productos p ON p.id_producto = m.id_producto
            WHERE YEAR(m.fecha) = %s AND MONTH(m.fecha) = %s
            ORDER BY m.fecha DESC, m.id_merma DESC
        """, (anio, numero_mes))

        mermas = [{
            'id_merma': m['id_merma'],
            'fecha': m['fecha'].strftime('%Y-%m-%d %H:%M'),
            'tipo': m['tipo'],
            'nombre': m['nombre'],
            'cantidad': float(m['cantidad']),
            'unidad': m['unidad'],
            'motivo': m['motivo'],
            'costo_estimado': float(m['costo_estimado'])
        } for m in cursor.fetchall()]

        return jsonify({
            'exito': True,
            'mes': f"{anio}-{numero_mes:02d}",
            'total_mermas': len(mermas),
            'costo_total_estimado': round(sum(m['costo_estimado'] for m in mermas), 2),
            'mermas': mermas
        }), 200

    except Exception as e:
        print("ERROR AL LISTAR MERMAS:", str(e))
        return jsonify({'exito': False, 'mensaje': 'No se pudieron obtener las mermas'}), 500

    finally:
        if cursor:
            cursor.close()