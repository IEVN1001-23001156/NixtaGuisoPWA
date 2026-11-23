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
  selector: 'app-formulario-especial',
  styleUrl: './formulario-especial.css',
  templateUrl: './formulario-especial.html',
})
export class FormularioEspecial implements OnInit {
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

  idProductoSeleccionado = 1;
  cantidad = 1;
  fechaProgramada = '';
  horaEntrega = '10:00';
  direccionEntrega = '';
  especificaciones = '';

  async ngOnInit(): Promise<void> {
    const u = this.authRol.usuario();
    const guardada = this.carritoService.cargarDireccionUsuario(u?.id_usuario ?? null);
    this.direccionEntrega = guardada.calle || u?.cliente?.direccion?.trim() || '';

    const manana = new Date(Date.now() + 86400000);
    this.fechaProgramada = manana.toISOString().slice(0, 10);

    const nivel = u?.cliente?.nivel_b2b ?? 1;
    const lista = await this.catalogoService.obtenerProductos(
      this.authRol.tipoCuenta(),
      nivel
    );
    if (lista.length > 0) {
      this.productosDisponibles.set(lista);
      this.idProductoSeleccionado = lista[0].id;
    }
  }

  async enviarPedidoEspecial(event: Event): Promise<void> {
    event.preventDefault();
    if (this.enviando()) return;

    this.errorMensaje.set('');
    this.mensajeEstado.set('');

    if (!this.authRol.usuario()) {
      this.errorMensaje.set('Inicia sesión para registrar un pedido especial.');
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
            tipo_solicitud: 'especial',
            frecuencia: 'unica',
            fecha_programada: this.fechaProgramada,
            hora_entrega: this.horaEntrega,
            direccion_entrega: this.direccionEntrega.trim(),
            notas: this.especificaciones.trim(),
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
        this.errorMensaje.set(resp?.mensaje || 'No se pudo guardar el pedido especial.');
        return;
      }

      this.mensajeEstado.set('Pedido especial registrado.');
      this.especificaciones = '';
    } catch (e: any) {
      this.errorMensaje.set(e?.status ? (e?.error?.mensaje || 'No se pudo guardar la solicitud.') : 'No se pudo conectar con el servidor.');
    } finally {
      this.enviando.set(false);
    }
  }
}