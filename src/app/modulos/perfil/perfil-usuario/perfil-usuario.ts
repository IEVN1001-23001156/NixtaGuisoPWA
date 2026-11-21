import { Component, computed, effect, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { BarraInferior } from '../../../compartidos/barra-inferior/barra-inferior';
import { BarraSuperior } from '../../../compartidos/barra-superior/barra-superior';
import { MenuLateral } from '../../../compartidos/menu-lateral/menu-lateral';
import { AuthRolService } from '../../../servicios/auth-rol.service';
import { CarritoService } from '../../../servicios/carrito.service';
import { FotoPerfilService } from '../../../servicios/foto-perfil.service';

@Component({
  imports: [FormsModule, RouterLink, BarraSuperior, BarraInferior, MenuLateral],
  selector: 'app-perfil-usuario',
  styleUrl: './perfil-usuario.css',
  templateUrl: './perfil-usuario.html',
})
export class PerfilUsuario {
  private readonly authRol = inject(AuthRolService);
  private readonly carritoService = inject(CarritoService);
  private readonly fotoPerfilService = inject(FotoPerfilService);
  private readonly http = inject(HttpClient);

  menuAbierto = false;
  direccionEdit = '';
  fotoPreview = signal<string | null>(null);
  mensajeEstado = signal<string>('');
  guardando = signal<boolean>(false);

  readonly usuarioActual = computed(() => this.authRol.usuario());
  readonly esAdmin = computed(
    () => this.usuarioActual()?.rol?.toLowerCase() === 'admin' || this.authRol.esAdmin()
  );

  constructor() {
    effect(() => {
      const u = this.usuarioActual();
      const id = u?.id_usuario ?? null;
      const fotoGuardada = localStorage.getItem(this.claveFotoStorage(id));
      this.fotoPreview.set(fotoGuardada);
      this.fotoPerfilService.establecerFoto(fotoGuardada);

      if (!this.esAdmin()) {
        const guardada = this.carritoService.cargarDireccionUsuario(id);
        const dirActual = guardada.calle || u?.cliente?.direccion?.trim() || '';
        if (dirActual) {
          this.direccionEdit = dirActual;
        }
      }
    });
  }

  get nombreUsuario(): string {
    return this.usuarioActual()?.nombre?.trim() || (this.esAdmin() ? 'Administrador NixtaGuiso' : 'Invitado NixtaGuiso');
  }

  get correoUsuario(): string {
    return this.usuarioActual()?.correo?.trim() || 'Sin sesión activa';
  }

  get telefonoUsuario(): string {
    return this.usuarioActual()?.telefono?.trim() || 'No registrado';
  }

  get tipoPerfil(): string {
    if (this.esAdmin()) {
      return 'Administrador';
    }
    if (!this.usuarioActual()) {
      return 'Invitado';
    }
    const tipo = this.usuarioActual()?.cliente?.tipo;
    if (tipo === 'B2B') {
      const nivel = this.usuarioActual()?.cliente?.nivel_b2b;
      return nivel ? `Negocio (B2B · Nivel ${nivel})` : 'Negocio (B2B)';
    }
    return 'Hogar (B2C)';
  }

  get nombreNegocio(): string | null {
    if (this.esAdmin()) return null;
    return this.usuarioActual()?.cliente?.nombre_negocio?.trim() || null;
  }

  get iniciales(): string {
    const partes = this.nombreUsuario.split(/\s+/).filter(Boolean);
    if (partes.length === 0) return 'NG';
    return partes.length > 1
      ? `${partes[0][0]}${partes[1][0]}`.toUpperCase()
      : partes[0].slice(0, 2).toUpperCase();
  }

  onSeleccionarFoto(event: Event): void {
    const input = event.target as HTMLInputElement;
    const archivo = input.files?.[0];
    if (!archivo) return;

    const lector = new FileReader();
    lector.onload = () => {
      const resultado = typeof lector.result === 'string' ? lector.result : null;
      this.fotoPreview.set(resultado);
      this.fotoPerfilService.establecerFoto(resultado);
      if (resultado) {
        localStorage.setItem(
          this.claveFotoStorage(this.usuarioActual()?.id_usuario ?? null),
          resultado
        );
        this.mensajeEstado.set('Foto de perfil actualizada.');
      }
    };
    lector.readAsDataURL(archivo);
  }

  async guardarDireccion(event: Event): Promise<void> {
    event.preventDefault();
    if (this.esAdmin()) return;
    const limpia = this.direccionEdit.trim();
    if (!limpia || this.guardando()) return;

    this.guardando.set(true);
    this.mensajeEstado.set('');
    const idUsuario = this.usuarioActual()?.id_usuario ?? null;

    this.carritoService.establecerDireccion(
      {
        calle: limpia,
        colonia: this.carritoService.direccionEntrega().colonia,
        ciudad: this.carritoService.direccionEntrega().ciudad || 'León, Guanajuato',
        referencias: this.carritoService.direccionEntrega().referencias,
      },
      idUsuario
    );

    try {
      await firstValueFrom(
        this.http.put(
          'http://localhost:5000/api/perfil/direccion',
          { direccion: limpia },
          { withCredentials: true }
        )
      );
      await this.authRol.consultarSesionActual();
    } catch {
    } finally {
      this.guardando.set(false);
      this.mensajeEstado.set('Dirección de entrega guardada.');
    }
  }

  private claveFotoStorage(idUsuario: number | null): string {
    return `nixtaguiso_foto_${idUsuario ?? 'invitado'}`;
  }
}