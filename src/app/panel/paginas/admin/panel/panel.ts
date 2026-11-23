import { Component, ElementRef, OnDestroy, OnInit, inject, signal, viewChild } from '@angular/core';
import { CurrencyPipe, DecimalPipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';
import { Chart, registerables } from 'chart.js';

import { AdminService } from '../../../servicios/admin.service';
import { AuthRolService } from '../../../../servicios/auth-rol.service';
import { Dashboard, Metrica, PedidoAdmin } from '../../../interfaces/admin';
import { COLOR_ESTADO, NOMBRE_ESTADO } from '../../../interfaces/pedidos';
import { hoyLocal } from '../../../utilidades/fechas';

Chart.register(...registerables);

@Component({
  selector: 'app-panel',
  imports: [CurrencyPipe, DecimalPipe, RouterLink],
  templateUrl: './panel.html'
})
export class Panel implements OnInit, OnDestroy {
  private admin = inject(AdminService);
  private auth = inject(AuthRolService);

  datos = signal<Dashboard | null>(null);
  mezcla = signal<any>(null);
  metas = signal<Metrica[]>([]);
  pedidosHoy = signal<PedidoAdmin[]>([]);
  fecha = signal(hoyLocal());
  hoy = hoyLocal();
  nombreEstado = NOMBRE_ESTADO;
  colorEstado = COLOR_ESTADO;

  private lienzoBarras = viewChild<ElementRef<HTMLCanvasElement>>('barras');
  private lienzoDona = viewChild<ElementRef<HTMLCanvasElement>>('dona');
  private graficas: Chart[] = [];

  primerNombre = () => this.auth.usuario()?.nombre.split(' ')[0] ?? '';

  // Metas que se muestran con barra de avance (sección 11 del documento)
  private indicadoresMeta = ['kg_mensuales', 'negocios_b2b', 'usuarios_registrados', 'escaneos_qr', 'csat'];

  ngOnInit(): void { this.cargar(); }

  cambiarFecha(valor: string): void {
    this.fecha.set(valor || this.hoy);
    this.cargar();
  }

  /** Todo el panel se calcula para el día elegido (y las metas, para su mes) */
  cargar(): void {
    const dia = this.fecha();
    forkJoin({
      dashboard: this.admin.dashboard(dia),
      kilos: this.admin.kilosCanal(6, dia),
      reporte: this.admin.reportes(dia.slice(0, 7)),
      pedidos: this.admin.pedidos({ fecha: dia })
    }).subscribe(({ dashboard, kilos, reporte, pedidos }) => {
      this.datos.set(dashboard);
      this.mezcla.set(kilos.mezcla_mes);
      const todas = reporte.grupos.flatMap(g => g.metricas);
      this.metas.set(this.indicadoresMeta.map(i => todas.find(m => m.indicador === i)).filter((m): m is Metrica => !!m));
      this.pedidosHoy.set(pedidos.pedidos);
      setTimeout(() => this.dibujar(kilos), 0);
    });
  }

  avance(m: Metrica): number {
    if (m.valor === null || !m.meta) return 0;
    return Math.min(100, Math.round((m.valor / m.meta) * 100));
  }

  textoValor(m: Metrica): string {
    if (m.valor === null) return 'Sin datos';
    const v = m.valor.toLocaleString('es-MX', { maximumFractionDigits: 1 });
    return `${v} de ${m.meta?.toLocaleString('es-MX')} ${m.unidad === 'kg' ? 'kg' : ''}`.trim();
  }

  private dibujar(k: any): void {
    this.graficas.forEach(g => g.destroy());
    this.graficas = [];
    const barras = this.lienzoBarras()?.nativeElement;
    if (barras) {
      this.graficas.push(new Chart(barras, {
        type: 'bar',
        data: { labels: k.etiquetas, datasets: [
          { label: 'Negocios (B2B)', data: k.b2b, backgroundColor: '#3B6E3C', borderRadius: 8 },
          { label: 'Hogares (B2C)', data: k.b2c, backgroundColor: '#F2A922', borderRadius: 8 }
        ] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'top', align: 'end' } },
                   scales: { y: { beginAtZero: true, ticks: { callback: v => v + ' kg' } }, x: { grid: { display: false } } } }
      }));
    }
    const dona = this.lienzoDona()?.nativeElement;
    if (dona && k.mezcla_mes?.b2b !== null) {
      this.graficas.push(new Chart(dona, {
        type: 'doughnut',
        data: { labels: ['B2B', 'B2C'], datasets: [{ data: [k.mezcla_mes.b2b, k.mezcla_mes.b2c], backgroundColor: ['#3B6E3C', '#F2A922'], borderWidth: 0 }] },
        options: { cutout: '62%', plugins: { legend: { display: false } } }
      }));
    }
  }

  ngOnDestroy(): void { this.graficas.forEach(g => g.destroy()); }
}
