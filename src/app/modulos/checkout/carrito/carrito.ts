import { Component, inject } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { BarraInferior } from '../../../compartidos/barra-inferior/barra-inferior';
import { BarraSuperior } from '../../../compartidos/barra-superior/barra-superior';
import { MenuLateral } from '../../../compartidos/menu-lateral/menu-lateral';
import { CarritoService } from '../../../servicios/carrito.service';
import { CatalogoService } from '../../../servicios/catalogo.service';

@Component({
  imports: [RouterLink, BarraSuperior, BarraInferior, MenuLateral],
  selector: 'app-carrito',
  styleUrl: './carrito.css',
  templateUrl: './carrito.html',
})
export class Carrito {
  private readonly router = inject(Router);
  readonly carritoService = inject(CarritoService);
  readonly catalogoService = inject(CatalogoService);

  menuAbierto = false;

  cambiarCantidad(indice: number, delta: number): void {
    const item = this.carritoService.items()[indice];
    if (!item) return;
    this.carritoService.actualizarCantidad(indice, item.cantidad + delta);
  }

  continuarEntrega(): void {
    if (this.carritoService.items().length === 0) return;
    this.router.navigate(['/checkout/entrega']);
  }
}