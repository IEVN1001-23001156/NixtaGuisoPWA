import { Injectable, signal, computed } from '@angular/core';
import { ProductoCatalogo } from './catalogo.service';

export interface ItemCarrito {
  producto: ProductoCatalogo;
  cantidad: number;
  notaEspecial: string;
}

export interface DatosEntrega {
  calle: string;
  colonia: string;
  ciudad: string;
  referencias: string;
}

@Injectable({
  providedIn: 'root',
})
export class CarritoService {
  readonly items = signal<ItemCarrito[]>([]);
  readonly envio = signal<number>(25);
  readonly direccionEntrega = signal<DatosEntrega>(this.cargarDireccionInicial());

  readonly totalArticulos = computed(() =>
    this.items().reduce((acc, item) => acc + item.cantidad, 0)
  );

  readonly subtotal = computed(() =>
    this.items().reduce((acc, item) => acc + item.producto.precio * item.cantidad, 0)
  );

  readonly total = computed(() =>
    this.items().length > 0 ? this.subtotal() + this.envio() : 0
  );

  readonly direccionResumen = computed(() => {
    const d = this.direccionEntrega();
    return [d.calle, d.colonia, d.ciudad].map((v) => v?.trim()).filter(Boolean).join(', ');
  });

  agregarProducto(producto: ProductoCatalogo, cantidad = 1, notaEspecial = ''): void {
    const notaLimpia = notaEspecial.trim();
    this.items.update((actual) => {
      const idx = actual.findIndex(
        (i) => i.producto.id === producto.id && i.notaEspecial === notaLimpia
      );
      if (idx >= 0) {
        const copia = [...actual];
        copia[idx] = {
          ...copia[idx],
          cantidad: copia[idx].cantidad + cantidad,
        };
        return copia;
      }
      return [...actual, { producto, cantidad, notaEspecial: notaLimpia }];
    });
  }

  actualizarCantidad(indice: number, nuevaCantidad: number): void {
    if (nuevaCantidad <= 0) {
      this.eliminarItem(indice);
      return;
    }
    this.items.update((actual) => {
      const copia = [...actual];
      if (copia[indice]) {
        copia[indice] = { ...copia[indice], cantidad: nuevaCantidad };
      }
      return copia;
    });
  }

  eliminarItem(indice: number): void {
    this.items.update((actual) => actual.filter((_, i) => i !== indice));
  }

  establecerDireccion(datos: DatosEntrega, idUsuario?: number | null): void {
    const limpia: DatosEntrega = {
      calle: (datos.calle || '').trim(),
      colonia: (datos.colonia || '').trim(),
      ciudad: (datos.ciudad || 'León, Guanajuato').trim(),
      referencias: (datos.referencias || '').trim(),
    };
    this.direccionEntrega.set(limpia);
    try {
      localStorage.setItem(this.claveDireccion(idUsuario), JSON.stringify(limpia));
    } catch {}
  }

  cargarDireccionUsuario(idUsuario?: number | null): DatosEntrega {
    try {
      const raw = localStorage.getItem(this.claveDireccion(idUsuario));
      if (raw) {
        const parsed = JSON.parse(raw) as Partial<DatosEntrega>;
        const cargada: DatosEntrega = {
          calle: (parsed.calle || '').trim(),
          colonia: (parsed.colonia || '').trim(),
          ciudad: (parsed.ciudad || 'León, Guanajuato').trim(),
          referencias: (parsed.referencias || '').trim(),
        };
        if (cargada.calle || cargada.colonia) {
          this.direccionEntrega.set(cargada);
          return cargada;
        }
      }
    } catch {}
    return this.direccionEntrega();
  }

  vaciar(): void {
    this.items.set([]);
  }

  private cargarDireccionInicial(): DatosEntrega {
    try {
      const keys = Object.keys(localStorage).filter((k) => k.startsWith('nixtaguiso_dir_'));
      for (const k of keys) {
        const raw = localStorage.getItem(k);
        if (raw) {
          const parsed = JSON.parse(raw) as Partial<DatosEntrega>;
          if (parsed.calle || parsed.colonia) {
            return {
              calle: (parsed.calle || '').trim(),
              colonia: (parsed.colonia || '').trim(),
              ciudad: (parsed.ciudad || 'León, Guanajuato').trim(),
              referencias: (parsed.referencias || '').trim(),
            };
          }
        }
      }
    } catch {}
    return {
      calle: '',
      colonia: '',
      ciudad: 'León, Guanajuato',
      referencias: '',
    };
  }

  private claveDireccion(idUsuario?: number | null): string {
    return `nixtaguiso_dir_${idUsuario ?? 'general'}`;
  }
}