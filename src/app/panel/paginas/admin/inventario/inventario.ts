import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { CurrencyPipe, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { AdminService } from '../../../servicios/admin.service';
import { AvisosService } from '../../../servicios/avisos.service';
import { Compra, Insumo, Merma, Produccion, ProductoAdmin, Receta } from '../../../interfaces/admin';

type Pestana = 'stock' | 'compras' | 'produccion' | 'mermas';

/** Inventario, insumos y producción (Módulo 8) */
@Component({
  selector: 'app-inventario',
  imports: [CurrencyPipe, DecimalPipe, FormsModule],
  templateUrl: './inventario.html'
})
export class Inventario implements OnInit {
  private admin = inject(AdminService);
  private avisos = inject(AvisosService);

  pestana = signal<Pestana>('stock');
  insumos = signal<Insumo[]>([]);
  terminado = signal<any[]>([]);
  compras = signal<Compra[]>([]);
  recetas = signal<Receta[]>([]);
  producciones = signal<Produccion[]>([]);
  mermas = signal<Merma[]>([]);
  costoMermas = signal(0);
  productos = signal<ProductoAdmin[]>([]);
  filtroStock = signal<'todos' | 'optimo' | 'por_surtir'>('todos');
  guardandoReceta = signal(false);

  insumosFiltrados = computed(() => this.filtroStock() === 'todos' ? this.insumos() : this.insumos().filter(i => i.estado === this.filtroStock()));
  porSurtir = computed(() => this.insumos().filter(i => i.estado === 'por_surtir').length);

  // Edición y creación
  insumoEditado = signal<any>(null);
  recetaEditada = signal<any>(null);
  cantidades: Record<number, number> = {};

  nuevoInsumo = { nombre: '', unidad: 'kg', stock_minimo: 0, costo_unitario: null as number | null };
  compra = { id_insumo: 0, cantidad: null as number | null, costo_total: null as number | null, proveedor: '' };
  produccion = { id_receta: 0, num_lotes: 1, notas: '' };
  merma = { tipo: 'insumo' as 'insumo' | 'producto', id: 0, cantidad: null as number | null, motivo: '' };
  nuevaReceta = {
    id_producto: 0,
    nombre: '',
    rendimiento: 1,
    costo_lote: 0,
    insumos: [{ id_insumo: 0, cantidad: 0 }] as { id_insumo: number; cantidad: number }[],
  };

  recetaElegida = computed(() => this.recetas().find(r => r.id_receta === Number(this.produccion.id_receta)) ?? null);

  ngOnInit(): void { this.cargarTodo(); }

  cargarTodo(): void {
    this.admin.insumos().subscribe(r => this.insumos.set(r.insumos));
    this.admin.productoTerminado().subscribe(r => this.terminado.set(r.productos));
    this.admin.compras().subscribe(r => this.compras.set(r.compras));
    this.admin.recetas().subscribe(r => this.recetas.set(r.recetas));
    this.admin.producciones().subscribe(r => this.producciones.set(r.producciones));
    this.admin.mermas().subscribe(r => { this.mermas.set(r.mermas); this.costoMermas.set(r.costo_total_estimado); });
    this.admin.productos().subscribe(r => this.productos.set(r.productos.filter(p => !p.es_paquete)));
  }

  private resultado(mensaje = 'Guardado', despues?: () => void) {
    return {
      next: (r: { mensaje?: string }) => { this.avisos.mostrar(r.mensaje ?? mensaje); despues?.(); this.cargarTodo(); },
      error: (err: { error?: { mensaje?: string } }) => this.avisos.error(err.error?.mensaje || 'No se pudo guardar')
    };
  }

  /** Barra de nivel: existencia frente al doble del mínimo */
  nivel(existencia: number, minimo: number): number {
    if (!minimo) return 100;
    return Math.min(100, Math.round((existencia / (minimo * 2)) * 100));
  }

  // ---------- Insumos ----------
  editarInsumo(i: Insumo): void {
    this.insumoEditado.set({ id_insumo: i.id_insumo, nombre: i.nombre, unidad: i.unidad, stock_minimo: i.stock_minimo, costo_unitario: i.costo_unitario, activo: true });
  }

  guardarInsumo(): void {
    const i = this.insumoEditado();
    this.admin.editarInsumo(i.id_insumo, { nombre: i.nombre, stock_minimo: Number(i.stock_minimo), costo_unitario: i.costo_unitario === null || i.costo_unitario === '' ? null : Number(i.costo_unitario), activo: i.activo } as any)
      .subscribe(this.resultado('Insumo actualizado', () => this.insumoEditado.set(null)));
  }

  crearInsumo(): void {
    this.admin.crearInsumo(this.nuevoInsumo as Partial<Insumo>).subscribe(this.resultado('Insumo agregado'));
    this.nuevoInsumo = { nombre: '', unidad: 'kg', stock_minimo: 0, costo_unitario: null };
  }

  // ---------- Producto terminado ----------
  reabastecer(p: any): void {
    const cantidad = Number(this.cantidades[p.id_producto]);
    if (!cantidad || cantidad <= 0) { this.avisos.error('Escribe la cantidad a sumar'); return; }
    this.admin.reabastecer(p.id_producto, cantidad).subscribe(this.resultado(`+${cantidad} a ${p.nombre}`, () => this.cantidades[p.id_producto] = 0));
  }

  ajustar(p: any): void {
    const valor = prompt(`Conteo físico de ${p.nombre} (existencia actual: ${p.existencia}):`, String(p.existencia));
    if (valor === null || valor.trim() === '' || isNaN(Number(valor))) return;
    this.admin.ajustarExistencia(p.id_producto, Number(valor)).subscribe(this.resultado('Existencia ajustada'));
  }

  // ---------- Compras, recetas y producción ----------
  registrarCompra(): void {
    this.admin.registrarCompra({ ...this.compra, cantidad: Number(this.compra.cantidad), costo_total: Number(this.compra.costo_total) }).subscribe(this.resultado());
    this.compra = { id_insumo: this.compra.id_insumo, cantidad: null, costo_total: null, proveedor: '' };
  }

  registrarProduccion(): void {
    this.admin.registrarProduccion(this.produccion).subscribe(this.resultado());
    this.produccion = { ...this.produccion, num_lotes: 1, notas: '' };
  }

  agregarInsumoNuevaReceta(): void {
    const usados = new Set(this.nuevaReceta.insumos.map(i => Number(i.id_insumo)));
    const libre = this.insumos().find(i => !usados.has(i.id_insumo)) ?? this.insumos()[0];
    this.nuevaReceta.insumos.push({ id_insumo: libre?.id_insumo ?? 0, cantidad: 0 });
  }

  quitarInsumoNuevaReceta(indice: number): void {
    this.nuevaReceta.insumos.splice(indice, 1);
  }

  crearReceta(): void {
    const insumosValidos = this.nuevaReceta.insumos
      .filter(i => Number(i.id_insumo) > 0 && Number(i.cantidad) > 0)
      .map(i => ({ id_insumo: Number(i.id_insumo), cantidad: Number(i.cantidad) }));

    if (!this.nuevaReceta.id_producto || !this.nuevaReceta.nombre.trim() || insumosValidos.length === 0) {
      this.avisos.error('Selecciona un producto, un nombre y al menos un insumo con cantidad mayor a 0');
      return;
    }

    this.guardandoReceta.set(true);
    this.admin.crearReceta({
      id_producto: Number(this.nuevaReceta.id_producto),
      nombre: this.nuevaReceta.nombre.trim(),
      rendimiento: Number(this.nuevaReceta.rendimiento),
      costo_lote: Number(this.nuevaReceta.costo_lote || 0),
      insumos: insumosValidos,
    }).subscribe({
      ...this.resultado('Receta creada', () => {
        this.nuevaReceta = {
          id_producto: 0,
          nombre: '',
          rendimiento: 1,
          costo_lote: 0,
          insumos: [{ id_insumo: 0, cantidad: 0 }],
        };
        this.guardandoReceta.set(false);
      }),
      error: (err: { error?: { mensaje?: string } }) => {
        this.guardandoReceta.set(false);
        this.avisos.error(err.error?.mensaje || 'No se pudo crear la receta');
      },
    });
  }

  editarReceta(r: Receta): void {
    this.admin.receta(r.id_receta).subscribe(x => this.recetaEditada.set({ ...x.receta, insumos: x.receta.insumos.map((i: any) => ({ ...i })) }));
  }

  agregarInsumoReceta(): void {
    const receta = this.recetaEditada();
    const usados = new Set(receta.insumos.map((i: any) => i.id_insumo));
    const libre = this.insumos().find(i => !usados.has(i.id_insumo));
    if (libre) receta.insumos.push({ id_insumo: libre.id_insumo, nombre: libre.nombre, unidad: libre.unidad, cantidad: 1 });
  }

  guardarReceta(): void {
    const r = this.recetaEditada();
    this.admin.editarReceta(r.id_receta, {
      nombre: r.nombre, rendimiento: Number(r.rendimiento), costo_lote: Number(r.costo_lote),
      insumos: r.insumos.map((i: any) => ({ id_insumo: Number(i.id_insumo), cantidad: Number(i.cantidad) }))
    }).subscribe(this.resultado('Receta actualizada', () => this.recetaEditada.set(null)));
  }

  unidadInsumo(id: number): string { return this.insumos().find(i => i.id_insumo === Number(id))?.unidad ?? ''; }

  // ---------- Mermas ----------
  registrarMerma(): void {
    const cuerpo = this.merma.tipo === 'insumo'
      ? { id_insumo: this.merma.id, cantidad: Number(this.merma.cantidad), motivo: this.merma.motivo }
      : { id_producto: this.merma.id, cantidad: Number(this.merma.cantidad), motivo: this.merma.motivo };
    this.admin.registrarMerma(cuerpo).subscribe(this.resultado());
    this.merma = { ...this.merma, cantidad: null, motivo: '' };
  }

  // ---------- Anular registros ----------
  anular(tipo: 'compra' | 'produccion' | 'merma', id: number): void {
    const textos = { compra: '¿Anular esta compra? Se restará del inventario lo que se había sumado.',
                     produccion: '¿Anular esta producción? Se regresarán los insumos y se restará el producto terminado.',
                     merma: '¿Anular esta merma? Se regresará la existencia.' };
    if (!confirm(textos[tipo])) return;
    const peticion = tipo === 'compra' ? this.admin.anularCompra(id) : tipo === 'produccion' ? this.admin.anularProduccion(id) : this.admin.anularMerma(id);
    peticion.subscribe(this.resultado('Registro anulado'));
  }
}