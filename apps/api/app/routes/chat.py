from typing import Dict, List
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import decode_token
from app.db.session import get_db
from app.models import Message, MessageType, Project, ProjectMember, User, Role
from app.schemas import MessageOut

router = APIRouter(prefix="/projects", tags=["chat"])


class ConnectionManager:
    def __init__(self):
        self.active: Dict[int, List[WebSocket]] = {}

    async def connect(self, project_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active.setdefault(project_id, []).append(websocket)

    def disconnect(self, project_id: int, websocket: WebSocket):
        if project_id in self.active and websocket in self.active[project_id]:
            self.active[project_id].remove(websocket)

    async def broadcast(self, project_id: int, message: dict):
        for ws in self.active.get(project_id, []):
            await ws.send_json(message)


manager = ConnectionManager()


def _ensure_access(db: Session, user: User, project_id: int):
    project = db.query(Project).filter(Project.id == project_id, Project.company_id == user.company_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if user.role == Role.CLIENT:
        member = db.query(ProjectMember).filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id).first()
        if not member:
            raise HTTPException(status_code=403, detail="Forbidden")
    return project


@router.get("/{project_id}/messages", response_model=list[MessageOut])
def get_messages(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _ensure_access(db, user, project_id)
    return db.query(Message).filter(Message.project_id == project_id).order_by(Message.created_at.asc()).all()


async def websocket_endpoint(websocket: WebSocket, project_id: int, token: str, db: Session):
    user_id = decode_token(token)
    if not user_id:
        await websocket.close()
        return
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        await websocket.close()
        return
    _ensure_access(db, user, project_id)
    await manager.connect(project_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            msg = Message(
                project_id=project_id,
                sender_id=user.id,
                type=MessageType.TEXT,
                text=data.get("text"),
            )
            db.add(msg)
            db.commit()
            db.refresh(msg)
            await manager.broadcast(project_id, {"type": "message", "message": MessageOut.from_orm(msg).dict()})
    except WebSocketDisconnect:
        manager.disconnect(project_id, websocket)
