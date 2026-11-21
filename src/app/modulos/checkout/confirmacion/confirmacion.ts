import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { BarraInferior } from '../../../compartidos/barra-inferior/barra-inferior';
import { BarraSuperior } from '../../../compartidos/barra-superior/barra-superior';
import { MenuLateral } from '../../../compartidos/menu-lateral/menu-lateral';
import { PedidosService } from '../../../servicios/pedidos.service';

@Component({
  imports: [RouterLink, BarraSuperior, BarraInferior, MenuLateral],
  selector: 'app-confirmacion',
  styleUrl: './confirmacion.css',
  templateUrl: './confirmacion.html',
})
export class Confirmacion {
  private readonly pedidosService = inject(PedidosService);

  menuAbierto = false;

  get folio(): string {
    return this.pedidosService.ultimoPedido()?.folio ?? 'NG-2026-048';
  }

  get total(): number | null {
    return this.pedidosService.ultimoPedido()?.total ?? null;
  }

  get direccionResumen(): string | null {
    return this.pedidosService.ultimoPedido()?.direccionResumen ?? null;
  }
}