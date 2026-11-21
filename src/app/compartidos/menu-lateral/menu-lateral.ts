import { Component, computed, EventEmitter, inject, Input, Output } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { AuthRolService } from '../../servicios/auth-rol.service';
import { CarritoService } from '../../servicios/carrito.service';

@Component({
  imports: [RouterLink],
  selector: 'app-menu-lateral',
  styleUrl: './menu-lateral.css',
  templateUrl: './menu-lateral.html',
})
export class MenuLateral {
  private readonly router = inject(Router);
  private readonly authRol = inject(AuthRolService);
  private readonly carritoService = inject(CarritoService);

  @Input() abierto = false;
  @Output() cerrar = new EventEmitter<void>();

  readonly esAdmin = computed(
    () => this.authRol.usuario()?.rol?.toLowerCase() === 'admin' || this.authRol.esAdmin()
  );

  cerrarMenu(): void {
    this.cerrar.emit();
  }

  async cerrarSesion(): Promise<void> {
    await this.authRol.cerrarSesion();
    this.carritoService.vaciar();
    this.cerrar.emit();
    await this.router.navigate(['/login']);
  }
}