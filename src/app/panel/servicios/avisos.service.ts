import { Injectable, signal } from '@angular/core';

export interface Aviso {
  id: number;
  texto: string;
  tipo: 'exito' | 'error' | 'info';
}

/** Mensajes flotantes que desaparecen solos ("Agregado al carrito", errores...) */
@Injectable({
  providedIn: 'root'
})
export class AvisosService {

  readonly avisos = signal<Aviso[]>([]);
  private contador = 0;

  mostrar(texto: string, tipo: Aviso['tipo'] = 'exito', segundos = 3): void {
    const aviso: Aviso = { id: ++this.contador, texto, tipo };
    this.avisos.update(lista => [...lista, aviso]);
    setTimeout(() => this.cerrar(aviso.id), segundos * 1000);
  }

  error(texto: string): void {
    this.mostrar(texto, 'error', 4);
  }

  cerrar(id: number): void {
    this.avisos.update(lista => lista.filter(a => a.id !== id));
  }
}
