-- =====================================================================
--  NixtaGuiso · Migración del paso 10: mapa de rutas
--  Archivo: database/migracion_mapa_rutas.sql
--
--  Agrega las columnas de ubicación SIN borrar los datos que ya tienen.
--  Ejecútenlo UNA sola vez sobre su base nixtaguiso actual.
--  (Si prefieren empezar de cero, importen nixtaguiso.sql y no usen este archivo.)
-- =====================================================================

SET NAMES utf8mb4;
USE nixtaguiso;

-- Ubicación guardada del cliente
ALTER TABLE clientes
  ADD COLUMN latitud  DECIMAL(9,6) NULL AFTER direccion,
  ADD COLUMN longitud DECIMAL(9,6) NULL AFTER latitud,
  ADD CONSTRAINT ck_clientes_ubicacion CHECK ((latitud IS NULL) = (longitud IS NULL));

-- Ubicación de entrega y número de parada de cada pedido
ALTER TABLE pedidos
  ADD COLUMN latitud    DECIMAL(9,6) NULL AFTER direccion_entrega,
  ADD COLUMN longitud   DECIMAL(9,6) NULL AFTER latitud,
  ADD COLUMN orden_ruta INT NULL AFTER longitud,
  ADD CONSTRAINT ck_pedidos_ubicacion CHECK ((latitud IS NULL) = (longitud IS NULL)),
  ADD CONSTRAINT ck_pedidos_orden CHECK (orden_ruta IS NULL OR orden_ruta > 0);

-- Ubicaciones de prueba para los clientes iniciales
UPDATE clientes SET latitud = 21.134000, longitud = -101.674500 WHERE codigo_referido = 'JUDITH20';
UPDATE clientes SET latitud = 21.110500, longitud = -101.658000 WHERE codigo_referido = 'TOMY20';
