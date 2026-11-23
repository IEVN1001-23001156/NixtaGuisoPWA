import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthRolService } from '../../../servicios/auth-rol.service';
import { CarritoService } from '../../../servicios/carrito.service';

@Component({
  imports: [FormsModule, RouterLink],
  selector: 'app-inicio-sesion',
  styleUrl: './inicio-sesion.css',
  templateUrl: './inicio-sesion.html',
})
export class InicioSesion {
  private readonly router = inject(Router);
  private readonly authRol = inject(AuthRolService);
  private readonly carritoService = inject(CarritoService);

  correo = '';
  contrasena = '';
  cargando = signal<boolean>(false);
  errorMensaje = signal<string>('');

  async iniciarSesion(event: Event): Promise<void> {
    event.preventDefault();
    if (this.cargando()) return;

    this.errorMensaje.set('');
    this.cargando.set(true);

    try {
      const resultado = await this.authRol.iniciarSesion(this.correo.trim(), this.contrasena);
      if (!resultado.exito) {
        this.errorMensaje.set(resultado.mensaje || 'Correo o contraseña incorrectos');
        return;
      }

      if (this.authRol.esAdmin()) {
        await this.router.navigate(['/admin/panel']);
      } else {
        await this.router.navigate(['/inicio']);
      }
    } catch (e: any) {
      this.errorMensaje.set(
        e?.status ? (e?.error?.mensaje || 'Correo o contraseña incorrectos') : 'No se pudo conectar con el servidor'
      );
    } finally {
      this.cargando.set(false);
    }
  }

  async continuarComoInvitado(): Promise<void> {
    await this.authRol.cerrarSesion();
    this.carritoService.vaciar();
    await this.router.navigate(['/inicio']);
  }
}