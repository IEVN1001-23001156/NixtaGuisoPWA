import { Component, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { BarraInferior } from '../../../compartidos/barra-inferior/barra-inferior';
import { BarraSuperior } from '../../../compartidos/barra-superior/barra-superior';
import { MenuLateral } from '../../../compartidos/menu-lateral/menu-lateral';
import { CarritoService } from '../../../servicios/carrito.service';
import { CatalogoService } from '../../../servicios/catalogo.service';

@Component({
  imports: [DecimalPipe, FormsModule, RouterLink, BarraSuperior, BarraInferior, MenuLateral],
  selector: 'app-carrito',
  styleUrl: './carrito.css',
  templateUrl: './carrito.html',
})
export class Carrito {
  private readonly router = inject(Router);
  readonly carritoService = inject(CarritoService);
  readonly catalogoService = inject(CatalogoService);

  menuAbierto = false;
  alertaCantidad = signal<string>('');

  pasoItem(unidad?: string): number {
    const u = (unidad || '').toLowerCase();
    return u.includes('1 kg') || u.trim() === 'kg' ? 0.5 : 1;
  }

  redondear(valor: number): number {
    return Math.round(valor * 100) / 100;
  }

  cambiarCantidad(indice: number, delta: number): void {
    const item = this.carritoService.items()[indice];
    if (!item) return;
    this.alertaCantidad.set('');
    const paso = this.pasoItem(item.producto.unidad);
    const nueva = item.cantidad + delta;
    const ajustada =
      nueva <= 0
        ? 0
        : paso === 0.5
          ? Math.round(nueva * 2) / 2
          : Math.round(nueva);
    this.carritoService.actualizarCantidad(indice, ajustada);
    if (delta > 0 && item.producto.agotado) {
      this.alertaCantidad.set(`${item.producto.nombre} está agotado por hoy.`);
    }
  }

  onCantidadItemInput(indice: number, valor: string | number): void {
    const item = this.carritoService.items()[indice];
    if (!item) return;
    this.alertaCantidad.set('');
    const num = typeof valor === 'number' ? valor : Number(String(valor).replace(',', '.'));
    if (!Number.isFinite(num) || num < 0) {
      return;
    }
    this.carritoService.actualizarCantidad(indice, num);
  }

  normalizarItemAlSalir(indice: number): void {
    const item = this.carritoService.items()[indice];
    if (!item) return;
    const paso = this.pasoItem(item.producto.unidad);
    if (!Number.isFinite(item.cantidad) || item.cantidad <= 0) {
      this.carritoService.eliminarItem(indice);
      return;
    }
    const normalizada = paso === 0.5 ? Math.round(item.cantidad * 2) / 2 : Math.round(item.cantidad);
    if (normalizada !== item.cantidad) {
      this.carritoService.actualizarCantidad(indice, normalizada);
    }
  }

  continuarEntrega(): void {
    if (this.carritoService.items().length === 0) return;
    if (!this.carritoService.puedeConfirmar()) {
      this.alertaCantidad.set(
        this.carritoService.avisoServidor() ||
          'No hay existencia o insumos suficientes para completar el pedido.'
      );
      return;
    }
    this.router.navigate(['/checkout/entrega']);
  }
}