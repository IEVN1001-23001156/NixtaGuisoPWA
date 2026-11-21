import { Component, effect, inject, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { BarraInferior } from '../../../compartidos/barra-inferior/barra-inferior';
import { BarraSuperior } from '../../../compartidos/barra-superior/barra-superior';
import { MenuLateral } from '../../../compartidos/menu-lateral/menu-lateral';
import { AuthRolService } from '../../../servicios/auth-rol.service';
import { CarritoService } from '../../../servicios/carrito.service';

@Component({
  imports: [FormsModule, RouterLink, BarraSuperior, BarraInferior, MenuLateral],
  selector: 'app-direccion-entrega',
  styleUrl: './direccion-entrega.css',
  templateUrl: './direccion-entrega.html',
})
export class DireccionEntrega implements OnInit {
  private readonly router = inject(Router);
  private readonly carritoService = inject(CarritoService);
  private readonly authRol = inject(AuthRolService);

  menuAbierto = false;
  calle = '';
  colonia = '';
  ciudad = 'León, Guanajuato';
  referencias = '';

  constructor() {
    effect(() => {
      const u = this.authRol.usuario();
      const guardada = this.carritoService.cargarDireccionUsuario(u?.id_usuario ?? null);
      if (guardada.calle || guardada.colonia) {
        this.calle = guardada.calle;
        this.colonia = guardada.colonia;
        this.ciudad = guardada.ciudad || 'León, Guanajuato';
        this.referencias = guardada.referencias;
      } else if (u?.cliente?.direccion?.trim()) {
        this.calle = u.cliente.direccion.trim();
      }
    });
  }

  ngOnInit(): void {
    const u = this.authRol.usuario();
    const guardada = this.carritoService.cargarDireccionUsuario(u?.id_usuario ?? null);
    this.calle = guardada.calle || u?.cliente?.direccion?.trim() || '';
    this.colonia = guardada.colonia || '';
    this.ciudad = guardada.ciudad || 'León, Guanajuato';
    this.referencias = guardada.referencias || '';
  }

  continuarPago(event: Event): void {
    event.preventDefault();
    this.carritoService.establecerDireccion(
      {
        calle: this.calle.trim(),
        colonia: this.colonia.trim(),
        ciudad: this.ciudad.trim() || 'León, Guanajuato',
        referencias: this.referencias.trim(),
      },
      this.authRol.usuario()?.id_usuario ?? null
    );
    this.router.navigate(['/checkout/pago']);
  }
}