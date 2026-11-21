from flask import session


# =====================================================================
#  REGLAS DE PRECIO
#  - Visitante, cliente Hogar o administrador  -> precio B2C
#  - Cliente Negocio nivel 1                   -> precio B2B nivel 1
#  - Cliente Negocio nivel 2                   -> precio B2B nivel 2
# =====================================================================


def tipo_de_cliente(cursor, id_cliente):
    """Regresa (tipo, nivel) de un cliente específico. Lo usa el panel administrativo."""
    cursor.execute(
        "SELECT tipo, nivel_b2b FROM clientes WHERE id_cliente = %s",
        (id_cliente,)
    )
    cliente = cursor.fetchone()
    if not cliente:
        return 'B2C', None
    return cliente['tipo'], cliente['nivel_b2b']


def obtener_tipo_cliente(cursor):
    """
    Revisa la sesión y regresa (tipo, nivel).
    El nivel se lee de la base de datos en cada petición, para que un
    cambio hecho por el administrador en el CRM se aplique de inmediato.
    """
    id_cliente = session.get('id_cliente')

    if not id_cliente:
        return 'B2C', None

    return tipo_de_cliente(cursor, id_cliente)


def precio_para(producto, tipo, nivel):
    """Regresa el precio que le toca pagar al cliente por un producto."""
    if tipo == 'B2B' and nivel == 2:
        return float(producto['precio_b2b_n2'])
    if tipo == 'B2B':
        return float(producto['precio_b2b_n1'])
    return float(producto['precio_b2c'])


def nombre_tarifa(tipo, nivel):
    """Texto para mostrar en pantalla qué tarifa se está aplicando."""
    if tipo == 'B2B':
        return f"Negocio nivel {nivel}"
    return "Hogar"
