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
        try:
            id_producto = int(item.get('id_producto'))
            cantidad = float(item.get('cantidad'))
        except (TypeError, ValueError, AttributeError):
            raise ErrorPedido('Hay un producto con datos incorrectos en el carrito')

        if cantidad <= 0:
            raise ErrorPedido('Las cantidades deben ser mayores a cero')

        cantidades[id_producto] = cantidades.get(id_producto, 0) + cantidad

    return cantidades


def calcular_pedido(cursor, id_cliente, tipo, nivel, cantidades,
                    modalidad='domicilio', codigo_cupon='', usar_saldo=False,
                    bloquear=False):
    """
    Calcula el pedido completo aplicando todas las reglas.
    bloquear=True se usa al confirmar el pedido: aparta las filas de
    productos (FOR UPDATE) para que dos pedidos al mismo tiempo no
    vendan la misma existencia.
    """
    if modalidad not in ('domicilio', 'recoger'):
        raise ErrorPedido('La modalidad de entrega no es válida')

    bloqueo = " FOR UPDATE" if bloquear else ""

    # ---------- 1. PRODUCTOS Y PRECIOS ----------
    lineas = []
    requeridos = {}          # id_producto -> cantidad que se descontará del inventario
    subtotal = 0.0
    kg_tortilla = 0.0

    for id_producto, cantidad in cantidades.items():
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

        if producto['es_paquete']:
            if tipo == 'B2B':
                raise ErrorPedido('Los paquetes son exclusivos para cuentas Hogar')
            precio = float(producto['precio_b2c'])

            cursor.execute(
                "SELECT id_producto, cantidad FROM paquete_componentes WHERE id_paquete = %s",
                (id_producto,)
            )
            for componente in cursor.fetchall():
                requerido = float(componente['cantidad']) * cantidad
                requeridos[componente['id_producto']] = requeridos.get(componente['id_producto'], 0) + requerido
        else:
            precio = precio_para(producto, tipo, nivel)
            requeridos[id_producto] = requeridos.get(id_producto, 0) + cantidad
            if producto['id_categoria'] == 1 and es_kg:
                kg_tortilla += cantidad

        importe = round(precio * cantidad, 2)
        subtotal += importe

        lineas.append({
            'id_producto': id_producto,
            'nombre': producto['nombre'],
            'presentacion': producto['presentacion'],
            'cantidad': cantidad,
            'precio_unitario': precio,
            'subtotal': importe,
            'es_paquete': bool(producto['es_paquete'])
        })

    subtotal = round(subtotal, 2)

    # ---------- 2. EXISTENCIA ----------
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

    # ---------- 3. PEDIDO MINIMO ----------
    if tipo == 'B2B':
        cumple_minimo = kg_tortilla >= KG_MINIMO_TORTILLA_B2B
        mensaje_minimo = None if cumple_minimo else \
            f"El pedido mínimo para negocios es de {KG_MINIMO_TORTILLA_B2B} kg de tortilla"
    else:
        cumple_minimo = subtotal >= PEDIDO_MINIMO_B2C
        mensaje_minimo = None if cumple_minimo else \
            f"El pedido mínimo es de ${PEDIDO_MINIMO_B2C:.2f} en productos"

    # ---------- 4. DESCUENTO (no se acumulan: se aplica el mayor) ----------
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

    # ---------- 5. ENVIO ----------
    if tipo == 'B2B' or modalidad == 'recoger' or subtotal >= ENVIO_GRATIS_DESDE:
        costo_envio = 0.0
    else:
        costo_envio = COSTO_ENVIO_B2C

    # ---------- 6. SALDO DE REFERIDOS ----------
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
        'puede_confirmar': cumple_minimo and not faltantes
    }


def descontar_inventario(cursor, requeridos):
    """Resta del producto terminado lo que se vendió."""
    for id_producto, cantidad in requeridos.items():
        cursor.execute(
            "UPDATE productos SET existencia = existencia - %s WHERE id_producto = %s",
            (cantidad, id_producto)
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

    # El precio se copia tal cual se cobró
    for linea in calculo['lineas']:
        cursor.execute("""
            INSERT INTO detalle_pedido (id_pedido, id_producto, cantidad, precio_unitario, subtotal)
            VALUES (%s, %s, %s, %s, %s)
        """, (id_pedido, linea['id_producto'], linea['cantidad'],
              linea['precio_unitario'], linea['subtotal']))

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
    """Regresa al inventario lo que se había descontado (al cancelar)."""
    cursor.execute("""
        SELECT d.id_producto, d.cantidad, p.es_paquete
        FROM detalle_pedido d
        JOIN productos p ON p.id_producto = d.id_producto
        WHERE d.id_pedido = %s
    """, (id_pedido,))

    for linea in cursor.fetchall():
        if linea['es_paquete']:
            cursor.execute(
                "SELECT id_producto, cantidad FROM paquete_componentes WHERE id_paquete = %s",
                (linea['id_producto'],)
            )
            for componente in cursor.fetchall():
                cursor.execute(
                    "UPDATE productos SET existencia = existencia + %s WHERE id_producto = %s",
                    (float(componente['cantidad']) * float(linea['cantidad']), componente['id_producto'])
                )
        else:
            cursor.execute(
                "UPDATE productos SET existencia = existencia + %s WHERE id_producto = %s",
                (linea['cantidad'], linea['id_producto'])
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
