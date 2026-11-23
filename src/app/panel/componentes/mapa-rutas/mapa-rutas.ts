import { AfterViewInit, Component, ElementRef, OnDestroy, effect, input, output, viewChild } from '@angular/core';
import * as L from 'leaflet';

import { Parada, Ruta } from '../../interfaces/admin';
import { CENTRO_LEON, capaMapa, marcador } from '../../utilidades/mapa';

export const COLORES_RUTA = ['#3B6E3C', '#C08E46', '#593936', '#2563EB', '#DB2777', '#7C3AED'];

/**
 * Mapa del panel: cada repartidor con su color, paradas numeradas y la línea del recorrido.
 * Los pedidos sin asignar aparecen en gris. Emite "clicMapa" para corregir ubicaciones.
 */
@Component({
  selector: 'app-mapa-rutas',
  template: `<div #contenedor class="w-full h-full min-h-80 rounded-3xl overflow-hidden z-0"></div>`
})
export class MapaRutas implements AfterViewInit, OnDestroy {
  rutas = input<Ruta[]>([]);
  sinAsignar = input<Parada[]>([]);
  clicMapa = output<{ latitud: number; longitud: number }>();

  private contenedor = viewChild.required<ElementRef<HTMLDivElement>>('contenedor');
  private mapa?: L.Map;
  private capa = L.layerGroup();

  constructor() {
    // Se vuelve a dibujar cuando cambian las rutas
    effect(() => { this.rutas(); this.sinAsignar(); this.dibujar(); });
  }

  ngAfterViewInit(): void {
    this.mapa = L.map(this.contenedor().nativeElement, { center: CENTRO_LEON, zoom: 13 });
    capaMapa().addTo(this.mapa);
    this.capa.addTo(this.mapa);
    this.mapa.on('click', (e: L.LeafletMouseEvent) =>
      this.clicMapa.emit({ latitud: Number(e.latlng.lat.toFixed(6)), longitud: Number(e.latlng.lng.toFixed(6)) }));
    this.dibujar();
    setTimeout(() => this.mapa?.invalidateSize(), 200);
  }

  private dibujar(): void {
    if (!this.mapa) return;
    this.capa.clearLayers();
    const puntos: L.LatLngTuple[] = [];

    this.rutas().forEach((ruta, i) => {
      const color = COLORES_RUTA[i % COLORES_RUTA.length];
      const linea: L.LatLngTuple[] = [];
      for (const p of ruta.paradas) {
        if (p.latitud == null || p.longitud == null) continue;
        const punto: L.LatLngTuple = [p.latitud, p.longitud];
        linea.push(punto); puntos.push(punto);
        const icono = marcador(p.estado === 'entregado' ? '#9CA3AF' : color, String(p.orden_ruta ?? '?'));
        L.marker(punto, { icon: icono }).bindPopup(
          `<b>#${p.id_pedido} · ${p.cliente}</b><br>${p.direccion_entrega ?? ''}<br>Parada ${p.orden_ruta} · ${ruta.repartidor}`
        ).addTo(this.capa);
      }
      if (linea.length > 1) L.polyline(linea, { color, weight: 4, opacity: 0.8, dashArray: '8 6' }).addTo(this.capa);
    });

    for (const p of this.sinAsignar()) {
      if (p.latitud == null || p.longitud == null) continue;
      const punto: L.LatLngTuple = [p.latitud, p.longitud];
      puntos.push(punto);
      L.marker(punto, { icon: marcador('#F2A922', '•', 28) })
        .bindPopup(`<b>#${p.id_pedido} · ${p.cliente}</b><br>Sin repartidor asignado`).addTo(this.capa);
    }

    if (puntos.length) this.mapa.fitBounds(L.latLngBounds(puntos).pad(0.25), { maxZoom: 15 });
  }

  ngOnDestroy(): void { this.mapa?.remove(); }
}
