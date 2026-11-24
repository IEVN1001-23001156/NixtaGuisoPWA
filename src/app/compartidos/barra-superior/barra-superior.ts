import { Component, OnInit, computed, effect, EventEmitter, inject, Output, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { RouterLink } from '@angular/router';
import { AuthRolService } from '../../servicios/auth-rol.service';
import { FotoPerfilService } from '../../servicios/foto-perfil.service';

export interface AvisoCliente {
  id_notificacion: number;
  titulo: string;
  mensaje: string;
  leida: boolean;
  fecha: string;
}

@Component({
  imports: [RouterLink],
  selector: 'app-barra-superior',
  templateUrl: './barra-superior.html',
})
export class BarraSuperior implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly authRol = inject(AuthRolService);
  readonly fotoPerfilService = inject(FotoPerfilService);
  private readonly apiNotificaciones = 'http://localhost:5000/api/notificaciones';

  @Output() abrirMenu = new EventEmitter<void>();

  readonly esAdmin = computed(
    () => this.authRol.usuario()?.rol?.toLowerCase() === 'admin' || this.authRol.esAdmin()
  );

  readonly avisos = signal<AvisoCliente[]>([]);
  readonly noLeidas = signal(0);
  readonly menuAvisosAbierto = signal(false);

  private readonly sincronizarSesion = effect(() => {
    const usuario = this.authRol.usuario();
    if (usuario && !this.esAdmin()) {
      this.cargarAvisos();
    } else {
      this.avisos.set([]);
      this.noLeidas.set(0);
      this.menuAvisosAbierto.set(false);
    }
  });

  ngOnInit(): void {
    if (!this.esAdmin() && this.authRol.usuario()) {
      this.cargarAvisos();
    }
  }

  get inicialesUsuario(): string {
    const nombre = this.authRol.usuario()?.nombre?.trim();
    if (!nombre) {
      return 'NG';
    }
    const partes = nombre.split(/\s+/);
    return partes.length > 1
      ? `${partes[0][0]}${partes[1][0]}`.toUpperCase()
      : partes[0].slice(0, 2).toUpperCase();
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

  toggleAvisos(): void {
    const siguiente = !this.menuAvisosAbierto();
    this.menuAvisosAbierto.set(siguiente);
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