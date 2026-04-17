from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models import Company, User, Role, CostCatalog


def seed_data(db: Session):
    existing = db.query(User).filter(User.email == "admin@demo.com").first()
    if existing:
        return

    company = Company(name="Demo Construction Co")
    db.add(company)
    db.commit()
    db.refresh(company)

    users = [
        User(
            company_id=company.id,
            email="admin@demo.com",
            password_hash=get_password_hash("Admin123!"),
            role=Role.ADMIN,
        ),
        User(
            company_id=company.id,
            email="consultant@demo.com",
            password_hash=get_password_hash("Consultant123!"),
            role=Role.CONSULTANT,
        ),
        User(
            company_id=company.id,
            email="client@demo.com",
            password_hash=get_password_hash("Client123!"),
            role=Role.CLIENT,
        ),
    ]
    db.add_all(users)
    db.commit()

    catalogs = [
        CostCatalog(company_id=company.id, quality_level="LOW", unit_cost_per_m2=450, location_multiplier_default=1.0),
        CostCatalog(company_id=company.id, quality_level="MED", unit_cost_per_m2=650, location_multiplier_default=1.0),
        CostCatalog(company_id=company.id, quality_level="HIGH", unit_cost_per_m2=900, location_multiplier_default=1.15),
    ]
    db.add_all(catalogs)
    db.commit()
