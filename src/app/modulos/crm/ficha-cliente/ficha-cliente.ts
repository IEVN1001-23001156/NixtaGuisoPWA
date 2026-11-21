import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { BarraInferior } from '../../../compartidos/barra-inferior/barra-inferior';
import { BarraSuperior } from '../../../compartidos/barra-superior/barra-superior';
import { MenuLateral } from '../../../compartidos/menu-lateral/menu-lateral';

interface DetalleClienteApi {
  id: number;
  segmento: string;
  negocio: string;
  correo: string;
  direccion: string;
  rfc: string;
  telefono: string;
}

@Component({
  imports: [FormsModule, RouterLink, BarraSuperior, BarraInferior, MenuLateral],
  selector: 'app-ficha-cliente',
  styleUrl: './ficha-cliente.css',
  templateUrl: './ficha-cliente.html',
})
export class FichaCliente implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly http = inject(HttpClient);

  menuAbierto = false;
  idCliente = signal<number | null>(null);
  segmento = signal<string>('Cliente');
  negocio = signal<string>('');
  correo = signal<string>('');
  direccion = signal<string>('');
  rfc = signal<string>('');
  telefono = signal<string>('');
  preferenciasEspeciales = '';
  mensajeGuardado = signal<string>('');
  errorCarga = signal<string>('');

  inicialesCliente = computed(() => {
    const base = (this.negocio() || 'CL').trim();
    const partes = base.split(/\s+/);
    return partes.length > 1
      ? `${partes[0][0]}${partes[1][0]}`.toUpperCase()
      : base.slice(0, 2).toUpperCase();
  });

  async ngOnInit(): Promise<void> {
    const idParam = this.route.snapshot.paramMap.get('id');
    if (!idParam) return;

    const idNum = Number(idParam);
    this.idCliente.set(idNum);
    this.preferenciasEspeciales =
      localStorage.getItem(`nixtaguiso_crm_pref_${idNum}`) || '';

    try {
      const resp = await firstValueFrom(
        this.http.get<{ exito?: boolean; cliente?: DetalleClienteApi; mensaje?: string }>(
          `http://localhost:5000/api/admin/clientes/${idNum}`,
          { withCredentials: true }
        )
      );
      if (resp?.exito && resp.cliente) {
        this.segmento.set(resp.cliente.segmento);
        this.negocio.set(resp.cliente.negocio);
        this.correo.set(resp.cliente.correo);
        this.direccion.set(resp.cliente.direccion);
        this.rfc.set(resp.cliente.rfc);
        this.telefono.set(resp.cliente.telefono);
      } else {
        this.errorCarga.set(resp?.mensaje || 'No se encontraron datos del cliente.');
      }
    } catch {
      this.errorCarga.set('Error al consultar los datos del cliente en la base de datos.');
    }
  }

  guardarPreferencias(): void {
    const id = this.idCliente();
    if (!id) return;
    localStorage.setItem(
      `nixtaguiso_crm_pref_${id}`,
      this.preferenciasEspeciales.trim()
    );
    this.mensajeGuardado.set('Preferencias guardadas.');
  }
}