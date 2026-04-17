from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, EmailStr


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    company_id: int
    email: EmailStr
    role: str

    class Config:
        from_attributes = True


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ProjectIn(BaseModel):
    name: str
    location: Optional[str] = None


class ProjectOut(BaseModel):
    id: int
    company_id: int
    name: str
    location: Optional[str] = None
    created_by: int
    created_at: datetime

    class Config:
        from_attributes = True


class MemberIn(BaseModel):
    user_id: int
    role_in_project: Optional[str] = None


class MessageOut(BaseModel):
    id: int
    project_id: int
    sender_id: int
    type: str
    text: Optional[str] = None
    media_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MediaOut(BaseModel):
    id: int
    project_id: int
    storage_key: str
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentOut(BaseModel):
    id: int
    project_id: int
    media_id: int
    status: str
    created_at: datetime
    processed_at: Optional[datetime] = None
    error: Optional[str] = None

    class Config:
        from_attributes = True


class AskIn(BaseModel):
    question: str


class Citation(BaseModel):
    document_id: int
    document_name: str
    chunk_id: int
    page_number: Optional[int] = None
    snippet: str


class AskOut(BaseModel):
    answer: str
    confidence: str
    citations: List[Citation]


class ParcelLookupIn(BaseModel):
    content: str


class CostEstimateIn(BaseModel):
    project_id: int
    total_m2: float
    quality_level: str
    expected_sale_price_total: Optional[float] = None


class CostEstimateOut(BaseModel):
    estimated_cost: float
    estimated_profit: Optional[float] = None
    suggestion: str


class AuditLogOut(BaseModel):
    id: int
    company_id: int
    user_id: Optional[int] = None
    action: str
    meta_json: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectAnalyticsOut(BaseModel):
    project_id: int
    messages_count: int
    documents_count: int
    media_count: int
    last_activity: Optional[datetime] = None


# ---------- Dashboard Schemas ----------


class KPISummary(BaseModel):
    schedule_health: float  # 0-100
    cost_health: float  # 0-100
    risk_count: int
    open_rfis: int
    open_submittals: int
    change_orders: int
    safety_incidents: int


class SchedulePoint(BaseModel):
    date: str
    planned: float
    actual: float


class CostBreakdown(BaseModel):
    category: str
    budgeted: float
    actual: float


class CashflowPoint(BaseModel):
    date: str
    budgeted: float
    actual: float


class RfiAgingBucket(BaseModel):
    bucket: str  # "0-7 days", "8-14 days", etc.
    count: int


class RfiStatusCount(BaseModel):
    status: str
    count: int


class RiskItem(BaseModel):
    id: int
    title: str
    severity: str
    zone: Optional[str] = None
    discipline: Optional[str] = None
    impact_score: Optional[float] = None
    probability_score: Optional[float] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class RiskHeatmapCell(BaseModel):
    zone: str
    discipline: str
    count: int
    max_severity: str


class DailyReportTrend(BaseModel):
    date: str
    issues_count: int
    safety_incidents: int
    workers_count: int


class DailyReportSummary(BaseModel):
    id: int
    report_date: datetime
    summary: Optional[str] = None
    issues_count: int
    safety_incidents: int

    class Config:
        from_attributes = True


class AlertItem(BaseModel):
    id: str
    title: str
    description: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    created_at: datetime


class DashboardResponse(BaseModel):
    kpis: KPISummary
    schedule: List[SchedulePoint]
    cost_breakdown: List[CostBreakdown]
    cashflow: List[CashflowPoint]
    rfi_aging: List[RfiAgingBucket]
    rfi_status: List[RfiStatusCount]
    risks: List[RiskItem]
    risk_heatmap: List[RiskHeatmapCell]
    daily_report_trend: List[DailyReportTrend]
    recent_reports: List[DailyReportSummary]
    alerts: List[AlertItem]


class RfiOut(BaseModel):
    id: int
    title: str
    status: str
    discipline: Optional[str] = None
    zone: Optional[str] = None
    due_date: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DailyReportOut(BaseModel):
    id: int
    report_date: datetime
    weather: Optional[str] = None
    workers_count: Optional[int] = None
    summary: Optional[str] = None
    issues_count: int
    safety_incidents: int
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Chat V2 Schemas ----------


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[UUID] = None
    project_id: Optional[int] = None
    attachments: Optional[List[int]] = None  # media_ids


class ChatResponse(BaseModel):
    session_id: UUID
    message_id: UUID
    content: str
    citations: Optional[List[Citation]] = None


class SessionOut(BaseModel):
    id: UUID
    title: Optional[str] = None
    project_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SessionMessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    citations: Optional[dict] = None
    attachments: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SessionDetailOut(BaseModel):
    session: SessionOut
    messages: List[SessionMessageOut]


class FeedbackRequest(BaseModel):
    message_id: UUID
    rating: int  # +1 or -1
    comment: Optional[str] = None


class FeedbackResponse(BaseModel):
    id: int
    message_id: UUID
    rating: int
    created_at: datetime

    class Config:
        from_attributes = True


class CompanyAIConfigIn(BaseModel):
    system_prompt: Optional[str] = None
    persona_name: Optional[str] = None
    temperature: Optional[float] = 0.2
    max_tokens_per_response: Optional[int] = None
    allowed_topics: Optional[List[str]] = None
    preferred_language: Optional[str] = None
    rate_limit_per_hour: Optional[int] = 30
    monthly_budget_usd: Optional[float] = None


class CompanyAIConfigOut(BaseModel):
    id: int
    company_id: int
    system_prompt: Optional[str] = None
    persona_name: Optional[str] = None
    temperature: float
    max_tokens_per_response: Optional[int] = None
    allowed_topics: Optional[List[str]] = None
    preferred_language: Optional[str] = None
    rate_limit_per_hour: Optional[int] = None
    monthly_budget_usd: Optional[float] = None

    class Config:
        from_attributes = True


class AIUsageOut(BaseModel):
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    request_count: int


class ChatAnalyticsOut(BaseModel):
    total_sessions: int
    total_messages: int
    satisfaction_rate: Optional[float] = None
    positive_feedback: int
    negative_feedback: int
    usage: AIUsageOut
