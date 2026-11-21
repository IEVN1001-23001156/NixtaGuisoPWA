import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { BarraInferior } from '../../../compartidos/barra-inferior/barra-inferior';
import { BarraSuperior } from '../../../compartidos/barra-superior/barra-superior';
import { MenuLateral } from '../../../compartidos/menu-lateral/menu-lateral';
import { AuthRolService } from '../../../servicios/auth-rol.service';
import { CarritoService } from '../../../servicios/carrito.service';
import { CatalogoService, ProductoCatalogo } from '../../../servicios/catalogo.service';

@Component({
  imports: [FormsModule, RouterLink, BarraSuperior, BarraInferior, MenuLateral],
  selector: 'app-cotizaciones-b2b',
  styleUrl: './cotizaciones-b2b.css',
  templateUrl: './cotizaciones-b2b.html',
})
export class CotizacionesB2b implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly authRol = inject(AuthRolService);
  private readonly carritoService = inject(CarritoService);
  private readonly catalogoService = inject(CatalogoService);

  private readonly apiUrl = 'http://localhost:5000/api/programaciones';

  menuAbierto = false;
  enviando = signal<boolean>(false);
  mensajeEstado = signal<string>('');
  errorMensaje = signal<string>('');

  productosDisponibles = signal<ProductoCatalogo[]>(this.catalogoService.productosRespaldo);

  nombreNegocio = '';
  idProductoSeleccionado = 1;
  cantidad = 10;
  fechaRequerida = '';
  horaEntrega = '08:30';
  direccionEntrega = '';
  notas = '';

  async ngOnInit(): Promise<void> {
    const u = this.authRol.usuario();
    this.nombreNegocio = u?.cliente?.nombre_negocio?.trim() || '';
    const guardada = this.carritoService.cargarDireccionUsuario(u?.id_usuario ?? null);
    this.direccionEntrega = guardada.calle || u?.cliente?.direccion?.trim() || '';

    const manana = new Date(Date.now() + 86400000);
    this.fechaRequerida = manana.toISOString().slice(0, 10);

    const nivel = u?.cliente?.nivel_b2b ?? 1;
    const lista = await this.catalogoService.obtenerProductos('B2B', nivel);
    if (lista.length > 0) {
      this.productosDisponibles.set(lista);
      this.idProductoSeleccionado = lista[0].id;
    }
  }

  async solicitarCotizacion(event: Event): Promise<void> {
    event.preventDefault();
    if (this.enviando()) return;

    this.errorMensaje.set('');
    this.mensajeEstado.set('');

    if (!this.authRol.usuario()) {
      this.errorMensaje.set('Inicia sesión para enviar una cotización B2B.');
      return;
    }

    const prod =
      this.productosDisponibles().find((p) => p.id === Number(this.idProductoSeleccionado)) ??
      this.productosDisponibles()[0];

    this.enviando.set(true);
    try {
      const resp = await firstValueFrom(
        this.http.post<{ exito?: boolean; mensaje?: string }>(
          this.apiUrl,
          {
            tipo_solicitud: 'cotizacion_b2b',
            nombre_negocio: this.nombreNegocio.trim(),
            frecuencia: 'unica',
            fecha_programada: this.fechaRequerida,
            hora_entrega: this.horaEntrega,
            direccion_entrega: this.direccionEntrega.trim(),
            notas: this.notas.trim(),
            items: [
              {
                id_producto: prod.id,
                cantidad: Number(this.cantidad),
                precio_unitario: Number(prod.precio),
              },
            ],
          },
          { withCredentials: true }
        )
      );

      if (!resp?.exito) {
        this.errorMensaje.set(resp?.mensaje || 'No se pudo enviar la cotización.');
        return;
      }

      this.mensajeEstado.set('Solicitud de cotización B2B registrada.');
      this.notas = '';
    } catch {
      this.errorMensaje.set('No se pudo conectar con el servidor.');
    } finally {
      this.enviando.set(false);
    }
  }
}