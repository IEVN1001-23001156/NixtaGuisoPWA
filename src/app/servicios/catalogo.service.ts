import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { TipoCuenta } from './auth-rol.service';

export interface ProductoCatalogo {
  id: number;
  nombre: string;
  categoria: string;
  idCategoria: number | null;
  esPaquete: boolean;
  precio: number;
  precioB2c: number;
  precioB2bN1: number;
  precioB2bN2: number;
  unidad: string;
  etiqueta: string;
  descripcion: string;
  existencia: number;
  imagenUrl: string | null;
  disponible?: boolean;
  agotado?: boolean;
}

interface RespuestaCatalogo {
  exito?: boolean;
  productos?: Record<string, unknown>[];
  datos?: Record<string, unknown>[];
}

const NOMBRES_CATEGORIA: Record<number, string> = {
  1: 'Derivados de maíz',
  2: 'Guisados',
  3: 'Salsas',
  4: 'Lácteos',
  5: 'Aguas frescas',
};

@Injectable({
  providedIn: 'root',
})
export class CatalogoService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = 'http://localhost:5000/api/catalogo';

  readonly productosRespaldo: ProductoCatalogo[] = [
    {
      id: 1,
      nombre: 'Tortilla tradicional',
      categoria: 'Derivados de maíz',
      idCategoria: 1,
      esPaquete: false,
      precio: 22,
      precioB2c: 22,
      precioB2bN1: 19.8,
      precioB2bN2: 18.7,
      unidad: '1 kg',
      etiqueta: '1 kg',
      descripcion: 'Tortilla de maíz nixtamalizado, molido en piedra.',
      existencia: 77,
      imagenUrl: null,
    },
    {
      id: 2,
      nombre: 'Tortilla taquera',
      categoria: 'Derivados de maíz',
      idCategoria: 1,
      esPaquete: false,
      precio: 22,
      precioB2c: 22,
      precioB2bN1: 19.8,
      precioB2bN2: 18.7,
      unidad: '1 kg',
      etiqueta: '1 kg',
      descripcion: 'Tortilla de maíz nixtamalizado en tamaño taquero.',
      existencia: 77,
      imagenUrl: null,
    },
    {
      id: 3,
      nombre: 'Sopes',
      categoria: 'Derivados de maíz',
      idCategoria: 1,
      esPaquete: false,
      precio: 25,
      precioB2c: 25,
      precioB2bN1: 22.5,
      precioB2bN2: 21.25,
      unidad: 'Paquete de 10 piezas',
      etiqueta: 'Paquete de 10 piezas',
      descripcion: 'Sopes de masa martajada con bordes pellizcados.',
      existencia: 11.7,
      imagenUrl: null,
    },
    {
      id: 4,
      nombre: 'Gorditas',
      categoria: 'Derivados de maíz',
      idCategoria: 1,
      esPaquete: false,
      precio: 25,
      precioB2c: 25,
      precioB2bN1: 22.5,
      precioB2bN2: 21.25,
      unidad: 'Paquete de 10 piezas',
      etiqueta: 'Paquete de 10 piezas',
      descripcion: 'Gorditas de masa martajada cocidas en comal.',
      existencia: 11.7,
      imagenUrl: null,
    },
    {
      id: 5,
      nombre: 'Frijoles',
      categoria: 'Guisados',
      idCategoria: 2,
      esPaquete: false,
      precio: 45,
      precioB2c: 45,
      precioB2bN1: 40.5,
      precioB2bN2: 38.25,
      unidad: '1 L',
      etiqueta: '1 L',
      descripcion: 'Frijoles flor de mayo refritos al estilo casero.',
      existencia: 2.85,
      imagenUrl: null,
    },
    {
      id: 6,
      nombre: 'Nopales',
      categoria: 'Guisados',
      idCategoria: 2,
      esPaquete: false,
      precio: 55,
      precioB2c: 55,
      precioB2bN1: 49.5,
      precioB2bN2: 46.75,
      unidad: '1 L',
      etiqueta: '1 L',
      descripcion: 'Nopales guisados a la mexicana con jitomate y cebolla.',
      existencia: 13.3,
      imagenUrl: null,
    },
    {
      id: 7,
      nombre: 'Papas con chorizo',
      categoria: 'Guisados',
      idCategoria: 2,
      esPaquete: false,
      precio: 75,
      precioB2c: 75,
      precioB2bN1: 67.5,
      precioB2bN2: 63.75,
      unidad: '1 L',
      etiqueta: '1 L',
      descripcion: 'Papa blanca con chorizo artesanal.',
      existencia: 10,
      imagenUrl: null,
    },
    {
      id: 8,
      nombre: 'Chicharrón en salsa',
      categoria: 'Guisados',
      idCategoria: 2,
      esPaquete: false,
      precio: 95,
      precioB2c: 95,
      precioB2bN1: 85.5,
      precioB2bN2: 80.75,
      unidad: '1 L',
      etiqueta: '1 L',
      descripcion: 'Chicharrón prensado en salsa de tomate y chile.',
      existencia: 10,
      imagenUrl: null,
    },
    {
      id: 9,
      nombre: 'Salsa roja',
      categoria: 'Salsas',
      idCategoria: 3,
      esPaquete: false,
      precio: 15,
      precioB2c: 15,
      precioB2bN1: 13.5,
      precioB2bN2: 12.75,
      unidad: '100 ml',
      etiqueta: '100 ml',
      descripcion: 'Salsa de jitomate y chile.',
      existencia: 118,
      imagenUrl: null,
    },
    {
      id: 10,
      nombre: 'Salsa verde',
      categoria: 'Salsas',
      idCategoria: 3,
      esPaquete: false,
      precio: 15,
      precioB2c: 15,
      precioB2bN1: 13.5,
      precioB2bN2: 12.75,
      unidad: '100 ml',
      etiqueta: '100 ml',
      descripcion: 'Salsa martajada de tomate verde y chile.',
      existencia: 118,
      imagenUrl: null,
    },
    {
      id: 11,
      nombre: 'Guacamole',
      categoria: 'Salsas',
      idCategoria: 3,
      esPaquete: false,
      precio: 25,
      precioB2c: 25,
      precioB2bN1: 22.5,
      precioB2bN2: 21.25,
      unidad: '100 ml',
      etiqueta: '100 ml',
      descripcion: 'Guacamole fresco de aguacate Hass.',
      existencia: 125,
      imagenUrl: null,
    },
    {
      id: 12,
      nombre: 'Queso fresco',
      categoria: 'Lácteos',
      idCategoria: 4,
      esPaquete: false,
      precio: 45,
      precioB2c: 45,
      precioB2bN1: 40.5,
      precioB2bN2: 38.25,
      unidad: '250 g',
      etiqueta: '250 g',
      descripcion: 'Queso fresco artesanal de leche entera.',
      existencia: 18,
      imagenUrl: null,
    },
    {
      id: 13,
      nombre: 'Crema de rancho',
      categoria: 'Lácteos',
      idCategoria: 4,
      esPaquete: false,
      precio: 38,
      precioB2c: 38,
      precioB2bN1: 34.2,
      precioB2bN2: 32.3,
      unidad: '250 ml',
      etiqueta: '250 ml',
      descripcion: 'Crema de rancho sin gomas ni almidones.',
      existencia: 40,
      imagenUrl: null,
    },
    {
      id: 14,
      nombre: 'Agua de horchata',
      categoria: 'Aguas frescas',
      idCategoria: 5,
      esPaquete: false,
      precio: 28,
      precioB2c: 28,
      precioB2bN1: 25.2,
      precioB2bN2: 23.8,
      unidad: '1 L',
      etiqueta: '1 L',
      descripcion: 'Agua fresca de arroz con canela.',
      existencia: 23.5,
      imagenUrl: null,
    },
    {
      id: 15,
      nombre: 'Agua de jamaica',
      categoria: 'Aguas frescas',
      idCategoria: 5,
      esPaquete: false,
      precio: 28,
      precioB2c: 28,
      precioB2bN1: 25.2,
      precioB2bN2: 23.8,
      unidad: '1 L',
      etiqueta: '1 L',
      descripcion: 'Agua fresca de flor de jamaica natural.',
      existencia: 23.5,
      imagenUrl: null,
    },
    {
      id: 16,
      nombre: 'Agua de limón con chía',
      categoria: 'Aguas frescas',
      idCategoria: 5,
      esPaquete: false,
      precio: 28,
      precioB2c: 28,
      precioB2bN1: 25.2,
      precioB2bN2: 23.8,
      unidad: '1 L',
      etiqueta: '1 L',
      descripcion: 'Agua fresca de limón persa con chía.',
      existencia: 23.5,
      imagenUrl: null,
    },
    {
      id: 17,
      nombre: 'Comida Completa con frijoles',
      categoria: 'Combos / Paquetes',
      idCategoria: null,
      esPaquete: true,
      precio: 99,
      precioB2c: 99,
      precioB2bN1: 99,
      precioB2bN2: 99,
      unidad: 'Paquete',
      etiqueta: 'Paquete',
      descripcion: '1 kg de tortilla + 1 L de frijoles + salsa de 100 ml.',
      existencia: 0,
      imagenUrl: null,
    },
    {
      id: 18,
      nombre: 'Comida Completa con nopales',
      categoria: 'Combos / Paquetes',
      idCategoria: null,
      esPaquete: true,
      precio: 108,
      precioB2c: 108,
      precioB2bN1: 108,
      precioB2bN2: 108,
      unidad: 'Paquete',
      etiqueta: 'Paquete',
      descripcion: '1 kg de tortilla + 1 L de nopales + salsa de 100 ml.',
      existencia: 0,
      imagenUrl: null,
    },
    {
      id: 19,
      nombre: 'Comida Completa con papas con chorizo',
      categoria: 'Combos / Paquetes',
      idCategoria: null,
      esPaquete: true,
      precio: 126,
      precioB2c: 126,
      precioB2bN1: 126,
      precioB2bN2: 126,
      unidad: 'Paquete',
      etiqueta: 'Paquete',
      descripcion: '1 kg de tortilla + 1 L de papas con chorizo + salsa.',
      existencia: 0,
      imagenUrl: null,
    },
    {
      id: 20,
      nombre: 'Comida Completa con chicharrón en salsa',
      categoria: 'Combos / Paquetes',
      idCategoria: null,
      esPaquete: true,
      precio: 144,
      precioB2c: 144,
      precioB2bN1: 144,
      precioB2bN2: 144,
      unidad: 'Paquete',
      etiqueta: 'Paquete',
      descripcion: '1 kg de tortilla + 1 L de chicharrón en salsa + salsa.',
      existencia: 0,
      imagenUrl: null,
    },
  ];

  async obtenerProductos(
    tipoCuenta: TipoCuenta,
    nivelB2b: number | null = 1
  ,
    incluirPausados = false): Promise<ProductoCatalogo[]> {
    const params = new URLSearchParams();
    if (tipoCuenta) {
      params.set('tipo', tipoCuenta);
    }
    if (nivelB2b) {
      params.set('nivel_b2b', String(nivelB2b));
    }
    const query = params.toString() ? `?${params.toString()}` : '';

    try {
      const resp = await firstValueFrom(
        this.http.get<RespuestaCatalogo | Record<string, unknown>[]>(
          `${this.apiUrl}${query}`,
          { withCredentials: true }
        )
      );

      const listaCruda = Array.isArray(resp)
        ? resp
        : resp.productos ?? resp.datos ?? [];

      if (!Array.isArray(listaCruda) || listaCruda.length === 0) {
        return this.productosRespaldo.map((p) =>
          this.aplicarPrecioPorCuenta(p, tipoCuenta, nivelB2b)
        );
      }

      return listaCruda
        .filter((fila) => {
          const activo = fila['activo'] === undefined ? true : Boolean(fila['activo']);
          const disponible = fila['disponible'] === undefined ? true : Boolean(fila['disponible']);
          return activo;
        })
        .map((fila, idx) => this.normalizarProducto(fila, idx + 1, tipoCuenta, nivelB2b));
    } catch {
      return this.productosRespaldo.map((p) =>
        this.aplicarPrecioPorCuenta(p, tipoCuenta, nivelB2b)
      );
    }
  }

  async obtenerProductoPorId(
    id: number,
    tipoCuenta: TipoCuenta,
    nivelB2b: number | null = 1
  ): Promise<ProductoCatalogo | null> {
    try {
      const resp = await firstValueFrom(
        this.http.get<{ exito?: boolean; producto?: Record<string, unknown> }>(
          `${this.apiUrl}/${id}`,
          { withCredentials: true }
        )
      );
      if (resp?.exito && resp.producto) {
        return this.normalizarProducto(resp.producto, id, tipoCuenta, nivelB2b);
      }
    } catch {
      const respaldo = this.productosRespaldo.find((p) => p.id === id);
      if (respaldo) {
        return this.aplicarPrecioPorCuenta(respaldo, tipoCuenta, nivelB2b);
      }
    }
    const respaldo = this.productosRespaldo.find((p) => p.id === id);
    return respaldo ? this.aplicarPrecioPorCuenta(respaldo, tipoCuenta, nivelB2b) : null;
  }

  resolverUrlImagen(imagenUrl: string | null): string {
    if (!imagenUrl || !imagenUrl.trim()) {
      return '/Isotipo.png';
    }
    const limpia = imagenUrl.trim();
    if (limpia.startsWith('http://') || limpia.startsWith('https://')) {
      return limpia;
    }
    // Las fotos subidas viven en Flask (/uploads/productos/...), no en Angular
    if (limpia.startsWith('/uploads/')) {
      return `http://localhost:5000${limpia}`;
    }
    if (limpia.startsWith('/')) {
      return limpia;
    }
    return `http://localhost:5000/uploads/productos/${limpia.replace(/^uploads\/productos\//, '')}`;
  }

  private aplicarPrecioPorCuenta(
    prod: ProductoCatalogo,
    tipoCuenta: TipoCuenta,
    nivelB2b: number | null
  ): ProductoCatalogo {
    let precioCalculado = prod.precioB2c;
    if (tipoCuenta === 'B2B') {
      precioCalculado = nivelB2b === 2 ? prod.precioB2bN2 : prod.precioB2bN1;
    }
    return {
      ...prod,
      precio: precioCalculado,
    };
  }

  private normalizarProducto(
    fila: Record<string, unknown>,
    fallbackId: number,
    tipoCuenta: TipoCuenta,
    nivelB2b: number | null
  ): ProductoCatalogo {
    const idCategoriaRaw = fila['id_categoria'];
    const idCategoria =
      idCategoriaRaw === null || idCategoriaRaw === undefined || idCategoriaRaw === ''
        ? null
        : Number(idCategoriaRaw);
    const esPaquete = Boolean(fila['es_paquete']) || idCategoria === null;

    const categoriaTexto = fila['categoria']
      ? String(fila['categoria'])
      : esPaquete
      ? 'Combos / Paquetes'
      : idCategoria !== null && NOMBRES_CATEGORIA[idCategoria]
      ? NOMBRES_CATEGORIA[idCategoria]
      : 'General';

    const precioB2c = Number(fila['precio_b2c'] ?? fila['precio'] ?? 0);
    const precioB2bN1 = Number(fila['precio_b2b_n1'] ?? precioB2c);
    const precioB2bN2 = Number(fila['precio_b2b_n2'] ?? precioB2bN1);

    let precioFinal = precioB2c;
    if (tipoCuenta === 'B2B') {
      precioFinal = nivelB2b === 2 ? precioB2bN2 : precioB2bN1;
    }

    const presentacion = String(
      fila['presentacion'] ?? fila['unidad'] ?? (esPaquete ? 'Paquete' : 'Unidad')
    );
    const imagenUrlRaw = fila['imagen_url'] ?? fila['imagen'] ?? null;

    return {
      id: Number(fila['id_producto'] ?? fila['id'] ?? fallbackId),
      nombre: String(fila['nombre'] ?? 'Producto NixtaGuiso'),
      categoria: categoriaTexto,
      idCategoria,
      esPaquete,
      precio: precioFinal,
      precioB2c,
      precioB2bN1,
      precioB2bN2,
      unidad: presentacion,
      etiqueta: presentacion,
      descripcion: String(fila['descripcion'] ?? ''),
      existencia: Number(fila['existencia'] ?? 0),
      disponible: fila['disponible'] === undefined ? true : Boolean(fila['disponible']),
      agotado: Boolean(fila['agotado']),
      imagenUrl: imagenUrlRaw ? String(imagenUrlRaw) : null,
    };
  }
}