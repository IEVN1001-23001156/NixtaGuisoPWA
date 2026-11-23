"""
Convierte una dirección escrita en coordenadas (latitud y longitud) con Nominatim,
el buscador gratuito de OpenStreetMap. No necesita clave ni librerías extra.

Reglas de uso de Nominatim: máximo una consulta por segundo y un User-Agent propio.
Para un proyecto escolar es más que suficiente; los resultados se guardan en memoria
para no repetir la misma consulta.
"""
import json
import time
import urllib.parse
import urllib.request

from utils.ubicacion import LATITUD_MIN, LATITUD_MAX, LONGITUD_MIN, LONGITUD_MAX

URL = 'https://nominatim.openstreetmap.org/search'
AGENTE = 'NixtaGuiso/1.0 (proyecto escolar, Leon Gto.)'
_cache = {}
_ultima_consulta = [0.0]


def geocodificar(direccion):
    """Regresa (latitud, longitud) dentro de León, o (None, None) si no la encuentra."""
    texto = ' '.join(str(direccion or '').split())
    if len(texto) < 5:
        return None, None

    clave = texto.lower()
    if clave in _cache:
        return _cache[clave]

    # Se agrega la ciudad si la dirección no la menciona
    consulta = texto if 'león' in clave or 'leon' in clave else f'{texto}, León, Guanajuato'
    parametros = urllib.parse.urlencode({
        'q': f'{consulta}, México', 'format': 'json', 'limit': 1, 'countrycodes': 'mx',
        # Solo resultados dentro de la zona de cobertura de León
        'viewbox': f'{LONGITUD_MIN},{LATITUD_MAX},{LONGITUD_MAX},{LATITUD_MIN}', 'bounded': 1
    })

    try:
        espera = 1.0 - (time.time() - _ultima_consulta[0])
        if espera > 0:
            time.sleep(espera)
        _ultima_consulta[0] = time.time()

        peticion = urllib.request.Request(f'{URL}?{parametros}', headers={'User-Agent': AGENTE})
        with urllib.request.urlopen(peticion, timeout=4) as respuesta:
            resultados = json.loads(respuesta.read().decode('utf-8'))

        if resultados:
            lat, lng = round(float(resultados[0]['lat']), 6), round(float(resultados[0]['lon']), 6)
            if LATITUD_MIN <= lat <= LATITUD_MAX and LONGITUD_MIN <= lng <= LONGITUD_MAX:
                _cache[clave] = (lat, lng)
                return lat, lng
        _cache[clave] = (None, None)
    except Exception as e:
        # Sin internet o sin respuesta: el pedido se guarda igual, sin punto en el mapa
        print("GEOCODIFICACION NO DISPONIBLE:", str(e))
    return None, None