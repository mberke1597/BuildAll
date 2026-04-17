from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.models import AuditLog


def log_audit(db: Session, company_id: int, action: str, user_id: Optional[int] = None, meta: Optional[Dict[str, Any]] = None):
    audit = AuditLog(company_id=company_id, user_id=user_id, action=action, meta_json=meta or {})
    db.add(audit)
    db.commit()
