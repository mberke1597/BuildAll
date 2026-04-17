'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  LineChart, Line, BarChart, Bar, AreaChart, Area, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { apiFetch } from '../lib/api';

/* ── Types ── */
interface KPISummary {
  schedule_health: number;
  cost_health: number;
  risk_count: number;
  open_rfis: number;
  open_submittals: number;
  change_orders: number;
  safety_incidents: number;
}

interface SchedulePoint { date: string; planned: number; actual: number }
interface CostBreakdown { category: string; budgeted: number; actual: number }
interface CashflowPoint { date: string; budgeted: number; actual: number }
interface RfiAgingBucket { bucket: string; count: number }
interface RfiStatusCount { status: string; count: number }
interface RiskItem {
  id: number; title: string; severity: string; zone: string;
  discipline: string; impact_score: number; probability_score: number;
  status: string; created_at: string;
}
interface RiskHeatmapCell { zone: string; discipline: string; count: number; max_severity: string }
interface DailyReportTrend { date: string; issues_count: number; safety_incidents: number; workers_count: number }
interface DailyReportSummary { id: number; report_date: string; summary: string; issues_count: number; safety_incidents: number }
interface AlertItem { id: string; title: string; description: string; severity: string; created_at: string }

interface DashboardData {
  kpis: KPISummary;
  schedule: SchedulePoint[];
  cost_breakdown: CostBreakdown[];
  cashflow: CashflowPoint[];
  rfi_aging: RfiAgingBucket[];
  rfi_status: RfiStatusCount[];
  risks: RiskItem[];
  risk_heatmap: RiskHeatmapCell[];
  daily_report_trend: DailyReportTrend[];
  recent_reports: DailyReportSummary[];
  alerts: AlertItem[];
}

/* ── Colors ── */
const BLUE = '#2563eb';
const PURPLE = '#7c3aed';
const GREEN = '#059669';
const ORANGE = '#d97706';
const RED = '#dc2626';
const SLATE = '#94a3b8';
const PIE_COLORS = [BLUE, GREEN, ORANGE, RED, PURPLE, SLATE];

const severityIcon: Record<string, string> = {
  critical: '🔴', high: '🟠', medium: '🔵', low: '🟢',
};

/* ── Component ── */
export default function ProjectDashboard({ projectId }: { projectId: number }) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [seeding, setSeeding] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      let qs = '';
      if (dateFrom) qs += `from=${dateFrom}&`;
      if (dateTo) qs += `to=${dateTo}&`;
      const d = await apiFetch<DashboardData>(`/projects/${projectId}/dashboard${qs ? '?' + qs : ''}`);
      setData(d);
    } catch (e: any) {
      setError(e.message || 'Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  }, [projectId, dateFrom, dateTo]);

  useEffect(() => { load(); }, [load]);

  const seedDemo = async () => {
    setSeeding(true);
    try {
      await apiFetch(`/projects/${projectId}/seed-dashboard`, { method: 'POST' });
      await load();
    } catch (e: any) {
      alert(e.message || 'Seed failed');
    } finally {
      setSeeding(false);
    }
  };

  if (loading) {
    return (
      <div className="dash-page" style={{ alignItems: 'center', justifyContent: 'center', minHeight: 400 }}>
        <div className="loading-spinner" style={{ width: 40, height: 40 }} />
        <p className="muted">Loading dashboard...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="dash-page" style={{ alignItems: 'center', justifyContent: 'center', minHeight: 400 }}>
        <p style={{ color: 'var(--error)' }}>{error}</p>
        <button className="button" onClick={load}>Retry</button>
      </div>
    );
  }

  if (!data) return null;

  const isEmpty = data.schedule.length === 0 && data.risks.length === 0 && data.cost_breakdown.length === 0;

  return (
    <div className="dash-page">
      {/* Toolbar */}
      <div className="dash-toolbar">
        <div className="dash-date-range">
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} title="From date" />
          <span className="muted">→</span>
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} title="To date" />
          <button className="button button-sm" onClick={load}>Apply</button>
        </div>
        <div style={{ flex: 1 }} />
        <button className="button-ghost button-sm" onClick={seedDemo} disabled={seeding}>
          {seeding ? 'Seeding...' : '🌱 Seed Demo Data'}
        </button>
      </div>

      {isEmpty && (
        <div className="empty-state">
          <div style={{ fontSize: 48 }}>📊</div>
          <h3 style={{ marginTop: 12 }}>No dashboard data yet</h3>
          <p className="muted" style={{ marginBottom: 16 }}>Click "Seed Demo Data" above to populate sample data, or add real project data through the API.</p>
        </div>
      )}

      {/* Alerts */}
      {data.alerts.length > 0 && (
        <div className="alert-banner">
          {data.alerts.map((a) => (
            <div key={a.id} className={`alert-item severity-${a.severity}`}>
              <div className="alert-icon">{severityIcon[a.severity] || '⚠️'}</div>
              <div className="alert-content">
                <div className="alert-title">{a.title}</div>
                <div className="alert-desc">{a.description}</div>
                <div className="alert-time">{new Date(a.created_at).toLocaleString()}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* KPI Cards */}
      <div className="kpi-grid">
        <KPICard icon="📅" color="blue" value={`${data.kpis.schedule_health}%`} label="Schedule Health" trend={data.kpis.schedule_health >= 80 ? 'up' : 'down'} />
        <KPICard icon="💰" color="green" value={`${data.kpis.cost_health}%`} label="Cost Health" trend={data.kpis.cost_health >= 80 ? 'up' : 'down'} />
        <KPICard icon="⚠️" color="orange" value={data.kpis.risk_count} label="Active Risks" />
        <KPICard icon="📋" color="purple" value={data.kpis.open_rfis} label="Open RFIs" />
        <KPICard icon="📑" color="blue" value={data.kpis.open_submittals} label="Open Submittals" />
        <KPICard icon="🔄" color="yellow" value={data.kpis.change_orders} label="Change Orders" />
        <KPICard icon="🦺" color="rose" value={data.kpis.safety_incidents} label="Safety Incidents" trend={data.kpis.safety_incidents > 0 ? 'down' : undefined} />
      </div>

      {/* Row 1: Schedule + Cost */}
      <div className="dash-grid-2">
        <ScheduleChart data={data.schedule} />
        <CostBreakdownChart data={data.cost_breakdown} />
      </div>

      {/* Row 2: Cashflow (full-width) */}
      {data.cashflow.length > 0 && <CashflowChart data={data.cashflow} />}

      {/* Row 3: RFIs */}
      <div className="dash-grid-2">
        <RfiAgingChart data={data.rfi_aging} />
        <RfiStatusChart data={data.rfi_status} />
      </div>

      {/* Row 4: Risks */}
      <div className="dash-grid-2">
        <RiskList risks={data.risks} />
        <RiskHeatmap cells={data.risk_heatmap} />
      </div>

      {/* Row 5: Daily Reports */}
      <div className="dash-grid-2">
        <DailyReportChart data={data.daily_report_trend} />
        <RecentReports reports={data.recent_reports} />
      </div>
    </div>
  );
}

/* ── Sub-components ── */

function KPICard({ icon, color, value, label, trend }: { icon: string; color: string; value: any; label: string; trend?: string }) {
  return (
    <div className="kpi-card">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <div className={`kpi-icon ${color}`}>{icon}</div>
        {trend && <span className={`kpi-trend ${trend}`}>{trend === 'up' ? '▲' : '▼'}</span>}
      </div>
      <div className="kpi-value">{value}</div>
      <div className="kpi-label">{label}</div>
    </div>
  );
}

function ScheduleChart({ data }: { data: SchedulePoint[] }) {
  if (!data.length) return null;
  return (
    <div className="chart-card">
      <div className="chart-header">
        <div>
          <div className="chart-title">Schedule Burndown</div>
          <div className="chart-subtitle">Planned vs Actual progress %</div>
        </div>
      </div>
      <div className="chart-body">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="date" tick={{ fontSize: 12, fill: '#94a3b8' }} />
            <YAxis tick={{ fontSize: 12, fill: '#94a3b8' }} domain={[0, 100]} />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="planned" stroke={BLUE} strokeWidth={2} dot={false} name="Planned" />
            <Line type="monotone" dataKey="actual" stroke={GREEN} strokeWidth={2} dot={{ r: 3 }} name="Actual" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function CostBreakdownChart({ data }: { data: CostBreakdown[] }) {
  if (!data.length) return null;
  return (
    <div className="chart-card">
      <div className="chart-header">
        <div>
          <div className="chart-title">Cost Breakdown</div>
          <div className="chart-subtitle">Budget vs Actual by category</div>
        </div>
      </div>
      <div className="chart-body">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="category" tick={{ fontSize: 12, fill: '#94a3b8' }} />
            <YAxis tick={{ fontSize: 12, fill: '#94a3b8' }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
            <Tooltip formatter={(v: number) => `$${v.toLocaleString()}`} />
            <Legend />
            <Bar dataKey="budgeted" fill={BLUE} name="Budget" radius={[4, 4, 0, 0]} />
            <Bar dataKey="actual" fill={ORANGE} name="Actual" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function CashflowChart({ data }: { data: CashflowPoint[] }) {
  return (
    <div className="chart-card chart-card-full">
      <div className="chart-header">
        <div>
          <div className="chart-title">Cash Flow</div>
          <div className="chart-subtitle">Monthly budgeted vs actual spend</div>
        </div>
      </div>
      <div className="chart-body">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="date" tick={{ fontSize: 12, fill: '#94a3b8' }} />
            <YAxis tick={{ fontSize: 12, fill: '#94a3b8' }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
            <Tooltip formatter={(v: number) => `$${v.toLocaleString()}`} />
            <Legend />
            <Area type="monotone" dataKey="budgeted" stroke={BLUE} fill="rgba(37,99,235,0.1)" strokeWidth={2} name="Budgeted" />
            <Area type="monotone" dataKey="actual" stroke={PURPLE} fill="rgba(124,58,237,0.1)" strokeWidth={2} name="Actual" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function RfiAgingChart({ data }: { data: RfiAgingBucket[] }) {
  if (!data.length) return null;
  return (
    <div className="chart-card">
      <div className="chart-header">
        <div>
          <div className="chart-title">RFI Aging</div>
          <div className="chart-subtitle">Open RFIs by age bucket (days)</div>
        </div>
      </div>
      <div className="chart-body">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="bucket" tick={{ fontSize: 12, fill: '#94a3b8' }} />
            <YAxis tick={{ fontSize: 12, fill: '#94a3b8' }} allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="count" name="RFIs" radius={[4, 4, 0, 0]}>
              {data.map((_, i) => (
                <Cell key={i} fill={[GREEN, BLUE, ORANGE, RED][i] || SLATE} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function RfiStatusChart({ data }: { data: RfiStatusCount[] }) {
  if (!data.length) return null;
  return (
    <div className="chart-card">
      <div className="chart-header">
        <div>
          <div className="chart-title">RFI Status</div>
          <div className="chart-subtitle">Distribution by status</div>
        </div>
      </div>
      <div className="chart-body" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} dataKey="count" nameKey="status" cx="50%" cy="50%" outerRadius={90} innerRadius={50} paddingAngle={3} label={({ status, count }) => `${status}: ${count}`}>
              {data.map((_, i) => (
                <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function RiskList({ risks }: { risks: RiskItem[] }) {
  const top = risks.slice(0, 8);
  if (!top.length) return null;
  return (
    <div className="chart-card">
      <div className="chart-header">
        <div>
          <div className="chart-title">Top Risks</div>
          <div className="chart-subtitle">Sorted by severity &amp; date</div>
        </div>
      </div>
      <div className="risk-list">
        {top.map((r) => (
          <div key={r.id} className="risk-item">
            <div className={`risk-severity-dot ${r.severity.toLowerCase()}`} />
            <div className="risk-info">
              <div className="risk-name">{r.title}</div>
              <div className="risk-meta">{r.zone} · {r.discipline} · {r.status}</div>
            </div>
            <div className="risk-score" style={{ color: r.severity === 'CRITICAL' ? RED : r.severity === 'HIGH' ? ORANGE : BLUE }}>
              {(r.impact_score * r.probability_score).toFixed(1)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function RiskHeatmap({ cells }: { cells: RiskHeatmapCell[] }) {
  if (!cells.length) return null;
  const zones = [...new Set(cells.map(c => c.zone))];
  const disciplines = [...new Set(cells.map(c => c.discipline))];
  const lookup = new Map(cells.map(c => [`${c.zone}|${c.discipline}`, c]));
  const colCount = disciplines.length + 1;

  const getLevel = (cell?: RiskHeatmapCell) => {
    if (!cell || cell.count === 0) return 'level-0';
    const s = cell.max_severity.toLowerCase();
    if (s === 'critical') return 'level-critical';
    if (s === 'high') return 'level-high';
    if (s === 'medium') return 'level-medium';
    return 'level-low';
  };

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div>
          <div className="chart-title">Risk Heatmap</div>
          <div className="chart-subtitle">Zone × Discipline</div>
        </div>
      </div>
      <div className="heatmap-grid" style={{ gridTemplateColumns: `100px repeat(${disciplines.length}, 1fr)` }}>
        {/* Header row */}
        <div className="heatmap-header" />
        {disciplines.map(d => <div key={d} className="heatmap-header">{d}</div>)}
        {/* Data rows */}
        {zones.map(z => (
          <>
            <div key={z} className="heatmap-row-label">{z}</div>
            {disciplines.map(d => {
              const cell = lookup.get(`${z}|${d}`);
              return (
                <div key={`${z}|${d}`} className={`heatmap-cell ${getLevel(cell)}`} title={`${z} / ${d}: ${cell?.count ?? 0} risks`}>
                  {cell?.count || ''}
                </div>
              );
            })}
          </>
        ))}
      </div>
    </div>
  );
}

function DailyReportChart({ data }: { data: DailyReportTrend[] }) {
  if (!data.length) return null;
  return (
    <div className="chart-card">
      <div className="chart-header">
        <div>
          <div className="chart-title">Daily Report Trends</div>
          <div className="chart-subtitle">Issues, safety incidents &amp; workforce</div>
        </div>
      </div>
      <div className="chart-body">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} />
            <YAxis tick={{ fontSize: 12, fill: '#94a3b8' }} />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="workers_count" stroke={BLUE} strokeWidth={2} name="Workers" dot={false} />
            <Line type="monotone" dataKey="issues_count" stroke={ORANGE} strokeWidth={2} name="Issues" dot={false} />
            <Line type="monotone" dataKey="safety_incidents" stroke={RED} strokeWidth={2} name="Safety" dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function RecentReports({ reports }: { reports: DailyReportSummary[] }) {
  if (!reports.length) return null;
  return (
    <div className="chart-card">
      <div className="chart-header">
        <div>
          <div className="chart-title">Recent Daily Reports</div>
          <div className="chart-subtitle">Last 10 reports</div>
        </div>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table className="reports-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Issues</th>
              <th>Safety</th>
              <th>Summary</th>
            </tr>
          </thead>
          <tbody>
            {reports.map(r => (
              <tr key={r.id}>
                <td style={{ whiteSpace: 'nowrap' }}>{new Date(r.report_date).toLocaleDateString()}</td>
                <td>{r.issues_count}</td>
                <td>
                  <span className={r.safety_incidents > 0 ? 'badge badge-error' : 'badge badge-success'}>
                    {r.safety_incidents}
                  </span>
                </td>
                <td style={{ maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.summary}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
