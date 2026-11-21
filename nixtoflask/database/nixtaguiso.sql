-- =====================================================================
--  NixtaGuiso · Base de datos MySQL
--  Archivo: database/nixtaguiso.sql
--  22 tablas en 4 grupos + datos iniciales para pruebas
--
--  ATENCIÓN: la primera instrucción BORRA la base "nixtaguiso" si ya
--  existe y la crea de nuevo. Úsenlo solo en desarrollo.
-- =====================================================================

-- Asegura que acentos y ñ se guarden correctamente al importar
SET NAMES utf8mb4;

DROP DATABASE IF EXISTS nixtaguiso;
CREATE DATABASE nixtaguiso
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
USE nixtaguiso;

-- =====================================================================
--  GRUPO 1. USUARIOS, CLIENTES Y CATÁLOGO
-- =====================================================================

-- Todas las personas que entran al sistema (clientes y administrador)
CREATE TABLE usuarios (
  id_usuario      INT AUTO_INCREMENT PRIMARY KEY,
  nombre          VARCHAR(100) NOT NULL,
  correo          VARCHAR(120) NOT NULL,
  telefono        VARCHAR(15)  NULL,
  contrasena_hash VARCHAR(255) NOT NULL,
  rol             ENUM('cliente','admin') NOT NULL DEFAULT 'cliente',
  activo          BOOLEAN NOT NULL DEFAULT TRUE,
  fecha_registro  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uk_usuarios_correo UNIQUE (correo)
) ENGINE=InnoDB;

-- Datos de compra de los clientes (1 a 1 con usuarios)
CREATE TABLE clientes (
  id_cliente             INT AUTO_INCREMENT PRIMARY KEY,
  id_usuario             INT NOT NULL,
  tipo                   ENUM('B2C','B2B') NOT NULL,
  nombre_negocio         VARCHAR(120) NULL,
  rfc                    VARCHAR(13)  NULL,
  nivel_b2b              TINYINT NULL,
  direccion              VARCHAR(255) NULL,
  latitud                DECIMAL(9,6) NULL,      -- ubicación marcada en el mapa
  longitud               DECIMAL(9,6) NULL,
  codigo_referido        VARCHAR(20)  NOT NULL,
  id_referido_por        INT NULL,
  saldo_favor            DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  bono_referido_otorgado BOOLEAN NOT NULL DEFAULT FALSE,
  preferencias           TEXT NULL,
  CONSTRAINT uk_clientes_usuario  UNIQUE (id_usuario),
  CONSTRAINT uk_clientes_codigo   UNIQUE (codigo_referido),
  CONSTRAINT fk_clientes_usuario  FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario),
  CONSTRAINT fk_clientes_referido FOREIGN KEY (id_referido_por) REFERENCES clientes(id_cliente),
  -- Hogar: sin nivel. Negocio: nivel 1 o 2 y nombre comercial obligatorio
  CONSTRAINT ck_clientes_nivel CHECK (
    (tipo = 'B2C' AND nivel_b2b IS NULL) OR
    (tipo = 'B2B' AND nivel_b2b IN (1,2) AND nombre_negocio IS NOT NULL)
  ),
  CONSTRAINT ck_clientes_saldo CHECK (saldo_favor >= 0),
  CONSTRAINT ck_clientes_ubicacion CHECK ((latitud IS NULL) = (longitud IS NULL))
) ENGINE=InnoDB;

-- Las 5 líneas de producto
CREATE TABLE categorias (
  id_categoria INT AUTO_INCREMENT PRIMARY KEY,
  nombre       VARCHAR(60)  NOT NULL,
  descripcion  VARCHAR(255) NULL,
  orden        TINYINT NOT NULL DEFAULT 0,
  CONSTRAINT uk_categorias_nombre UNIQUE (nombre)
) ENGINE=InnoDB;

-- Productos del catálogo y paquetes "Comida Completa"
-- existencia = producto terminado disponible (en unidades de venta)
-- kg_por_unidad = equivalencia en kg para el indicador de kg vendidos
CREATE TABLE productos (
  id_producto    INT AUTO_INCREMENT PRIMARY KEY,
  id_categoria   INT NULL,                -- NULL solo en paquetes
  nombre         VARCHAR(100) NOT NULL,
  descripcion    TEXT NULL,
  presentacion   VARCHAR(50)  NOT NULL,
  kg_por_unidad  DECIMAL(10,3) NOT NULL,
  precio_b2c     DECIMAL(10,2) NOT NULL,
  precio_b2b_n1  DECIMAL(10,2) NOT NULL,
  precio_b2b_n2  DECIMAL(10,2) NOT NULL,
  costo_unitario DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  existencia     DECIMAL(10,3) NOT NULL DEFAULT 0.000,
  imagen_url     VARCHAR(255) NULL,
  es_paquete     BOOLEAN NOT NULL DEFAULT FALSE,
  disponible     BOOLEAN NOT NULL DEFAULT TRUE,
  activo         BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT fk_productos_categoria FOREIGN KEY (id_categoria) REFERENCES categorias(id_categoria),
  CONSTRAINT ck_productos_precios CHECK (precio_b2c >= 0 AND precio_b2b_n1 >= 0 AND precio_b2b_n2 >= 0 AND costo_unitario >= 0),
  CONSTRAINT ck_productos_kg CHECK (kg_por_unidad > 0),
  CONSTRAINT ck_productos_existencia CHECK (existencia >= 0),
  CONSTRAINT ck_productos_categoria CHECK (es_paquete = TRUE OR id_categoria IS NOT NULL)
) ENGINE=InnoDB;

-- Productos que forman cada paquete
CREATE TABLE paquete_componentes (
  id_paquete  INT NOT NULL,
  id_producto INT NOT NULL,
  cantidad    DECIMAL(10,3) NOT NULL,
  PRIMARY KEY (id_paquete, id_producto),
  CONSTRAINT fk_paqcomp_paquete  FOREIGN KEY (id_paquete)  REFERENCES productos(id_producto),
  CONSTRAINT fk_paqcomp_producto FOREIGN KEY (id_producto) REFERENCES productos(id_producto),
  CONSTRAINT ck_paqcomp_cantidad CHECK (cantidad > 0)
) ENGINE=InnoDB;

-- Productos favoritos de cada cliente
CREATE TABLE favoritos (
  id_cliente  INT NOT NULL,
  id_producto INT NOT NULL,
  fecha       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id_cliente, id_producto),
  CONSTRAINT fk_favoritos_cliente  FOREIGN KEY (id_cliente)  REFERENCES clientes(id_cliente),
  CONSTRAINT fk_favoritos_producto FOREIGN KEY (id_producto) REFERENCES productos(id_producto)
) ENGINE=InnoDB;

-- =====================================================================
--  GRUPO 2. PEDIDOS
-- =====================================================================

CREATE TABLE cupones (
  id_cupon       INT AUTO_INCREMENT PRIMARY KEY,
  codigo         VARCHAR(30)  NOT NULL,
  descripcion    VARCHAR(255) NULL,
  tipo_descuento ENUM('porcentaje','monto') NOT NULL,
  valor          DECIMAL(10,2) NOT NULL,
  origen         ENUM('qr','promocion') NOT NULL,
  vigencia_fin   DATE NULL,
  activo         BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT uk_cupones_codigo UNIQUE (codigo),
  CONSTRAINT ck_cupones_valor CHECK (valor > 0)
) ENGINE=InnoDB;

CREATE TABLE repartidores (
  id_repartidor INT AUTO_INCREMENT PRIMARY KEY,
  nombre        VARCHAR(100) NOT NULL,
  telefono      VARCHAR(15)  NOT NULL,
  placas        VARCHAR(15)  NOT NULL,
  activo        BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB;

-- Pedidos agendados (eventos o abasto recurrente de negocios)
CREATE TABLE programaciones (
  id_programacion   INT AUTO_INCREMENT PRIMARY KEY,
  id_cliente        INT NOT NULL,
  tipo              ENUM('evento','negocio') NOT NULL,
  fecha_inicio      DATE NOT NULL,
  hora_desde        TIME NOT NULL,
  hora_hasta        TIME NOT NULL,
  frecuencia        ENUM('unica','semanal') NOT NULL DEFAULT 'unica',
  direccion_entrega VARCHAR(255) NOT NULL,
  notas             TEXT NULL,
  estado            ENUM('activa','cancelada','finalizada') NOT NULL DEFAULT 'activa',
  CONSTRAINT fk_programaciones_cliente FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente),
  CONSTRAINT ck_programaciones_horario CHECK (hora_hasta > hora_desde)
) ENGINE=InnoDB;

CREATE TABLE detalle_programacion (
  id_detalle      INT AUTO_INCREMENT PRIMARY KEY,
  id_programacion INT NOT NULL,
  id_producto     INT NOT NULL,
  cantidad        DECIMAL(10,3) NOT NULL,
  CONSTRAINT fk_detprog_programacion FOREIGN KEY (id_programacion) REFERENCES programaciones(id_programacion) ON DELETE CASCADE,
  CONSTRAINT fk_detprog_producto     FOREIGN KEY (id_producto)     REFERENCES productos(id_producto),
  CONSTRAINT ck_detprog_cantidad CHECK (cantidad > 0)
) ENGINE=InnoDB;

CREATE TABLE pedidos (
  id_pedido         INT AUTO_INCREMENT PRIMARY KEY,
  id_cliente        INT NOT NULL,
  id_programacion   INT NULL,
  id_cupon          INT NULL,
  id_repartidor     INT NULL,
  fecha_pedido      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  tipo_cliente      ENUM('B2C','B2B') NOT NULL,
  estado            ENUM('pendiente','preparando','en_ruta','entregado','cancelado') NOT NULL DEFAULT 'pendiente',
  modalidad         ENUM('domicilio','recoger') NOT NULL,
  direccion_entrega VARCHAR(255) NULL,
  latitud           DECIMAL(9,6) NULL,           -- ubicación de entrega (mapa de rutas)
  longitud          DECIMAL(9,6) NULL,
  orden_ruta        INT NULL,                    -- número de parada del repartidor
  telefono_contacto VARCHAR(15)  NOT NULL,
  subtotal          DECIMAL(10,2) NOT NULL,
  descuento         DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  costo_envio       DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  saldo_aplicado    DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  total             DECIMAL(10,2) NOT NULL,
  metodo_pago       ENUM('tarjeta','transferencia') NOT NULL,
  estado_pago       ENUM('pagado','por_validar','rechazado') NOT NULL,
  comprobante_url   VARCHAR(255) NULL,
  notas             TEXT NULL,
  CONSTRAINT fk_pedidos_cliente      FOREIGN KEY (id_cliente)      REFERENCES clientes(id_cliente),
  CONSTRAINT fk_pedidos_programacion FOREIGN KEY (id_programacion) REFERENCES programaciones(id_programacion),
  CONSTRAINT fk_pedidos_cupon        FOREIGN KEY (id_cupon)        REFERENCES cupones(id_cupon),
  CONSTRAINT fk_pedidos_repartidor   FOREIGN KEY (id_repartidor)   REFERENCES repartidores(id_repartidor),
  CONSTRAINT ck_pedidos_montos CHECK (subtotal >= 0 AND descuento >= 0 AND costo_envio >= 0 AND saldo_aplicado >= 0 AND total >= 0),
  CONSTRAINT ck_pedidos_direccion CHECK (modalidad = 'recoger' OR direccion_entrega IS NOT NULL),
  CONSTRAINT ck_pedidos_ubicacion CHECK ((latitud IS NULL) = (longitud IS NULL)),
  CONSTRAINT ck_pedidos_orden CHECK (orden_ruta IS NULL OR orden_ruta > 0),
  INDEX idx_pedidos_fecha (fecha_pedido),
  INDEX idx_pedidos_estado (estado)
) ENGINE=InnoDB;

-- Renglones de cada pedido (el precio se copia al momento de comprar)
CREATE TABLE detalle_pedido (
  id_detalle      INT AUTO_INCREMENT PRIMARY KEY,
  id_pedido       INT NOT NULL,
  id_producto     INT NOT NULL,
  cantidad        DECIMAL(10,3) NOT NULL,
  precio_unitario DECIMAL(10,2) NOT NULL,
  subtotal        DECIMAL(10,2) NOT NULL,
  CONSTRAINT fk_detped_pedido   FOREIGN KEY (id_pedido)   REFERENCES pedidos(id_pedido) ON DELETE CASCADE,
  CONSTRAINT fk_detped_producto FOREIGN KEY (id_producto) REFERENCES productos(id_producto),
  CONSTRAINT ck_detped_valores CHECK (cantidad > 0 AND precio_unitario >= 0 AND subtotal >= 0)
) ENGINE=InnoDB;

-- Una calificación por pedido (CSAT)
CREATE TABLE calificaciones (
  id_calificacion INT AUTO_INCREMENT PRIMARY KEY,
  id_pedido       INT NOT NULL,
  estrellas       TINYINT NOT NULL,
  comentario      TEXT NULL,
  fecha           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uk_calificaciones_pedido UNIQUE (id_pedido),
  CONSTRAINT fk_calificaciones_pedido FOREIGN KEY (id_pedido) REFERENCES pedidos(id_pedido),
  CONSTRAINT ck_calificaciones_estrellas CHECK (estrellas BETWEEN 1 AND 5)
) ENGINE=InnoDB;

-- Avisos que se muestran dentro del sistema
CREATE TABLE notificaciones (
  id_notificacion INT AUTO_INCREMENT PRIMARY KEY,
  id_usuario      INT NOT NULL,
  titulo          VARCHAR(100) NOT NULL,
  mensaje         VARCHAR(255) NOT NULL,
  leida           BOOLEAN NOT NULL DEFAULT FALSE,
  fecha           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_notificaciones_usuario FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
) ENGINE=InnoDB;

-- =====================================================================
--  GRUPO 3. INVENTARIO Y PRODUCCIÓN
-- =====================================================================

-- Materias primas y empaques (costo_unitario NULL = se captura con la primera compra)
CREATE TABLE insumos (
  id_insumo      INT AUTO_INCREMENT PRIMARY KEY,
  nombre         VARCHAR(100) NOT NULL,
  unidad         ENUM('kg','L','pieza') NOT NULL,
  existencia     DECIMAL(10,3) NOT NULL DEFAULT 0.000,
  stock_minimo   DECIMAL(10,3) NOT NULL DEFAULT 0.000,
  costo_unitario DECIMAL(10,2) NULL,
  activo         BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT uk_insumos_nombre UNIQUE (nombre),
  CONSTRAINT ck_insumos_cantidades CHECK (existencia >= 0 AND stock_minimo >= 0)
) ENGINE=InnoDB;

-- Lote estándar de producción de cada producto (hoja de proporciones)
CREATE TABLE recetas (
  id_receta   INT AUTO_INCREMENT PRIMARY KEY,
  id_producto INT NOT NULL,
  nombre      VARCHAR(100) NOT NULL,
  rendimiento DECIMAL(10,3) NOT NULL,     -- unidades de venta que produce 1 lote
  costo_lote  DECIMAL(10,2) NOT NULL,
  CONSTRAINT fk_recetas_producto FOREIGN KEY (id_producto) REFERENCES productos(id_producto),
  CONSTRAINT ck_recetas_valores CHECK (rendimiento > 0 AND costo_lote >= 0)
) ENGINE=InnoDB;

-- Insumos que consume 1 lote
CREATE TABLE receta_insumos (
  id_receta INT NOT NULL,
  id_insumo INT NOT NULL,
  cantidad  DECIMAL(10,3) NOT NULL,
  PRIMARY KEY (id_receta, id_insumo),
  CONSTRAINT fk_recins_receta FOREIGN KEY (id_receta) REFERENCES recetas(id_receta) ON DELETE CASCADE,
  CONSTRAINT fk_recins_insumo FOREIGN KEY (id_insumo) REFERENCES insumos(id_insumo),
  CONSTRAINT ck_recins_cantidad CHECK (cantidad > 0)
) ENGINE=InnoDB;

-- Registro de lotes producidos (descuenta insumos y suma producto)
CREATE TABLE producciones (
  id_produccion      INT AUTO_INCREMENT PRIMARY KEY,
  id_receta          INT NOT NULL,
  num_lotes          DECIMAL(10,3) NOT NULL,
  cantidad_producida DECIMAL(10,3) NOT NULL,
  fecha              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  notas              TEXT NULL,
  CONSTRAINT fk_producciones_receta FOREIGN KEY (id_receta) REFERENCES recetas(id_receta),
  CONSTRAINT ck_producciones_valores CHECK (num_lotes > 0 AND cantidad_producida > 0)
) ENGINE=InnoDB;

-- Entradas de insumos por compra
CREATE TABLE compras_insumos (
  id_compra   INT AUTO_INCREMENT PRIMARY KEY,
  id_insumo   INT NOT NULL,
  cantidad    DECIMAL(10,3) NOT NULL,
  costo_total DECIMAL(10,2) NOT NULL,
  proveedor   VARCHAR(120) NULL,
  fecha       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_compras_insumo FOREIGN KEY (id_insumo) REFERENCES insumos(id_insumo),
  CONSTRAINT ck_compras_valores CHECK (cantidad > 0 AND costo_total >= 0)
) ENGINE=InnoDB;

-- Pérdidas de insumo O de producto terminado (solo uno de los dos)
CREATE TABLE mermas (
  id_merma    INT AUTO_INCREMENT PRIMARY KEY,
  id_insumo   INT NULL,
  id_producto INT NULL,
  cantidad    DECIMAL(10,3) NOT NULL,
  motivo      VARCHAR(255) NOT NULL,
  fecha       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_mermas_insumo   FOREIGN KEY (id_insumo)   REFERENCES insumos(id_insumo),
  CONSTRAINT fk_mermas_producto FOREIGN KEY (id_producto) REFERENCES productos(id_producto),
  CONSTRAINT ck_mermas_uno CHECK ((id_insumo IS NULL) <> (id_producto IS NULL)),
  CONSTRAINT ck_mermas_cantidad CHECK (cantidad > 0)
) ENGINE=InnoDB;

-- =====================================================================
--  GRUPO 4. MERCADEO
-- =====================================================================

CREATE TABLE gastos_mercadeo (
  id_gasto  INT AUTO_INCREMENT PRIMARY KEY,
  categoria ENUM('infraestructura','empaque','publicidad_b2c','muestras_b2b',
                 'lead_ads_b2b','referidos_cupones','bono_primer_pedido') NOT NULL,
  concepto  VARCHAR(150) NOT NULL,
  monto     DECIMAL(10,2) NOT NULL,
  fecha     DATE NOT NULL,
  CONSTRAINT ck_gastos_monto CHECK (monto >= 0)
) ENGINE=InnoDB;

-- Metas del documento (fecha_meta NULL = meta permanente)
CREATE TABLE metas (
  id_meta     INT AUTO_INCREMENT PRIMARY KEY,
  indicador   VARCHAR(50)  NOT NULL,
  descripcion VARCHAR(150) NOT NULL,
  valor_meta  DECIMAL(12,2) NOT NULL,
  fecha_meta  DATE NULL,
  CONSTRAINT uk_metas UNIQUE (indicador, fecha_meta)
) ENGINE=InnoDB;

-- =====================================================================
--  DATOS INICIALES
-- =====================================================================

-- Usuarios (contraseñas cifradas con Werkzeug, compatibles con Flask)
--   admin@nixtaguiso.mx   ->  Admin123*
--   judith@ejemplo.com    ->  Cliente123*
--   tacoseltomy@ejemplo.com -> Cliente123*
INSERT INTO usuarios (id_usuario, nombre, correo, telefono, contrasena_hash, rol) VALUES
(1, 'Administrador NixtaGuiso', 'admin@nixtaguiso.mx', '4770000000',
 'pbkdf2:sha256:1000000$FKePZ79oK8IIJDuI$505e96d5870209d8f9ee218e9a0abb473ec96ee97cb4b94c7261b647cb765bbb', 'admin'),
(2, 'Judith Rodríguez', 'judith@ejemplo.com', '4777332626',
 'pbkdf2:sha256:1000000$pCxO2egyCBWRspKr$9af16bfcd590c3ff204f4cea6b564ab5aec95690cc45f384997e17051cbb916d', 'cliente'),
(3, 'Tomás Hernández', 'tacoseltomy@ejemplo.com', '4771234567',
 'pbkdf2:sha256:1000000$3veEoGNvlAaXjoFT$b5152c6ea55ecfad30b230ccd7ee06c8e6494212508fec3f358f80d16115d008', 'cliente');

-- Las coordenadas son ubicaciones de prueba dentro de León, para ver el mapa de rutas
INSERT INTO clientes (id_cliente, id_usuario, tipo, nombre_negocio, rfc, nivel_b2b, direccion, latitud, longitud, codigo_referido) VALUES
(1, 2, 'B2C', NULL, NULL, NULL, 'Colina Santa Julia #205, León, Gto.', 21.134000, -101.674500, 'JUDITH20'),
(2, 3, 'B2B', 'Tacos el Tomy', 'XAXX010101000', 1, 'Bosques de Santa Rita #107, León, Gto.', 21.110500, -101.658000, 'TOMY20');

INSERT INTO categorias (id_categoria, nombre, descripcion, orden) VALUES
(1, 'Derivados de maíz', 'Tortillas, sopes y gorditas de maíz nixtamalizado', 1),
(2, 'Guisados',          'Guisados caseros en envase de 1 L',                  2),
(3, 'Salsas',            'Salsas y guacamole en envase de 100 ml',             3),
(4, 'Lácteos',           'Queso fresco y crema de rancho',                     4),
(5, 'Aguas frescas',     'Aguas naturales en botella de 1 L',                  5);

-- Productos: precios de la sección 7.2 y costo unitario de la tabla de márgenes.
-- Existencia inicial = 1 lote de cada producto, para poder hacer pruebas.
INSERT INTO productos (id_producto, id_categoria, nombre, descripcion, presentacion, kg_por_unidad,
  precio_b2c, precio_b2b_n1, precio_b2b_n2, costo_unitario, existencia) VALUES
(1,  1, 'Tortilla tradicional', 'Tortilla de maíz nixtamalizado, molido en piedra volcánica y cocida en comal.', '1 kg', 1.000, 22.00, 19.80, 18.70, 8.44, 77.000),
(2,  1, 'Tortilla taquera',     'Tortilla de maíz nixtamalizado en tamaño taquero.',                         '1 kg', 1.000, 22.00, 19.80, 18.70, 8.44, 77.000),
(3,  1, 'Sopes',                'Sopes de masa martajada con bordes pellizcados a mano.',                     'Paquete de 10 piezas', 0.850, 25.00, 22.50, 21.25, 9.49, 11.700),
(4,  1, 'Gorditas',             'Gorditas de masa martajada cocidas en comal.',                               'Paquete de 10 piezas', 0.850, 25.00, 22.50, 21.25, 9.49, 11.700),
(5,  2, 'Frijoles',             'Frijoles flor de mayo refritos al estilo casero.',                           '1 L',    1.000, 45.00, 40.50, 38.25, 18.07, 2.850),
(6,  2, 'Nopales',              'Nopales guisados a la mexicana con jitomate, cebolla y chile.',              '1 L',    1.000, 55.00, 49.50, 46.75, 21.95, 13.300),
(7,  2, 'Papas con chorizo',    'Papa blanca con chorizo artesanal.',                                         '1 L',    1.000, 75.00, 67.50, 63.75, 33.00, 10.000),
(8,  2, 'Chicharrón en salsa',  'Chicharrón prensado en salsa de tomate y chile.',                            '1 L',    1.000, 95.00, 85.50, 80.75, 41.00, 10.000),
(9,  3, 'Salsa roja',           'Salsa de jitomate y chile.',                                                 '100 ml', 0.100, 15.00, 13.50, 12.75, 5.00, 118.000),
(10, 3, 'Salsa verde',          'Salsa martajada de tomate verde y chile.',                                   '100 ml', 0.100, 15.00, 13.50, 12.75, 5.00, 118.000),
(11, 3, 'Guacamole',            'Guacamole fresco de aguacate Hass.',                                         '100 ml', 0.100, 25.00, 22.50, 21.25, 9.00, 125.000),
(12, 4, 'Queso fresco',         'Queso fresco artesanal de leche entera.',                                    '250 g',  0.250, 45.00, 40.50, 38.25, 22.72, 18.000),
(13, 4, 'Crema de rancho',      'Crema de rancho sin gomas ni almidones.',                                    '250 ml', 0.250, 38.00, 34.20, 32.30, 19.00, 40.000),
(14, 5, 'Agua de horchata',     'Agua fresca de arroz con canela.',                                           '1 L',    1.000, 28.00, 25.20, 23.80, 9.49, 23.500),
(15, 5, 'Agua de jamaica',      'Agua fresca de flor de jamaica natural.',                                    '1 L',    1.000, 28.00, 25.20, 23.80, 9.49, 23.500),
(16, 5, 'Agua de limón con chía','Agua fresca de limón persa con chía.',                                      '1 L',    1.000, 28.00, 25.20, 23.80, 9.49, 23.500);

-- Paquetes "Comida Completa" (sección 7.3). Solo se vende a clientes Hogar.
-- Costo = suma del costo de sus componentes.
INSERT INTO productos (id_producto, id_categoria, nombre, descripcion, presentacion, kg_por_unidad,
  precio_b2c, precio_b2b_n1, precio_b2b_n2, costo_unitario, existencia, es_paquete) VALUES
(17, NULL, 'Comida Completa con frijoles',           '1 kg de tortilla + 1 L de frijoles + salsa de 100 ml + 1 L de agua fresca.',           'Paquete', 3.100,  99.00,  99.00,  99.00, 41.00, 0, TRUE),
(18, NULL, 'Comida Completa con nopales',            '1 kg de tortilla + 1 L de nopales + salsa de 100 ml + 1 L de agua fresca.',            'Paquete', 3.100, 108.00, 108.00, 108.00, 44.88, 0, TRUE),
(19, NULL, 'Comida Completa con papas con chorizo',  '1 kg de tortilla + 1 L de papas con chorizo + salsa de 100 ml + 1 L de agua fresca.',  'Paquete', 3.100, 126.00, 126.00, 126.00, 55.93, 0, TRUE),
(20, NULL, 'Comida Completa con chicharrón en salsa','1 kg de tortilla + 1 L de chicharrón en salsa + salsa de 100 ml + 1 L de agua fresca.','Paquete', 3.100, 144.00, 144.00, 144.00, 63.93, 0, TRUE);

-- Componentes: tortilla tradicional + guisado + salsa roja + agua de jamaica
INSERT INTO paquete_componentes (id_paquete, id_producto, cantidad) VALUES
(17, 1, 1), (17, 5, 1), (17, 9, 1), (17, 15, 1),
(18, 1, 1), (18, 6, 1), (18, 9, 1), (18, 15, 1),
(19, 1, 1), (19, 7, 1), (19, 9, 1), (19, 15, 1),
(20, 1, 1), (20, 8, 1), (20, 9, 1), (20, 15, 1);

-- Cupón del QR de reorden
INSERT INTO cupones (id_cupon, codigo, descripcion, tipo_descuento, valor, origen) VALUES
(1, 'QR-REORDEN', 'Cupón del QR del empaque para la siguiente compra', 'porcentaje', 10.00, 'qr');

INSERT INTO repartidores (id_repartidor, nombre, telefono, placas) VALUES
(1, 'Sergio González', '4773211998', 'WLU-94-69');

-- Insumos de la hoja de proporciones.
-- Existencias de prueba; aguacate y bolsas QR quedan bajo el mínimo para ver las alertas.
INSERT INTO insumos (id_insumo, nombre, unidad, existencia, stock_minimo, costo_unitario) VALUES
(1,  'Maíz blanco',                 'kg',    150.000,  50.000,  8.50),
(2,  'Cal alimentaria',             'kg',      5.000,   1.000,  NULL),
(3,  'Masa nixtamalizada',          'kg',     30.000,  10.000,  8.50),
(4,  'Manteca / aceite',            'L',       3.000,   1.000,  NULL),
(5,  'Frijol flor de mayo',         'kg',     10.000,   3.000, 35.00),
(6,  'Nopal limpio picado',         'kg',     20.000,  10.000, 18.00),
(7,  'Papa blanca',                 'kg',     12.000,   6.000,  NULL),
(8,  'Chorizo',                     'kg',      5.000,   2.500,  NULL),
(9,  'Chicharrón prensado',         'kg',      6.000,   3.000, 90.00),
(10, 'Jitomate',                    'kg',     20.000,  10.000, 24.50),
(11, 'Tomate verde',                'kg',     20.000,  10.000, 24.50),
(12, 'Aguacate Hass',               'kg',      8.000,  10.000, 80.00),
(13, 'Verduras y condimentos',      'kg',     15.000,   5.000,  NULL),
(14, 'Leche entera',                'L',      80.000,  40.000,  9.00),
(15, 'Crema pura a granel',         'L',      12.000,  10.000, 66.00),
(16, 'Agua purificada',             'L',      60.000,  20.000,  0.90),
(17, 'Arroz',                       'kg',      6.000,   2.800,  NULL),
(18, 'Flor de jamaica',             'kg',      2.000,   0.940,  NULL),
(19, 'Limón persa y chía',          'kg',      7.000,   3.500,  NULL),
(20, 'Azúcar',                      'kg',     10.000,   4.200,  NULL),
(21, 'Bolsa biodegradable con QR',  'pieza', 120.000, 200.000,  NULL),
(22, 'Envase térmico de 1 L',       'pieza',  60.000,  30.000,  NULL),
(23, 'Envase de 100 ml con tapa',   'pieza', 300.000, 150.000,  NULL),
(24, 'Envase de 250 ml',            'pieza',  80.000,  40.000,  NULL),
(25, 'Empaque para queso',          'pieza',  36.000,  18.000,  NULL),
(26, 'Botella de 1 L',              'pieza',  60.000,  23.000,  NULL);

-- Recetas: 1 por producto, con rendimiento y costo de la hoja de proporciones
INSERT INTO recetas (id_receta, id_producto, nombre, rendimiento, costo_lote) VALUES
(1,  1,  'Bulto de maíz 50 kg (tortilla tradicional)',  77.000,  650.00),
(2,  2,  'Bulto de maíz 50 kg (tortilla taquera)',      77.000,  650.00),
(3,  3,  'Masa nixtamalizada 10 kg (sopes)',            11.700,  111.00),
(4,  4,  'Masa nixtamalizada 10 kg (gorditas)',         11.700,  111.00),
(5,  5,  'Frijol flor de mayo 1 kg',                     2.850,   51.50),
(6,  6,  'Nopal limpio 10 kg',                          13.300,  292.00),
(7,  7,  'Papa 6 kg + chorizo 2.5 kg',                  10.000,  330.00),
(8,  8,  'Chicharrón prensado 3 kg',                    10.000,  410.00),
(9,  9,  'Jitomate 10 kg (salsa roja)',                118.000,  590.00),
(10, 10, 'Tomate verde 10 kg (salsa verde)',           118.000,  590.00),
(11, 11, 'Aguacate Hass 10 kg',                        125.000, 1125.00),
(12, 12, 'Leche entera 40 L',                           18.000,  409.00),
(13, 13, 'Crema pura 10 L',                             40.000,  760.00),
(14, 14, 'Agua purificada 20 L (horchata)',             23.500,  223.00),
(15, 15, 'Agua purificada 20 L (jamaica)',              23.500,  223.00),
(16, 16, 'Agua purificada 20 L (limón con chía)',       23.500,  223.00);

-- Insumos por lote (cantidades de la hoja de proporciones)
INSERT INTO receta_insumos (id_receta, id_insumo, cantidad) VALUES
(1, 1, 50.000), (1, 2, 0.750), (1, 21, 77),
(2, 1, 50.000), (2, 2, 0.750), (2, 21, 77),
(3, 3, 10.000), (3, 4, 0.250), (3, 21, 12),
(4, 3, 10.000), (4, 4, 0.250), (4, 21, 12),
(5, 5, 1.000),  (5, 22, 3),
(6, 6, 10.000), (6, 13, 3.300), (6, 22, 13),
(7, 7, 6.000),  (7, 8, 2.500),  (7, 22, 10),
(8, 9, 3.000),  (8, 13, 4.500), (8, 22, 10),
(9, 10, 10.000),(9, 13, 3.000), (9, 23, 118),
(10, 11, 10.000),(10, 13, 3.000),(10, 23, 118),
(11, 12, 10.000),(11, 13, 2.500),(11, 23, 125),
(12, 14, 40.000),(12, 25, 18),
(13, 15, 10.000),(13, 24, 40),
(14, 16, 20.000),(14, 17, 2.800),(14, 20, 2.100),(14, 26, 23),
(15, 16, 20.000),(15, 18, 0.940),(15, 20, 2.100),(15, 26, 23),
(16, 16, 20.000),(16, 19, 3.500),(16, 20, 2.100),(16, 26, 23);

-- Metas del documento (mes 1 de operación = febrero de 2027)
INSERT INTO metas (indicador, descripcion, valor_meta, fecha_meta) VALUES
('kg_mensuales',        'Kilogramos vendidos al mes',                     2000.00, '2027-04-30'),
('kg_mensuales',        'Kilogramos vendidos al mes',                     4000.00, '2027-07-31'),
('kg_mensuales',        'Kilogramos vendidos al mes',                     8000.00, '2028-01-31'),
('negocios_b2b',        'Negocios B2B con pedidos recurrentes',              6.00, '2027-04-30'),
('negocios_b2b',        'Negocios B2B con pedidos recurrentes',             12.00, '2027-07-31'),
('negocios_b2b',        'Negocios B2B con pedidos recurrentes',             25.00, '2028-01-31'),
('usuarios_registrados','Usuarios registrados en la PWA',                  150.00, '2027-04-30'),
('usuarios_registrados','Usuarios registrados en la PWA',                  400.00, '2027-07-31'),
('ticket_b2c',          'Ticket promedio B2C (MXN)',                       115.00, NULL),
('ticket_b2b',          'Ticket promedio B2B por entrega (MXN)',           200.00, NULL),
('conversion',          'Conversión a primer pedido (%)',                   30.00, NULL),
('automatizacion_b2b',  'Clientes B2B con pedido programado (%)',           40.00, NULL),
('escaneos_qr',         'Reórdenes desde el QR al mes',                     40.00, NULL),
('recompra',            'Recompra dentro de 15 días (%)',                   45.00, NULL),
('referidos',           'Referidos concretados al mes',                     10.00, NULL),
('roas',                'Retorno de la inversión publicitaria (ROAS)',       3.00, NULL),
('csat',                'Calificación promedio de servicio',                 4.50, NULL),
('costo_registro',      'Costo publicitario por registro (MXN, máximo)',    40.00, NULL);
