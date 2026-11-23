import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { BarraSuperior } from '../../../compartidos/barra-superior/barra-superior';
import { MenuLateral } from '../../../compartidos/menu-lateral/menu-lateral';
import { CatalogoService, ProductoCatalogo } from '../../../servicios/catalogo.service';

interface ProductoMenuItem {
  id: number;
  nombre: string;
  presentacion: string;
  categoria: string;
  precioB2c: number;
  imagenSrc: string;
  activo: boolean;
}

@Component({
  imports: [FormsModule, RouterLink, BarraSuperior, MenuLateral],
  selector: 'app-listado-menu',
  styleUrl: './listado-menu.css',
  templateUrl: './listado-menu.html',
})
export class ListadoMenu implements OnInit {
  readonly catalogoService = inject(CatalogoService);
  private readonly http = inject(HttpClient);

  menuAbierto = false;
  busqueda = '';
  categoriaSeleccionada = 'Todas';
  cargando = signal<boolean>(true);
  mensajeEstado = signal<string>('');

  categorias = ['Todas', 'Tortillas', 'Guisados', 'Aguas', 'Salsas', 'Lácteos'];

  productos = signal<ProductoMenuItem[]>(
    this.catalogoService.productosRespaldo.map((p) => this.mapearProducto(p))
  );

  async ngOnInit(): Promise<void> {
    await this.cargarProductos();
  }

  async cargarProductos(): Promise<void> {
    this.cargando.set(true);
    try {
      const lista = await this.catalogoService.obtenerProductos('B2C', 1, true);
      if (lista.length > 0) {
        this.productos.set(lista.map((p) => this.mapearProducto(p)));
      }
    } finally {
      this.cargando.set(false);
    }
  }

  get productosFiltrados(): ProductoMenuItem[] {
    return this.productos().filter((p) => {
      const catFiltro = this.categoriaSeleccionada.toLowerCase();
      const catProd = (p.categoria || '').toLowerCase();
      const coincideCat =
        this.categoriaSeleccionada === 'Todas' ||
        catProd === catFiltro ||
        catProd.includes(catFiltro);
      const q = this.busqueda.trim().toLowerCase();
      const coincideTexto = !q || p.nombre.toLowerCase().includes(q);
      return coincideCat && coincideTexto;
    });
  }

  async onSeleccionarImagen(event: Event, idProducto: number): Promise<void> {
    const input = event.target as HTMLInputElement;
    const archivo = input.files?.[0];
    if (!archivo) return;

    const formData = new FormData();
    formData.append('imagen', archivo);

    try {
      const resp = await firstValueFrom(
        this.http.post<{ exito?: boolean; imagen_url?: string }>(
          `http://localhost:5000/api/admin/productos/${idProducto}/imagen`,
          formData,
          { withCredentials: true }
        )
      );
      if (resp?.exito && resp.imagen_url) {
        const nuevaSrc = this.catalogoService.resolverUrlImagen(resp.imagen_url);
        this.productos.update((lista) =>
          lista.map((p) => (p.id === idProducto ? { ...p, imagenSrc: nuevaSrc } : p))
        );
        this.mensajeEstado.set('Imagen del producto actualizada.');
      }
    } catch {}
    input.value = '';
  }

  async alternarEstado(id: number): Promise<void> {
    const actual = this.productos().find((p) => p.id === id);
    if (!actual) return;

    const nuevoEstado = !actual.activo;
    this.productos.update((lista) =>
      lista.map((p) => (p.id === id ? { ...p, activo: nuevoEstado } : p))
    );

    try {
      await firstValueFrom(
        this.http.patch(
          `http://localhost:5000/api/catalogo/${id}/estado`,
          { activo: nuevoEstado },
          { withCredentials: true }
        )
      );
    } catch {}
  }

  private mapearProducto(p: ProductoCatalogo): ProductoMenuItem {
    return {
      id: p.id,
      nombre: p.nombre,
      presentacion: p.unidad || p.etiqueta || 'Unidad',
      categoria: p.categoria || 'General',
      precioB2c: Number(p.precioB2c ?? p.precio ?? 0),
      imagenSrc: this.catalogoService.resolverUrlImagen(p.imagenUrl),
      activo: p.disponible ?? true,
    };
  }
}