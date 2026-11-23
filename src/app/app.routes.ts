import { Routes } from '@angular/router';

import { adminGuard, clienteGuard } from './guards/acceso.guard';
import { MarcoAdmin } from './panel/marco-admin/marco-admin';

import { Bienvenida } from './modulos/autenticacion/bienvenida/bienvenida';
import { InicioSesion } from './modulos/autenticacion/inicio-sesion/inicio-sesion';
import { Registro } from './modulos/autenticacion/registro/registro';
import { RecuperarContrasena } from './modulos/autenticacion/recuperar-contrasena/recuperar-contrasena';

import { Inicio } from './modulos/catalogo/inicio/inicio';
import { Buscador } from './modulos/catalogo/buscador/buscador';
import { DetalleProducto } from './modulos/catalogo/detalle-producto/detalle-producto';

import { Carrito } from './modulos/checkout/carrito/carrito';
import { DireccionEntrega } from './modulos/checkout/direccion-entrega/direccion-entrega';
import { MetodoPago } from './modulos/checkout/metodo-pago/metodo-pago';
import { Confirmacion } from './modulos/checkout/confirmacion/confirmacion';

import { PerfilUsuario } from './modulos/perfil/perfil-usuario/perfil-usuario';
import { HistorialPedidos } from './modulos/perfil/historial-pedidos/historial-pedidos';

import { CalendarioAgendamiento } from './modulos/pedidos-programados/calendario-agendamiento/calendario-agendamiento';
import { FormularioEspecial } from './modulos/pedidos-programados/formulario-especial/formulario-especial';
import { CotizacionesB2b } from './modulos/pedidos-programados/cotizaciones-b2b/cotizaciones-b2b';

import { RastreoPedido } from './modulos/logistica/rastreo-pedido/rastreo-pedido';

export const routes: Routes = [
  { path: '', component: Bienvenida },
  { path: 'iniciar-sesion', component: InicioSesion },
  { path: 'registro', component: Registro },
  { path: 'recuperar-contrasena', component: RecuperarContrasena },

  { path: 'inicio', component: Inicio },
  { path: 'buscador', component: Buscador },
  { path: 'producto/:id', component: DetalleProducto },
  { path: 'arma-tu-paquete', loadComponent: () => import('./modulos/catalogo/arma-paquete/arma-paquete').then(m => m.ArmaPaquete) },

  { path: 'carrito', component: Carrito, canActivate: [clienteGuard] },
  { path: 'checkout/entrega', component: DireccionEntrega, canActivate: [clienteGuard] },
  { path: 'checkout/pago', component: MetodoPago, canActivate: [clienteGuard] },
  { path: 'checkout/confirmacion', component: Confirmacion, canActivate: [clienteGuard] },

  { path: 'perfil', component: PerfilUsuario },
  { path: 'historial-pedidos', component: HistorialPedidos, canActivate: [clienteGuard] },

  { path: 'programados', component: CalendarioAgendamiento, canActivate: [clienteGuard] },
  { path: 'programados/nuevo', component: FormularioEspecial, canActivate: [clienteGuard] },
  { path: 'cotizaciones-b2b', component: CotizacionesB2b, canActivate: [clienteGuard] },

  { path: 'rastreo', component: RastreoPedido, canActivate: [clienteGuard] },

  {
    path: 'admin',
    component: MarcoAdmin,
    canActivate: [adminGuard],
    children: [
      { path: '', redirectTo: 'panel', pathMatch: 'full' },
      { path: 'panel', loadComponent: () => import('./panel/paginas/admin/panel/panel').then(m => m.Panel) },
      { path: 'menu', loadComponent: () => import('./panel/paginas/admin/menu/menu').then(m => m.MenuAdmin) },
      { path: 'inventario', loadComponent: () => import('./panel/paginas/admin/inventario/inventario').then(m => m.Inventario) },
      { path: 'crm', loadComponent: () => import('./panel/paginas/admin/crm/crm').then(m => m.CrmAdmin) },
      { path: 'logistica', loadComponent: () => import('./panel/paginas/admin/logistica/logistica').then(m => m.LogisticaAdmin) },
      { path: 'reportes', loadComponent: () => import('./panel/paginas/admin/reportes/reportes').then(m => m.Reportes) },
      { path: 'indicadores', redirectTo: 'panel' },
      { path: 'pedidos', redirectTo: 'logistica' },
      { path: 'rutas', redirectTo: 'logistica' },
      { path: 'repartidores', redirectTo: 'logistica' },
      { path: 'produccion', redirectTo: 'inventario' },
      { path: 'menu/nuevo', redirectTo: 'menu' },
      { path: 'menu/editar/:id', redirectTo: 'menu' },
      { path: 'crm/:id', redirectTo: 'crm' }
    ]
  },

  { path: '**', redirectTo: '' }
];