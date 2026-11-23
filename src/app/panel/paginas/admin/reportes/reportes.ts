import { Component, ElementRef, OnDestroy, OnInit, computed, inject, signal, viewChild } from '@angular/core';
import { CurrencyPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Chart, registerables } from 'chart.js';

import { AdminService } from '../../../servicios/admin.service';
import { AvisosService } from '../../../servicios/avisos.service';
import { Gasto, Meta, Metrica, Reporte } from '../../../interfaces/admin';
import { hoyLocal, mesLocal } from '../../../utilidades/fechas';

Chart.register(...registerables);

/** Reportes y KPIs: métricas de la sección 11 contra su meta, plan de kilos, gastos y metas */
@Component({
  selector: 'app-reportes',
  imports: [CurrencyPipe, FormsModule],
  templateUrl: './reportes.html'
})
export class Reportes implements OnInit, OnDestroy {
  private admin = inject(AdminService);
  private avisos = inject(AvisosService);

  mes = mesLocal();
  reporte = signal<Reporte | null>(null);
  gastos = signal<Gasto[]>([]);
  totalGastos = signal(0);
  metas = signal<Meta[]>([]);
  gastoEditado = signal<any>(null);
  nuevoGasto = { categoria: 'publicidad_b2c', concepto: '', monto: null as number | null, fecha: hoyLocal() };
  categorias = [
    ['infraestructura', 'Infraestructura digital'], ['empaque', 'Empaque biodegradable'], ['publicidad_b2c', 'Publicidad digital B2C'],
    ['muestras_b2b', 'Muestras B2B'], ['lead_ads_b2b', 'Lead Ads B2B'], ['referidos_cupones', 'Referidos y cupones QR'], ['bono_primer_pedido', 'Bono de primer pedido']
  ];

  private lienzo = viewChild<ElementRef<HTMLCanvasElement>>('plan');
  private grafica?: Chart;

  todas = computed(() => this.reporte()?.grupos.flatMap(g => g.metricas) ?? []);
  destacada = (indicador: string) => this.todas().find(m => m.indicador === indicador);

  ngOnInit(): void {
    this.cargar();
    this.admin.metas().subscribe(r => this.metas.set(r.metas));
    this.admin.planKilos().subscribe(p => setTimeout(() => this.dibujar(p), 0));
  }

  cargar(): void {
    this.admin.reportes(this.mes).subscribe(r => this.reporte.set(r));
    this.admin.gastos(this.mes).subscribe(r => { this.gastos.set(r.gastos); this.totalGastos.set(r.total); });
  }

  valor(m?: Metrica): string {
    if (!m || m.valor === null) return 'Sin datos';
    if (m.unidad === 'MXN') return '$' + m.valor.toLocaleString('es-MX', { maximumFractionDigits: 2 });
    if (m.unidad === '%') return m.valor + ' %';
    return m.valor.toLocaleString('es-MX', { maximumFractionDigits: 2 }) + (m.unidad === 'veces' || m.unidad === 'estrellas' ? '' : ' ' + m.unidad);
  }

  textoMeta(m: Metrica): string {
    const signo = m.indicador === 'costo_registro' ? ' o menos' : ' o más';
    const v = m.meta === null ? '—' : (m.unidad === 'MXN' ? '$' : '') + m.meta.toLocaleString('es-MX') + (m.unidad === '%' ? ' %' : m.unidad === 'MXN' ? '' : ' ' + m.unidad);
    return v + signo + (m.fecha_meta ? ` (al ${m.fecha_meta})` : '');
  }

  private dibujar(p: any): void {
    const canvas = this.lienzo()?.nativeElement;
    if (!canvas) return;
    this.grafica?.destroy();
    this.grafica = new Chart(canvas, {
      type: 'bar',
      data: { labels: p.etiquetas, datasets: [
        { type: 'line', label: 'Plan del documento (kg)', data: p.plan, borderColor: '#F2A922', backgroundColor: '#F2A922', tension: 0.3 },
        { type: 'bar', label: 'Real (kg)', data: p.real, backgroundColor: '#3B6E3C', borderRadius: 8 }
      ] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } },
                 scales: { y: { beginAtZero: true, ticks: { callback: v => v + ' kg' } } } }
    });
  }

  // ---------- Gastos ----------
  agregarGasto(): void {
    this.admin.crearGasto(this.nuevoGasto as Partial<Gasto>).subscribe({
      next: () => { this.avisos.mostrar('Gasto registrado'); this.nuevoGasto.concepto = ''; this.nuevoGasto.monto = null; this.cargar(); },
      error: err => this.avisos.error(err.error?.mensaje || 'No se pudo registrar')
    });
  }

  editarGasto(g: Gasto): void { this.gastoEditado.set({ ...g }); }

  guardarGasto(): void {
    const g = this.gastoEditado();
    this.admin.editarGasto(g.id_gasto, { categoria: g.categoria, concepto: g.concepto, monto: Number(g.monto), fecha: g.fecha }).subscribe({
      next: () => { this.avisos.mostrar('Gasto actualizado'); this.gastoEditado.set(null); this.cargar(); },
      error: err => this.avisos.error(err.error?.mensaje || 'No se pudo actualizar')
    });
  }

  eliminarGasto(g: Gasto): void {
    if (!confirm(`¿Eliminar "${g.concepto}"?`)) return;
    this.admin.eliminarGasto(g.id_gasto).subscribe(() => { this.avisos.mostrar('Gasto eliminado'); this.cargar(); });
  }

  // ---------- Metas ----------
  guardarMeta(m: Meta, valor: string): void {
    const numero = Number(valor);
    if (!numero || numero === m.valor_meta) return;
    this.admin.editarMeta(m.id_meta, numero).subscribe({
      next: () => { this.avisos.mostrar('Meta actualizada'); m.valor_meta = numero; this.cargar(); },
      error: err => this.avisos.error(err.error?.mensaje || 'No se pudo actualizar')
    });
  }

  nombreCategoria(c: string): string { return this.categorias.find(x => x[0] === c)?.[1] ?? c; }

  ngOnDestroy(): void { this.grafica?.destroy(); }
}
