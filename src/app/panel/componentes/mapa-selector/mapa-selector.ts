import { AfterViewInit, Component, ElementRef, OnDestroy, input, output, signal, viewChild } from '@angular/core';
import * as L from 'leaflet';

import { CENTRO_LEON, LIMITES_LEON, capaMapa, dentroDeLeon, marcador } from '../../utilidades/mapa';

export interface Ubicacion { latitud: number; longitud: number; }

/**
 * Mapa para marcar una ubicación tocando el mapa o con el GPS del navegador.
 * Uso: <app-mapa-selector [latitud]="..." [longitud]="..." (cambio)="..." />
 * Con [soloLectura]="true" solo muestra el punto.
 */
@Component({
  selector: 'app-mapa-selector',
  templateUrl: './mapa-selector.html'
})
export class MapaSelector implements AfterViewInit, OnDestroy {

  latitud = input<number | null>(null);
  longitud = input<number | null>(null);
  soloLectura = input<boolean>(false);
  alto = input<string>('h-64');
  cambio = output<Ubicacion>();

  private contenedor = viewChild.required<ElementRef<HTMLDivElement>>('contenedor');
  private mapa?: L.Map;
  private punto?: L.Marker;

  mensaje = signal('');
  buscandoGps = signal(false);

  ngAfterViewInit(): void {
    const lat = this.latitud(), lng = this.longitud();
    const inicio: L.LatLngTuple = lat != null && lng != null ? [lat, lng] : CENTRO_LEON;

    this.mapa = L.map(this.contenedor().nativeElement, {
      center: inicio, zoom: lat != null ? 16 : 13, maxBounds: LIMITES_LEON.pad(0.1)
    });
    capaMapa().addTo(this.mapa);

    if (lat != null && lng != null) this.colocar(lat, lng, false);

    if (!this.soloLectura()) {
      this.mapa.on('click', (e: L.LeafletMouseEvent) => this.colocar(e.latlng.lat, e.latlng.lng, true));
    }
    // El mapa se dibuja bien aunque esté dentro de una tarjeta que se acaba de mostrar
    setTimeout(() => this.mapa?.invalidateSize(), 200);
  }

  private colocar(lat: number, lng: number, avisar: boolean): void {
    if (!dentroDeLeon(lat, lng)) {
      this.mensaje.set('Ese punto está fuera de la zona de cobertura en León.');
      return;
    }
    this.mensaje.set('');
    if (this.punto) {
      this.punto.setLatLng([lat, lng]);
    } else if (this.mapa) {
      this.punto = L.marker([lat, lng], { icon: marcador('#3B6E3C', '📍', 36) }).addTo(this.mapa);
    }
    if (avisar) this.cambio.emit({ latitud: Number(lat.toFixed(6)), longitud: Number(lng.toFixed(6)) });
  }

  usarMiUbicacion(): void {
    if (!navigator.geolocation) {
      this.mensaje.set('Tu navegador no permite obtener la ubicación.');
      return;
    }
    this.buscandoGps.set(true);
    navigator.geolocation.getCurrentPosition(
      pos => {
        this.buscandoGps.set(false);
        const { latitude, longitude } = pos.coords;
        this.mapa?.setView([latitude, longitude], 17);
        this.colocar(latitude, longitude, true);
      },
      () => {
        this.buscandoGps.set(false);
        this.mensaje.set('No se pudo obtener tu ubicación. Toca el mapa para marcarla.');
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }

  ngOnDestroy(): void {
    this.mapa?.remove();
  }
}
