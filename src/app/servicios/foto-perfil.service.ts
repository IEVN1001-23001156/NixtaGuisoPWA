import { Injectable, signal } from '@angular/core';

const CLAVE_FOTO_PERFIL = 'nixtaguiso_foto_perfil';

@Injectable({
  providedIn: 'root',
})
export class FotoPerfilService {
  readonly fotoUrl = signal<string | null>(this.leerGuardada());

  establecerFoto(url: string | null | undefined): void {
    if (!url || !url.trim()) {
      localStorage.removeItem(CLAVE_FOTO_PERFIL);
      this.fotoUrl.set(null);
      return;
    }

    const limpia = url.trim();
    const resuelta = this.resolverUrl(limpia);
    const conVersion = this.agregarVersion(resuelta);

    localStorage.setItem(CLAVE_FOTO_PERFIL, conVersion);
    this.fotoUrl.set(conVersion);
  }

  limpiar(): void {
    localStorage.removeItem(CLAVE_FOTO_PERFIL);
    this.fotoUrl.set(null);
  }

  private leerGuardada(): string | null {
    const valor = localStorage.getItem(CLAVE_FOTO_PERFIL);
    return valor && valor.trim() ? valor.trim() : null;
  }

  private resolverUrl(valor: string): string {
    if (
      valor.startsWith('http://') ||
      valor.startsWith('https://') ||
      valor.startsWith('data:') ||
      valor.startsWith('blob:')
    ) {
      return valor;
    }
    if (valor.startsWith('/')) {
      return `http://localhost:5000${valor}`;
    }
    return `http://localhost:5000/uploads/perfiles/${valor.replace(/^uploads\/perfiles\//, '')}`;
  }

  private agregarVersion(url: string): string {
    if (url.startsWith('data:') || url.startsWith('blob:')) {
      return url;
    }
    const sinVersion = url.split('?')[0];
    return `${sinVersion}?v=${Date.now()}`;
  }
}