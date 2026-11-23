import { Respuesta } from './respuesta';

export type EstadoPedido = 'pendiente' | 'preparando' | 'en_ruta' | 'entregado' | 'cancelado';
export type EstadoPago = 'pagado' | 'por_validar' | 'rechazado';

export interface LineaCalculo {
  id_producto: number;
  nombre: string;
  presentacion: string;
  cantidad: number;
  precio_unitario: number;
  subtotal: number;
  es_paquete: boolean;
}

export interface Calculo extends Respuesta {
  tarifa: string;
  tipo_cliente: 'B2C' | 'B2B';
  modalidad: 'domicilio' | 'recoger';
  lineas: LineaCalculo[];
  subtotal: number;
  descuento: number;
  motivo_descuento: string | null;
  costo_envio: number;
  saldo_disponible: number;
  saldo_aplicado: number;
  total: number;
  cumple_minimo: boolean;
  mensaje_minimo: string | null;
  faltantes: { id_producto: number; nombre: string; disponible: number; solicitado: number }[];
  puede_confirmar: boolean;
}

export interface DatosPedido {
  productos: { id_producto: number; cantidad: number }[];
  modalidad: 'domicilio' | 'recoger';
  codigo_cupon?: string;
  usar_saldo?: boolean;
  direccion_entrega?: string;
  telefono_contacto?: string;
  latitud?: number | null;
  longitud?: number | null;
  metodo_pago?: 'tarjeta' | 'transferencia';
  tarjeta?: { numero: string; vencimiento: string; cvv: string };
  notas?: string;
}

export interface PedidoCreado extends Respuesta {
  id_pedido: number;
  estado_pago: EstadoPago;
  tiempo_estimado: string;
  total: number;
}

export interface PedidoResumen {
  id_pedido: number;
  fecha_pedido: string;
  estado: EstadoPedido;
  estado_pago: EstadoPago;
  metodo_pago: 'tarjeta' | 'transferencia';
  modalidad: 'domicilio' | 'recoger';
  total: number;
  resumen: string;
  puede_calificar: boolean;
}

export interface ProductoPedido {
  id_producto: number;
  nombre: string;
  presentacion: string;
  cantidad: number;
  precio_unitario: number;
  subtotal: number;
}

export interface PedidoDetalle {
  id_pedido: number;
  fecha_pedido: string;
  estado: EstadoPedido;
  modalidad: 'domicilio' | 'recoger';
  direccion_entrega: string | null;
  latitud: number | null;
  longitud: number | null;
  telefono_contacto: string;
  metodo_pago: 'tarjeta' | 'transferencia';
  estado_pago: EstadoPago;
  tiene_comprobante: boolean;
  subtotal: number;
  descuento: number;
  costo_envio: number;
  saldo_aplicado: number;
  total: number;
  notas: string | null;
  productos: ProductoPedido[];
  repartidor: { nombre: string; telefono: string; placas: string } | null;
  calificacion: { estrellas: number; comentario: string | null } | null;
  puede_calificar: boolean;
}

export interface Notificacion {
  id_notificacion: number;
  titulo: string;
  mensaje: string;
  leida: boolean;
  fecha: string;
}

export interface Programacion {
  id_programacion: number;
  tipo: 'evento' | 'negocio';
  frecuencia: 'unica' | 'semanal';
  fecha_inicio: string;
  hora_desde: string;
  hora_hasta: string;
  direccion_entrega: string;
  notas: string | null;
  estado: 'activa' | 'cancelada' | 'finalizada';
  proxima_entrega: string | null;
  subtotal_estimado: number;
  productos: ProductoPedido[];
}

export interface DatosProgramacion {
  tipo: 'evento' | 'negocio';
  fecha_inicio: string;
  hora_desde: string;
  hora_hasta: string;
  frecuencia: 'unica' | 'semanal';
  direccion_entrega: string;
  notas?: string;
  productos: { id_producto: number; cantidad: number }[];
}

export const NOMBRE_ESTADO: Record<EstadoPedido, string> = {
  pendiente: 'Pendiente',
  preparando: 'Preparando',
  en_ruta: 'En ruta',
  entregado: 'Entregado',
  cancelado: 'Cancelado'
};

export const COLOR_ESTADO: Record<EstadoPedido, string> = {
  pendiente: 'bg-nixta-amarillo text-nixta-cafe',
  preparando: 'bg-nixta-naranja text-nixta-cafe',
  en_ruta: 'bg-nixta-dorado text-white',
  entregado: 'bg-nixta-verde text-white',
  cancelado: 'bg-gray-300 text-gray-700'
};

export const NOMBRE_PAGO: Record<EstadoPago, string> = {
  pagado: 'Pagado',
  por_validar: 'Pago por validar',
  rechazado: 'Pago rechazado'
};
