import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { BarraInferior } from '../../../compartidos/barra-inferior/barra-inferior';
import { BarraSuperior } from '../../../compartidos/barra-superior/barra-superior';
import { MenuLateral } from '../../../compartidos/menu-lateral/menu-lateral';
import { PedidoHistorialItem, PedidosService } from '../../../servicios/pedidos.service';

@Component({
  imports: [RouterLink, BarraSuperior, BarraInferior, MenuLateral],
  selector: 'app-historial-pedidos',
  styleUrl: './historial-pedidos.css',
  templateUrl: './historial-pedidos.html',
})
export class HistorialPedidos implements OnInit {
  private readonly pedidosService = inject(PedidosService);

  menuAbierto = false;
  cargando = signal<boolean>(true);
  pedidos = signal<PedidoHistorialItem[]>([]);

  async ngOnInit(): Promise<void> {
    this.cargando.set(true);
    try {
      const lista = await this.pedidosService.obtenerHistorial();
      this.pedidos.set(lista);
    } finally {
      this.cargando.set(false);
    }
  }

  etiquetaEstado(estado: string): string {
    const limpio = (estado || 'pendiente').toLowerCase();
    const mapa: Record<string, string> = {
      pendiente: 'Pendiente',
      en_preparacion: 'En preparación',
      en_camino: 'En camino',
      entregado: 'Entregado',
      completado: 'Completado',
      cancelado: 'Cancelado',
    };
    return mapa[limpio] ?? estado;
  }
}