import { Component, OnInit, computed, effect, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { AuthRolService } from '../../servicios/auth-rol.service';

export interface AvisoCliente {
  id_notificacion: number;
  titulo: string;
  mensaje: string;
  leida: boolean;
  fecha: string;
}

@Component({
  selector: 'app-campana-avisos',
  templateUrl: './campana-avisos.html',
})
export class CampanaAvisos implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly authRol = inject(AuthRolService);
  private readonly apiNotificaciones = 'http://localhost:5000/api/notificaciones';

  readonly esAdmin = computed(
    () => this.authRol.usuario()?.rol?.toLowerCase() === 'admin' || this.authRol.esAdmin()
  );

  readonly avisos = signal<AvisoCliente[]>([]);
  readonly noLeidas = signal(0);
  readonly abierto = signal(false);

  private readonly sincronizarSesion = effect(() => {
    const usuario = this.authRol.usuario();
    if (usuario && !this.esAdmin()) {
      this.cargarAvisos();
    } else {
      this.avisos.set([]);
      this.noLeidas.set(0);
      this.abierto.set(false);
    }
  });

  ngOnInit(): void {
    if (!this.esAdmin() && this.authRol.usuario()) {
      this.cargarAvisos();
    }
  }

  cargarAvisos(): void {
    this.http
      .get<{ exito: boolean; no_leidas?: number; notificaciones?: AvisoCliente[] }>(
        this.apiNotificaciones,
        { withCredentials: true }
      )
      .subscribe({
        next: (r) => {
          if (r?.exito) {
            this.avisos.set(r.notificaciones ?? []);
            this.noLeidas.set(r.no_leidas ?? 0);
          }
        },
        error: () => {
          // Sin sesión activa o error de red
        },
      });
  }

  toggleMenu(): void {
    const siguiente = !this.abierto();
    this.abierto.set(siguiente);
    if (siguiente && !this.esAdmin()) {
      this.cargarAvisos();
    }
  }

  marcarLeida(aviso: AvisoCliente): void {
    if (aviso.leida) {
      return;
    }
    this.http
      .put(
        `${this.apiNotificaciones}/${aviso.id_notificacion}/leida`,
        {},
        { withCredentials: true }
      )
      .subscribe({
        next: () => this.cargarAvisos(),
      });
  }

  marcarTodasLeidas(): void {
    this.http
      .put(
        `${this.apiNotificaciones}/leer-todas`,
        {},
        { withCredentials: true }
      )
      .subscribe({
        next: () => this.cargarAvisos(),
      });
  }
}