import { HttpClient } from '@angular/common/http';
import { inject, Injectable, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { DatosEntrega, ItemCarrito } from './carrito.service';

export interface UltimoPedidoConfirmado {
  folio: string;
  total: number;
  metodoPago: string;
  direccionResumen: string;
  idPedido?: number | null;
}

export interface PedidoHistorialItem {
  id_pedido: number;
  folio: string;
  fecha_pedido: string;
  estado: string;
  modalidad: string;
  direccion_entrega: string;
  subtotal: number;
  costo_envio: number;
  total: number;
  metodo_pago: string;
  resumen: string;
}

interface RespuestaCrearPedido {
  exito?: boolean;
  total?: number;
  mensaje?: string;
  folio?: string;
  id_pedido?: number;
  pedido?: Record<string, unknown>;
}

interface RespuestaHistorial {
  exito?: boolean;
  pedidos?: PedidoHistorialItem[];
}

@Injectable({
  providedIn: 'root',
})
export class PedidosService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = 'http://localhost:5000/api/pedidos';

  readonly ultimoPedido = signal<UltimoPedidoConfirmado | null>(null);

  async crearPedido(
    items: ItemCarrito[],
    direccion: DatosEntrega,
    metodoPago: 'tarjeta',
    subtotal: number,
    envio: number,
    total: number
  ): Promise<UltimoPedidoConfirmado> {
    const direccionCompleta = [direccion.calle, direccion.colonia, direccion.ciudad]
      .filter(Boolean)
      .join(', ');

    const payload = {
      metodo_pago: 'tarjeta',
      subtotal,
      envio,
      total,
      direccion_entrega: direccionCompleta,
      calle: direccion.calle,
      colonia: direccion.colonia,
      ciudad: direccion.ciudad,
      referencias: direccion.referencias,
      items: items.map((i) => ({
        id_producto: i.producto.id,
        nombre: i.producto.nombre,
        cantidad: i.cantidad,
        precio_unitario: i.producto.precio,
        nota_especial: i.notaEspecial,
        salsa: i.salsa ?? null,
        agua: i.agua ?? null,
        arma: i.arma ?? null,
      })),
    };

    const resp = await firstValueFrom(
      this.http.post<RespuestaCrearPedido>(this.apiUrl, payload, {
        withCredentials: true,
      })
    );

    if (!resp || resp.exito === false) {
      throw new Error(resp?.mensaje || 'No se pudo registrar el pedido en la base de datos.');
    }

    const idPedido =
      resp.id_pedido ??
      (resp.pedido && resp.pedido['id_pedido'] ? Number(resp.pedido['id_pedido']) : null);

    const folio =
      resp.folio ??
      (resp.pedido && resp.pedido['folio'] ? String(resp.pedido['folio']) : null) ??
      (idPedido ? `NG-${String(idPedido).padStart(4, '0')}` : 'NG-REGISTRADO');

    const confirmado: UltimoPedidoConfirmado = {
      folio,
      total: Number(resp.total ?? total),   // el total real lo calcula Flask
      metodoPago: 'tarjeta',
      direccionResumen: direccionCompleta || 'Entrega a domicilio',
      idPedido,
    };

    this.ultimoPedido.set(confirmado);
    return confirmado;
  }

  async obtenerHistorial(): Promise<PedidoHistorialItem[]> {
    const resp = await firstValueFrom(
      this.http.get<RespuestaHistorial>(this.apiUrl, {
        withCredentials: true,
      })
    );
    if (resp?.exito && Array.isArray(resp.pedidos)) {
      return resp.pedidos;
    }
    return [];
  }
}