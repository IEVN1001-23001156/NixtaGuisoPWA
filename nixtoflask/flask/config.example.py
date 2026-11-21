# =====================================================================
#  NixtaGuiso · Plantilla de configuración
#
#  1. Copien este archivo y nómbrenlo config.py (en esta misma carpeta).
#  2. Cambien MYSQL_USER y MYSQL_PASSWORD por los de su computadora.
#  3. config.py NO se sube a GitHub; este archivo de ejemplo sí.
# =====================================================================

config = {
    "development": {
        # Conexión a MySQL (Laragon)
        "MYSQL_HOST": "localhost",
        "MYSQL_USER": "root",
        "MYSQL_PASSWORD": "",
        "MYSQL_DB": "nixtaguiso",
        "MYSQL_PORT": 3306,
        "MYSQL_CHARSET": "utf8mb4",          # acentos y ñ
        "MYSQL_CURSORCLASS": "DictCursor",   # filas como diccionario: fila["nombre"]

        # Sesiones (login). Cambien el texto por uno largo y difícil de adivinar.
        "SECRET_KEY": "cambien-esta-clave-por-una-propia",

        # Archivos subidos (fotos de productos y comprobantes)
        "UPLOAD_FOLDER": "uploads",
        "MAX_CONTENT_LENGTH": 5 * 1024 * 1024  # máximo 5 MB por archivo
    }
}
