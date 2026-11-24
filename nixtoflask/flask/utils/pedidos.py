from datetime import date

from utils.precios import precio_para, nombre_tarifa


# =====================================================================
#  REGLAS DEL NEGOCIO PARA LOS PEDIDOS (documento, sección 7)
# =====================================================================

PEDIDO_MINIMO_B2C = 90.00          # pesos en productos
KG_MINIMO_TORTILLA_B2B = 5         # kg de tortilla por entrega
COSTO_ENVIO_B2C = 30.00
ENVIO_GRATIS_DESDE = 250.00
DESCUENTO_PRIMER_PEDIDO = 15       # por ciento, solo clientes Hogar
BONO_REFERIDO = 20.00              # saldo para quien invita y para el invitado


class ErrorPedido(Exception):
    """Error de reglas del negocio que se muestra al cliente."""
    def __init__(self, mensaje, codigo=400):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo


def leer_productos(datos):
    """Valida la lista de productos del carrito y junta los repetidos."""
    productos = datos.get('productos')

    if not isinstance(productos, list) or len(productos) == 0:
        raise ErrorPedido('El carrito está vacío')

    cantidades = {}
    for item in productos:
        if isinstance(item, dict) and item.get('arma'):
            arma = item.get('arma') or {}
            try:
                cantidad = float(item.get('cantidad'))
                ids = [(int(arma[k]), k) for k in ('tortilla', 'guisado', 'salsa', 'agua')]
            except (TypeError, ValueError, KeyError):
                raise ErrorPedido('Elige tortilla, guisado, salsa y agua para armar tu paquete')
            if cantidad <= 0 or cantidad != int(cantidad):
                raise ErrorPedido('La cantidad de paquetes debe ser un número entero')
            for id_componente, lugar in ids:
                clave = ('arma', id_componente, lugar)
                cantidades[clave] = cantidades.get(clave, 0) + cantidad
            continue

        try:
            id_producto = int(item.get('id_producto'))
            cantidad = float(item.get('cantidad'))
        except (TypeError, ValueError, AttributeError):
            raise ErrorPedido('Hay un producto con datos incorrectos en el carrito')

        if cantidad <= 0:
            raise ErrorPedido('Las cantidades deben ser mayores a cero')

        salsa, agua = item.get('salsa'), item.get('agua')
        if salsa or agua:
            try:
                clave = (id_producto, int(salsa) if salsa else None, int(agua) if agua else None)
            except (TypeError, ValueError):
                raise ErrorPedido('La salsa o el agua elegidas no son válidas')
        else:
            clave = id_producto

        cantidades[clave] = cantidades.get(clave, 0) + cantidad

    return cantidades


def componentes_paquete(cursor, id_paquete, salsa=None, agua=None):
    """
    Componentes del paquete "Comida Completa" con la salsa y el agua elegidas.
    Solo se aceptan opciones del mismo precio, para que el precio del paquete no cambie.
    Regresa ([(id_producto, cantidad), ...], texto de las opciones o None).
    """
    cursor.execute("""
        SELECT pc.id_producto, pc.cantidad, pr.id_categoria, pr.precio_b2c
        FROM paquete_componentes pc JOIN productos pr ON pr.id_producto = pc.id_producto
        WHERE pc.id_paquete = %s
    """, (id_paquete,))
    componentes = cursor.fetchall()
    elegidos, textos = [], []

    for comp in componentes:
        id_final = comp['id_producto']
        for elegido, categoria, nombre_opcion in ((salsa, 3, 'La salsa'), (agua, 5, 'El agua')):
            if elegido and comp['id_categoria'] == categoria:
                cursor.execute(
                    "SELECT nombre, id_categoria, precio_b2c, disponible FROM productos WHERE id_producto = %s AND activo = TRUE",
                    (elegido,)
                )
                opcion = cursor.fetchone()
                if not opcion or opcion['id_categoria'] != categoria or opcion['precio_b2c'] != comp['precio_b2c']:
                    raise ErrorPedido(f'{nombre_opcion} elegida no está disponible para el paquete')
                if not opcion['disponible']:
                    raise ErrorPedido(f"{opcion['nombre']} no está disponible por ahora")
                id_final = elegido
                textos.append(opcion['nombre'])
        elegidos.append((id_final, float(comp['cantidad'])))

    return elegidos, (' y '.join(textos) if textos else None)


def _consumo_insumos_por_productos(cursor, requeridos):
    """Calcula el total de insumos requeridos según las recetas de los productos."""
    consumo_insumos = {}
    for id_producto, cantidad in requeridos.items():
        cursor.execute("""
            SELECT ri.id_insumo, ri.cantidad, r.rendimiento
            FROM receta_insumos ri
            JOIN recetas r ON r.id_receta = ri.id_receta
            WHERE r.id_producto = %s
        """, (id_producto,))
        for fila in cursor.fetchall():
            rendimiento = float(fila['rendimiento'] or 1) or 1.0
            total_insumo = (float(fila['cantidad']) / rendimiento) * float(cantidad)
            id_insumo = int(fila['id_insumo'])
            consumo_insumos[id_insumo] = consumo_insumos.get(id_insumo, 0.0) + total_insumo
    return consumo_insumos


def calcular_pedido(cursor, id_cliente, tipo, nivel, cantidades,
                    modalidad='domicilio', codigo_cupon='', usar_saldo=False,
                    bloquear=False):
    """
    Calcula el pedido completo aplicando todas las reglas.
    bloquear=True se usa al confirmar el pedido: aparta las filas de
    productos e insumos (FOR UPDATE) para que dos pedidos al mismo tiempo
    no vendan la misma existencia.
    """
    if modalidad not in ('domicilio', 'recoger'):
        raise ErrorPedido('La modalidad de entrega no es válida')

    bloqueo = " FOR UPDATE" if bloquear else ""

    lineas = []
    requeridos = {}
    subtotal = 0.0
    kg_tortilla = 0.0

    for clave, cantidad in cantidades.items():
        armado = isinstance(clave, tuple) and clave[0] == 'arma'
        if armado:
            id_producto, lugar, salsa, agua = clave[1], clave[2], None, None
        else:
            id_producto, salsa, agua = clave if isinstance(clave, tuple) else (clave, None, None)
        opciones = None
        cursor.execute(
            "SELECT * FROM productos WHERE id_producto = %s AND activo = TRUE" + bloqueo,
            (id_producto,)
        )
        producto = cursor.fetchone()

        if not producto:
            raise ErrorPedido('Uno de los productos ya no existe en el catálogo')

        if not producto['disponible']:
            raise ErrorPedido(f"{producto['nombre']} no está disponible por ahora")

        es_kg = producto['presentacion'] == '1 kg'
        if not es_kg and cantidad != int(cantidad):
            raise ErrorPedido(f"La cantidad de {producto['nombre']} debe ser un número entero")
        if es_kg and (cantidad * 2) != int(cantidad * 2):
            raise ErrorPedido(f"{producto['nombre']} se vende por kilo o medio kilo")

        if armado:
            if tipo == 'B2B':
                raise ErrorPedido('Los paquetes son exclusivos para cuentas Hogar')
            categoria_lugar = {'tortilla': 1, 'guisado': 2, 'salsa': 3, 'agua': 5}[lugar]
            permitido = producto['id_categoria'] == categoria_lugar and (lugar != 'tortilla' or es_kg)
            if producto['es_paquete'] or not permitido:
                raise ErrorPedido(f"{producto['nombre']} no se puede incluir en el paquete")
            precio = round(float(producto['precio_b2c']) * 0.9, 2)
            requeridos[id_producto] = requeridos.get(id_producto, 0) + cantidad
            opciones = '|Arma tu Comida Completa'
        elif producto['es_paquete']:
            if tipo == 'B2B':
                raise ErrorPedido('Los paquetes son exclusivos para cuentas Hogar')
            precio = float(producto['precio_b2c'])

            componentes, texto_opciones = componentes_paquete(cursor, id_producto, salsa, agua)
            for id_componente, cantidad_componente in componentes:
                requeridos[id_componente] = requeridos.get(id_componente, 0) + cantidad_componente * cantidad
            if salsa or agua:
                opciones = f"{salsa or ''},{agua or ''}|{texto_opciones or ''}"
        else:
            precio = precio_para(producto, tipo, nivel)
            requeridos[id_producto] = requeridos.get(id_producto, 0) + cantidad
            if producto['id_categoria'] == 1 and es_kg:
                kg_tortilla += cantidad

        importe = round(precio * cantidad, 2)
        subtotal += importe

        lineas.append({
            'id_producto': id_producto,
            'nombre': producto['nombre'] + (f" ({opciones.split('|')[1]})" if opciones else ''),
            'presentacion': producto['presentacion'],
            'opciones': opciones,
            'salsa': salsa,
            'agua': agua,
            'cantidad': cantidad,
            'precio_unitario': precio,
            'subtotal': importe,
            'es_paquete': bool(producto['es_paquete'])
        })

    subtotal = round(subtotal, 2)

    faltantes = []
    for id_producto, requerido in requeridos.items():
        cursor.execute(
            "SELECT nombre, existencia, disponible FROM productos WHERE id_producto = %s" + bloqueo,
            (id_producto,)
        )
        base = cursor.fetchone()
        if (not base['disponible']) or float(base['existencia']) < requerido:
            faltantes.append({
                'id_producto': id_producto,
                'nombre': base['nombre'],
                'disponible': float(base['existencia']) if base['disponible'] else 0,
                'solicitado': requerido
            })

    consumo_insumos = _consumo_insumos_por_productos(cursor, requeridos)
    for id_insumo, requerido_insumo in consumo_insumos.items():
        cursor.execute(
            "SELECT nombre, unidad, existencia, activo FROM insumos WHERE id_insumo = %s" + bloqueo,
            (id_insumo,)
        )
        ins = cursor.fetchone()
        if ins and ((not ins['activo']) or float(ins['existencia']) < requerido_insumo):
            faltantes.append({
                'id_insumo': id_insumo,
                'nombre': f"{ins['nombre']} ({ins['unidad']})",
                'disponible': float(ins['existencia']) if ins['activo'] else 0,
                'solicitado': round(requerido_insumo, 3)
            })

    if tipo == 'B2B':
        cumple_minimo = kg_tortilla >= KG_MINIMO_TORTILLA_B2B
        mensaje_minimo = None if cumple_minimo else \
            f"El pedido mínimo para negocios es de {KG_MINIMO_TORTILLA_B2B} kg de tortilla"
    else:
        cumple_minimo = subtotal >= PEDIDO_MINIMO_B2C
        mensaje_minimo = None if cumple_minimo else \
            f"El pedido mínimo es de ${PEDIDO_MINIMO_B2C:.2f} en productos"

    descuento = 0.0
    motivo_descuento = None
    id_cupon = None
    codigo_cupon = (codigo_cupon or '').strip().upper()

    if tipo == 'B2C':
        cursor.execute("""
            SELECT COUNT(*) AS total FROM pedidos
            WHERE id_cliente = %s AND estado <> 'cancelado'
        """, (id_cliente,))
        es_primer_pedido = cursor.fetchone()['total'] == 0

        if es_primer_pedido:
            descuento = round(subtotal * DESCUENTO_PRIMER_PEDIDO / 100, 2)
            motivo_descuento = f"Primer pedido ({DESCUENTO_PRIMER_PEDIDO} %)"

        if codigo_cupon:
            cursor.execute("""
                SELECT * FROM cupones
                WHERE codigo = %s AND activo = TRUE
                  AND (vigencia_fin IS NULL OR vigencia_fin >= %s)
            """, (codigo_cupon, date.today()))
            cupon = cursor.fetchone()

            if not cupon:
                raise ErrorPedido('El cupón no existe o ya no está vigente')

            if cupon['tipo_descuento'] == 'porcentaje':
                descuento_cupon = round(subtotal * float(cupon['valor']) / 100, 2)
            else:
                descuento_cupon = min(float(cupon['valor']), subtotal)

            if descuento_cupon > descuento:
                descuento = descuento_cupon
                motivo_descuento = f"Cupón {cupon['codigo']}"
                id_cupon = cupon['id_cupon']
            elif motivo_descuento:
                motivo_descuento += " (mayor que el cupón; los descuentos no se acumulan)"

    elif codigo_cupon:
        raise ErrorPedido('Los cupones son exclusivos para cuentas Hogar')

    if tipo == 'B2B' or modalidad == 'recoger' or subtotal >= ENVIO_GRATIS_DESDE:
        costo_envio = 0.0
    else:
        costo_envio = COSTO_ENVIO_B2C

    cursor.execute(
        "SELECT saldo_favor FROM clientes WHERE id_cliente = %s" + bloqueo,
        (id_cliente,)
    )
    saldo_disponible = float(cursor.fetchone()['saldo_favor'])
    antes_de_saldo = round(subtotal - descuento + costo_envio, 2)
    saldo_aplicado = round(min(saldo_disponible, antes_de_saldo), 2) if usar_saldo else 0.0

    total = round(antes_de_saldo - saldo_aplicado, 2)

    return {
        'tarifa': nombre_tarifa(tipo, nivel),
        'tipo_cliente': tipo,
        'modalidad': modalidad,
        'lineas': lineas,
        'subtotal': subtotal,
        'descuento': descuento,
        'motivo_descuento': motivo_descuento,
        'id_cupon': id_cupon,
        'costo_envio': costo_envio,
        'saldo_disponible': saldo_disponible,
        'saldo_aplicado': saldo_aplicado,
        'total': total,
        'cumple_minimo': cumple_minimo,
        'mensaje_minimo': mensaje_minimo,
        'faltantes': faltantes,
        'requeridos': requeridos,
        'consumo_insumos': consumo_insumos,
        'puede_confirmar': cumple_minimo and not faltantes
    }


def descontar_inventario(cursor, requeridos):
    """Resta del producto terminado y de sus insumos de receta lo que se vendió."""
    for id_producto, cantidad in requeridos.items():
        cursor.execute(
            """
            UPDATE productos
            SET existencia = GREATEST(0, existencia - %s)
            WHERE id_producto = %s
            """,
            (cantidad, id_producto)
        )

    consumo_insumos = _consumo_insumos_por_productos(cursor, requeridos)
    for id_insumo, total_insumo in consumo_insumos.items():
        cursor.execute(
            """
            UPDATE insumos
            SET existencia = GREATEST(0, existencia - %s)
            WHERE id_insumo = %s
            """,
            (total_insumo, id_insumo)
        )


def insertar_pedido(cursor, id_cliente, id_usuario, calculo, modalidad, direccion,
                    telefono, metodo_pago, estado_pago, notas=None, id_programacion=None,
                    latitud=None, longitud=None):
    """
    Guarda un pedido ya calculado: encabezado, detalle, inventario, saldo
    y aviso. Lo usan el pedido del cliente y los pedidos programados.
    No hace commit: quien llama decide.
    """
    cursor.execute("""
        INSERT INTO pedidos
        (id_cliente, id_programacion, id_cupon, tipo_cliente, modalidad,
         direccion_entrega, latitud, longitud, telefono_contacto, subtotal,
         descuento, costo_envio, saldo_aplicado, total, metodo_pago, estado_pago, notas)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        id_cliente, id_programacion, calculo['id_cupon'], calculo['tipo_cliente'],
        modalidad, direccion if modalidad == 'domicilio' else None,
        latitud if modalidad == 'domicilio' else None,
        longitud if modalidad == 'domicilio' else None, telefono,
        calculo['subtotal'], calculo['descuento'], calculo['costo_envio'],
        calculo['saldo_aplicado'], calculo['total'], metodo_pago, estado_pago, notas
    ))
    id_pedido = cursor.lastrowid

    for linea in calculo['lineas']:
        cursor.execute("""
            INSERT INTO detalle_pedido (id_pedido, id_producto, cantidad, precio_unitario, subtotal, opciones)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (id_pedido, linea['id_producto'], linea['cantidad'],
              linea['precio_unitario'], linea['subtotal'], linea.get('opciones')))

    descontar_inventario(cursor, calculo['requeridos'])

    if calculo['saldo_aplicado'] > 0:
        cursor.execute(
            "UPDATE clientes SET saldo_favor = saldo_favor - %s WHERE id_cliente = %s",
            (calculo['saldo_aplicado'], id_cliente)
        )

    mensaje = 'Pago aprobado.' if estado_pago == 'pagado' else \
        'Sube tu comprobante de transferencia para validar el pago.'
    notificar(cursor, id_usuario, f"Pedido #{id_pedido} recibido", mensaje)

    return id_pedido


def reponer_inventario(cursor, id_pedido):
    """Regresa al inventario de productos e insumos lo descontado (al cancelar)."""
    cursor.execute("""
        SELECT d.id_producto, d.cantidad, d.opciones, p.es_paquete
        FROM detalle_pedido d
        JOIN productos p ON p.id_producto = d.id_producto
        WHERE d.id_pedido = %s
    """, (id_pedido,))

    repuestos = {}
    for linea in cursor.fetchall():
        if linea['es_paquete']:
            salsa = agua = None
            if linea['opciones']:
                ids = linea['opciones'].split('|')[0].split(',')
                salsa = int(ids[0]) if ids[0] else None
                agua = int(ids[1]) if len(ids) > 1 and ids[1] else None
            try:
                componentes, _ = componentes_paquete(cursor, linea['id_producto'], salsa, agua)
            except ErrorPedido:
                componentes, _ = componentes_paquete(cursor, linea['id_producto'])
            for id_componente, cantidad_componente in componentes:
                cant_comp = cantidad_componente * float(linea['cantidad'])
                repuestos[id_componente] = repuestos.get(id_componente, 0.0) + cant_comp
                cursor.execute(
                    "UPDATE productos SET existencia = existencia + %s WHERE id_producto = %s",
                    (cant_comp, id_componente)
                )
        else:
            cant = float(linea['cantidad'])
            id_prod = int(linea['id_producto'])
            repuestos[id_prod] = repuestos.get(id_prod, 0.0) + cant
            cursor.execute(
                "UPDATE productos SET existencia = existencia + %s WHERE id_producto = %s",
                (cant, id_prod)
            )

    consumo_insumos = _consumo_insumos_por_productos(cursor, repuestos)
    for id_insumo, total_insumo in consumo_insumos.items():
        cursor.execute(
            "UPDATE insumos SET existencia = existencia + %s WHERE id_insumo = %s",
            (total_insumo, id_insumo)
        )


def notificar(cursor, id_usuario, titulo, mensaje):
    cursor.execute("""
        INSERT INTO notificaciones (id_usuario, titulo, mensaje) VALUES (%s, %s, %s)
    """, (id_usuario, titulo, mensaje))


def otorgar_bono_referido(cursor, id_cliente):
    """
    Si es el primer pedido entregado de un cliente invitado, da el bono a
    ambos una sola vez. Se llama justo después de marcar un pedido como
    entregado. Regresa True si se otorgó el bono.
    """
    cursor.execute("""
        SELECT c.id_usuario, c.id_referido_por, c.bono_referido_otorgado,
               cr.id_usuario AS id_usuario_invitador
        FROM clientes c
        LEFT JOIN clientes cr ON cr.id_cliente = c.id_referido_por
        WHERE c.id_cliente = %s
        FOR UPDATE
    """, (id_cliente,))
    cliente = cursor.fetchone()

    if not cliente or not cliente['id_referido_por'] or cliente['bono_referido_otorgado']:
        return False

    cursor.execute("""
        SELECT COUNT(*) AS entregados FROM pedidos
        WHERE id_cliente = %s AND estado = 'entregado'
    """, (id_cliente,))
    if cursor.fetchone()['entregados'] != 1:
        return False

    cursor.execute("""
        UPDATE clientes SET saldo_favor = saldo_favor + %s, bono_referido_otorgado = TRUE
        WHERE id_cliente = %s
    """, (BONO_REFERIDO, id_cliente))
    cursor.execute(
        "UPDATE clientes SET saldo_favor = saldo_favor + %s WHERE id_cliente = %s",
        (BONO_REFERIDO, cliente['id_referido_por'])
    )

    notificar(cursor, cliente['id_usuario'], '¡Ganaste saldo!',
              f"Recibiste ${BONO_REFERIDO:.0f} de saldo por tu primer pedido como invitado.")
    notificar(cursor, cliente['id_usuario_invitador'], '¡Tu invitado hizo su primer pedido!',
              f"Recibiste ${BONO_REFERIDO:.0f} de saldo por recomendar NixtaGuiso.")
    return True