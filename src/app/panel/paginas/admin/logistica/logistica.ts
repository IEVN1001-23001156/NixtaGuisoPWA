import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { CurrencyPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';

import { AdminService } from '../../../servicios/admin.service';
import { AvisosService } from '../../../servicios/avisos.service';
import { PedidoAdmin, PedidoAdminDetalle, Repartidor } from '../../../interfaces/admin';
import { EstadoPedido, NOMBRE_PAGO } from '../../../interfaces/pedidos';
import { Rutas } from '../rutas/rutas';
import { Repartidores } from '../repartidores/repartidores';
import { hoyLocal } from '../../../utilidades/fechas';

/** Logística y despacho (Módulo 10): tablero por estado, mapa de rutas y repartidores */
@Component({
  selector: 'app-logistica-admin',
  imports: [CurrencyPipe, FormsModule, Rutas, Repartidores],
  templateUrl: './logistica.html'
})
export class LogisticaAdmin implements OnInit {
  private admin = inject(AdminService);
  private avisos = inject(AvisosService);
  private route = inject(ActivatedRoute);

  pestana = signal<'tablero' | 'programados' | 'mapa' | 'repartidores'>('tablero');
  programados = signal<any[]>([]);
  pedidos = signal<PedidoAdmin[]>([]);
  repartidores = signal<Repartidor[]>([]);
  detalle = signal<PedidoAdminDetalle | null>(null);
  asignaciones: Record<number, number> = {};
  procesando = signal<number | null>(null);
  nombrePago = NOMBRE_PAGO;
  hoy = hoyLocal();
  fecha = signal(hoyLocal());   // día que se consulta en Entregados y Cancelados

  columnas: { estado: EstadoPedido; titulo: string; color: string }[] = [
    { estado: 'pendiente', titulo: 'Pendiente', color: 'bg-nixta-amarillo' },
    { estado: 'preparando', titulo: 'Preparando', color: 'bg-nixta-naranja' },
    { estado: 'en_ruta', titulo: 'En ruta', color: 'bg-nixta-dorado text-white' },
    { estado: 'entregado', titulo: 'Entregados del día', color: 'bg-nixta-verde text-white' },
    { estado: 'cancelado', titulo: 'Cancelados del día', color: 'bg-gray-300' }
  ];

  porColumna = computed(() => {
    const grupos: Record<string, PedidoAdmin[]> = { pendiente: [], preparando: [], en_ruta: [], entregado: [], cancelado: [] };
    for (const p of this.pedidos()) {
      // Los activos se ven siempre; entregados y cancelados, solo los del día elegido
      if ((p.estado === 'entregado' || p.estado === 'cancelado') && !p.fecha_pedido.startsWith(this.fecha())) continue;
      grupos[p.estado]?.push(p);
    }
    return grupos;
  });

  ngOnInit(): void {
    const pestana = this.route.snapshot.queryParamMap.get('pestana');
    if (pestana === 'mapa' || pestana === 'repartidores' || pestana === 'programados') this.pestana.set(pestana);
    this.cargar();
    this.admin.programacionesActivas().subscribe(r => this.programados.set(r.programaciones));
    this.admin.repartidores().subscribe(r => this.repartidores.set(r.repartidores));
    const id = Number(this.route.snapshot.queryParamMap.get('pedido'));
    if (id) this.verDetalle(id);
  }

  cargar(): void {
    this.admin.pedidos().subscribe(r => this.pedidos.set(r.pedidos));
  }

  folio(id: number): string { return 'NG-' + id.toString().padStart(4, '0'); }

  verDetalle(id: number): void {
    this.admin.pedido(id).subscribe(r => {
      this.detalle.set(r.pedido);
      this.asignaciones[id] = r.pedido.repartidor?.id_repartidor ?? this.asignaciones[id] ?? 0;
    });
  }

  private hecho(id: number, mensaje?: string) {
    return {
      next: (r: any) => { this.avisos.mostrar(mensaje ?? r.mensaje ?? 'Actualizado'); this.procesando.set(null); this.cargar(); if (this.detalle()?.id_pedido === id) this.verDetalle(id); },
      error: (err: any) => { this.avisos.error(err.error?.mensaje || 'No se pudo actualizar'); this.procesando.set(null); }
    };
  }

  cambiarEstado(p: { id_pedido: number }, estado: EstadoPedido): void {
    if (estado === 'cancelado' && !confirm('¿Cancelar este pedido? Se regresan el inventario y el saldo.')) return;
    this.procesando.set(p.id_pedido);
    this.admin.cambiarEstado(p.id_pedido, estado).subscribe(this.hecho(p.id_pedido));
  }

  pago(p: { id_pedido: number }, accion: 'validar' | 'rechazar'): void {
    this.procesando.set(p.id_pedido);
    this.admin.validarPago(p.id_pedido, accion).subscribe(this.hecho(p.id_pedido));
  }

  /** Asigna el repartidor elegido y pone el pedido "En ruta" */
  enviar(p: PedidoAdmin): void {
    const id_repartidor = this.asignaciones[p.id_pedido] || this.repartidores()[0]?.id_repartidor;
    if (!id_repartidor) { this.avisos.error('Primero registra un repartidor'); return; }
    this.procesando.set(p.id_pedido);
    this.admin.asignarRepartidor(p.id_pedido, id_repartidor).subscribe({
      next: () => this.admin.cambiarEstado(p.id_pedido, 'en_ruta').subscribe(this.hecho(p.id_pedido, `${this.folio(p.id_pedido)} va en camino`)),
      error: err => { this.avisos.error(err.error?.mensaje || 'No se pudo asignar'); this.procesando.set(null); }
    });
  }

  verComprobante(id: number): void { window.open(this.admin.urlComprobante(id), '_blank'); }

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
