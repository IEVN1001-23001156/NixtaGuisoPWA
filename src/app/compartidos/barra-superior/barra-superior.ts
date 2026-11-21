import { Component, EventEmitter, inject, Output } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthRolService } from '../../servicios/auth-rol.service';
import { FotoPerfilService } from '../../servicios/foto-perfil.service';

@Component({
  imports: [RouterLink],
  selector: 'app-barra-superior',
  templateUrl: './barra-superior.html',
})
export class BarraSuperior {
  private readonly authRol = inject(AuthRolService);
  readonly fotoPerfilService = inject(FotoPerfilService);

  @Output() abrirMenu = new EventEmitter<void>();

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
}