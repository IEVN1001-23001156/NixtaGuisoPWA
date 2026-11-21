import { Routes } from '@angular/router';

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

import { PanelOperativo } from './modulos/administracion/panel-operativo/panel-operativo';
import { ListadoMenu } from './modulos/gestion-menu/listado-menu/listado-menu';
import { FormularioProducto } from './modulos/gestion-menu/formulario-producto/formulario-producto';
import { ControlInventario } from './modulos/inventario/control-inventario/control-inventario';
import { DirectorioClientes } from './modulos/crm/directorio-clientes/directorio-clientes';
import { FichaCliente } from './modulos/crm/ficha-cliente/ficha-cliente';
import { MapaDespacho } from './modulos/logistica/mapa-despacho/mapa-despacho';
import { RastreoPedido } from './modulos/logistica/rastreo-pedido/rastreo-pedido';

export const routes: Routes = [
  { path: '', component: Bienvenida },
  { path: 'iniciar-sesion', component: InicioSesion },
  { path: 'registro', component: Registro },
  { path: 'recuperar-contrasena', component: RecuperarContrasena },

  { path: 'inicio', component: Inicio },
  { path: 'buscador', component: Buscador },
  { path: 'producto/:id', component: DetalleProducto },

  { path: 'carrito', component: Carrito },
  { path: 'checkout/entrega', component: DireccionEntrega },
  { path: 'checkout/pago', component: MetodoPago },
  { path: 'checkout/confirmacion', component: Confirmacion },

  { path: 'perfil', component: PerfilUsuario },
  { path: 'historial-pedidos', component: HistorialPedidos },

  { path: 'programados', component: CalendarioAgendamiento },
  { path: 'programados/nuevo', component: FormularioEspecial },
  { path: 'cotizaciones-b2b', component: CotizacionesB2b },

  { path: 'admin/panel', component: PanelOperativo },
  { path: 'admin/menu', component: ListadoMenu },
  { path: 'admin/menu/nuevo', component: FormularioProducto },
  { path: 'admin/menu/editar/:id', component: FormularioProducto },
  { path: 'admin/inventario', component: ControlInventario },
  { path: 'admin/crm', component: DirectorioClientes },
  { path: 'admin/crm/:id', component: FichaCliente },
  { path: 'admin/logistica', component: MapaDespacho },
  { path: 'rastreo', component: RastreoPedido },

  { path: '**', redirectTo: '' }
];