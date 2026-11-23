import { HttpInterceptorFn } from '@angular/common/http';

/** Toda petición a Flask lleva la cookie de sesión (withCredentials). */
export const credencialesInterceptor: HttpInterceptorFn = (req, next) =>
  next(req.url.startsWith('http://localhost:5000') ? req.clone({ withCredentials: true }) : req);
