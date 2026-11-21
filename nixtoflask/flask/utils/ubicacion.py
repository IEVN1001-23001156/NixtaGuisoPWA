from utils.validaciones import ErrorValidacion


# =====================================================================
#  UBICACIONES (mapa de rutas)
#  Rectángulo aproximado de la zona urbana de León, Guanajuato.
#  Si la cobertura cambia, solo se ajustan estos cuatro valores.
# =====================================================================

LATITUD_MIN, LATITUD_MAX = 20.95, 21.30
LONGITUD_MIN, LONGITUD_MAX = -101.85, -101.45


def leer_ubicacion(datos, obligatorio=False):
    """
    Lee "latitud" y "longitud" del formulario.
    Regresa (latitud, longitud) o (None, None) si no se enviaron.
    """
    latitud = datos.get('latitud')
    longitud = datos.get('longitud')

    if latitud in (None, '') and longitud in (None, ''):
        if obligatorio:
            raise ErrorValidacion('Marca tu ubicación en el mapa')
        return None, None

    try:
        latitud = round(float(latitud), 6)
        longitud = round(float(longitud), 6)
    except (TypeError, ValueError):
        raise ErrorValidacion('La ubicación no es válida')

    if not (LATITUD_MIN <= latitud <= LATITUD_MAX and LONGITUD_MIN <= longitud <= LONGITUD_MAX):
        raise ErrorValidacion('La ubicación está fuera de la zona de cobertura en León, Gto.')

    return latitud, longitud


def a_numero(valor):
    """Convierte la coordenada de MySQL (Decimal) a número para el JSON."""
    return float(valor) if valor is not None else None
