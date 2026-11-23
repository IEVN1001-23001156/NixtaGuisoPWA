import { EstadoPago, EstadoPedido } from './pedidos';

export interface Tarjetas {
  ventas_dia: number; pedidos_dia: number; ticket_promedio_dia: number | null; kg_vendidos_dia: number;
  pedidos_activos: number; usuarios_registrados: number; clientes_b2c: number; clientes_b2b: number;
}
export interface Dashboard {
  fecha: string;
  tarjetas: Tarjetas;
  grafica: { etiquetas: string[]; b2c: number[]; b2b: number[]; participacion_b2b: number | null };
  mas_vendidos: { nombre: string; presentacion: string; cantidad: number; importe: number }[];
  alertas: { tipo: 'insumo' | 'producto' | 'pago'; mensaje: string }[];
}
export interface Metrica {
  indicador: string; nombre: string; valor: number | null; meta: number | null;
  fecha_meta: string | null; unidad: string; cumple: boolean | null;
}
export interface Reporte {
  mes: string;
  resumen: { ventas_mes: number; ventas_b2c: number; ventas_b2b: number; pedidos_mes: number; nuevos_registros: number;
             gasto_mercadeo: number; metas_cumplidas: number; metas_evaluadas: number };
  grupos: { grupo: string; metricas: Metrica[] }[];
}
export interface Gasto { id_gasto: number; categoria: string; concepto: string; monto: number; fecha: string; }
export interface Meta { id_meta: number; indicador: string; descripcion: string; valor_meta: number; fecha_meta: string | null; }

export interface ProductoAdmin {
  id_producto: number; id_categoria: number | null; categoria: string; nombre: string; descripcion: string | null;
  presentacion: string; kg_por_unidad: number; precio_b2c: number; precio_b2b_n1: number; precio_b2b_n2: number;
  costo_unitario: number; margen_b2c: number; existencia: number; imagen_url: string | null;
  es_paquete: boolean; disponible: boolean; componentes?: { id_producto: number; nombre: string; presentacion: string; cantidad: number }[];
}

export interface ClienteResumen {
  id_cliente: number; nombre: string; nombre_negocio: string | null; correo: string; telefono: string;
  tipo: 'B2C' | 'B2B'; nivel_b2b: number | null; activo: boolean; fecha_registro: string;
  total_pedidos: number; total_comprado: number; ultimo_pedido: string | null; frecuencia: string;
}
export interface ClienteFicha extends ClienteResumen {
  rfc: string | null; direccion: string | null; latitud: number | null; longitud: number | null;
  preferencias: string | null; saldo_favor: number; codigo_referido: string; referido_por: string | null;
  invitados: number; programaciones_activas: number; calificacion_promedio: number | null;
  historial: { id_pedido: number; fecha_pedido: string; estado: EstadoPedido; estado_pago: EstadoPago; total: number }[];
}

export interface Repartidor { id_repartidor: number; nombre: string; telefono: string; placas: string; activo: boolean; pedidos_en_ruta: number; }

export interface Insumo {
  id_insumo: number; nombre: string; unidad: 'kg' | 'L' | 'pieza'; existencia: number; stock_minimo: number;
  costo_unitario: number | null; valor_inventario: number | null; estado: 'optimo' | 'por_surtir';
}
export interface Receta {
  id_receta: number; nombre: string; id_producto: number; producto: string; presentacion: string;
  rendimiento: number; costo_lote: number; existencia_producto: number; lotes_posibles: number;
  insumos: { nombre: string; unidad: string; cantidad_por_lote: number; existencia: number }[];
}
export interface Compra { id_compra: number; fecha: string; insumo: string; unidad: string; cantidad: number; costo_total: number; proveedor: string | null; }
export interface Produccion { id_produccion: number; fecha: string; receta: string; producto: string; presentacion: string; num_lotes: number; cantidad_producida: number; costo: number; notas: string | null; }
export interface Merma { id_merma: number; fecha: string; tipo: 'insumo' | 'producto'; nombre: string; cantidad: number; unidad: string; motivo: string; costo_estimado: number; }

export interface PedidoAdmin {
  id_pedido: number; fecha_pedido: string; cliente: string; tipo_cliente: 'B2C' | 'B2B'; estado: EstadoPedido;
  estado_pago: EstadoPago; metodo_pago: 'tarjeta' | 'transferencia'; tiene_comprobante: boolean;
  modalidad: 'domicilio' | 'recoger'; direccion_entrega: string | null; total: number; repartidor: string | null;
  programado: boolean; resumen: string; siguientes_estados: EstadoPedido[];
}
export interface PedidoAdminDetalle {
  id_pedido: number; fecha_pedido: string; cliente: string; nombre_negocio: string | null; tipo_cliente: 'B2C' | 'B2B';
  preferencias: string | null; estado: EstadoPedido; siguientes_estados: EstadoPedido[]; modalidad: 'domicilio' | 'recoger';
  direccion_entrega: string | null; latitud: number | null; longitud: number | null; orden_ruta: number | null;
  telefono_contacto: string; metodo_pago: 'tarjeta' | 'transferencia'; estado_pago: EstadoPago; tiene_comprobante: boolean;
  subtotal: number; descuento: number; costo_envio: number; saldo_aplicado: number; total: number; notas: string | null;
  programado: boolean; repartidor: { id_repartidor: number; nombre: string; telefono: string; placas: string } | null;
  productos: { nombre: string; presentacion: string; cantidad: number; precio_unitario: number; subtotal: number }[];
}

export interface Parada {
  id_pedido: number; orden_ruta: number | null; cliente: string; tipo_cliente: string; direccion_entrega: string | null;
  telefono_contacto: string; latitud: number | null; longitud: number | null; estado: EstadoPedido; total: number; notas: string | null;
}
export interface Ruta {
  id_repartidor: number; repartidor: string; telefono: string; placas: string;
  paradas: Parada[]; total_paradas: number; entregadas: number;
}
