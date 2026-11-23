import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { BarraSuperior } from '../../../compartidos/barra-superior/barra-superior';
import { MenuLateral } from '../../../compartidos/menu-lateral/menu-lateral';

interface ProductoInventario {
  id: number;
  nombre: string;
  categoria: string;
  existencia: number;
  presentacion: string;
  optimo: boolean;
  cantidadAjuste: number;
}

interface RegistroMerma {
  id: number;
  fecha: string;
  producto: string;
  cantidadPerdida: string;
  motivo: string;
}

interface RespuestaInventarioBd {
  exito?: boolean;
  productos?: {
    id_producto: number;
    nombre: string;
    presentacion: string;
    categoria: string;
    existencia: number;
  }[];
  mermas?: {
    id_merma: number;
    fecha: string;
    cantidad: number;
    motivo: string;
  }[];
}

@Component({
  imports: [FormsModule, RouterLink, BarraSuperior, MenuLateral],
  selector: 'app-control-inventario',
  styleUrl: './control-inventario.css',
  templateUrl: './control-inventario.html',
})
export class ControlInventario implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly apiBase = 'http://localhost:5000/api/inventario';

  menuAbierto = false;
  pestana: 'stock' | 'mermas' = 'stock';
  cargando = signal<boolean>(true);
  mensajeEstado = signal<string>('');
  errorMensaje = signal<string>('');

  productoMermaId = 1;
  cantidadMerma: number | null = null;
  motivoMerma = 'Caducidad / Merma operativa';

  productos = signal<ProductoInventario[]>([]);
  mermasMes = signal<RegistroMerma[]>([]);

  async ngOnInit(): Promise<void> {
    await this.cargarProductosDesdeBd();
  }

  async cargarProductosDesdeBd(): Promise<void> {
    this.cargando.set(true);
    this.errorMensaje.set('');
    try {
      const resp = await firstValueFrom(
        this.http.get<RespuestaInventarioBd>(`${this.apiBase}/productos`, {
          withCredentials: true,
        })
      );
      if (resp?.exito && Array.isArray(resp.productos)) {
        const mapeados: ProductoInventario[] = resp.productos.map((p) => {
          const ext = Number(p.existencia ?? 0);
          return {
            id: p.id_producto,
            nombre: p.nombre,
            categoria: p.categoria || 'General',
            existencia: ext,
            presentacion: p.presentacion || 'Unidad',
            optimo: ext >= 15,
            cantidadAjuste: 10,
          };
        });
        this.productos.set(mapeados);
        if (mapeados.length > 0 && !mapeados.some((m) => m.id === this.productoMermaId)) {
          this.productoMermaId = mapeados[0].id;
        }
      }

      if (resp?.exito && Array.isArray(resp.mermas)) {
        this.mermasMes.set(
          resp.mermas.map((m) => ({
            id: m.id_merma,
            fecha: m.fecha,
            producto: (m as any).producto || 'Producto en inventario',
            cantidadPerdida: `${m.cantidad}`,
            motivo: m.motivo,
          }))
        );
      }
    } catch {
      this.errorMensaje.set('No se pudo cargar la existencia desde la base de datos.');
    } finally {
      this.cargando.set(false);
    }
  }

  async agregarCantidad(id: number): Promise<void> {
    const actual = this.productos().find((p) => p.id === id);
    if (!actual) return;

    const delta = Number(actual.cantidadAjuste || 0);
    if (delta <= 0) return;

    this.errorMensaje.set('');
    this.mensajeEstado.set('');

    try {
      const resp = await firstValueFrom(
        this.http.post<{ exito?: boolean; existencia?: number; mensaje?: string }>(
          `${this.apiBase}/reabastecer`,
          { id_producto: id, cantidad: delta },
          { withCredentials: true }
        )
      );
      if (!resp?.exito) {
        this.errorMensaje.set(resp?.mensaje || 'No se pudo sumar al stock.');
        return;
      }

      const nuevaExt = Number(resp.existencia ?? actual.existencia + delta);
      this.productos.update((lista) =>
        lista.map((p) =>
          p.id === id
            ? { ...p, existencia: nuevaExt, optimo: nuevaExt >= 15, cantidadAjuste: 10 }
            : p
        )
      );
      this.mensajeEstado.set(
        `Se sumaron ${delta} a ${actual.nombre}. Existencia actual: ${nuevaExt} (${actual.presentacion}).`
      );
    } catch {
      this.errorMensaje.set('Error al guardar el incremento en la base de datos.');
    }
  }

  async guardarStockDirecto(item: ProductoInventario): Promise<void> {
    const nuevaExt = Math.max(0, Number(item.existencia || 0));
    this.errorMensaje.set('');
    this.mensajeEstado.set('');

    try {
      const resp = await firstValueFrom(
        this.http.put<{ exito?: boolean; existencia?: number; mensaje?: string }>(
          `${this.apiBase}/productos/${item.id}`,
          { existencia: nuevaExt },
          { withCredentials: true }
        )
      );
      if (!resp?.exito) {
        this.errorMensaje.set(resp?.mensaje || 'No se pudo guardar la existencia.');
        return;
      }

      const extConfirmada = Number(resp.existencia ?? nuevaExt);
      this.productos.update((lista) =>
        lista.map((p) =>
          p.id === item.id
            ? { ...p, existencia: extConfirmada, optimo: extConfirmada >= 15 }
            : p
        )
      );
      this.mensajeEstado.set(
        `Existencia de ${item.nombre} guardada en BD: ${extConfirmada} (${item.presentacion}).`
      );
    } catch {
      this.errorMensaje.set('Error al actualizar la existencia en la base de datos.');
    }
  }

  async registrarMerma(event: Event): Promise<void> {
    event.preventDefault();
    if (!this.cantidadMerma || this.cantidadMerma <= 0) return;

    const cant = Number(this.cantidadMerma);
    const prod =
      this.productos().find((p) => p.id === Number(this.productoMermaId)) ??
      this.productos()[0];

    this.errorMensaje.set('');
    this.mensajeEstado.set('');

    try {
      const resp = await firstValueFrom(
        this.http.post<{
          exito?: boolean;
          id_merma?: number;
          existencia?: number | null;
          mensaje?: string;
        }>(
          `${this.apiBase}/mermas`,
          {
            id_producto: prod?.id ?? null,
            cantidad: cant,
            motivo: this.motivoMerma,
          },
          { withCredentials: true }
        )
      );

      if (!resp?.exito) {
        this.errorMensaje.set(resp?.mensaje || 'No se pudo registrar la merma.');
        return;
      }

      const nombreProd = prod?.nombre || 'Producto';
      this.mermasMes.update((lista) => [
        {
          id: resp.id_merma ?? Date.now(),
          fecha: 'Hoy',
          producto: nombreProd,
          cantidadPerdida: `${cant} (${prod?.presentacion || 'unidad'})`,
          motivo: this.motivoMerma,
        },
        ...lista,
      ]);

      if (prod && typeof resp.existencia === 'number') {
        const extActualizada = Number(resp.existencia);
        this.productos.update((lista) =>
          lista.map((p) =>
            p.id === prod.id
              ? { ...p, existencia: extActualizada, optimo: extActualizada >= 15 }
              : p
          )
        );
      }

      this.mensajeEstado.set(`Merma de ${cant} registrada para ${nombreProd}.`);
      this.cantidadMerma = null;
    } catch (e: any) {
      this.errorMensaje.set(
        e?.status ? (e?.error?.mensaje || 'No se pudo registrar la merma.') : 'No se pudo conectar con el servidor.'
      );
    }
  }
}