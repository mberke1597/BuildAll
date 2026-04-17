"""
Seed demo dashboard data for a project.
Run via: POST /projects/{id}/seed-dashboard (admin only)
"""

import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import (
    CostLine,
    DailyReport,
    RFI,
    RfiStatus,
    Risk,
    RiskSeverity,
    RiskStatus,
    ScheduleItem,
)


def seed_dashboard_data(db: Session, project_id: int, user_id: int):
    """Insert realistic demo data for all dashboard tables."""
    now = datetime.utcnow()
    base = now - timedelta(days=90)

    # ── Schedule Items (8 construction phases) ──
    phases = [
        ("Foundation Work", "Structural", 0, 21, 95),
        ("Structural Framing", "Structural", 14, 45, 78),
        ("MEP Rough-In", "MEP", 35, 65, 55),
        ("Exterior Envelope", "Architectural", 50, 80, 35),
        ("Interior Framing", "Architectural", 60, 85, 20),
        ("Plumbing & HVAC", "MEP", 55, 80, 40),
        ("Electrical Systems", "MEP", 60, 85, 25),
        ("Finishing & Punchlist", "Architectural", 75, 90, 5),
    ]
    for name, disc, start_offset, end_offset, progress in phases:
        db.add(
            ScheduleItem(
                project_id=project_id,
                task_name=name,
                discipline=disc,
                planned_start=base + timedelta(days=start_offset),
                planned_end=base + timedelta(days=end_offset),
                actual_start=base + timedelta(days=start_offset + random.randint(-2, 3)),
                progress_pct=progress,
                created_at=now,
            )
        )

    # ── Cost Lines (4 categories, 3 months) ──
    categories = ["Labor", "Materials", "Equipment", "Subcontractor"]
    for month_offset in range(3):
        period = base + timedelta(days=month_offset * 30)
        for cat in categories:
            budgeted = random.uniform(15000, 80000)
            variance = random.uniform(-0.15, 0.12)
            db.add(
                CostLine(
                    project_id=project_id,
                    category=cat,
                    discipline=random.choice(["Structural", "MEP", "Architectural"]),
                    budgeted=round(budgeted, 2),
                    actual=round(budgeted * (1 + variance), 2),
                    period_date=period,
                    created_at=now,
                )
            )

    # ── RFIs (12 items with various statuses) ──
    rfi_data = [
        ("Beam depth clarification at Grid C-4", "Structural", "Zone A", RfiStatus.CLOSED, -45),
        ("Waterproofing detail at parking level", "Architectural", "Zone B", RfiStatus.CLOSED, -38),
        ("Fire sprinkler routing conflict", "MEP", "Zone A", RfiStatus.IN_REVIEW, -20),
        ("Exterior cladding material substitution", "Architectural", "Zone C", RfiStatus.OPEN, -15),
        ("HVAC duct size discrepancy", "MEP", "Zone B", RfiStatus.OPEN, -12),
        ("Elevator pit depth confirmation", "Structural", "Zone A", RfiStatus.OPEN, -10),
        ("Electrical panel location change", "MEP", "Zone C", RfiStatus.IN_REVIEW, -8),
        ("Window schedule conflict", "Architectural", "Zone B", RfiStatus.OPEN, -5),
        ("Plumbing riser coordination", "MEP", "Zone B", RfiStatus.OVERDUE, -35),
        ("Structural steel connection detail", "Structural", "Zone A", RfiStatus.OVERDUE, -28),
        ("Roof drain location update", "MEP", "Zone C", RfiStatus.OPEN, -3),
        ("Stair pressurization requirement", "MEP", "Zone A", RfiStatus.OPEN, -1),
    ]
    for title, disc, zone, status, offset in rfi_data:
        created = now + timedelta(days=offset)
        db.add(
            RFI(
                project_id=project_id,
                title=title,
                status=status,
                discipline=disc,
                zone=zone,
                created_by=user_id,
                due_date=created + timedelta(days=14),
                closed_at=now + timedelta(days=offset + 10) if status == RfiStatus.CLOSED else None,
                created_at=created,
            )
        )

    # ── Risks (8 items) ──
    risk_data = [
        ("Plumbing misalignment in Zone B", "Repeated clashes between plumbing and structural", RiskSeverity.CRITICAL, "MEP", "Zone B", 9, 7),
        ("Foundation settlement risk", "Soil report indicates potential settling", RiskSeverity.HIGH, "Structural", "Zone A", 8, 5),
        ("Fire code compliance gap", "Sprinkler coverage below requirement", RiskSeverity.HIGH, "MEP", "Zone A", 7, 6),
        ("Schedule delay: MEP coordination", "MEP rough-in behind schedule", RiskSeverity.MEDIUM, "MEP", "Zone C", 5, 7),
        ("Material price escalation", "Steel costs trending up 12%", RiskSeverity.MEDIUM, "Structural", "Zone A", 6, 4),
        ("Subcontractor capacity constraint", "HVAC sub short on crews", RiskSeverity.MEDIUM, "MEP", "Zone B", 5, 5),
        ("Weather delay probability", "Rainy season approaching", RiskSeverity.LOW, "Architectural", "Zone C", 3, 6),
        ("Permit approval delay", "Zoning board review pending", RiskSeverity.HIGH, "Architectural", "Zone B", 8, 4),
    ]
    for title, desc, sev, disc, zone, impact, prob in risk_data:
        db.add(
            Risk(
                project_id=project_id,
                title=title,
                description=desc,
                severity=sev,
                status=RiskStatus.OPEN,
                discipline=disc,
                zone=zone,
                impact_score=impact,
                probability_score=prob,
                detected_by=random.choice(["AI", "USER"]),
                created_at=now - timedelta(days=random.randint(1, 30)),
                updated_at=now,
            )
        )

    # ── Daily Reports (last 30 days) ──
    weathers = ["Sunny", "Cloudy", "Partly Cloudy", "Rainy", "Overcast"]
    for day_offset in range(30):
        day = now - timedelta(days=30 - day_offset)
        is_weekend = day.weekday() >= 5
        if is_weekend:
            continue
        db.add(
            DailyReport(
                project_id=project_id,
                report_date=day,
                weather=random.choice(weathers),
                workers_count=random.randint(25, 65),
                summary=f"Day {day_offset + 1}: Normal operations. {random.randint(0, 3)} minor issues noted.",
                issues_count=random.randint(0, 5),
                safety_incidents=1 if random.random() < 0.15 else 0,
                created_by=user_id,
                created_at=day,
            )
        )

    db.commit()
