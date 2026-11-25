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

/** Un renglón de la cotización: producto y cantidad */
interface LineaCotizacion {
  idProducto: number;
  cantidad: number;
}

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

  productosDisponibles = signal<ProductoCatalogo[]>([]);

  nombreNegocio = '';
  lineas: LineaCotizacion[] = [];
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
    const lista = await this.catalogoService.obtenerProductos(this.authRol.tipoCuenta(), nivel);
    const disponibles = lista.filter((p) => !p.agotado);
    this.productosDisponibles.set(disponibles);
    this.lineas = disponibles.length ? [{ idProducto: disponibles[0].id, cantidad: 1 }] : [];
  }

  producto(id: number): ProductoCatalogo | undefined {
    return this.productosDisponibles().find((p) => p.id === Number(id));
  }

  pasoLinea(indice: number): number {
    const u = (this.producto(this.lineas[indice]?.idProducto)?.unidad || '').toLowerCase();
    return u.includes('1 kg') || u.trim() === 'kg' ? 0.5 : 1;
  }

  minimoLinea(indice: number): number {
    return this.pasoLinea(indice);
  }

  normalizarLinea(indice: number): void {
    const linea = this.lineas[indice];
    if (!linea) return;
    this.errorMensaje.set('');
    const min = this.minimoLinea(indice);
    const paso = this.pasoLinea(indice);
    const num = Number(linea.cantidad);
    if (!Number.isFinite(num) || num < min) {
      linea.cantidad = min;
      return;
    }
    linea.cantidad = paso === 0.5 ? Math.round(num * 2) / 2 : Math.round(num);
  }

  agregarLinea(): void {
    const usados = new Set(this.lineas.map((l) => Number(l.idProducto)));
    const siguiente = this.productosDisponibles().find((p) => !usados.has(p.id)) ?? this.productosDisponibles()[0];
    if (siguiente) this.lineas = [...this.lineas, { idProducto: siguiente.id, cantidad: 1 }];
  }

  quitarLinea(indice: number): void {
    this.lineas = this.lineas.filter((_, i) => i !== indice);
  }

  /** Estimado con los precios del catálogo; el total oficial lo calcula Flask */
  get totalEstimado(): number {
    return this.lineas.reduce((suma, l) => suma + (this.producto(l.idProducto)?.precio ?? 0) * Number(l.cantidad || 0), 0);
  }

  async solicitarCotizacion(event: Event): Promise<void> {
    event.preventDefault();
    if (this.enviando()) return;

    this.errorMensaje.set('');
    this.mensajeEstado.set('');
    this.lineas.forEach((_, idx) => this.normalizarLinea(idx));

    if (!this.authRol.usuario()) {
      this.errorMensaje.set('Inicia sesión para enviar tu cotización.');
      return;
    }

    const items = this.lineas
      .filter((l) => Number(l.cantidad) > 0)
      .map((l) => ({ id_producto: Number(l.idProducto), cantidad: Number(l.cantidad) }));

    if (items.length === 0) {
      this.errorMensaje.set('Agrega al menos un producto con su cantidad.');
      return;
    }

    for (const item of items) {
      const prod = this.producto(item.id_producto);
      if (prod?.agotado) {
        this.errorMensaje.set(`${prod.nombre} está agotado o no tiene insumos suficientes.`);
        return;
      }
      if (prod) {
        const validacion = await this.carritoService.validarDisponibilidadAdicion(prod, item.cantidad);
        if (!validacion.ok) {
          this.errorMensaje.set(
            validacion.mensaje || `Existencia o insumos insuficientes para ${prod.nombre}.`
          );
          return;
        }
      }
    }

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
            items,
          },
          { withCredentials: true }
        )
      );

      if (!resp?.exito) {
        this.errorMensaje.set(resp?.mensaje || 'No se pudo enviar la cotización.');
        return;
      }

      this.mensajeEstado.set('Tu solicitud de cotización quedó registrada. Puedes verla en tus entregas agendadas.');
      this.notas = '';
    } catch (e: any) {
      this.errorMensaje.set(e?.status ? (e?.error?.mensaje || 'No se pudo guardar la solicitud.') : 'No se pudo conectar con el servidor.');
    } finally {
      this.enviando.set(false);
    }
  }
}