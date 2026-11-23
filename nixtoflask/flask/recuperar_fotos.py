"""
NixtaGuiso · Conectar las fotos de productos con la base de datos

Busca las fotos en:
  1. public/productos/                    (versión anterior del equipo)
  2. nixtoflask/flask/uploads/productos/  (versión actual)

Reconoce el producto de dos formas:
  - Por número:  producto_1_tortilla.jpg   o   prod_1_xxxx_tortilla.jpg
  - Por nombre:  tortilla-tradicional.jpg, agua-de-horchata.png, combo-frijoles.jpg
    (sin importar acentos, mayúsculas, espacios o guiones bajos;
     "combo-..." o "paquete-..." = "Comida Completa con ...")

Uso (con el venv activado, desde nixtoflask\\flask):
    python recuperar_fotos.py
"""
import os
import re
import unicodedata

import MySQLdb
from config import config

CARPETA_FLASK = os.path.dirname(os.path.abspath(__file__))
CARPETAS = [
    # (carpeta física, prefijo con el que se guarda en la base de datos)
    (os.path.join(CARPETA_FLASK, '..', '..', 'public', 'productos'), '/productos/'),
    (os.path.join(CARPETA_FLASK, 'uploads', 'productos'), '/uploads/productos/'),
]
EXTENSIONES = ('.jpg', '.jpeg', '.png', '.webp')
PATRON_NUMERO = re.compile(r'^(?:prod|producto)_(\d+)_', re.IGNORECASE)


def simplificar(texto):
    """'Agua de limón con chía' -> 'agua-de-limon-con-chia'"""
    sin_acentos = unicodedata.normalize('NFD', texto)
    sin_acentos = ''.join(c for c in sin_acentos if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', '-', sin_acentos.lower()).strip('-')


c = config['development']
conexion = MySQLdb.connect(host=c['MYSQL_HOST'], user=c['MYSQL_USER'], passwd=c['MYSQL_PASSWORD'],
                           db=c['MYSQL_DB'], port=c['MYSQL_PORT'], charset='utf8mb4')
cursor = conexion.cursor()

# Nombres de los productos -> número de producto
cursor.execute("SELECT id_producto, nombre FROM productos WHERE activo = 1")
por_nombre = {}
for id_producto, nombre in cursor.fetchall():
    por_nombre[simplificar(nombre)] = id_producto
    if nombre.lower().startswith('comida completa con '):
        guisado = simplificar(nombre[len('comida completa con '):])
        por_nombre['combo-' + guisado] = id_producto
        por_nombre['paquete-' + guisado] = id_producto

# Por cada producto se queda la foto más reciente que se encuentre
encontradas, sin_reconocer = {}, []
for carpeta, prefijo in CARPETAS:
    if not os.path.isdir(carpeta):
        continue
    for archivo in os.listdir(carpeta):
        base, extension = os.path.splitext(archivo)
        if extension.lower() not in EXTENSIONES:
            continue
        coincide = PATRON_NUMERO.match(archivo)
        id_producto = int(coincide.group(1)) if coincide else por_nombre.get(simplificar(base))
        if id_producto is None:
            sin_reconocer.append(archivo)
            continue
        fecha = os.path.getmtime(os.path.join(carpeta, archivo))
        if id_producto not in encontradas or fecha > encontradas[id_producto][0]:
            encontradas[id_producto] = (fecha, prefijo + archivo)

for id_producto, (_, ruta) in sorted(encontradas.items()):
    cursor.execute("UPDATE productos SET imagen_url = %s WHERE id_producto = %s", (ruta, id_producto))
    estado = 'conectada' if cursor.rowcount else 'ya estaba conectada'
    print(f'Producto {id_producto}: {ruta} -> {estado}')
conexion.commit()

print(f'\nListo: {len(encontradas)} foto(s) conectada(s).')
if sin_reconocer:
    print('\nNo se reconoció el producto de estas fotos (renómbralas con el nombre del producto):')
    for archivo in sin_reconocer:
        print('  -', archivo)

cursor.close()
conexion.close()
