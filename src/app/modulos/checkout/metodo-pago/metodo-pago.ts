import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { BarraSuperior } from '../../../compartidos/barra-superior/barra-superior';
import { BarraInferior } from '../../../compartidos/barra-inferior/barra-inferior';
import { MenuLateral } from '../../../compartidos/menu-lateral/menu-lateral';
import { CarritoService } from '../../../servicios/carrito.service';
import { AuthRolService } from '../../../servicios/auth-rol.service';

interface RespuestaPedido {
  exito: boolean;
  mensaje?: string;
  id_pedido?: number;
  folio?: string;
}

@Component({
  imports: [CommonModule, FormsModule, RouterLink, BarraSuperior, BarraInferior, MenuLateral],
  selector: 'app-metodo-pago',
  templateUrl: './metodo-pago.html',
})
export class MetodoPago implements OnInit {
  private readonly router = inject(Router);
  private readonly http = inject(HttpClient);
  private readonly authRol = inject(AuthRolService);
  readonly carritoService = inject(CarritoService);

  menuAbierto = false;

  titular = '';
  numeroTarjeta = '';
  vencimiento = '';
  cvv = '';

  procesando = signal(false);
  errorMensaje = signal('');

  async ngOnInit(): Promise<void> {
    if (!this.authRol.usuario()) {
      await this.authRol.consultarSesionActual();
    }
    const idUsuario = this.authRol.usuario()?.id_usuario ?? null;
    this.carritoService.cargarDireccionUsuario(idUsuario);
  }

  get marcaTarjeta(): string {
    const digitos = this.numeroTarjeta.replace(/\D/g, '');
    if (digitos.startsWith('4')) return 'VISA (SIM)';
    if (/^(5[1-5]|2[2-7])/.test(digitos)) return 'MASTERCARD (SIM)';
    return 'TARJETA SIM';
  }

  onNumeroTarjetaChange(valor: string): void {
    const soloDigitos = valor.replace(/\D/g, '').slice(0, 16);
    this.numeroTarjeta = soloDigitos.replace(/(\d{4})(?=\d)/g, '$1 ').trim();
  }

  onVencimientoChange(valor: string): void {
    const soloDigitos = valor.replace(/\D/g, '').slice(0, 4);
    if (soloDigitos.length <= 2) {
      this.vencimiento = soloDigitos;
    } else {
      this.vencimiento = `${soloDigitos.slice(0, 2)}/${soloDigitos.slice(2)}`;
    }
  }

  onCvvChange(valor: string): void {
    this.cvv = valor.replace(/\D/g, '').slice(0, 4);
  }

  async confirmarPago(event: Event): Promise<void> {
    event.preventDefault();
    this.errorMensaje.set('');

    if (this.carritoService.items().length === 0) {
      this.errorMensaje.set('Tu carrito está vacío.');
      return;
    }

    const usuario = this.authRol.usuario();
    const idUsuario = usuario?.id_usuario ?? null;
    const dir = this.carritoService.cargarDireccionUsuario(idUsuario);
    const resumenDireccion = this.carritoService.direccionResumen().trim();
    const direccionFinal =
      resumenDireccion ||
      usuario?.cliente?.direccion?.trim() ||
      [dir.calle, dir.colonia, dir.ciudad].filter(Boolean).join(', ');

    if (!direccionFinal || direccionFinal.length < 5) {
      this.errorMensaje.set('Escribe la dirección de entrega en el paso anterior.');
      return;
    }

    const digitos = this.numeroTarjeta.replace(/\D/g, '');
    const partesFecha = this.vencimiento.split('/');
    const mes = Number(partesFecha[0] || 0);

    if (!this.titular.trim()) {
      this.errorMensaje.set('Ingresa el nombre del titular.');
      return;
    }
    if (digitos.length !== 16) {
      this.errorMensaje.set('El número de tarjeta debe tener 16 dígitos.');
      return;
    }
    if (this.vencimiento.length !== 5 || mes < 1 || mes > 12) {
      this.errorMensaje.set('Ingresa una vigencia válida en formato MM/AA.');
      return;
    }
    if (this.cvv.length < 3) {
      this.errorMensaje.set('Ingresa el código CVV.');
      return;
    }

    this.procesando.set(true);
    try {
      const payload = {
        modalidad: 'domicilio',
        metodo_pago: 'tarjeta',
        direccion: direccionFinal,
        direccion_entrega: direccionFinal,
        telefono_contacto: usuario?.telefono?.trim() || '4770000000',
        tarjeta: {
          titular: this.titular.trim(),
          numero: digitos,
          vencimiento: this.vencimiento.trim(),
          cvv: this.cvv.trim(),
        },
        productos: this.carritoService.items().map((i) => ({
          id_producto: i.producto.id,
          cantidad: i.cantidad,
          nota_especial: i.notaEspecial,
          salsa: i.salsa ?? null,
          agua: i.agua ?? null,
          arma: i.arma ?? null,
        })),
      };

      const resp = await firstValueFrom(
        this.http.post<RespuestaPedido>('http://localhost:5000/api/pedidos', payload, {
          withCredentials: true,
        })
      );

      if (resp && resp.exito === false) {
        this.errorMensaje.set(resp.mensaje || 'No se pudo procesar el pedido.');
        return;
      }

      this.carritoService.vaciar();
      await this.router.navigate(['/checkout/confirmacion']);
    } catch (err: any) {
      this.errorMensaje.set(
        err?.error?.mensaje || 'Ocurrió un error al registrar el pedido en el servidor.'
      );
    } finally {
      this.procesando.set(false);
    }
  }
}