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

export interface PedidoProgramadoItem {
  id_programacion: number;
  frecuencia: string;
  fecha_programada: string;
  hora_entrega: string;
  estado: string;
  direccion_entrega: string;
  total_estimado: number;
  resumen: string;
}

interface RespuestaProgramaciones {
  exito?: boolean;
  programaciones?: PedidoProgramadoItem[];
  mensaje?: string;
}

@Component({
  imports: [FormsModule, RouterLink, BarraSuperior, BarraInferior, MenuLateral],
  selector: 'app-calendario-agendamiento',
  styleUrl: './calendario-agendamiento.css',
  templateUrl: './calendario-agendamiento.html',
})
export class CalendarioAgendamiento implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly authRol = inject(AuthRolService);
  private readonly carritoService = inject(CarritoService);
  private readonly catalogoService = inject(CatalogoService);

  private readonly apiUrl = 'http://localhost:5000/api/programaciones';

  menuAbierto = false;
  cargando = signal<boolean>(true);
  guardando = signal<boolean>(false);
  mensajeEstado = signal<string>('');
  errorMensaje = signal<string>('');

  programaciones = signal<PedidoProgramadoItem[]>([]);
  productosDisponibles = signal<ProductoCatalogo[]>(this.catalogoService.productosRespaldo);

  idProductoSeleccionado = 1;
  cantidad = 1;
  frecuencia: 'unica' | 'semanal' | 'quincenal' = 'semanal';
  fechaProgramada = '';
  horaEntrega = '09:00';
  direccionEntrega = '';

  async ngOnInit(): Promise<void> {
    const u = this.authRol.usuario();
    const guardada = this.carritoService.cargarDireccionUsuario(u?.id_usuario ?? null);
    this.direccionEntrega =
      guardada.calle ||
      u?.cliente?.direccion?.trim() ||
      '';

    const manana = new Date(Date.now() + 86400000);
    this.fechaProgramada = manana.toISOString().slice(0, 10);

    await this.cargarDatos();
  }

  productoSeleccionado(): ProductoCatalogo | undefined {
    return this.productosDisponibles().find((p) => p.id === Number(this.idProductoSeleccionado));
  }

  pasoProducto(prod?: ProductoCatalogo): number {
    const u = (prod?.unidad || '').toLowerCase();
    return u.includes('1 kg') || u.trim() === 'kg' ? 0.5 : 1;
  }

  minimoProducto(prod?: ProductoCatalogo): number {
    return this.pasoProducto(prod);
  }

  alCambiarProducto(): void {
    this.errorMensaje.set('');
    this.normalizarCantidad();
  }

  normalizarCantidad(): void {
    const prod = this.productoSeleccionado();
    const min = this.minimoProducto(prod);
    const paso = this.pasoProducto(prod);
    const num = Number(this.cantidad);
    if (!Number.isFinite(num) || num < min) {
      this.cantidad = min;
      return;
    }
    this.cantidad = paso === 0.5 ? Math.round(num * 2) / 2 : Math.round(num);
  }

  async cargarDatos(): Promise<void> {
    this.cargando.set(true);
    try {
      const nivel = this.authRol.usuario()?.cliente?.nivel_b2b ?? 1;
      const listaProd = await this.catalogoService.obtenerProductos(
        this.authRol.tipoCuenta(),
        nivel
      );
      if (listaProd.length > 0) {
        this.productosDisponibles.set(listaProd);
        if (!listaProd.some((p) => p.id === this.idProductoSeleccionado)) {
          this.idProductoSeleccionado = listaProd[0].id;
        }
      }

      const resp = await firstValueFrom(
        this.http.get<RespuestaProgramaciones>(this.apiUrl, { withCredentials: true })
      );
      if (resp?.exito && Array.isArray(resp.programaciones)) {
        this.programaciones.set(resp.programaciones);
      }
    } catch {
      this.programaciones.set([]);
    } finally {
      this.cargando.set(false);
    }
  }

  async guardarProgramacion(event: Event): Promise<void> {
    event.preventDefault();
    if (this.guardando()) return;

    this.errorMensaje.set('');
    this.mensajeEstado.set('');
    this.normalizarCantidad();

    if (!this.authRol.usuario()) {
      this.errorMensaje.set('Inicia sesión para agendar un pedido programado.');
      return;
    }

    if (!this.fechaProgramada || this.cantidad <= 0) {
      this.errorMensaje.set('Selecciona una fecha válida y cantidad mayor a 0.');
      return;
    }

    const prod =
      this.productoSeleccionado() ??
      this.productosDisponibles()[0];

    if (prod?.agotado) {
      this.errorMensaje.set(`${prod.nombre} está agotado o no tiene insumos suficientes.`);
      return;
    }

    this.guardando.set(true);
    try {
      if (prod) {
        const validacion = await this.carritoService.validarDisponibilidadAdicion(
          prod,
          Number(this.cantidad)
        );
        if (!validacion.ok) {
          this.errorMensaje.set(
            validacion.mensaje || 'No hay existencia o insumos suficientes para esa cantidad.'
          );
          return;
        }
      }

      const resp = await firstValueFrom(
        this.http.post<RespuestaProgramaciones>(
          this.apiUrl,
          {
            tipo_solicitud: 'calendario',
            frecuencia: this.frecuencia,
            fecha_programada: this.fechaProgramada,
            hora_entrega: this.horaEntrega,
            direccion_entrega: this.direccionEntrega.trim(),
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
        this.errorMensaje.set(resp?.mensaje || 'No se pudo programar el pedido.');
        return;
      }

      this.mensajeEstado.set('Entrega programada registrada.');
      await this.cargarDatos();
    } catch (e: any) {
      this.errorMensaje.set(e?.status ? (e?.error?.mensaje || 'No se pudo guardar la solicitud.') : 'No se pudo conectar con el servidor.');
    } finally {
      this.guardando.set(false);
    }
  }

  etiquetaFrecuencia(freq: string): string {
    const mapa: Record<string, string> = {
      unica: 'Una vez',
      semanal: 'Semanal',
      quincenal: 'Quincenal',
    };
    return mapa[(freq || '').toLowerCase()] ?? freq;
  }
} 