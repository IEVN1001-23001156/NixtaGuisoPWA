from utils.validaciones import ErrorValidacion


# =====================================================================
#  PRODUCCION POR LOTES (hoja de proporciones)
#  Un lote descuenta los insumos de su receta y suma el producto terminado.
# =====================================================================

def registrar_produccion(cursor, id_receta, num_lotes, notas=None):
    """
    Registra num_lotes de una receta. Si falta algún insumo, lanza
    ErrorValidacion y no modifica nada (quien llama hace rollback).
    """
    cursor.execute("""
        SELECT r.*, p.nombre AS producto, p.presentacion
        FROM recetas r
        JOIN productos p ON p.id_producto = r.id_producto
        WHERE r.id_receta = %s AND p.activo = TRUE
    """, (id_receta,))
    receta = cursor.fetchone()

    if not receta:
        raise ErrorValidacion('La receta no existe', 404)

    # Insumos de la receta, apartados (FOR UPDATE) mientras se registra
    cursor.execute("""
        SELECT i.id_insumo, i.nombre, i.unidad, i.existencia, ri.cantidad
        FROM receta_insumos ri
        JOIN insumos i ON i.id_insumo = ri.id_insumo
        WHERE ri.id_receta = %s
        FOR UPDATE
    """, (id_receta,))
    insumos = cursor.fetchall()

    # 1. REVISAR QUE ALCANCEN
    faltantes = []
    for insumo in insumos:
        necesario = round(float(insumo['cantidad']) * num_lotes, 3)
        if float(insumo['existencia']) < necesario:
            faltantes.append(
                f"{insumo['nombre']} (se necesitan {necesario:g} {insumo['unidad']}, "
                f"hay {float(insumo['existencia']):g})"
            )

    if faltantes:
        raise ErrorValidacion('No alcanzan los insumos: ' + '; '.join(faltantes), 409)

    # 2. DESCONTAR INSUMOS
    consumidos = []
    for insumo in insumos:
        necesario = round(float(insumo['cantidad']) * num_lotes, 3)
        cursor.execute(
            "UPDATE insumos SET existencia = existencia - %s WHERE id_insumo = %s",
            (necesario, insumo['id_insumo'])
        )
        consumidos.append({
            'insumo': insumo['nombre'],
            'cantidad': necesario,
            'unidad': insumo['unidad']
        })

    # 3. SUMAR PRODUCTO TERMINADO
    producido = round(float(receta['rendimiento']) * num_lotes, 3)
    cursor.execute(
        "UPDATE productos SET existencia = existencia + %s WHERE id_producto = %s",
        (producido, receta['id_producto'])
    )

    # 4. GUARDAR EL REGISTRO
    cursor.execute("""
        INSERT INTO producciones (id_receta, num_lotes, cantidad_producida, notas)
        VALUES (%s, %s, %s, %s)
    """, (id_receta, num_lotes, producido, notas))

    return {
        'id_produccion': cursor.lastrowid,
        'producto': receta['producto'],
        'presentacion': receta['presentacion'],
        'num_lotes': num_lotes,
        'cantidad_producida': producido,
        'insumos_consumidos': consumidos
    }
