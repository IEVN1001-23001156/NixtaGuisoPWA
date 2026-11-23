import { Component, OnInit, inject, signal } from '@angular/core';
import { CurrencyPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { AdminService } from '../../../servicios/admin.service';
import { AvisosService } from '../../../servicios/avisos.service';
import { PedidoAdmin, PedidoAdminDetalle, Repartidor } from '../../../interfaces/admin';
import { COLOR_ESTADO, EstadoPedido, NOMBRE_ESTADO, NOMBRE_PAGO } from '../../../interfaces/pedidos';

@Component({
  selector: 'app-pedidos-admin',
  imports: [CurrencyPipe, FormsModule, RouterLink],
  templateUrl: './pedidos-admin.html'
})
export class PedidosAdmin implements OnInit {
  private admin = inject(AdminService);
  private avisos = inject(AvisosService);

  pedidos = signal<PedidoAdmin[]>([]);
  conteo = signal<Record<string, number>>({});
  detalle = signal<PedidoAdminDetalle | null>(null);
  repartidores = signal<Repartidor[]>([]);
  estado = signal<string>('');
  fecha = '';
  tipo = '';
  repartidorElegido = 0;

  estados: EstadoPedido[] = ['pendiente', 'preparando', 'en_ruta', 'entregado', 'cancelado'];
  nombreEstado = NOMBRE_ESTADO;
  colorEstado = COLOR_ESTADO;
  nombrePago = NOMBRE_PAGO;

  ngOnInit(): void {
    this.cargar();
    this.admin.repartidores().subscribe(r => this.repartidores.set(r.repartidores));
  }

  cargar(): void {
    this.admin.pedidos({ estado: this.estado(), fecha: this.fecha, tipo: this.tipo }).subscribe(r => {
      this.pedidos.set(r.pedidos);
      this.conteo.set(r.conteo);
    });
  }

  filtrarEstado(e: string): void { this.estado.set(e); this.cargar(); }

  abrir(id: number): void {
    this.admin.pedido(id).subscribe(r => { this.detalle.set(r.pedido); this.repartidorElegido = r.pedido.repartidor?.id_repartidor ?? 0; });
  }

  private despues(id: number) {
    return {
      next: (r: { mensaje?: string }) => { this.avisos.mostrar(r.mensaje ?? 'Actualizado'); this.cargar(); this.abrir(id); },
      error: (err: { error?: { mensaje?: string } }) => this.avisos.error(err.error?.mensaje || 'No se pudo actualizar')
    };
  }

  cambiarEstado(d: PedidoAdminDetalle, estado: EstadoPedido): void {
    if (estado === 'cancelado' && !confirm('¿Cancelar este pedido? Se regresa el inventario y el saldo.')) return;
    this.admin.cambiarEstado(d.id_pedido, estado).subscribe(this.despues(d.id_pedido));
  }

  pago(d: PedidoAdminDetalle, accion: 'validar' | 'rechazar'): void { this.admin.validarPago(d.id_pedido, accion).subscribe(this.despues(d.id_pedido)); }

  asignar(d: PedidoAdminDetalle): void {
    if (!this.repartidorElegido) return;
    this.admin.asignarRepartidor(d.id_pedido, this.repartidorElegido).subscribe(this.despues(d.id_pedido));
  }

  verComprobante(d: PedidoAdminDetalle): void { window.open(this.admin.urlComprobante(d.id_pedido), '_blank'); }

  generarProgramados(): void {
    this.admin.generarProgramados().subscribe({
      next: r => {
        this.avisos.mostrar(`${r.generados.length} pedido(s) generado(s)` + (r.omitidos.length ? `, ${r.omitidos.length} omitido(s)` : ''), 'exito', 5);
        r.omitidos.forEach(o => this.avisos.mostrar(`${o.cliente}: ${o.motivo}`, 'info', 6));
        this.cargar();
      },
      error: err => this.avisos.error(err.error?.mensaje || 'No se pudieron generar')
    });
  }
}
