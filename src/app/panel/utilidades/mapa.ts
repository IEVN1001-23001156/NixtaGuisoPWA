import * as L from 'leaflet';

// Centro de León, Gto. y límites de la zona de cobertura (los mismos que valida Flask)
export const CENTRO_LEON: L.LatLngTuple = [21.1220, -101.6820];
export const LIMITES_LEON = L.latLngBounds([20.95, -101.85], [21.30, -101.45]);

/** Capa de mapas gratuita de OpenStreetMap */
export function capaMapa(): L.TileLayer {
  return L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap'
  });
}

/** Marcador hecho con HTML (círculo de color con número o ícono), sin imágenes */
export function marcador(color: string, texto = '', tamano = 34): L.DivIcon {
  return L.divIcon({
    className: 'marcador-mapa',
    iconSize: [tamano, tamano],
    iconAnchor: [tamano / 2, tamano / 2],
    html: `<div style="width:${tamano}px;height:${tamano}px;border-radius:9999px;background:${color};
           border:3px solid white;box-shadow:0 2px 6px rgba(0,0,0,.35);color:white;font:700 13px Poppins,sans-serif;
           display:grid;place-items:center">${texto}</div>`
  });
}

export function dentroDeLeon(lat: number, lng: number): boolean {
  return LIMITES_LEON.contains([lat, lng]);
}
