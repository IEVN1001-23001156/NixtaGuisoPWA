import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { BarraSuperior } from '../../../compartidos/barra-superior/barra-superior';
import { MenuLateral } from '../../../compartidos/menu-lateral/menu-lateral';

interface ClienteCrm {
  id: number;
  nombre: string;
  frecuencia: 'Frecuente' | 'Casual' | 'Ocasional';
  segmento: 'domicilio' | 'negocio';
  colorIndicador: 'verde' | 'amarillo';
}

interface RespuestaClientesCrm {
  exito?: boolean;
  clientes?: ClienteCrm[];
}

@Component({
  imports: [FormsModule, RouterLink, BarraSuperior, MenuLateral],
  selector: 'app-directorio-clientes',
  styleUrl: './directorio-clientes.css',
  templateUrl: './directorio-clientes.html',
})
export class DirectorioClientes implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = 'http://localhost:5000/api/admin/clientes';

  menuAbierto = false;
  busqueda = '';
  filtro: 'todos' | 'domicilio' | 'negocio' = 'todos';
  cargando = signal<boolean>(true);
  clientes = signal<ClienteCrm[]>([]);

  async ngOnInit(): Promise<void> {
    await this.cargarClientes();
  }

  async cargarClientes(): Promise<void> {
    this.cargando.set(true);
    try {
      const resp = await firstValueFrom(
        this.http.get<RespuestaClientesCrm>(this.apiUrl, { withCredentials: true })
      );
      if (resp?.exito && Array.isArray(resp.clientes)) {
        this.clientes.set(resp.clientes);
      } else {
        this.clientes.set([]);
      }
    } catch {
      this.clientes.set([]);
    } finally {
      this.cargando.set(false);
    }
  }

  get clientesFiltrados(): ClienteCrm[] {
    return this.clientes().filter((c) => {
      const coincideFiltro = this.filtro === 'todos' || c.segmento === this.filtro;
      const q = this.busqueda.trim().toLowerCase();
      const coincideTexto = !q || c.nombre.toLowerCase().includes(q);
      return coincideFiltro && coincideTexto;
    });
  }
}