"""
Copilot Tool Endpoints — provides data for AI tool calls.
The Copilot side-panel can invoke these to fetch widget data,
explain charts, and list available widgets for a project.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import (
    CostLine, DailyReport, Project, ProjectMember, RFI, Risk,
    Role, ScheduleItem, User,
)
from app.services.analyzer import build_dashboard

router = APIRouter(prefix="/projects", tags=["copilot-tools"])


# ── Helpers ──

def _ensure_access(db: Session, project_id: int, user: User):
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.company_id == user.company_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if user.role == Role.CLIENT:
        member = (
            db.query(ProjectMember)
            .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id)
            .first()
        )
        if not member:
            raise HTTPException(status_code=403, detail="Forbidden")
    return project


# ── Schemas ──

class WidgetInfo(BaseModel):
    widget_id: str
    label: str
    description: str
    module: str  # which horizontal module it belongs to


class WidgetDataResponse(BaseModel):
    widget_id: str
    project_id: int
    data: dict
    summary: str  # human-readable one-liner for LLM context


WIDGET_REGISTRY: list[WidgetInfo] = [
    WidgetInfo(widget_id="kpis", label="KPI Özeti", description="Proje KPI kartları: takvim sağlığı, maliyet, risk, RFI", module="overview"),
    WidgetInfo(widget_id="schedule_burndown", label="Takvim Burndown", description="Planlanan vs gerçekleşen ilerleme çizgi grafiği", module="overview"),
    WidgetInfo(widget_id="cost_breakdown", label="Maliyet Dağılımı", description="Kategoriye göre bütçe vs gerçekleşen bar grafiği", module="overview"),
    WidgetInfo(widget_id="cashflow", label="Nakit Akışı", description="Aylık bütçe vs gerçekleşen alan grafiği", module="overview"),
    WidgetInfo(widget_id="rfi_aging", label="RFI Yaşlandırma", description="Açık RFI'ların yaş dağılımı", module="rfis"),
    WidgetInfo(widget_id="rfi_status", label="RFI Durum", description="RFI durum dağılımı pasta grafiği", module="rfis"),
    WidgetInfo(widget_id="risk_list", label="Risk Listesi", description="Ciddiyete göre sıralı risk listesi", module="risks"),
    WidgetInfo(widget_id="risk_heatmap", label="Risk Isı Haritası", description="Bölge × Disiplin risk yoğunluk matrisi", module="risks"),
    WidgetInfo(widget_id="daily_trend", label="Günlük Rapor Trendi", description="Sorun, güvenlik ve işçi sayısı trend grafiği", module="reports"),
    WidgetInfo(widget_id="recent_reports", label="Son Raporlar", description="Son 10 günlük saha raporu", module="reports"),
    WidgetInfo(widget_id="alerts", label="Uyarılar", description="Otomatik tespit edilen proje uyarıları", module="overview"),
]


# ── Endpoints ──

@router.get("/{project_id}/widgets", response_model=list[WidgetInfo])
def list_widgets(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all available dashboard widgets for a project."""
    _ensure_access(db, project_id, user)
    return WIDGET_REGISTRY


@router.get("/{project_id}/widgets/{widget_id}/data", response_model=WidgetDataResponse)
def get_widget_data(
    project_id: int,
    widget_id: str,
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Fetch data for a specific widget. Used by Copilot tool calls
    so the AI can read chart data without hallucinating.
    """
    _ensure_access(db, project_id, user)

    from_dt = datetime.fromisoformat(date_from) if date_from else None
    to_dt = datetime.fromisoformat(date_to) if date_to else None

    # Build the full dashboard (cached in future; fine for V1)
    dash = build_dashboard(db, project_id, from_dt, to_dt)

    # Extract the requested widget slice
    extractors = {
        "kpis": lambda: (
            dash.kpis.model_dump(),
            f"Schedule: {dash.kpis.schedule_health}%, Cost: {dash.kpis.cost_health}%, Risks: {dash.kpis.risk_count}, Open RFIs: {dash.kpis.open_rfis}, Safety: {dash.kpis.safety_incidents}",
        ),
        "schedule_burndown": lambda: (
            [p.model_dump() for p in dash.schedule],
            f"{len(dash.schedule)} data noktası, son planlanan: {dash.schedule[-1].planned if dash.schedule else 'N/A'}%",
        ),
        "cost_breakdown": lambda: (
            [c.model_dump() for c in dash.cost_breakdown],
            f"{len(dash.cost_breakdown)} kategori, toplam bütçe: ${sum(c.budgeted for c in dash.cost_breakdown):,.0f}, toplam gerçekleşen: ${sum(c.actual for c in dash.cost_breakdown):,.0f}",
        ),
        "cashflow": lambda: (
            [c.model_dump() for c in dash.cashflow],
            f"{len(dash.cashflow)} aylık dönem",
        ),
        "rfi_aging": lambda: (
            [b.model_dump() for b in dash.rfi_aging],
            f"Toplam açık RFI: {sum(b.count for b in dash.rfi_aging)}, en yaşlı grupta: {dash.rfi_aging[-1].count if dash.rfi_aging else 0}",
        ),
        "rfi_status": lambda: (
            [s.model_dump() for s in dash.rfi_status],
            f"RFI durumları: " + ", ".join(f"{s.status}: {s.count}" for s in dash.rfi_status),
        ),
        "risk_list": lambda: (
            [r.model_dump() for r in dash.risks],
            f"{len(dash.risks)} aktif risk, en yüksek: {dash.risks[0].severity if dash.risks else 'yok'}",
        ),
        "risk_heatmap": lambda: (
            [h.model_dump() for h in dash.risk_heatmap],
            f"{len(dash.risk_heatmap)} bölge×disiplin hücre",
        ),
        "daily_trend": lambda: (
            [d.model_dump() for d in dash.daily_report_trend],
            f"{len(dash.daily_report_trend)} günlük veri noktası",
        ),
        "recent_reports": lambda: (
            [r.model_dump() for r in dash.recent_reports],
            f"Son {len(dash.recent_reports)} rapor",
        ),
        "alerts": lambda: (
            [a.model_dump() for a in dash.alerts],
            f"{len(dash.alerts)} aktif uyarı" + (f", en ciddi: {dash.alerts[0].severity}" if dash.alerts else ""),
        ),
    }

    if widget_id not in extractors:
        raise HTTPException(status_code=404, detail=f"Widget '{widget_id}' not found")

    data, summary = extractors[widget_id]()

    return WidgetDataResponse(
        widget_id=widget_id,
        project_id=project_id,
        data={"items": data} if isinstance(data, list) else data,
        summary=summary,
    )
