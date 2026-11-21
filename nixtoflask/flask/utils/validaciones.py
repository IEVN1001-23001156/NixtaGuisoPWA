# =====================================================================
#  FUNCIONES PARA VALIDAR DATOS DE LOS FORMULARIOS DEL PANEL
# =====================================================================


class ErrorValidacion(Exception):
    """Dato incorrecto en un formulario; el mensaje se muestra tal cual."""
    def __init__(self, mensaje, codigo=400):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo


def texto(datos, campo, etiqueta, minimo=1, maximo=255, obligatorio=True):
    valor = str(datos.get(campo, '') or '').strip()
    if not valor and not obligatorio:
        return None
    if len(valor) < minimo:
        raise ErrorValidacion(f"{etiqueta}: escribe al menos {minimo} caracteres")
    if len(valor) > maximo:
        raise ErrorValidacion(f"{etiqueta}: máximo {maximo} caracteres")
    return valor


def numero(datos, campo, etiqueta, minimo=0, permitir_cero=True):
    try:
        valor = float(datos.get(campo))
    except (TypeError, ValueError):
        raise ErrorValidacion(f"{etiqueta}: escribe un número válido")
    if valor < minimo or (not permitir_cero and valor == 0):
        raise ErrorValidacion(f"{etiqueta}: debe ser mayor a {minimo}")
    return round(valor, 3)


def booleano(datos, campo, por_defecto=True):
    valor = datos.get(campo, por_defecto)
    if isinstance(valor, bool):
        return valor
    return str(valor).lower() in ('1', 'true', 'si', 'sí')
