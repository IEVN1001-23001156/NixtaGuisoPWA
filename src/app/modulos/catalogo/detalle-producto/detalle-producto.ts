import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { BarraInferior } from '../../../compartidos/barra-inferior/barra-inferior';
import { BarraSuperior } from '../../../compartidos/barra-superior/barra-superior';
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

  async ngOnInit(): Promise<void> {
    const idParam = Number(this.route.snapshot.paramMap.get('id'));
    const nivel = this.authRol.usuario()?.cliente?.nivel_b2b ?? 1;
    this.cargando.set(true);
    try {
      const encontrado = await this.catalogoService.obtenerProductoPorId(
        idParam,
        this.authRol.tipoCuenta(),
        nivel
      );
      if (encontrado) {
        this.producto.set(encontrado);
      }
    } finally {
      this.cargando.set(false);
    }
  }

  cambiarCantidad(delta: number): void {
    const nueva = this.cantidad + delta;
    if (nueva >= 1) {
      this.cantidad = nueva;
    }
  }

  agregarAlCarrito(): void {
    if (!this.authRol.usuario()) {
      this.router.navigate(['/login']);
      return;
    }
    this.carritoService.agregarProducto(this.producto(), this.cantidad, this.notaEspecial);
    this.router.navigate(['/carrito']);
  }
}