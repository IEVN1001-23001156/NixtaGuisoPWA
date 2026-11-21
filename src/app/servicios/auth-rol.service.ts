import { HttpClient } from '@angular/common/http';
import { inject, Injectable, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

export type RolUsuario = 'cliente' | 'admin';
export type TipoCuenta = 'B2C' | 'B2B' | null;

export interface DatosClienteBackend {
  id_cliente: number;
  tipo: 'B2C' | 'B2B';
  nombre_negocio: string | null;
  rfc: string | null;
  nivel_b2b: number | null;
  direccion: string | null;
  latitud: number | null;
  longitud: number | null;
  codigo_referido: string;
  saldo_favor: number;
}

export interface UsuarioSesion {
  id_usuario: number;
  nombre: string;
  correo: string;
  telefono: string | null;
  rol: RolUsuario;
  cliente?: DatosClienteBackend;
}

export interface RespuestaAuth {
  exito: boolean;
  mensaje?: string;
  usuario?: UsuarioSesion;
}

@Injectable({
  providedIn: 'root',
})
export class AuthRolService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = 'http://localhost:5000/api/auth';

  readonly usuario = signal<UsuarioSesion | null>(null);
  readonly rol = signal<RolUsuario>('cliente');
  readonly tipoCuenta = signal<TipoCuenta>(null);

  esAdmin(): boolean {
    return this.rol() === 'admin';
  }

  esNegocioB2B(): boolean {
    return this.tipoCuenta() === 'B2B';
  }

  establecerSesion(usuario: UsuarioSesion | null): void {
    this.usuario.set(usuario);
    this.rol.set(usuario?.rol ?? 'cliente');
    this.tipoCuenta.set(usuario?.cliente?.tipo ?? null);
  }

  establecerRolPrueba(nuevoRol: RolUsuario): void {
    this.rol.set(nuevoRol);
  }

  async iniciarSesion(correo: string, contrasena: string): Promise<RespuestaAuth> {
    const resp = await firstValueFrom(
      this.http.post<RespuestaAuth>(
        `${this.apiUrl}/login`,
        { correo, contrasena },
        { withCredentials: true }
      )
    );
    if (resp.exito && resp.usuario) {
      this.establecerSesion(resp.usuario);
    }
    return resp;
  }

  async registrar(payload: {
    nombre: string;
    correo: string;
    telefono: string;
    contrasena: string;
    tipo: 'B2C' | 'B2B';
    nombre_negocio?: string;
    rfc?: string;
    direccion?: string;
    codigo_invitacion?: string;
  }): Promise<RespuestaAuth> {
    const resp = await firstValueFrom(
      this.http.post<RespuestaAuth>(
        `${this.apiUrl}/registro`,
        payload,
        { withCredentials: true }
      )
    );
    if (resp.exito && resp.usuario) {
      this.establecerSesion(resp.usuario);
    }
    return resp;
  }

  async consultarSesionActual(): Promise<boolean> {
    try {
      const resp = await firstValueFrom(
        this.http.get<RespuestaAuth>(`${this.apiUrl}/yo`, { withCredentials: true })
      );
      if (resp.exito && resp.usuario) {
        this.establecerSesion(resp.usuario);
        return true;
      }
      this.establecerSesion(null);
      return false;
    } catch {
      this.establecerSesion(null);
      return false;
    }
  }

  async cerrarSesion(): Promise<void> {
    try {
      await firstValueFrom(
        this.http.post(`${this.apiUrl}/logout`, {}, { withCredentials: true })
      );
    } finally {
      this.establecerSesion(null);
    }
  }
}