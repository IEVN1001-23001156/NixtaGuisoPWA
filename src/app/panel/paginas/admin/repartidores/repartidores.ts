import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AdminService } from '../../../servicios/admin.service';
import { AvisosService } from '../../../servicios/avisos.service';
import { Repartidor } from '../../../interfaces/admin';

@Component({
  selector: 'app-repartidores',
  imports: [FormsModule],
  templateUrl: './repartidores.html'
})
export class Repartidores implements OnInit {
  private admin = inject(AdminService);
  private avisos = inject(AvisosService);
  repartidores = signal<Repartidor[]>([]);
  datos = { nombre: '', telefono: '', placas: '' };
  editandoId = signal<number | null>(null);

  ngOnInit(): void { this.cargar(); }
  cargar(): void { this.admin.repartidores(true).subscribe(r => this.repartidores.set(r.repartidores)); }

  editar(r: Repartidor): void { this.editandoId.set(r.id_repartidor); this.datos = { nombre: r.nombre, telefono: r.telefono, placas: r.placas }; }
  cancelar(): void { this.editandoId.set(null); this.datos = { nombre: '', telefono: '', placas: '' }; }

  guardar(): void {
    const id = this.editandoId();
    const actual = this.repartidores().find(x => x.id_repartidor === id);
    const peticion = id ? this.admin.editarRepartidor(id, { ...this.datos, activo: actual?.activo ?? true }) : this.admin.crearRepartidor(this.datos);
    peticion.subscribe({
      next: r => { this.avisos.mostrar(r.mensaje ?? 'Guardado'); this.cancelar(); this.cargar(); },
      error: err => this.avisos.error(err.error?.mensaje || 'No se pudo guardar')
    });
  }

  alternar(r: Repartidor): void {
    this.admin.editarRepartidor(r.id_repartidor, { nombre: r.nombre, telefono: r.telefono, placas: r.placas, activo: !r.activo }).subscribe({
      next: x => { this.avisos.mostrar(x.mensaje ?? 'Actualizado'); this.cargar(); },
      error: err => this.avisos.error(err.error?.mensaje || 'No se pudo actualizar')
    });
  }
}
