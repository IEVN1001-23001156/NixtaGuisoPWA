import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { BarraSuperior } from '../../../compartidos/barra-superior/barra-superior';
import { BarraInferior } from '../../../compartidos/barra-inferior/barra-inferior';
import { MenuLateral } from '../../../compartidos/menu-lateral/menu-lateral';
import { AuthRolService } from '../../../servicios/auth-rol.service';
import { CarritoService } from '../../../servicios/carrito.service';
import { CatalogoService, ProductoCatalogo } from '../../../servicios/catalogo.service';

/**
 * "Arma tu Comida Completa": el cliente elige tortilla, guisado, salsa y agua,
 * y obtiene 10 % de descuento sobre la suma (el precio final lo calcula Flask).
 */
@Component({
  imports: [FormsModule, RouterLink, BarraSuperior, BarraInferior, MenuLateral],
  selector: 'app-arma-paquete',
  templateUrl: './arma-paquete.html',
})
export class ArmaPaquete implements OnInit {
  private readonly router = inject(Router);
  private readonly authRol = inject(AuthRolService);
  private readonly carritoService = inject(CarritoService);
  private readonly catalogoService = inject(CatalogoService);

  menuAbierto = false;
  cargando = signal(true);
  mensaje = signal('');
  cantidad = 1;

  tortillas = signal<ProductoCatalogo[]>([]);
  guisados = signal<ProductoCatalogo[]>([]);
  salsas = signal<ProductoCatalogo[]>([]);
  aguas = signal<ProductoCatalogo[]>([]);

  tortilla = signal<number | null>(null);
  guisado = signal<number | null>(null);
  salsa = signal<number | null>(null);
  agua = signal<number | null>(null);

  private elegido(lista: ProductoCatalogo[], id: number | null) {
    return lista.find((p) => p.id === id);
  }

  /** Precio de referencia: precio de Hogar de cada producto, menos 10 % */
  porSeparado = computed(() =>
    [this.elegido(this.tortillas(), this.tortilla()), this.elegido(this.guisados(), this.guisado()),
     this.elegido(this.salsas(), this.salsa()), this.elegido(this.aguas(), this.agua())]
      .reduce((suma, p) => suma + (p?.precioB2c ?? 0), 0)
  );
  precioPaquete = computed(() => Math.round(this.porSeparado() * 0.9 * 100) / 100);

  async ngOnInit(): Promise<void> {
    try {
      const todos = await this.catalogoService.obtenerProductos('B2C', 1);
      const de = (texto: string) => todos.filter((p) => !p.esPaquete && (p.categoria || '').toLowerCase().includes(texto));
      this.tortillas.set(de('maíz').filter((p) => p.unidad === '1 kg' || p.etiqueta === '1 kg' || p.nombre.toLowerCase().includes('tortilla')));
      this.guisados.set(de('guisado'));
      this.salsas.set(de('salsa'));
      this.aguas.set(de('agua'));
      const primero = (l: ProductoCatalogo[]) => l.find((p) => !p.agotado)?.id ?? null;
      this.tortilla.set(primero(this.tortillas()));
      this.guisado.set(primero(this.guisados()));
      this.salsa.set(primero(this.salsas()));
      this.agua.set(primero(this.aguas()));
    } finally {
      this.cargando.set(false);
    }
  }

  cambiarCantidad(delta: number): void {
    if (this.cantidad + delta >= 1) this.cantidad += delta;
  }

  agregar(): void {
    if (!this.authRol.usuario()) {
      this.router.navigate(['/iniciar-sesion']);
      return;
    }
    if (this.authRol.usuario()?.cliente?.tipo === 'B2B') {
      this.mensaje.set('Los paquetes son exclusivos para cuentas Hogar.');
      return;
    }
    const partes = [this.elegido(this.tortillas(), this.tortilla()), this.elegido(this.guisados(), this.guisado()),
                    this.elegido(this.salsas(), this.salsa()), this.elegido(this.aguas(), this.agua())];
    if (partes.some((p) => !p) || partes.some((p) => p?.agotado)) {
      this.mensaje.set('Elige tortilla, guisado, salsa y agua disponibles.');
      return;
    }
    const guisado = partes[1]!;
    // Se agrega al carrito como un renglón propio; Flask lo convierte en sus cuatro productos
    const paquete: ProductoCatalogo = {
      ...guisado,
      id: -1,
      nombre: 'Arma tu Comida Completa',
      categoria: 'Combos / Paquetes',
      idCategoria: null,
      esPaquete: true,
      precio: this.precioPaquete(),
      precioB2c: this.precioPaquete(),
      descripcion: 'Paquete armado por el cliente',
    };
    this.carritoService.agregarProducto(paquete, this.cantidad, '', undefined, {
      tortilla: this.tortilla()!, guisado: this.guisado()!, salsa: this.salsa()!, agua: this.agua()!,
      texto: partes.map((p) => p!.nombre).join(', '),
    });
    this.router.navigate(['/carrito']);
  }
}
