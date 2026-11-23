import { Component, OnInit, inject, input, signal } from '@angular/core';
import { CurrencyPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { AdminService } from '../../../servicios/admin.service';
import { AvisosService } from '../../../servicios/avisos.service';
import { ClienteFicha as Ficha } from '../../../interfaces/admin';
import { COLOR_ESTADO, NOMBRE_ESTADO } from '../../../interfaces/pedidos';
import { MapaSelector } from '../../../componentes/mapa-selector/mapa-selector';

@Component({
  selector: 'app-cliente-ficha',
  imports: [CurrencyPipe, FormsModule, RouterLink, MapaSelector],
  templateUrl: './cliente-ficha.html'
})
export class ClienteFicha implements OnInit {
  private admin = inject(AdminService);
  private avisos = inject(AvisosService);
  id = input.required<string>();
  cliente = signal<Ficha | null>(null);
  preferencias = '';
  nombreEstado = NOMBRE_ESTADO;
  colorEstado = COLOR_ESTADO;

  ngOnInit(): void { this.cargar(); }

  cargar(): void {
    this.admin.cliente(Number(this.id())).subscribe(r => { this.cliente.set(r.cliente); this.preferencias = r.cliente.preferencias ?? ''; });
  }

  actualizar(datos: { nivel_b2b?: number; preferencias?: string; activo?: boolean }): void {
    this.admin.actualizarCliente(Number(this.id()), datos).subscribe({
      next: r => { this.avisos.mostrar(r.mensaje ?? 'Cliente actualizado'); this.cargar(); },
      error: err => this.avisos.error(err.error?.mensaje || 'No se pudo actualizar')
    });
  }
}
