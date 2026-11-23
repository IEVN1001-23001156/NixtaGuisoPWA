import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { Subject, Subscription, debounceTime, filter, switchMap, of } from 'rxjs';

import { AdminService } from '../servicios/admin.service';
import { BarraSuperior } from '../../compartidos/barra-superior/barra-superior';
import { MenuLateral } from '../../compartidos/menu-lateral/menu-lateral';
import { AuthRolService } from '../../servicios/auth-rol.service';


@Component({
  selector: 'app-marco-admin',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, FormsModule, BarraSuperior, MenuLateral],
  templateUrl: './marco-admin.html'
})
export class MarcoAdmin implements OnInit, OnDestroy {
  private admin = inject(AdminService);
  private auth = inject(AuthRolService);
  private router = inject(Router);

  menuAbierto = false;
  avisosAbiertos = signal(false);
  contadores = signal<any>({ insumos_por_surtir: 0, pedidos_activos: 0, avisos: [] });
  textoBusqueda = '';
  resultados = signal<any[]>([]);
  private busqueda$ = new Subject<string>();
  private suscripciones: Subscription[] = [];

  menu = [
    { ruta: '/admin/panel', texto: 'Panel operativo', contador: '' },
    { ruta: '/admin/menu', texto: 'Gestión de menú', contador: '' },
    { ruta: '/admin/inventario', texto: 'Inventario y producción', contador: 'insumos_por_surtir' },
    { ruta: '/admin/crm', texto: 'Clientes (CRM)', contador: '' },
    { ruta: '/admin/logistica', texto: 'Logística y despacho', contador: 'pedidos_activos' },
    { ruta: '/admin/reportes', texto: 'Reportes y KPIs', contador: '' }
  ];

  ngOnInit(): void {
    this.cargarContadores();
    // Los contadores se actualizan cada vez que se cambia de pantalla
    this.suscripciones.push(this.router.events.pipe(filter(e => e instanceof NavigationEnd)).subscribe(() => {
      this.cargarContadores();
      this.menuAbierto = false;
    }));
    this.suscripciones.push(this.busqueda$.pipe(
      debounceTime(250),
      switchMap(q => q.trim().length < 2 ? of({ resultados: [] }) : this.admin.buscar(q.trim()))
    ).subscribe(r => this.resultados.set(r.resultados ?? [])));
  }

  cargarContadores(): void {
    this.admin.contadores().subscribe({ next: c => this.contadores.set(c), error: () => {} });
  }

  buscar(texto: string): void { this.busqueda$.next(texto); }

  abrirResultado(r: any): void {
    this.textoBusqueda = '';
    this.resultados.set([]);
    const parametro = r.tipo === 'Pedido' ? { pedido: r.id } : r.tipo === 'Cliente' ? { cliente: r.id } : { producto: r.id };
    this.router.navigate([r.ruta], { queryParams: parametro });
  }

  irAviso(a: any): void {
    this.avisosAbiertos.set(false);
    this.router.navigate([a.ruta]);
  }

  ngOnDestroy(): void { this.suscripciones.forEach(s => s.unsubscribe()); }
}
