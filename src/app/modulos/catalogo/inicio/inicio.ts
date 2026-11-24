import { Component, inject, OnInit, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { BarraInferior } from '../../../compartidos/barra-inferior/barra-inferior';
import { MenuLateral } from '../../../compartidos/menu-lateral/menu-lateral';
import { CampanaAvisos } from '../../../compartidos/campana-avisos/campana-avisos';
import { AuthRolService } from '../../../servicios/auth-rol.service';
import { CarritoService } from '../../../servicios/carrito.service';
import { CatalogoService, ProductoCatalogo } from '../../../servicios/catalogo.service';
import { FotoPerfilService } from '../../../servicios/foto-perfil.service';

export type FiltroCategoria =
  | 'Todos'
  | 'Tortillas y masa'
  | 'Guisados'
  | 'Salsas'
  | 'Lácteos'
  | 'Aguas frescas'
  | 'Combos / Paquetes';

@Component({
  imports: [RouterLink, BarraInferior, MenuLateral, CampanaAvisos],
  selector: 'app-inicio',
  styleUrl: './inicio.css',
  templateUrl: './inicio.html',
})
export class Inicio implements OnInit {
  private readonly router = inject(Router);
  readonly catalogoService = inject(CatalogoService);
  readonly authRol = inject(AuthRolService);
  readonly carritoService = inject(CarritoService);
  readonly fotoPerfilService = inject(FotoPerfilService);

  menuAbierto = false;
  categoriaActiva: FiltroCategoria = 'Todos';
  readonly categorias: FiltroCategoria[] = [
    'Todos',
    'Tortillas y masa',
    'Guisados',
    'Salsas',
    'Lácteos',
    'Aguas frescas',
    'Combos / Paquetes',
  ];

  productos = signal<ProductoCatalogo[]>(this.catalogoService.productosRespaldo);
  cargando = signal<boolean>(false);

  async ngOnInit(): Promise<void> {
    this.carritoService.cargarDireccionUsuario(this.authRol.usuario()?.id_usuario ?? null);
    this.cargando.set(true);
    try {
      const nivel = this.authRol.usuario()?.cliente?.nivel_b2b ?? 1;
      const lista = await this.catalogoService.obtenerProductos(
        this.authRol.tipoCuenta(),
        nivel
      );
      this.productos.set(lista);
    } finally {
      this.cargando.set(false);
    }
  }

  get tituloBuenProvecho(): string {
    const nombre = this.authRol.usuario()?.nombre?.trim();
    if (!nombre) {
      return '¡Buen provecho!';
    }
    const primerNombre = nombre.split(' ')[0];
    return `¡Buen provecho, ${primerNombre}!`;
  }

  get direccionEnvio(): string {
    const idUsuario = this.authRol.usuario()?.id_usuario ?? null;
    this.carritoService.cargarDireccionUsuario(idUsuario);
    const resumenCarrito = this.carritoService.direccionResumen();
    if (resumenCarrito) {
      return resumenCarrito;
    }
    const dirPerfil = this.authRol.usuario()?.cliente?.direccion?.trim();
    return dirPerfil || 'Agregar dirección de entrega';
  }

  get inicialesUsuario(): string {
    const nombre = this.authRol.usuario()?.nombre?.trim();
    if (!nombre) {
      return 'NG';
    }
    const partes = nombre.split(/\s+/);
    return partes.length > 1
      ? `${partes[0][0]}${partes[1][0]}`.toUpperCase()
      : partes[0].slice(0, 2).toUpperCase();
  }

  get productosFiltrados(): ProductoCatalogo[] {
    if (this.categoriaActiva === 'Todos') {
      return this.productos();
    }

    const normalizar = (texto: string) =>
      texto
        .toLowerCase()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .trim();

    const filtro = normalizar(this.categoriaActiva);

    return this.productos().filter((p) => {
      const cat = normalizar(p.categoria);
      if (filtro === 'tortillas y masa') {
        return (
          cat.includes('tortilla') ||
          cat.includes('maiz') ||
          p.idCategoria === 1
        );
      }
      if (filtro === 'combos / paquetes') {
        return p.esPaquete || cat.includes('combo') || cat.includes('paquete');
      }
      return cat === filtro || cat.includes(filtro);
    });
  }

  seleccionarCategoria(cat: FiltroCategoria): void {
    this.categoriaActiva = cat;
  }

  irAlBuscador(): void {
    this.router.navigate(['/buscador']);
  }

  irAEditarDireccion(): void {
    this.router.navigate(['/perfil']);
  }
}