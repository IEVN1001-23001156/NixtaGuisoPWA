import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import { Respuesta } from '../interfaces/respuesta';
import {
  ClienteFicha, ClienteResumen, Compra, Dashboard, Gasto, Insumo, Merma, Meta, PedidoAdmin, PedidoAdminDetalle,
  ProductoAdmin, Produccion, Receta, Repartidor, Reporte, Ruta, Parada
} from '../interfaces/admin';
import { EstadoPedido } from '../interfaces/pedidos';

type R<T> = Observable<Respuesta & T>;

@Injectable({ providedIn: 'root' })
export class AdminService {

  private http = inject(HttpClient);
  private api = `${environment.apiUrl}/api/admin`;

  private params(filtros: Record<string, string | number | undefined | null>): HttpParams {
    let p = new HttpParams();
    for (const [k, v] of Object.entries(filtros)) if (v !== undefined && v !== null && v !== '') p = p.set(k, v);
    return p;
  }

  dashboard(fecha?: string): Observable<Respuesta & Dashboard> {
    return this.http.get<Respuesta & Dashboard>(`${this.api}/dashboard`, { params: this.params({ fecha }) });
  }
  reportes(mes?: string): Observable<Respuesta & Reporte> {
    return this.http.get<Respuesta & Reporte>(`${this.api}/reportes`, { params: this.params({ mes }) });
  }
  gastos(mes?: string): R<{ total: number; gastos: Gasto[] }> {
    return this.http.get<Respuesta & { total: number; gastos: Gasto[] }>(`${this.api}/gastos-mercadeo`, { params: this.params({ mes }) });
  }
  crearGasto(datos: Partial<Gasto>): R<{}> { return this.http.post<Respuesta>(`${this.api}/gastos-mercadeo`, datos); }
  eliminarGasto(id: number): R<{}> { return this.http.delete<Respuesta>(`${this.api}/gastos-mercadeo/${id}`); }
  metas(): R<{ metas: Meta[] }> { return this.http.get<Respuesta & { metas: Meta[] }>(`${this.api}/metas`); }
  editarMeta(id: number, valor_meta: number): R<{}> { return this.http.put<Respuesta>(`${this.api}/metas/${id}`, { valor_meta }); }

  productos(filtros: { categoria?: string; buscar?: string; estado?: string } = {}): R<{ total: number; productos: ProductoAdmin[] }> {
    return this.http.get<Respuesta & { total: number; productos: ProductoAdmin[] }>(`${this.api}/productos`, { params: this.params(filtros) });
  }
  producto(id: number): R<{ producto: ProductoAdmin }> { return this.http.get<Respuesta & { producto: ProductoAdmin }>(`${this.api}/productos/${id}`); }
  crearProducto(datos: Partial<ProductoAdmin>): R<{ producto: ProductoAdmin }> { return this.http.post<Respuesta & { producto: ProductoAdmin }>(`${this.api}/productos`, datos); }
  editarProducto(id: number, datos: Partial<ProductoAdmin>): R<{ producto: ProductoAdmin }> { return this.http.put<Respuesta & { producto: ProductoAdmin }>(`${this.api}/productos/${id}`, datos); }
  cambiarDisponible(id: number, disponible: boolean): R<{}> { return this.http.patch<Respuesta>(`${this.api}/productos/${id}/disponible`, { disponible }); }
  bajaProducto(id: number): R<{}> { return this.http.delete<Respuesta>(`${this.api}/productos/${id}`); }
  subirImagen(id: number, archivo: File): R<{ imagen_url: string }> {
    const f = new FormData(); f.append('imagen', archivo);
    return this.http.post<Respuesta & { imagen_url: string }>(`${this.api}/productos/${id}/imagen`, f);
  }
  editarCategoria(id: number, datos: { nombre: string; descripcion: string | null; orden: number }): R<{}> {
    return this.http.put<Respuesta>(`${this.api}/categorias/${id}`, datos);
  }

  insumos(): R<{ por_surtir: number; insumos: Insumo[] }> { return this.http.get<Respuesta & { por_surtir: number; insumos: Insumo[] }>(`${this.api}/insumos`); }
  crearInsumo(datos: Partial<Insumo>): R<{}> { return this.http.post<Respuesta>(`${this.api}/insumos`, datos); }
  editarInsumo(id: number, datos: Partial<Insumo> & { activo?: boolean }): R<{}> { return this.http.put<Respuesta>(`${this.api}/insumos/${id}`, datos); }
  compras(): R<{ compras: Compra[] }> { return this.http.get<Respuesta & { compras: Compra[] }>(`${this.api}/compras`); }
  registrarCompra(datos: { id_insumo: number; cantidad: number; costo_total: number; proveedor?: string }): R<{}> { return this.http.post<Respuesta>(`${this.api}/compras`, datos); }
  recetas(): R<{ recetas: Receta[] }> { return this.http.get<Respuesta & { recetas: Receta[] }>(`${this.api}/recetas`); }
  crearReceta(datos: {
    id_producto: number;
    nombre: string;
    rendimiento: number;
    costo_lote: number;
    insumos: { id_insumo: number; cantidad: number }[];
  }): R<{ id_receta?: number }> {
    return this.http.post<Respuesta & { id_receta?: number }>(`${this.api}/recetas`, datos);
  }
  eliminarReceta(id: number): R<{}> { return this.http.delete<Respuesta>(`${this.api}/recetas/${id}`); }
  producciones(): R<{ producciones: Produccion[] }> { return this.http.get<Respuesta & { producciones: Produccion[] }>(`${this.api}/producciones`); }
  registrarProduccion(datos: { id_receta: number; num_lotes: number; notas?: string }): R<{ cantidad_producida: number }> {
    return this.http.post<Respuesta & { cantidad_producida: number }>(`${this.api}/producciones`, datos);
  }
  mermas(mes?: string): R<{ total_mermas: number; costo_total_estimado: number; mermas: Merma[] }> {
    return this.http.get<Respuesta & { total_mermas: number; costo_total_estimado: number; mermas: Merma[] }>(`${this.api}/mermas`, { params: this.params({ mes }) });
  }
  registrarMerma(datos: { id_insumo?: number; id_producto?: number; cantidad: number; motivo: string }): R<{}> { return this.http.post<Respuesta>(`${this.api}/mermas`, datos); }

  clientes(filtros: { tipo?: string; buscar?: string } = {}): R<{ total: number; clientes: ClienteResumen[] }> {
    return this.http.get<Respuesta & { total: number; clientes: ClienteResumen[] }>(`${this.api}/clientes`, { params: this.params(filtros) });
  }
  cliente(id: number): R<{ cliente: ClienteFicha }> { return this.http.get<Respuesta & { cliente: ClienteFicha }>(`${this.api}/clientes/${id}`); }
  actualizarCliente(id: number, datos: { nivel_b2b?: number; preferencias?: string; activo?: boolean }): R<{}> { return this.http.put<Respuesta>(`${this.api}/clientes/${id}`, datos); }

  repartidores(incluirInactivos = false): R<{ repartidores: Repartidor[] }> {
    return this.http.get<Respuesta & { repartidores: Repartidor[] }>(`${this.api}/repartidores`, { params: this.params({ incluir_inactivos: incluirInactivos ? 1 : null }) });
  }
  crearRepartidor(datos: Partial<Repartidor>): R<{}> { return this.http.post<Respuesta>(`${this.api}/repartidores`, datos); }
  editarRepartidor(id: number, datos: Partial<Repartidor>): R<{}> { return this.http.put<Respuesta>(`${this.api}/repartidores/${id}`, datos); }

  pedidos(filtros: { estado?: string; fecha?: string; tipo?: string } = {}): R<{ conteo: Record<EstadoPedido, number>; pedidos: PedidoAdmin[] }> {
    return this.http.get<Respuesta & { conteo: Record<EstadoPedido, number>; pedidos: PedidoAdmin[] }>(`${this.api}/pedidos`, { params: this.params(filtros) });
  }
  pedido(id: number): R<{ pedido: PedidoAdminDetalle }> { return this.http.get<Respuesta & { pedido: PedidoAdminDetalle }>(`${this.api}/pedidos/${id}`); }
  cambiarEstado(id: number, estado: EstadoPedido, motivo?: string): R<{ bono_referido: boolean }> {
    return this.http.put<Respuesta & { bono_referido: boolean }>(`${this.api}/pedidos/${id}/estado`, { estado, ...(motivo ? { motivo } : {}) });
  }
  validarPago(id: number, accion: 'validar' | 'rechazar'): R<{}> { return this.http.put<Respuesta>(`${this.api}/pedidos/${id}/pago`, { accion }); }
  asignarRepartidor(id: number, id_repartidor: number): R<{}> { return this.http.put<Respuesta>(`${this.api}/pedidos/${id}/repartidor`, { id_repartidor }); }
  corregirUbicacion(id: number, latitud: number, longitud: number): R<{}> { return this.http.put<Respuesta>(`${this.api}/pedidos/${id}/ubicacion`, { latitud, longitud }); }
  urlComprobante(id: number): string { return `${this.api}/pedidos/${id}/comprobante`; }
  generarProgramados(): R<{ generados: { id_pedido: number; cliente: string; total: number }[]; omitidos: { cliente: string; motivo: string }[] }> {
    return this.http.post<Respuesta & { generados: { id_pedido: number; cliente: string; total: number }[]; omitidos: { cliente: string; motivo: string }[] }>(`${this.api}/programaciones/generar`, {});
  }
  rutas(fecha?: string): R<{ fecha: string; rutas: Ruta[]; sin_asignar: Parada[]; pedidos_sin_ubicacion: number }> {
    return this.http.get<Respuesta & { fecha: string; rutas: Ruta[]; sin_asignar: Parada[]; pedidos_sin_ubicacion: number }>(`${this.api}/rutas`, { params: this.params({ fecha }) });
  }
  guardarOrden(id_repartidor: number, pedidos: number[]): R<{}> { return this.http.put<Respuesta>(`${this.api}/rutas/orden`, { id_repartidor, pedidos }); }

  contadores(): Observable<any> { return this.http.get(`${this.api}/contadores`); }
  buscar(q: string): Observable<any> { return this.http.get(`${this.api}/buscar`, { params: this.params({ q }) }); }
  kilosCanal(dias = 6, fecha?: string): Observable<any> { return this.http.get(`${this.api}/kilos-canal`, { params: this.params({ dias, fecha }) }); }
  planKilos(): Observable<any> { return this.http.get(`${this.api}/plan-kilos`); }
  consumoCliente(id: number): Observable<any> { return this.http.get(`${this.api}/clientes/${id}/consumo`); }
  receta(id: number): Observable<any> { return this.http.get(`${this.api}/recetas/${id}`); }
  editarReceta(id: number, datos: any): R<{}> { return this.http.put<Respuesta>(`${this.api}/recetas/${id}`, datos); }
  editarGasto(id: number, datos: Partial<Gasto>): R<{}> { return this.http.put<Respuesta>(`${this.api}/gastos-mercadeo/${id}`, datos); }
  anularCompra(id: number): R<{}> { return this.http.delete<Respuesta>(`${this.api}/compras/${id}`); }
  anularProduccion(id: number): R<{}> { return this.http.delete<Respuesta>(`${this.api}/producciones/${id}`); }
  anularMerma(id: number): R<{}> { return this.http.delete<Respuesta>(`${this.api}/mermas/${id}`); }
  categorias(): Observable<any> { return this.http.get(`${environment.apiUrl}/api/categorias`); }
  programacionesActivas(): Observable<any> { return this.http.get(`${environment.apiUrl}/api/programaciones`); }
  productoTerminado(): Observable<any> { return this.http.get(`${environment.apiUrl}/api/inventario/productos`); }
  reabastecer(id_producto: number, cantidad: number): R<{}> { return this.http.post<Respuesta>(`${environment.apiUrl}/api/inventario/reabastecer`, { id_producto, cantidad }); }
  ajustarExistencia(id_producto: number, existencia: number): R<{}> { return this.http.put<Respuesta>(`${environment.apiUrl}/api/inventario/productos/${id_producto}`, { existencia }); }
}