import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { AuthRolService } from '../servicios/auth-rol.service';

/** Si todavía no se sabe quién está conectado, se pregunta a Flask (/api/auth/yo). */
async function usuarioActual(auth: AuthRolService) {
  if (!auth.usuario()) {
    await auth.consultarSesionActual();
  }
  return auth.usuario();
}

/** Pantallas del cliente: carrito, pago, perfil, historial, programados y rastreo. */
export const clienteGuard: CanActivateFn = async () => {
  const auth = inject(AuthRolService);
  const router = inject(Router);
  const usuario = await usuarioActual(auth);

  if (usuario?.rol === 'cliente') return true;
  if (usuario?.rol === 'admin') return router.createUrlTree(['/admin/panel']);
  return router.createUrlTree(['/iniciar-sesion']);
};

/** Pantallas del panel administrativo (Módulos 6 a 10). */
export const adminGuard: CanActivateFn = async () => {
  const auth = inject(AuthRolService);
  const router = inject(Router);
  const usuario = await usuarioActual(auth);

  if (usuario?.rol === 'admin') return true;
  if (usuario?.rol === 'cliente') return router.createUrlTree(['/inicio']);
  return router.createUrlTree(['/iniciar-sesion']);
};
