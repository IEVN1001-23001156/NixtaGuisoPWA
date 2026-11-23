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

interface PedidoRuta {
  id: number;
  folio: string;
  hora: string;
  fecha: string;
  cliente: string;
  detalle: string;
  estado: string;
  asignado: boolean;
  origen: Coordenadas;
  destino: Coordenadas;
}

@Component({
  imports: [RouterLink, BarraSuperior, MenuLateral],
  selector: 'app-mapa-despacho',
  styleUrl: './mapa-despacho.css',
  templateUrl: './mapa-despacho.html',
})
export class MapaDespacho implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('mapaDespachoEl') private mapaEl?: ElementRef<HTMLDivElement>;

  private readonly http = inject(HttpClient);
  private mapa?: L.Map;
  private capaRuta?: L.LayerGroup;
  private vistaLista = false;

  menuAbierto = false;
  pedidos = signal<PedidoRuta[]>([]);
  pedidoSeleccionado = signal<PedidoRuta | null>(null);
  resumenRuta = signal<string>('Selecciona un pedido para trazar la ruta por calles.');

  async ngOnInit(): Promise<void> {
    await this.cargarPedidos();
  }

  ngAfterViewInit(): void {
    this.vistaLista = true;
    this.inicializarMapa();
    const actual = this.pedidoSeleccionado();
    if (actual) {
      void this.trazarRuta(actual);
    }
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

  async cargarPedidos(): Promise<void> {
    try {
      const resp = await firstValueFrom(
        this.http.get<{ exito?: boolean; pedidos?: PedidoRuta[] }>(
          'http://localhost:5000/api/admin/despacho/pedidos',
          { withCredentials: true }
        )
      );
      if (resp?.exito && Array.isArray(resp.pedidos)) {
        this.pedidos.set(resp.pedidos);
        if (resp.pedidos.length > 0) {
          this.pedidoSeleccionado.set(resp.pedidos[0]);
          if (this.vistaLista) {
            void this.trazarRuta(resp.pedidos[0]);
          }
        }
      }
    } catch {
      this.pedidos.set([]);
    }
  }

  async seleccionarYVerRuta(pedido: PedidoRuta): Promise<void> {
    this.pedidoSeleccionado.set(pedido);
    await this.trazarRuta(pedido);
  }

  async trazarRuta(pedido: PedidoRuta): Promise<void> {
    if (!this.mapa || !this.capaRuta) return;
    this.capaRuta.clearLayers();

    const origenLatLng = L.latLng(pedido.origen.lat, pedido.origen.lng);
    const destinoLatLng = L.latLng(pedido.destino.lat, pedido.destino.lng);

    L.circleMarker(origenLatLng, {
      radius: 8,
      color: '#ffffff',
      weight: 2,
      fillColor: '#2d6a4f',
      fillOpacity: 1,
    })
      .bindPopup('Punto de salida · NixtaGuiso')
      .addTo(this.capaRuta);

    L.circleMarker(destinoLatLng, {
      radius: 8,
      color: '#ffffff',
      weight: 2,
      fillColor: '#bc4749',
      fillOpacity: 1,
    })
      .bindPopup(pedido.cliente)
      .addTo(this.capaRuta);

    try {
      const url = `https://router.project-osrm.org/route/v1/driving/${pedido.origen.lng},${pedido.origen.lat};${pedido.destino.lng},${pedido.destino.lat}?overview=full&geometries=geojson`;
      const data = await firstValueFrom(
        this.http.get<{
          routes?: {
            distance: number;
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

        const km = (ruta.distance / 1000).toFixed(1);
        const min = Math.max(1, Math.round(ruta.duration / 60));
        this.resumenRuta.set(
          `${pedido.folio} · ${pedido.cliente}: ${km} km · ~${min} min por vialidades`
        );
        return;
      }
    } catch {}

    const fallback = L.polyline([origenLatLng, destinoLatLng], {
      color: '#d97706',
      weight: 4,
      dashArray: '6 6',
    }).addTo(this.capaRuta);
    this.mapa.fitBounds(fallback.getBounds(), { padding: [30, 30] });
    this.resumenRuta.set(`${pedido.folio} · ${pedido.cliente} (ruta directa aproximada)`);
  }

  async asignarPedido(pedido: PedidoRuta): Promise<void> {
    this.pedidoSeleccionado.set(pedido);
    await this.trazarRuta(pedido);

    try {
      const resp = await firstValueFrom(
        this.http.post<{ exito?: boolean; estado?: string }>(
          `http://localhost:5000/api/admin/despacho/asignar/${pedido.id}`,
          {},
          { withCredentials: true }
        )
      );
      if (resp?.exito) {
        this.pedidos.update((lista) =>
          lista.map((item) =>
            item.id === pedido.id
              ? { ...item, asignado: true, estado: resp.estado || 'En Ruta' }
              : item
          )
        );
      }
    } catch {}
  }
}