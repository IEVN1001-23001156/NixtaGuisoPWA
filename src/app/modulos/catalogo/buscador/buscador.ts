import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { BarraInferior } from '../../../compartidos/barra-inferior/barra-inferior';
import { BarraSuperior } from '../../../compartidos/barra-superior/barra-superior';
import { MenuLateral } from '../../../compartidos/menu-lateral/menu-lateral';
import { AuthRolService } from '../../../servicios/auth-rol.service';
import { CatalogoService, ProductoCatalogo } from '../../../servicios/catalogo.service';

@Component({
  imports: [FormsModule, RouterLink, BarraSuperior, BarraInferior, MenuLateral],
  selector: 'app-buscador',
  styleUrl: './buscador.css',
  templateUrl: './buscador.html',
})
export class Buscador implements OnInit {
  readonly catalogoService = inject(CatalogoService);
  private readonly authRol = inject(AuthRolService);

  menuAbierto = false;
  termino = '';
  cargando = signal<boolean>(false);
  catalogo = signal<ProductoCatalogo[]>(this.catalogoService.productosRespaldo);

  sugerenciasRapidas = ['Tortilla', 'Chicharrón', 'Frijoles', 'Salsa', 'Agua', 'Comida Completa'];

  async ngOnInit(): Promise<void> {
    this.cargando.set(true);
    try {
      const nivel = this.authRol.usuario()?.cliente?.nivel_b2b ?? 1;
      const lista = await this.catalogoService.obtenerProductos(
        this.authRol.tipoCuenta(),
        nivel
      );
      this.catalogo.set(lista);
    } finally {
      this.cargando.set(false);
    }
  }

  get resultados(): ProductoCatalogo[] {
    const q = this.normalizar(this.termino);
    if (!q) {
      return this.catalogo();
    }
    return this.catalogo().filter(
      (item) =>
        this.normalizar(item.nombre).includes(q) ||
        this.normalizar(item.categoria).includes(q) ||
        this.normalizar(item.descripcion).includes(q)
    );
  }

  aplicarSugerencia(texto: string): void {
    this.termino = texto;
  }

  private normalizar(texto: string): string {
    return texto
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .trim();
  }
}