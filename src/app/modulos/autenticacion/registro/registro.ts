import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthRolService } from '../../../servicios/auth-rol.service';

@Component({
  imports: [FormsModule, RouterLink],
  selector: 'app-registro',
  styleUrl: './registro.css',
  templateUrl: './registro.html',
})
export class Registro {
  private readonly router = inject(Router);
  private readonly authRol = inject(AuthRolService);

  nombre = '';
  correo = '';
  telefono = '';
  contrasena = '';
  tipo: 'B2C' | 'B2B' = 'B2C';
  nombreNegocio = '';
  rfc = '';
  direccion = '';

  cargando = signal<boolean>(false);
  errorMensaje = signal<string>('');

  async registrar(event: Event): Promise<void> {
    event.preventDefault();
    if (this.cargando()) return;

    this.errorMensaje.set('');
    this.cargando.set(true);

    try {
      const resultado = await this.authRol.registrar({
        nombre: this.nombre.trim(),
        correo: this.correo.trim(),
        telefono: this.telefono.trim(),
        contrasena: this.contrasena,
        tipo: this.tipo,
        nombre_negocio: this.tipo === 'B2B' ? this.nombreNegocio.trim() : '',
        rfc: this.tipo === 'B2B' ? this.rfc.trim().toUpperCase() : '',
        direccion: this.direccion.trim(),
      });

      if (!resultado.exito) {
        this.errorMensaje.set(resultado.mensaje || 'No se pudo crear la cuenta');
        return;
      }

      await this.router.navigate(['/inicio']);
    } catch {
      this.errorMensaje.set('No se pudo conectar con el servidor');
    } finally {
      this.cargando.set(false);
    }
  }
}