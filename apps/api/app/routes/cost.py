from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import CostCatalog, Project, ProjectMember, Role, User
from app.schemas import CostEstimateIn, CostEstimateOut

router = APIRouter(prefix="/projects", tags=["cost"])

# Default unit costs (TRY/m²) when no catalog entry exists in the DB
_DEFAULT_UNIT_COSTS: dict[str, float] = {
    "economy":  8_500.0,
    "standard": 12_000.0,
    "premium":  18_000.0,
    "luxury":   28_000.0,
}


@router.post("/{project_id}/cost/estimate", response_model=CostEstimateOut)
def estimate_cost(
    project_id: int,
    payload: CostEstimateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.company_id == user.company_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if user.role == Role.CLIENT:
        member = db.query(ProjectMember).filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user.id,
        ).first()
        if not member:
            raise HTTPException(status_code=403, detail="Forbidden")

    catalog = (
        db.query(CostCatalog)
        .filter(
            CostCatalog.company_id == user.company_id,
            CostCatalog.quality_level == payload.quality_level,
        )
        .first()
    )

    if catalog:
        unit_cost = catalog.unit_cost_per_m2
        location_multiplier = catalog.location_multiplier_default
        suggestion = "Review assumptions and refine with local bids."
    else:
        # Fall back to built-in defaults — no 400 error for missing catalog
        quality_key = (payload.quality_level or "standard").lower()
        unit_cost = _DEFAULT_UNIT_COSTS.get(quality_key, _DEFAULT_UNIT_COSTS["standard"])
        location_multiplier = 1.0
        suggestion = (
            f"Estimated using built-in {quality_key} defaults "
            f"({unit_cost:,.0f} TRY/m²). "
            "Add a CostCatalog entry for company-specific pricing."
        )

    estimated_cost = payload.total_m2 * unit_cost * location_multiplier
    estimated_profit = None
    if payload.expected_sale_price_total is not None:
        estimated_profit = payload.expected_sale_price_total - estimated_cost

    return CostEstimateOut(
        estimated_cost=estimated_cost,
        estimated_profit=estimated_profit,
        suggestion=suggestion,
    )

