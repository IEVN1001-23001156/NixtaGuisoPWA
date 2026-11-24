import { Component, OnInit, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { BarraSuperior } from '../../../compartidos/barra-superior/barra-superior';
import { BarraInferior } from '../../../compartidos/barra-inferior/barra-inferior';
import { MenuLateral } from '../../../compartidos/menu-lateral/menu-lateral';
import { AuthRolService } from '../../../servicios/auth-rol.service';
import { CarritoService } from '../../../servicios/carrito.service';
import { CatalogoService, ProductoCatalogo } from '../../../servicios/catalogo.service';

@Component({
  imports: [DecimalPipe, FormsModule, RouterLink, BarraSuperior, BarraInferior, MenuLateral],
  selector: 'app-detalle-producto',
  styleUrl: './detalle-producto.css',
  templateUrl: './detalle-producto.html',
})
export class DetalleProducto implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly authRol = inject(AuthRolService);
  private readonly carritoService = inject(CarritoService);
  readonly catalogoService = inject(CatalogoService);

  menuAbierto = false;
  cantidad = 1;
  notaEspecial = '';
  cargando = signal<boolean>(true);
  validandoStock = signal<boolean>(false);
  errorStock = signal<string>('');
  producto = signal<ProductoCatalogo>(this.catalogoService.productosRespaldo[0]);

  paquetes = signal<ProductoCatalogo[]>([]);
  salsas = signal<ProductoCatalogo[]>([]);
  aguas = signal<ProductoCatalogo[]>([]);
  salsaElegida: number | null = null;
  aguaElegida: number | null = null;

  get esProductoKg(): boolean {
    const u = (this.producto().unidad || '').toLowerCase();
    return u.includes('1 kg') || u.trim() === 'kg';
  }

  get pasoCantidad(): number {
    return this.esProductoKg ? 0.5 : 1;
  }

  get minimoCantidad(): number {
    return this.esProductoKg ? 0.5 : 1;
  }

  redondear(valor: number): number {
    return Math.round(valor * 100) / 100;
  }

  async ngOnInit(): Promise<void> {
    await this.cargarProducto(Number(this.route.snapshot.paramMap.get('id')));
  }

  private get nivel(): number {
    return this.authRol.usuario()?.cliente?.nivel_b2b ?? 1;
  }

  async cargarProducto(id: number): Promise<void> {
    this.cargando.set(true);
    this.errorStock.set('');
    this.cantidad = 1;
    try {
      const encontrado = await this.catalogoService.obtenerProductoPorId(
        id,
        this.authRol.tipoCuenta(),
        this.nivel
      );
      if (encontrado) {
        this.producto.set(encontrado);
        if (encontrado.esPaquete) await this.cargarOpcionesPaquete();
      }
    } finally {
      this.cargando.set(false);
    }
  }

  private async cargarOpcionesPaquete(): Promise<void> {
    if (this.paquetes().length) return;
    const todos = await this.catalogoService.obtenerProductos(this.authRol.tipoCuenta(), this.nivel);
    const categoria = (p: ProductoCatalogo) => (p.categoria || '').toLowerCase();
    this.paquetes.set(todos.filter((p) => p.esPaquete));
    this.salsas.set(
      todos.filter((p) => !p.esPaquete && categoria(p).includes('salsa') && p.precio === 15)
    );
    this.aguas.set(todos.filter((p) => !p.esPaquete && categoria(p).includes('agua')));
    this.salsaElegida =
      this.salsas().find((s) => s.nombre === 'Salsa roja')?.id ?? this.salsas()[0]?.id ?? null;
    this.aguaElegida =
      this.aguas().find((a) => a.nombre === 'Agua de jamaica')?.id ?? this.aguas()[0]?.id ?? null;
  }

  async cambiarGuisado(id: number): Promise<void> {
    await this.router.navigate(['/producto', id], { replaceUrl: true });
    await this.cargarProducto(id);
  }

  nombreGuisado(nombre: string): string {
    const texto = nombre.replace('Comida Completa con ', '');
    return texto.charAt(0).toUpperCase() + texto.slice(1);
  }

  ejemploNota(): string {
    const p = this.producto();
    if (p.esPaquete) return 'Ej. Guisado poco picante, tortillas bien calientes';
    const categoria = (p.categoria || '').toLowerCase();
    if (categoria.includes('maíz') || categoria.includes('maiz') || categoria.includes('tortilla')) {
      return 'Ej. Tortillas bien calientes, separadas por kilo';
    }
    if (categoria.includes('guisado')) return 'Ej. Poco picante, sin cebolla';
    if (categoria.includes('salsa')) return 'Ej. Que pique poquito';
    if (categoria.includes('lácteo') || categoria.includes('lacteo')) {
      return 'Ej. Queso poco salado';
    }
    if (categoria.includes('agua')) return 'Ej. Con poca azúcar y bien fría';
    return 'Ej. Indicaciones para este producto';
  }

  cambiarCantidad(delta: number): void {
    const nueva = this.cantidad + delta;
    if (nueva >= this.minimoCantidad) {
      this.cantidad = this.esProductoKg ? Math.round(nueva * 2) / 2 : Math.round(nueva);
      this.errorStock.set('');
    }
  }

  onCantidadInput(valor: string | number): void {
    this.errorStock.set('');
    const num = typeof valor === 'number' ? valor : Number(String(valor).replace(',', '.'));
    if (!Number.isFinite(num)) {
      return;
    }
    this.cantidad = num;
  }

  normalizarCantidadAlSalir(): void {
    const min = this.minimoCantidad;
    if (!Number.isFinite(this.cantidad) || this.cantidad < min) {
      this.cantidad = min;
      return;
    }
    if (this.esProductoKg) {
      this.cantidad = Math.round(this.cantidad * 2) / 2;
    } else {
      this.cantidad = Math.round(this.cantidad);
    }
  }

  async agregarAlCarrito(): Promise<void> {
    this.errorStock.set('');
    this.normalizarCantidadAlSalir();

    if (!this.authRol.usuario()) {
      this.router.navigate(['/iniciar-sesion']);
      return;
    }
    if (this.producto().agotado) {
      this.errorStock.set('Este producto está agotado por hoy.');
      return;
    }

    let opciones;
    if (this.producto().esPaquete) {
      const salsa = this.salsas().find((s) => s.id === this.salsaElegida);
      const agua = this.aguas().find((a) => a.id === this.aguaElegida);
      opciones = {
        salsa: this.salsaElegida,
        agua: this.aguaElegida,
        texto: [salsa?.nombre, agua?.nombre].filter(Boolean).join(' y '),
      };
    }

    this.validandoStock.set(true);
    try {
      const validacion = await this.carritoService.validarDisponibilidadAdicion(
        this.producto(),
        this.cantidad,
        opciones
      );
      if (!validacion.ok) {
        this.errorStock.set(
          validacion.mensaje || 'No hay existencia o insumos suficientes para esa cantidad.'
        );
        return;
      }

      this.carritoService.agregarProducto(
        this.producto(),
        this.cantidad,
        this.notaEspecial,
        opciones
      );
      await this.router.navigate(['/carrito']);
    } finally {
      this.validandoStock.set(false);
    }
  }
}