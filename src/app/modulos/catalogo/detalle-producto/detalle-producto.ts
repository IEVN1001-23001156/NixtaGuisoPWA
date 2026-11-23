import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { BarraSuperior } from '../../../compartidos/barra-superior/barra-superior';
import { BarraInferior } from '../../../compartidos/barra-inferior/barra-inferior';
import { MenuLateral } from '../../../compartidos/menu-lateral/menu-lateral';
import { AuthRolService } from '../../../servicios/auth-rol.service';
import { CarritoService } from '../../../servicios/carrito.service';
import { CatalogoService, ProductoCatalogo } from '../../../servicios/catalogo.service';

@Component({
  imports: [FormsModule, RouterLink, BarraSuperior, BarraInferior, MenuLateral],
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
  producto = signal<ProductoCatalogo>(this.catalogoService.productosRespaldo[0]);

  // Opciones del paquete "Comida Completa"
  paquetes = signal<ProductoCatalogo[]>([]);
  salsas = signal<ProductoCatalogo[]>([]);
  aguas = signal<ProductoCatalogo[]>([]);
  salsaElegida: number | null = null;
  aguaElegida: number | null = null;

  async ngOnInit(): Promise<void> {
    await this.cargarProducto(Number(this.route.snapshot.paramMap.get('id')));
  }

  private get nivel(): number {
    return this.authRol.usuario()?.cliente?.nivel_b2b ?? 1;
  }

  async cargarProducto(id: number): Promise<void> {
    this.cargando.set(true);
    try {
      const encontrado = await this.catalogoService.obtenerProductoPorId(id, this.authRol.tipoCuenta(), this.nivel);
      if (encontrado) {
        this.producto.set(encontrado);
        if (encontrado.esPaquete) await this.cargarOpcionesPaquete();
      }
    } finally {
      this.cargando.set(false);
    }
  }

  /** Salsas de $15 (roja y verde) y aguas frescas: así el precio del paquete no cambia */
  private async cargarOpcionesPaquete(): Promise<void> {
    if (this.paquetes().length) return;
    const todos = await this.catalogoService.obtenerProductos(this.authRol.tipoCuenta(), this.nivel);
    const categoria = (p: ProductoCatalogo) => (p.categoria || '').toLowerCase();
    this.paquetes.set(todos.filter((p) => p.esPaquete));
    this.salsas.set(todos.filter((p) => !p.esPaquete && categoria(p).includes('salsa') && p.precio === 15));
    this.aguas.set(todos.filter((p) => !p.esPaquete && categoria(p).includes('agua')));
    // Valores iniciales: los del paquete original (salsa roja y agua de jamaica)
    this.salsaElegida = this.salsas().find((s) => s.nombre === 'Salsa roja')?.id ?? this.salsas()[0]?.id ?? null;
    this.aguaElegida = this.aguas().find((a) => a.nombre === 'Agua de jamaica')?.id ?? this.aguas()[0]?.id ?? null;
  }

  async cambiarGuisado(id: number): Promise<void> {
    await this.router.navigate(['/producto', id], { replaceUrl: true });
    await this.cargarProducto(id);
  }

  nombreGuisado(nombre: string): string {
    const texto = nombre.replace('Comida Completa con ', '');
    return texto.charAt(0).toUpperCase() + texto.slice(1);
  }

  /** Ejemplo de nota según el tipo de producto */
  ejemploNota(): string {
    const p = this.producto();
    if (p.esPaquete) return 'Ej. Guisado poco picante, tortillas bien calientes';
    const categoria = (p.categoria || '').toLowerCase();
    if (categoria.includes('maíz') || categoria.includes('maiz') || categoria.includes('tortilla')) return 'Ej. Tortillas bien calientes, separadas por kilo';
    if (categoria.includes('guisado')) return 'Ej. Poco picante, sin cebolla';
    if (categoria.includes('salsa')) return 'Ej. Que pique poquito';
    if (categoria.includes('lácteo') || categoria.includes('lacteo')) return 'Ej. Queso poco salado';
    if (categoria.includes('agua')) return 'Ej. Con poca azúcar y bien fría';
    return 'Ej. Indicaciones para este producto';
  }

  cambiarCantidad(delta: number): void {
    const nueva = this.cantidad + delta;
    if (nueva >= 1) {
      this.cantidad = nueva;
    }
  }

  agregarAlCarrito(): void {
    if (!this.authRol.usuario()) {
      this.router.navigate(['/iniciar-sesion']);
      return;
    }
    if (this.producto().agotado) return;

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
    this.carritoService.agregarProducto(this.producto(), this.cantidad, this.notaEspecial, opciones);
    this.router.navigate(['/carrito']);
  }
}
