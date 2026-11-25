import { Injectable, signal, computed, effect, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { ProductoCatalogo } from './catalogo.service';

export interface ItemCarrito {
  producto: ProductoCatalogo;
  cantidad: number;
  notaEspecial: string;
  salsa?: number | null;
  agua?: number | null;
  opcionesTexto?: string;
  arma?: ArmaPaquete;
}

export interface ArmaPaquete {
  tortilla: number;
  guisado: number;
  salsa: number;
  agua: number;
  texto: string;
}

export interface OpcionesPaquete {
  salsa: number | null;
  agua: number | null;
  texto: string;
}

export interface DatosEntrega {
  calle: string;
  colonia: string;
  ciudad: string;
  referencias: string;
}

interface CalculoServidor {
  exito: boolean;
  mensaje?: string;
  subtotal: number;
  descuento: number;
  motivo_descuento: string | null;
  costo_envio: number;
  total: number;
  cumple_minimo: boolean;
  mensaje_minimo: string | null;
  faltantes: { nombre: string; disponible?: number; solicitado?: number }[];
  puede_confirmar: boolean;
}

@Injectable({
  providedIn: 'root',
})
export class CarritoService {
  private readonly usuarioActivoId = signal<number | null>(null);
  readonly items = signal<ItemCarrito[]>(this.leerCarritoGuardado(null));

  private readonly guardarCarrito = effect(() => {
    const id = this.usuarioActivoId();
    const lista = this.items();
    try {
      localStorage.setItem(this.claveCarrito(id), JSON.stringify(lista));
    } catch {
      // Si el navegador no permite guardar, el carrito dura mientras la página esté abierta
    }
  });

  private claveCarrito(idUsuario: number | null): string {
    return `nixtaguiso_carrito_${idUsuario ?? 'invitado'}`;
  }

  private leerCarritoGuardado(idUsuario: number | null): ItemCarrito[] {
    try {
      const guardado = JSON.parse(localStorage.getItem(this.claveCarrito(idUsuario)) || '[]');
      return Array.isArray(guardado) ? guardado : [];
    } catch {
      return [];
    }
  }

  private readonly http = inject(HttpClient);

  readonly calculo = signal<CalculoServidor | null>(null);
  private esperaCalculo?: ReturnType<typeof setTimeout>;

  private readonly recalcular = effect(() => {
    const items = this.items();
    clearTimeout(this.esperaCalculo);
    if (items.length === 0) {
      this.calculo.set(null);
      return;
    }
    this.esperaCalculo = setTimeout(() => {
      this.http
        .post<CalculoServidor>(
          'http://localhost:5000/api/pedidos/calcular',
          {
            productos: items.map((i) => ({
              id_producto: i.producto.id,
              cantidad: i.cantidad,
              salsa: i.salsa,
              agua: i.agua,
              arma: i.arma,
            })),
            modalidad: 'domicilio',
          },
          { withCredentials: true }
        )
        .subscribe({
          next: (r) => this.calculo.set(r),
          error: (e) =>
            this.calculo.set({ exito: false, mensaje: e?.error?.mensaje } as CalculoServidor),
        });
    }, 300);
  });

  readonly envio = computed(() => this.calculo()?.costo_envio ?? 30);
  readonly descuento = computed(() => this.calculo()?.descuento ?? 0);
  readonly motivoDescuento = computed(() => this.calculo()?.motivo_descuento ?? null);
  readonly avisoServidor = computed(() => {
    const c = this.calculo();
    if (!c) return null;
    if (c.exito === false) return c.mensaje || 'No se pudo calcular el total';
    if (!c.cumple_minimo) return c.mensaje_minimo;
    if (c.faltantes?.length) {
      return `Sin existencia suficiente de: ${c.faltantes.map((f) => f.nombre).join(', ')}`;
    }
    return null;
  });
  readonly puedeConfirmar = computed(() => !!this.calculo()?.puede_confirmar);
  readonly direccionEntrega = signal<DatosEntrega>(this.cargarDireccionInicial());

  readonly totalArticulos = computed(() =>
    this.items().reduce((acc, item) => acc + item.cantidad, 0)
  );

  readonly subtotal = computed(() => {
    const c = this.calculo();
    if (c?.exito !== false && c?.subtotal !== undefined) return c.subtotal;
    return this.items().reduce((acc, item) => acc + item.producto.precio * item.cantidad, 0);
  });

  readonly total = computed(() => {
    if (this.items().length === 0) return 0;
    const c = this.calculo();
    return c?.exito !== false && c?.total !== undefined ? c.total : this.subtotal() + this.envio();
  });

  readonly direccionResumen = computed(() => {
    const d = this.direccionEntrega();
    return [d.calle, d.colonia, d.ciudad].map((v) => v?.trim()).filter(Boolean).join(', ');
  });

  async validarDisponibilidadAdicion(
    producto: ProductoCatalogo,
    cantidadExtra: number,
    opciones?: OpcionesPaquete,
    arma?: ArmaPaquete,
    soloProducto = false
  ): Promise<{ ok: boolean; mensaje?: string }> {
    const mismosEnCarrito = soloProducto
      ? []
      : this.items()
          .filter((i) => i.producto.id === producto.id)
          .map((i) => ({
            id_producto: i.producto.id,
            cantidad: i.cantidad,
            salsa: i.salsa ?? null,
            agua: i.agua ?? null,
            arma: i.arma ?? null,
          }));

    const simulados = [
      ...mismosEnCarrito,
      {
        id_producto: producto.id,
        cantidad: cantidadExtra,
        salsa: opciones?.salsa ?? null,
        agua: opciones?.agua ?? null,
        arma: arma ?? null,
      },
    ];

    try {
      const resp = await firstValueFrom(
        this.http.post<CalculoServidor>(
          'http://localhost:5000/api/pedidos/calcular',
          { productos: simulados, modalidad: 'domicilio' },
          { withCredentials: true }
        )
      );

      if (resp.exito === false) {
        return { ok: false, mensaje: resp.mensaje || 'No se pudo verificar la existencia.' };
      }
      if (resp.faltantes && resp.faltantes.length > 0) {
        const nombres = resp.faltantes.map((f) => f.nombre).join(', ');
        return {
          ok: false,
          mensaje: `Existencia/insumos insuficientes para esa cantidad (faltantes: ${nombres}).`,
        };
      }
      return { ok: true };
    } catch (err: any) {
      return {
        ok: false,
        mensaje: err?.error?.mensaje || 'No se pudo validar la existencia disponible.',
      };
    }
  }

  cargarCarritoUsuario(idUsuario: number | null): void {
    const idAnterior = this.usuarioActivoId();
    if (idAnterior === idUsuario) return;

    const itemsInvitado = idAnterior === null && idUsuario !== null ? this.items() : [];
    const itemsGuardados = this.leerCarritoGuardado(idUsuario);

    this.usuarioActivoId.set(idUsuario);
    this.items.set(itemsGuardados);
    this.cargarDireccionUsuario(idUsuario);

    if (itemsInvitado.length > 0) {
      for (const item of itemsInvitado) {
        this.agregarProducto(
          item.producto,
          item.cantidad,
          item.notaEspecial,
          { salsa: item.salsa ?? null, agua: item.agua ?? null, texto: item.opcionesTexto ?? '' },
          item.arma
        );
      }
      try {
        localStorage.removeItem(this.claveCarrito(null));
      } catch {}
    }
  }

  agregarProducto(
    producto: ProductoCatalogo,
    cantidad = 1,
    notaEspecial = '',
    opciones?: OpcionesPaquete,
    arma?: ArmaPaquete
  ): void {
    const notaLimpia = notaEspecial.trim();
    const salsa = opciones?.salsa ?? null;
    const agua = opciones?.agua ?? null;
    this.items.update((actual) => {
      const idx = actual.findIndex(
        (i) =>
          i.producto.id === producto.id &&
          i.notaEspecial === notaLimpia &&
          (i.salsa ?? null) === salsa &&
          (i.agua ?? null) === agua &&
          JSON.stringify(i.arma ?? null) === JSON.stringify(arma ?? null)
      );
      if (idx >= 0) {
        const copia = [...actual];
        copia[idx] = {
          ...copia[idx],
          cantidad: copia[idx].cantidad + cantidad,
        };
        return copia;
      }
      return [
        ...actual,
        {
          producto,
          cantidad,
          notaEspecial: notaLimpia,
          salsa,
          agua,
          opcionesTexto: arma?.texto ?? opciones?.texto,
          arma,
        },
      ];
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
    const idDestino = idUsuario ?? this.usuarioActivoId();
    try {
      localStorage.setItem(this.claveDireccion(idDestino), JSON.stringify(limpia));
      if (idDestino !== null && idDestino !== undefined) {
        localStorage.setItem(this.claveDireccion(null), JSON.stringify(limpia));
      }
    } catch {}
  }

  cargarDireccionUsuario(idUsuario?: number | null): DatosEntrega {
    const idConsulta = idUsuario ?? this.usuarioActivoId();
    try {
      const raw =
        localStorage.getItem(this.claveDireccion(idConsulta)) ||
        localStorage.getItem(this.claveDireccion(null));
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