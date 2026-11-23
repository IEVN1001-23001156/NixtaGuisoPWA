import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { BarraSuperior } from '../../../compartidos/barra-superior/barra-superior';
import { MenuLateral } from '../../../compartidos/menu-lateral/menu-lateral';
import { CatalogoService } from '../../../servicios/catalogo.service';

@Component({
  imports: [FormsModule, RouterLink, BarraSuperior, MenuLateral],
  selector: 'app-formulario-producto',
  styleUrl: './formulario-producto.css',
  templateUrl: './formulario-producto.html',
})
export class FormularioProducto implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly http = inject(HttpClient);
  private readonly catalogoService = inject(CatalogoService);

  menuAbierto = false;
  esEdicion = false;
  idProducto: number | null = null;
  nombre = '';
  presentacion = '1 Kg';
  categoria = 'Tortillas';
  precioB2c: number | null = null;
  precioB2b: number | null = null;
  descripcion = '';
  imagenSrc = '/Isotipo.png';
  archivoImagen: File | null = null;
  guardando = signal<boolean>(false);
  errorMensaje = signal<string>('');

  async ngOnInit(): Promise<void> {
    const idParam = this.route.snapshot.paramMap.get('id');
    if (idParam) {
      this.esEdicion = true;
      this.idProducto = Number(idParam);
      const encontrado = await this.catalogoService.obtenerProductoPorId(this.idProducto, 'B2C', 1);
      if (encontrado) {
        this.nombre = encontrado.nombre;
        this.presentacion = encontrado.unidad || encontrado.etiqueta || '1 Kg';
        this.categoria = encontrado.categoria || 'Tortillas';
        this.precioB2c = Number(encontrado.precioB2c ?? encontrado.precio ?? 0);
        this.precioB2b = Number(encontrado.precioB2bN1 ?? encontrado.precioB2c ?? 0);
        this.descripcion = encontrado.descripcion || '';
        this.imagenSrc = this.catalogoService.resolverUrlImagen(encontrado.imagenUrl);
      }
    }
  }

  onSeleccionarArchivo(event: Event): void {
    const input = event.target as HTMLInputElement;
    const archivo = input.files?.[0];
    if (!archivo) return;

    this.archivoImagen = archivo;
    const lector = new FileReader();
    lector.onload = () => {
      if (typeof lector.result === 'string') {
        this.imagenSrc = lector.result;
      }
    };
    lector.readAsDataURL(archivo);
  }

  async guardarCambios(event: Event): Promise<void> {
    event.preventDefault();
    if (this.guardando()) return;

    this.errorMensaje.set('');
    this.guardando.set(true);

    const payload = {
      nombre: this.nombre.trim(),
      presentacion: this.presentacion.trim(),
      categoria: this.categoria,
      precio_b2c: Number(this.precioB2c ?? 0),
      precio_b2b: Number(this.precioB2b ?? this.precioB2c ?? 0),
      descripcion: this.descripcion.trim(),
    };

    try {
      let idGuardado = this.idProducto;

      if (this.esEdicion && this.idProducto) {
        await firstValueFrom(
          this.http.put(`http://localhost:5000/api/catalogo/${this.idProducto}`, payload, {
            withCredentials: true,
          })
        );
      } else {
        const resp = await firstValueFrom(
          this.http.post<{ id_producto?: number; id?: number }>(
            'http://localhost:5000/api/catalogo',
            payload,
            { withCredentials: true }
          )
        );
        idGuardado = resp?.id_producto ?? resp?.id ?? null;
      }

      if (this.archivoImagen && idGuardado) {
        const formData = new FormData();
        formData.append('imagen', this.archivoImagen);
        await firstValueFrom(
          this.http.post(
            `http://localhost:5000/api/admin/productos/${idGuardado}/imagen`,
            formData,
            { withCredentials: true }
          )
        );
      }

      await this.router.navigate(['/admin/menu']);
    } catch {
      await this.router.navigate(['/admin/menu']);
    } finally {
      this.guardando.set(false);
    }
  }
}