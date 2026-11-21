import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { BarraSuperior } from '../../../compartidos/barra-superior/barra-superior';
import { MenuLateral } from '../../../compartidos/menu-lateral/menu-lateral';

export interface ResumenOperativoPedido {
  id_pedido: number;
  folio: string;
  fecha_pedido: string;
  estado: string;
  modalidad: string;
  direccion_entrega: string;
  total: number;
  metodo_pago: string;
}

interface RespuestaPedidosAdmin {
  exito?: boolean;
  pedidos?: ResumenOperativoPedido[];
}

interface RespuestaProgramacionesAdmin {
  exito?: boolean;
  programaciones?: { id_programacion: number; estado: string }[];
}

@Component({
  imports: [RouterLink, BarraSuperior, MenuLateral],
  selector: 'app-panel-operativo',
  styleUrl: './panel-operativo.css',
  templateUrl: './panel-operativo.html',
})
export class PanelOperativo implements OnInit {
  private readonly http = inject(HttpClient);

  menuAbierto = false;
  cargando = signal<boolean>(true);
  pedidos = signal<ResumenOperativoPedido[]>([]);
  totalPedidos = signal<number>(0);
  pedidosPendientes = signal<number>(0);
  ingresosTotales = signal<number>(0);
  programacionesActivas = signal<number>(0);

  async ngOnInit(): Promise<void> {
    await this.cargarMetricas();
  }

  async cargarMetricas(): Promise<void> {
    this.cargando.set(true);
    try {
      const respPedidos = await firstValueFrom(
        this.http.get<RespuestaPedidosAdmin>('http://localhost:5000/api/pedidos', {
          withCredentials: true,
        })
      );

      const lista = Array.isArray(respPedidos?.pedidos) ? respPedidos.pedidos : [];
      this.pedidos.set(lista.slice(0, 8));
      this.totalPedidos.set(lista.length);
      this.pedidosPendientes.set(
        lista.filter((p) => (p.estado || '').toLowerCase() === 'pendiente').length
      );
      this.ingresosTotales.set(
        lista.reduce((acc, p) => acc + Number(p.total || 0), 0)
      );
    } catch {
      this.pedidos.set([]);
      this.totalPedidos.set(0);
      this.pedidosPendientes.set(0);
      this.ingresosTotales.set(0);
    }

    try {
      const respProg = await firstValueFrom(
        this.http.get<RespuestaProgramacionesAdmin>('http://localhost:5000/api/programaciones', {
          withCredentials: true,
        })
      );
      const progs = Array.isArray(respProg?.programaciones) ? respProg.programaciones : [];
      this.programacionesActivas.set(progs.length);
    } catch {
      this.programacionesActivas.set(0);
    } finally {
      this.cargando.set(false);
    }
  }
}