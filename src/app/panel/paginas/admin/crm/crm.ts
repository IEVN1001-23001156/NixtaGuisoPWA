import { Component, OnInit, inject, signal } from '@angular/core';
import { CurrencyPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';

import { AdminService } from '../../../servicios/admin.service';
import { AvisosService } from '../../../servicios/avisos.service';
import { ClienteFicha, ClienteResumen } from '../../../interfaces/admin';
import { COLOR_ESTADO, NOMBRE_ESTADO } from '../../../interfaces/pedidos';
import { MapaSelector } from '../../../componentes/mapa-selector/mapa-selector';

/** Clientes y segmentación (Módulo 9): lista y ficha lado a lado */
@Component({
  selector: 'app-crm-admin',
  imports: [CurrencyPipe, FormsModule, MapaSelector],
  templateUrl: './crm.html'
})
export class CrmAdmin implements OnInit {
  private admin = inject(AdminService);
  private avisos = inject(AvisosService);
  private route = inject(ActivatedRoute);

  clientes = signal<ClienteResumen[]>([]);
  tipo = signal('');
  buscar = '';
  ficha = signal<ClienteFicha | null>(null);
  consumo = signal<any>(null);
  preferencias = '';
  nombreEstado = NOMBRE_ESTADO;
  colorEstado = COLOR_ESTADO;

  ngOnInit(): void {
    this.cargar(() => {
      const id = Number(this.route.snapshot.queryParamMap.get('cliente')) || this.clientes()[0]?.id_cliente;
      if (id) this.abrir(id);
    });
  }

  cargar(despues?: () => void): void {
    this.admin.clientes({ tipo: this.tipo(), buscar: this.buscar }).subscribe(r => { this.clientes.set(r.clientes); despues?.(); });
  }

  filtrar(tipo: string): void { this.tipo.set(tipo); this.cargar(); }

  abrir(id: number): void {
    this.consumo.set(null);
    this.admin.cliente(id).subscribe(r => {
      this.ficha.set(r.cliente);
      this.preferencias = r.cliente.preferencias ?? '';
      if (r.cliente.tipo === 'B2B') this.admin.consumoCliente(id).subscribe(c => this.consumo.set(c));
    });
  }

  actualizar(datos: { nivel_b2b?: number; preferencias?: string; activo?: boolean }): void {
    const f = this.ficha();
    if (!f) return;
    this.admin.actualizarCliente(f.id_cliente, datos).subscribe({
      next: r => { this.avisos.mostrar(r.mensaje ?? 'Cliente actualizado'); this.abrir(f.id_cliente); this.cargar(); },
      error: err => this.avisos.error(err.error?.mensaje || 'No se pudo actualizar')
    });
  }

  /** Totales calculados con el historial (sin contar pedidos cancelados) */
  totales(c: ClienteFicha): { pedidos: number; comprado: number } {
    const validos = c.historial.filter(p => p.estado !== 'cancelado');
    return { pedidos: validos.length, comprado: validos.reduce((s, p) => s + p.total, 0) };
  }

  folio(id: number): string { return 'NG-' + id.toString().padStart(4, '0'); }
}
