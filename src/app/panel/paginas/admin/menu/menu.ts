import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { CurrencyPipe, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';

import { AdminService } from '../../../servicios/admin.service';
import { AvisosService } from '../../../servicios/avisos.service';
import { ProductoAdmin } from '../../../interfaces/admin';
import { environment } from '../../../../environments/environment';

type Formulario = {
  id_categoria: number | null;
  nombre: string;
  descripcion: string;
  presentacion: string;
  kg_por_unidad: number;
  precio_b2c: number;
  precio_b2b_n1: number;
  precio_b2b_n2: number;
  costo_unitario: number;
  disponible: boolean;
};

/** Gestión de menú (Módulo 7): tabla con tres tarifas y edición en la misma pantalla */
@Component({
  selector: 'app-menu-admin',
  imports: [CurrencyPipe, DecimalPipe, FormsModule],
  templateUrl: './menu.html'
})
export class MenuAdmin implements OnInit {
  private admin = inject(AdminService);
  private avisos = inject(AvisosService);
  private route = inject(ActivatedRoute);

  productos = signal<ProductoAdmin[]>([]);
  listaCategorias = signal<any[]>([]);
  filtro = signal<string>('todos');
  buscar = signal('');
  seleccionado = signal<ProductoAdmin | null>(null);
  modo = signal<'cerrado' | 'editar' | 'nuevo'>('cerrado');
  guardando = signal(false);
  error = signal('');
  vista = signal<'productos' | 'categorias'>('productos');
  f: Formulario = this.vacio();

  categorias = computed(() => {
    if (this.listaCategorias().length > 0) {
      return this.listaCategorias().map(c => ({
        id: Number(c.id_categoria),
        nombre: c.nombre
      }));
    }
    const vistas = new Map<number, string>();
    this.productos().forEach(p => {
      if (p.id_categoria) vistas.set(p.id_categoria, p.categoria);
    });
    return [...vistas.entries()].map(([id, nombre]) => ({ id, nombre }));
  });

  visibles = computed(() => {
    const texto = this.buscar().toLowerCase().trim();
    return this.productos().filter(p => {
      const enFiltro =
        this.filtro() === 'todos' ||
        (this.filtro() === 'paquetes' ? p.es_paquete : String(p.id_categoria) === this.filtro());
      return enFiltro && (!texto || p.nombre.toLowerCase().includes(texto));
    });
  });

  ngOnInit(): void {
    this.cargarCategorias();
    this.cargar(() => {
      const id = Number(this.route.snapshot.queryParamMap.get('producto'));
      const p = this.productos().find(x => x.id_producto === id);
      if (p) this.editar(p);
    });
  }

  cargarCategorias(): void {
    this.admin.categorias().subscribe(r => {
      this.listaCategorias.set(r.categorias || []);
      if (this.modo() === 'nuevo' && this.listaCategorias().length > 0) {
        this.f.id_categoria = Number(this.listaCategorias()[0].id_categoria);
      }
    });
  }

  guardarCategoria(c: any, nombre: string, descripcion: string, orden: string): void {
    this.admin
      .editarCategoria(c.id_categoria, {
        nombre,
        descripcion: descripcion || null,
        orden: Number(orden)
      })
      .subscribe({
        next: () => {
          this.avisos.mostrar('Categoría actualizada');
          this.cargarCategorias();
          this.cargar();
        },
        error: err => this.avisos.error(err.error?.mensaje || 'No se pudo actualizar')
      });
  }

  cargar(despues?: () => void): void {
    this.admin.productos({ estado: 'todos' }).subscribe(r => {
      this.productos.set(r.productos);
      despues?.();
    });
  }

  private vacio(): Formulario {
    const cats = this.listaCategorias?.() ?? [];
    const primeraCat = cats[0]?.id_categoria ?? 1;
    return {
      id_categoria: Number(primeraCat),
      nombre: '',
      descripcion: '',
      presentacion: '1 L',
      kg_por_unidad: 1,
      precio_b2c: 0,
      precio_b2b_n1: 0,
      precio_b2b_n2: 0,
      costo_unitario: 0,
      disponible: true
    };
  }

  private enfocarEditor(): void {
    setTimeout(() => {
      document.getElementById('editor-producto')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 50);
  }

  nuevo(): void {
    this.vista.set('productos');
    this.seleccionado.set(null);
    this.f = this.vacio();
    this.error.set('');
    this.modo.set('nuevo');
    this.enfocarEditor();
  }

  editar(p: ProductoAdmin): void {
    this.seleccionado.set(p);
    this.f = {
      id_categoria: p.id_categoria,
      nombre: p.nombre,
      descripcion: p.descripcion ?? '',
      presentacion: p.presentacion,
      kg_por_unidad: p.kg_por_unidad,
      precio_b2c: p.precio_b2c,
      precio_b2b_n1: p.precio_b2b_n1,
      precio_b2b_n2: p.precio_b2b_n2,
      costo_unitario: p.costo_unitario,
      disponible: p.disponible
    };
    this.error.set('');
    this.modo.set('editar');
    this.enfocarEditor();
  }

  cerrar(): void {
    this.modo.set('cerrado');
    this.seleccionado.set(null);
    this.error.set('');
  }

  margenActual(): number | null {
    if (!this.f.precio_b2c) return null;
    return Math.round(((this.f.precio_b2c - (this.f.costo_unitario || 0)) / this.f.precio_b2c) * 1000) / 10;
  }

  /** Documento, sección 7.2: B2B nivel 1 = −10 % y nivel 2 = −15 % */
  sugerirPrecios(): void {
    this.f.precio_b2b_n1 = Math.round(this.f.precio_b2c * 0.9 * 100) / 100;
    this.f.precio_b2b_n2 = Math.round(this.f.precio_b2c * 0.85 * 100) / 100;
  }

  guardar(): void {
    if (!this.f.nombre.trim()) {
      this.error.set('Escribe el nombre del producto');
      return;
    }
    this.guardando.set(true);
    this.error.set('');
    const p = this.seleccionado();
    const peticion = p
      ? this.admin.editarProducto(p.id_producto, this.f as any)
      : this.admin.crearProducto(this.f as any);

    peticion.subscribe({
      next: r => {
        this.avisos.mostrar(r.mensaje ?? 'Producto guardado');
        this.guardando.set(false);
        this.cargar(() => {
          const id = p?.id_producto ?? r.producto?.id_producto;
          const actualizado = this.productos().find(x => x.id_producto === id);
          if (actualizado) this.editar(actualizado);
        });
      },
      error: err => {
        this.error.set(err.error?.mensaje || 'No se pudo guardar');
        this.guardando.set(false);
      }
    });
  }

  alternar(p: ProductoAdmin, evento: Event): void {
    evento.stopPropagation();
    this.admin.cambiarDisponible(p.id_producto, !p.disponible).subscribe({
      next: r => {
        this.avisos.mostrar(r.mensaje ?? 'Actualizado');
        this.cargar();
      },
      error: err => this.avisos.error(err.error?.mensaje || 'No se pudo actualizar')
    });
  }

  darDeBaja(): void {
    const p = this.seleccionado();
    if (!p || !confirm(`¿Dar de baja "${p.nombre}"? Dejará de aparecer en el catálogo.`)) return;
    this.admin.bajaProducto(p.id_producto).subscribe({
      next: r => {
        this.avisos.mostrar(r.mensaje ?? 'Producto dado de baja');
        this.cerrar();
        this.cargar();
      },
      error: err => this.avisos.error(err.error?.mensaje || 'No se pudo dar de baja')
    });
  }

  subirFoto(evento: Event): void {
    const archivo = (evento.target as HTMLInputElement).files?.[0];
    const p = this.seleccionado();
    if (!archivo || !p) return;
    this.admin.subirImagen(p.id_producto, archivo).subscribe({
      next: r => {
        this.avisos.mostrar('Foto actualizada');
        this.seleccionado.set({ ...p, imagen_url: r.imagen_url });
        this.cargar();
      },
      error: err => this.avisos.error(err.error?.mensaje || 'No se pudo subir la foto')
    });
  }

  urlFoto(ruta: string | null): string | null {
    if (!ruta) return null;
    return ruta.startsWith('/uploads/') ? `${environment.apiUrl}${ruta}` : ruta;
  }
}