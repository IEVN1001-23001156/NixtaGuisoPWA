import { Respuesta } from './respuesta';

export interface Categoria {
  id_categoria: number;
  nombre: string;
  descripcion: string | null;
  total_productos: number;
}

export interface Producto {
  id_producto: number;
  id_categoria: number;
  categoria: string;
  nombre: string;
  descripcion: string | null;
  presentacion: string;
  precio: number;        
  precio_b2c: number;   
  imagen_url: string | null;
  agotado: boolean;
  favorito: boolean;
}

export interface ComponentePaquete {
  id_producto: number;
  nombre: string;
  presentacion: string;
  cantidad: number;
}

export interface Paquete {
  id_producto: number;
  nombre: string;
  descripcion: string | null;
  precio: number;
  precio_por_separado: number;
  ahorro: number;
  imagen_url: string | null;
  agotado: boolean;
  componentes: ComponentePaquete[];
}

export interface RespuestaCategorias extends Respuesta {
  categorias: Categoria[];
}

export interface RespuestaProductos extends Respuesta {
  tarifa: string;
  total: number;
  productos: Producto[];
}

export interface RespuestaProducto extends Respuesta {
  tarifa: string;
  producto: Producto;
}

export interface RespuestaPaquetes extends Respuesta {
  paquetes: Paquete[];
}

export interface RespuestaFavoritos extends Respuesta {
  tarifa: string;
  favoritos: Producto[];
}
