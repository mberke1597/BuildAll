"""
Data Analyzer — turns raw project events into dashboard-ready aggregates.

Inputs:  ScheduleItem, CostLine, RFI, Risk, DailyReport rows from DB
Outputs: KPISummary, schedule/cost/rfi/risk aggregates, alerts

Algorithm highlights:
  - schedule_health = avg(progress_pct) weighted by date proximity
  - cost_health     = 100 - abs(budget_variance_pct)
  - rfi_aging       = bucket open RFIs into 0-7, 8-14, 15-30, 30+ day bins
  - risk_score      = impact_score * probability_score; heuristic alerts
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models import (
    CostLine,
    DailyReport,
    Message,
    Document,
    RFI,
    RfiStatus,
    Risk,
    RiskSeverity,
    ScheduleItem,
)
from app.schemas import (
    AlertItem,
    CashflowPoint,
    CostBreakdown,
    DailyReportSummary,
    DailyReportTrend,
    DashboardResponse,
    KPISummary,
    RfiAgingBucket,
    RfiStatusCount,
    RiskHeatmapCell,
    RiskItem,
    SchedulePoint,
)

logger = logging.getLogger(__name__)


def build_dashboard(
    db: Session,
    project_id: int,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> DashboardResponse:
    """Main entry: compute all dashboard sections for a given project."""
    now = datetime.utcnow()
    if not date_to:
        date_to = now
    if not date_from:
        date_from = now - timedelta(days=90)

    kpis = _compute_kpis(db, project_id, date_from, date_to, now)
    schedule = _compute_schedule(db, project_id, date_from, date_to)
    cost_breakdown, cashflow = _compute_costs(db, project_id, date_from, date_to)
    rfi_aging, rfi_status = _compute_rfis(db, project_id, now)
    risks, risk_heatmap = _compute_risks(db, project_id)
    daily_trend, recent_reports = _compute_daily_reports(db, project_id, date_from, date_to)
    alerts = _detect_alerts(db, project_id, kpis, now)

    return DashboardResponse(
        kpis=kpis,
        schedule=schedule,
        cost_breakdown=cost_breakdown,
        cashflow=cashflow,
        rfi_aging=rfi_aging,
        rfi_status=rfi_status,
        risks=risks,
        risk_heatmap=risk_heatmap,
        daily_report_trend=daily_trend,
        recent_reports=recent_reports,
        alerts=alerts,
    )


# ──────────────────── KPIs ────────────────────


def _compute_kpis(
    db: Session, project_id: int, date_from, date_to, now
) -> KPISummary:
    # Schedule health: avg progress of active items
    schedule_items = (
        db.query(ScheduleItem)
        .filter(ScheduleItem.project_id == project_id)
        .all()
    )
    if schedule_items:
        total_expected = 0
        total_actual = 0
        for s in schedule_items:
            # expected progress based on time elapsed
            duration = max((s.planned_end - s.planned_start).days, 1)
            elapsed = max((min(now, s.planned_end) - s.planned_start).days, 0)
            expected_pct = min(elapsed / duration * 100, 100)
            total_expected += expected_pct
            total_actual += s.progress_pct
        schedule_health = min(
            round(total_actual / max(total_expected, 1) * 100, 1), 100
        )
    else:
        schedule_health = 100.0  # No items → all good

    # Cost health: 100 - |variance %|
    budget_total = (
        db.query(func.coalesce(func.sum(CostLine.budgeted), 0))
        .filter(CostLine.project_id == project_id)
        .scalar()
    )
    actual_total = (
        db.query(func.coalesce(func.sum(CostLine.actual), 0))
        .filter(CostLine.project_id == project_id)
        .scalar()
    )
    if budget_total > 0:
        variance_pct = abs((actual_total - budget_total) / budget_total * 100)
        cost_health = max(round(100 - variance_pct, 1), 0)
    else:
        cost_health = 100.0

    risk_count = (
        db.query(func.count(Risk.id))
        .filter(Risk.project_id == project_id, Risk.status == "OPEN")
        .scalar()
        or 0
    )
    open_rfis = (
        db.query(func.count(RFI.id))
        .filter(
            RFI.project_id == project_id,
            RFI.status.in_([RfiStatus.OPEN, RfiStatus.IN_REVIEW, RfiStatus.OVERDUE]),
        )
        .scalar()
        or 0
    )
    safety = (
        db.query(func.coalesce(func.sum(DailyReport.safety_incidents), 0))
        .filter(
            DailyReport.project_id == project_id,
            DailyReport.report_date >= date_from,
        )
        .scalar()
        or 0
    )

    return KPISummary(
        schedule_health=schedule_health,
        cost_health=cost_health,
        risk_count=risk_count,
        open_rfis=open_rfis,
        open_submittals=0,  # V2 feature
        change_orders=0,  # V2 feature
        safety_incidents=safety,
    )


# ──────────────────── Schedule ────────────────────


def _compute_schedule(db, project_id, date_from, date_to):
    items = (
        db.query(ScheduleItem)
        .filter(ScheduleItem.project_id == project_id)
        .order_by(ScheduleItem.planned_start)
        .all()
    )
    if not items:
        return []

    # Build weekly points
    points = []
    current = date_from
    while current <= date_to:
        planned_pct = 0
        actual_pct = 0
        counted = 0
        for s in items:
            if s.planned_start <= current:
                counted += 1
                duration = max((s.planned_end - s.planned_start).days, 1)
                elapsed = max((min(current, s.planned_end) - s.planned_start).days, 0)
                planned_pct += min(elapsed / duration * 100, 100)
                actual_pct += s.progress_pct
        if counted > 0:
            points.append(
                SchedulePoint(
                    date=current.strftime("%Y-%m-%d"),
                    planned=round(planned_pct / counted, 1),
                    actual=round(actual_pct / counted, 1),
                )
            )
        current += timedelta(days=7)
    return points


# ──────────────────── Cost ────────────────────


def _compute_costs(db, project_id, date_from, date_to):
    lines = (
        db.query(CostLine)
        .filter(CostLine.project_id == project_id)
        .all()
    )

    # Cost breakdown by category
    by_cat = defaultdict(lambda: {"budgeted": 0, "actual": 0})
    # Cashflow by month
    by_month = defaultdict(lambda: {"budgeted": 0, "actual": 0})

    for line in lines:
        by_cat[line.category]["budgeted"] += line.budgeted
        by_cat[line.category]["actual"] += line.actual
        month_key = line.period_date.strftime("%Y-%m")
        by_month[month_key]["budgeted"] += line.budgeted
        by_month[month_key]["actual"] += line.actual

    cost_breakdown = [
        CostBreakdown(category=cat, budgeted=round(v["budgeted"], 2), actual=round(v["actual"], 2))
        for cat, v in sorted(by_cat.items())
    ]

    cashflow = [
        CashflowPoint(date=m, budgeted=round(v["budgeted"], 2), actual=round(v["actual"], 2))
        for m, v in sorted(by_month.items())
    ]

    return cost_breakdown, cashflow


# ──────────────────── RFIs ────────────────────


def _compute_rfis(db, project_id, now):
    open_rfis = (
        db.query(RFI)
        .filter(
            RFI.project_id == project_id,
            RFI.status.in_([RfiStatus.OPEN, RfiStatus.IN_REVIEW, RfiStatus.OVERDUE]),
        )
        .all()
    )

    # Aging buckets
    buckets = {"0-7 days": 0, "8-14 days": 0, "15-30 days": 0, "30+ days": 0}
    for rfi in open_rfis:
        age = (now - rfi.created_at).days
        if age <= 7:
            buckets["0-7 days"] += 1
        elif age <= 14:
            buckets["8-14 days"] += 1
        elif age <= 30:
            buckets["15-30 days"] += 1
        else:
            buckets["30+ days"] += 1

    aging = [RfiAgingBucket(bucket=k, count=v) for k, v in buckets.items()]

    # Status distribution (all RFIs)
    status_counts = (
        db.query(RFI.status, func.count(RFI.id))
        .filter(RFI.project_id == project_id)
        .group_by(RFI.status)
        .all()
    )
    rfi_status = [
        RfiStatusCount(status=s.value if hasattr(s, "value") else str(s), count=c)
        for s, c in status_counts
    ]

    return aging, rfi_status


# ──────────────────── Risks ────────────────────


def _compute_risks(db, project_id):
    risks = (
        db.query(Risk)
        .filter(Risk.project_id == project_id, Risk.status == "OPEN")
        .order_by(Risk.severity.desc(), Risk.created_at.desc())
        .all()
    )

    risk_items = [
        RiskItem(
            id=r.id,
            title=r.title,
            severity=r.severity.value,
            zone=r.zone,
            discipline=r.discipline,
            impact_score=r.impact_score,
            probability_score=r.probability_score,
            status=r.status.value,
            created_at=r.created_at,
        )
        for r in risks
    ]

    # Heatmap: zone x discipline
    heatmap_data = defaultdict(lambda: {"count": 0, "max_sev": 0})
    sev_order = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    sev_labels = {1: "LOW", 2: "MEDIUM", 3: "HIGH", 4: "CRITICAL"}

    for r in risks:
        zone = r.zone or "General"
        disc = r.discipline or "General"
        key = (zone, disc)
        heatmap_data[key]["count"] += 1
        sev_val = sev_order.get(r.severity.value, 1)
        if sev_val > heatmap_data[key]["max_sev"]:
            heatmap_data[key]["max_sev"] = sev_val

    risk_heatmap = [
        RiskHeatmapCell(
            zone=zone,
            discipline=disc,
            count=v["count"],
            max_severity=sev_labels.get(v["max_sev"], "LOW"),
        )
        for (zone, disc), v in heatmap_data.items()
    ]

    return risk_items, risk_heatmap


# ──────────────────── Daily Reports ────────────────────


def _compute_daily_reports(db, project_id, date_from, date_to):
    reports = (
        db.query(DailyReport)
        .filter(
            DailyReport.project_id == project_id,
            DailyReport.report_date >= date_from,
            DailyReport.report_date <= date_to,
        )
        .order_by(DailyReport.report_date.asc())
        .all()
    )

    trend = [
        DailyReportTrend(
            date=r.report_date.strftime("%Y-%m-%d"),
            issues_count=r.issues_count,
            safety_incidents=r.safety_incidents,
            workers_count=r.workers_count or 0,
        )
        for r in reports
    ]

    recent = [
        DailyReportSummary(
            id=r.id,
            report_date=r.report_date,
            summary=r.summary,
            issues_count=r.issues_count,
            safety_incidents=r.safety_incidents,
        )
        for r in reports[-10:]  # last 10
    ]

    return trend, recent


# ──────────────────── Alert Detection ────────────────────


def _detect_alerts(db, project_id, kpis: KPISummary, now) -> List[AlertItem]:
    """Heuristic rule engine that creates alerts from data patterns."""
    alerts: List[AlertItem] = []

    # Rule 1: Low schedule health
    if kpis.schedule_health < 80:
        alerts.append(
            AlertItem(
                id=str(uuid4()),
                title="Schedule Behind",
                description=f"Project schedule health at {kpis.schedule_health}% — behind planned progress.",
                severity="HIGH" if kpis.schedule_health < 60 else "MEDIUM",
                created_at=now,
            )
        )

    # Rule 2: Cost overrun
    if kpis.cost_health < 85:
        alerts.append(
            AlertItem(
                id=str(uuid4()),
                title="Cost Overrun Detected",
                description=f"Cost health at {kpis.cost_health}% — spending exceeds budget.",
                severity="HIGH" if kpis.cost_health < 70 else "MEDIUM",
                created_at=now,
            )
        )

    # Rule 3: Overdue RFIs
    overdue_rfis = (
        db.query(func.count(RFI.id))
        .filter(
            RFI.project_id == project_id,
            RFI.status == RfiStatus.OVERDUE,
        )
        .scalar()
        or 0
    )
    if overdue_rfis > 0:
        alerts.append(
            AlertItem(
                id=str(uuid4()),
                title=f"{overdue_rfis} Overdue RFIs",
                description=f"{overdue_rfis} RFI(s) have passed their due date without resolution.",
                severity="HIGH",
                created_at=now,
            )
        )

    # Rule 4: Repeated issues in same zone (heuristic for misalignment)
    zone_issues = (
        db.query(Risk.zone, func.count(Risk.id))
        .filter(Risk.project_id == project_id, Risk.status == "OPEN")
        .group_by(Risk.zone)
        .having(func.count(Risk.id) >= 3)
        .all()
    )
    for zone, count in zone_issues:
        if zone:
            alerts.append(
                AlertItem(
                    id=str(uuid4()),
                    title=f"Risk Cluster: {zone}",
                    description=f"{count} open risks detected in {zone} — possible systemic issue (e.g. plumbing misalignment).",
                    severity="CRITICAL",
                    created_at=now,
                )
            )

    # Rule 5: Safety incidents spike
    if kpis.safety_incidents > 3:
        alerts.append(
            AlertItem(
                id=str(uuid4()),
                title="Safety Incident Spike",
                description=f"{kpis.safety_incidents} safety incidents recorded in the period — review site safety protocols.",
                severity="CRITICAL",
                created_at=now,
            )
        )

    return alerts
