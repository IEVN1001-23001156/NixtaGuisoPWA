import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AdminService } from '../../../servicios/admin.service';
import { AvisosService } from '../../../servicios/avisos.service';
import { Parada, Repartidor, Ruta } from '../../../interfaces/admin';
import { NOMBRE_ESTADO } from '../../../interfaces/pedidos';
import { COLORES_RUTA, MapaRutas } from '../../../componentes/mapa-rutas/mapa-rutas';
import { dentroDeLeon } from '../../../utilidades/mapa';
import { hoyLocal } from '../../../utilidades/fechas';

@Component({
  selector: 'app-rutas',
  imports: [FormsModule, MapaRutas],
  templateUrl: './rutas.html'
})
export class Rutas implements OnInit {
  private admin = inject(AdminService);
  private avisos = inject(AvisosService);

  fecha = hoyLocal();
  rutas = signal<Ruta[]>([]);
  sinAsignar = signal<Parada[]>([]);
  sinUbicacion = signal(0);
  repartidores = signal<Repartidor[]>([]);
  cambiosSinGuardar = signal<Set<number>>(new Set());
  corrigiendo = signal<Parada | null>(null);
  asignaciones: Record<number, number> = {};
  colores = COLORES_RUTA;
  nombreEstado = NOMBRE_ESTADO;

  ngOnInit(): void {
    this.cargar();
    this.admin.repartidores().subscribe(r => this.repartidores.set(r.repartidores));
  }

  cargar(): void {
    this.admin.rutas(this.fecha).subscribe(r => {
      this.rutas.set(r.rutas);
      this.sinAsignar.set(r.sin_asignar);
      this.sinUbicacion.set(r.pedidos_sin_ubicacion);
      this.cambiosSinGuardar.set(new Set());
    });
  }

  /** Mueve una parada arriba o abajo dentro de su ruta (solo en pantalla, hasta guardar) */
  mover(ruta: Ruta, indice: number, delta: number): void {
    const destino = indice + delta;
    if (destino < 0 || destino >= ruta.paradas.length) return;
    const paradas = [...ruta.paradas];
    [paradas[indice], paradas[destino]] = [paradas[destino], paradas[indice]];
    paradas.forEach((p, i) => (p.orden_ruta = i + 1));
    this.rutas.update(lista => lista.map(r => (r.id_repartidor === ruta.id_repartidor ? { ...r, paradas } : r)));
    this.cambiosSinGuardar.update(s => new Set(s).add(ruta.id_repartidor));
  }

  guardar(ruta: Ruta): void {
    this.admin.guardarOrden(ruta.id_repartidor, ruta.paradas.map(p => p.id_pedido)).subscribe({
      next: r => { this.avisos.mostrar(r.mensaje ?? 'Ruta guardada'); this.cargar(); },
      error: err => this.avisos.error(err.error?.mensaje || 'No se pudo guardar la ruta')
    });
  }

  asignar(p: Parada): void {
    const id = this.asignaciones[p.id_pedido];
    if (!id) return;
    this.admin.asignarRepartidor(p.id_pedido, id).subscribe({
      next: r => { this.avisos.mostrar(r.mensaje ?? 'Asignado'); this.cargar(); },
      error: err => this.avisos.error(err.error?.mensaje || 'No se pudo asignar')
    });
  }

  /** Con un pedido seleccionado para corregir, el siguiente clic en el mapa fija su ubicación */
  clicEnMapa(punto: { latitud: number; longitud: number }): void {
    const p = this.corrigiendo();
    if (!p) return;
    if (!dentroDeLeon(punto.latitud, punto.longitud)) { this.avisos.error('Ese punto está fuera de León'); return; }
    this.admin.corregirUbicacion(p.id_pedido, punto.latitud, punto.longitud).subscribe({
      next: () => { this.avisos.mostrar(`Ubicación del pedido #${p.id_pedido} actualizada`); this.corrigiendo.set(null); this.cargar(); },
      error: err => this.avisos.error(err.error?.mensaje || 'No se pudo actualizar')
    });
  }
}
