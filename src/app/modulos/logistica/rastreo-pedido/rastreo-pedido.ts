import {
  AfterViewInit,
  Component,
  ElementRef,
  inject,
  OnDestroy,
  OnInit,
  signal,
  ViewChild,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import * as L from 'leaflet';
import { BarraSuperior } from '../../../compartidos/barra-superior/barra-superior';
import { MenuLateral } from '../../../compartidos/menu-lateral/menu-lateral';

interface Coordenadas {
  lat: number;
  lng: number;
}

interface RespuestaRastreo {
  exito?: boolean;
  folio?: string;
  direccion?: string;
  estadoPedido?: 'Preparando' | 'En Ruta' | 'Entregado';
  origen?: Coordenadas;
  destino?: Coordenadas;
  repartidor?: {
    nombre: string;
    telefono: string;
    placa: string;
  };
}

@Component({
  imports: [RouterLink, MenuLateral, BarraSuperior],
  selector: 'app-rastreo-pedido',
  styleUrl: './rastreo-pedido.css',
  templateUrl: './rastreo-pedido.html',
})
export class RastreoPedido implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('mapaRastreoEl') private mapaEl?: ElementRef<HTMLDivElement>;

  private readonly http = inject(HttpClient);
  private mapa?: L.Map;
  private capaRuta?: L.LayerGroup;
  private vistaLista = false;

  menuAbierto = false;
  estadoPedido = signal<'Preparando' | 'En Ruta' | 'Entregado'>('En Ruta');
  tiempoEstimado = signal<string>('Calculando...');
  direccionEntrega = signal<string>('León, Guanajuato');
  repartidor = signal<{ nombre: string; telefono: string; placa: string }>({
    nombre: 'Por asignar',
    telefono: '',
    placa: '—',
  });

  private origen: Coordenadas = { lat: 21.1221, lng: -101.6826 };
  private destino: Coordenadas = { lat: 21.1165, lng: -101.6715 };

  async ngOnInit(): Promise<void> {
    await this.cargarRastreo();
  }

  ngAfterViewInit(): void {
    this.vistaLista = true;
    this.inicializarMapa();
    void this.dibujarRutaReal();
  }

  ngOnDestroy(): void {
    this.mapa?.remove();
  }

  private inicializarMapa(): void {
    if (!this.mapaEl || this.mapa) return;
    this.mapa = L.map(this.mapaEl.nativeElement).setView([21.1221, -101.6826], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap',
      maxZoom: 19,
    }).addTo(this.mapa);
    this.capaRuta = L.layerGroup().addTo(this.mapa);
  }

  async cargarRastreo(): Promise<void> {
    try {
      const resp = await firstValueFrom(
        this.http.get<RespuestaRastreo>('http://localhost:5000/api/rastreo/actual', {
          withCredentials: true,
        })
      );
      if (resp?.exito) {
        if (resp.estadoPedido) {
          this.estadoPedido.set(resp.estadoPedido);
        }
        if (resp.direccion) {
          this.direccionEntrega.set(resp.direccion);
        }
        if (resp.origen) {
          this.origen = resp.origen;
        }
        if (resp.destino) {
          this.destino = resp.destino;
        }
        if (resp.repartidor) {
          this.repartidor.set(resp.repartidor);
        } else {
          this.repartidor.set({ nombre: 'Por asignar', telefono: '', placa: '—' });
        }
        if (this.vistaLista) {
          await this.dibujarRutaReal();
        }
      }
    } catch {
      // 404 = el cliente no tiene pedidos en curso
      this.direccionEntrega.set('No tienes pedidos en curso');
      this.estadoPedido.set('Preparando');
      this.tiempoEstimado.set('—');
    }
  }

  private async dibujarRutaReal(): Promise<void> {
    if (!this.mapa || !this.capaRuta) return;
    this.capaRuta.clearLayers();

    const pOrigen = L.latLng(this.origen.lat, this.origen.lng);
    const pDestino = L.latLng(this.destino.lat, this.destino.lng);

    L.circleMarker(pOrigen, {
      radius: 8,
      color: '#ffffff',
      weight: 2,
      fillColor: '#2d6a4f',
      fillOpacity: 1,
    })
      .bindPopup('Origen')
      .addTo(this.capaRuta);

    L.circleMarker(pDestino, {
      radius: 8,
      color: '#ffffff',
      weight: 2,
      fillColor: '#bc4749',
      fillOpacity: 1,
    })
      .bindPopup(this.direccionEntrega())
      .addTo(this.capaRuta);

    try {
      const url = `https://router.project-osrm.org/route/v1/driving/${this.origen.lng},${this.origen.lat};${this.destino.lng},${this.destino.lat}?overview=full&geometries=geojson`;
      const data = await firstValueFrom(
        this.http.get<{
          routes?: {
            duration: number;
            geometry: { coordinates: [number, number][] };
          }[];
        }>(url)
      );
      const ruta = data?.routes?.[0];
      if (ruta?.geometry?.coordinates?.length) {
        const puntos = ruta.geometry.coordinates.map(([lng, lat]) =>
          L.latLng(lat, lng)
        );
        const linea = L.polyline(puntos, {
          color: '#2d6a4f',
          weight: 5,
          opacity: 0.9,
        }).addTo(this.capaRuta);
        this.mapa.fitBounds(linea.getBounds(), { padding: [30, 30] });

        const min = Math.max(1, Math.round(ruta.duration / 60));
        this.tiempoEstimado.set(`${min} min`);
        return;
      }
    } catch {}

    const fallback = L.polyline([pOrigen, pDestino], {
      color: '#d97706',
      weight: 4,
      dashArray: '6 6',
    }).addTo(this.capaRuta);
    this.mapa.fitBounds(fallback.getBounds(), { padding: [30, 30] });
    this.tiempoEstimado.set('25 min');
  }

  get inicialesRepartidor(): string {
    const partes = (this.repartidor().nombre || 'SG').trim().split(/\s+/);
    return partes.length > 1
      ? `${partes[0][0]}${partes[1][0]}`.toUpperCase()
      : (this.repartidor().nombre || 'SG').slice(0, 2).toUpperCase();
  }
}