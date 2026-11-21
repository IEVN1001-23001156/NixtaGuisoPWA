import { Component, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { BarraInferior } from '../../../compartidos/barra-inferior/barra-inferior';
import { BarraSuperior } from '../../../compartidos/barra-superior/barra-superior';
import { MenuLateral } from '../../../compartidos/menu-lateral/menu-lateral';
import { CarritoService } from '../../../servicios/carrito.service';
import { PedidosService } from '../../../servicios/pedidos.service';

@Component({
  imports: [RouterLink, BarraSuperior, BarraInferior, MenuLateral],
  selector: 'app-metodo-pago',
  styleUrl: './metodo-pago.css',
  templateUrl: './metodo-pago.html',
})
export class MetodoPago {
  private readonly router = inject(Router);
  readonly carritoService = inject(CarritoService);
  private readonly pedidosService = inject(PedidosService);

  menuAbierto = false;
  metodoSeleccionado: 'tarjeta' = 'tarjeta';
  enviando = signal<boolean>(false);
  errorMensaje = signal<string>('');

  async confirmarPedido(): Promise<void> {
    if (this.enviando()) return;

    if (this.carritoService.items().length === 0) {
      this.errorMensaje.set('Tu carrito está vacío.');
      return;
    }

    this.errorMensaje.set('');
    this.enviando.set(true);

    try {
      await this.pedidosService.crearPedido(
        this.carritoService.items(),
        this.carritoService.direccionEntrega(),
        this.metodoSeleccionado,
        this.carritoService.subtotal(),
        this.carritoService.envio(),
        this.carritoService.total()
      );
      this.carritoService.vaciar();
      this.router.navigate(['/checkout/confirmacion']);
    } catch {
      this.errorMensaje.set('No se pudo registrar el pedido. Intenta de nuevo.');
    } finally {
      this.enviando.set(false);
    }
  }
}