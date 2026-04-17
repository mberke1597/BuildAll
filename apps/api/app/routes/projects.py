from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import Project, ProjectMember, User, Role
from app.schemas import ProjectIn, ProjectOut, MemberIn

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/my", response_model=list[ProjectOut])
def list_my_projects(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    List projects based on user role:
    - ADMIN: All company projects
    - CONSULTANT: Only projects where they are assigned as a member
    - CLIENT: Only projects where they are assigned as a member
    """
    if user.role == Role.ADMIN:
        # Admins see all company projects
        return db.query(Project).filter(Project.company_id == user.company_id).all()
    
    # Both CONSULTANTs and CLIENTs only see projects they are members of
    project_ids = [
        pm.project_id 
        for pm in db.query(ProjectMember).filter(ProjectMember.user_id == user.id).all()
    ]
    return db.query(Project).filter(Project.id.in_(project_ids)).all()


@router.post("", response_model=ProjectOut)
def create_project(
    payload: ProjectIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.CONSULTANT)),
):
    project = Project(
        company_id=user.company_id,
        name=payload.name,
        location=payload.location,
        created_by=user.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    member = ProjectMember(project_id=project.id, user_id=user.id, role_in_project="OWNER")
    db.add(member)
    db.commit()
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role in (Role.ADMIN, Role.CONSULTANT):
        return db.query(Project).filter(Project.company_id == user.company_id).all()
    project_ids = [pm.project_id for pm in db.query(ProjectMember).filter(ProjectMember.user_id == user.id).all()]
    return db.query(Project).filter(Project.id.in_(project_ids)).all()


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = db.query(Project).filter(Project.id == project_id, Project.company_id == user.company_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if user.role == Role.CLIENT:
        member = db.query(ProjectMember).filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id).first()
        if not member:
            raise HTTPException(status_code=403, detail="Forbidden")
    return project


@router.put("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int,
    payload: ProjectIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.CONSULTANT)),
):
    project = db.query(Project).filter(Project.id == project_id, Project.company_id == user.company_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project.name = payload.name
    project.location = payload.location
    db.commit()
    return project


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.CONSULTANT)),
):
    project = db.query(Project).filter(Project.id == project_id, Project.company_id == user.company_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    return {"status": "deleted"}


@router.post("/{project_id}/members")
def add_member(
    project_id: int,
    payload: MemberIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.CONSULTANT)),
):
    project = db.query(Project).filter(Project.id == project_id, Project.company_id == user.company_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    member_user = db.query(User).filter(User.id == payload.user_id, User.company_id == user.company_id).first()
    if not member_user:
        raise HTTPException(status_code=404, detail="User not found")
    existing = db.query(ProjectMember).filter(ProjectMember.project_id == project_id, ProjectMember.user_id == payload.user_id).first()
    if existing:
        return {"status": "already_member"}
    member = ProjectMember(project_id=project_id, user_id=payload.user_id, role_in_project=payload.role_in_project)
    db.add(member)
    db.commit()
    return {"status": "ok"}
