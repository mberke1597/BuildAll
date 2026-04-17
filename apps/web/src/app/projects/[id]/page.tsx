'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { apiFetch, getToken } from '../../../lib/api';
import ProjectDashboard from '../../../components/ProjectDashboard';
import Sidebar from '../../../components/Sidebar';
import PageContainer from '../../../components/PageContainer';
import { useAppStore, ModuleKey } from '../../../lib/store';

type Message = {
  id: number;
  sender_id: number;
  type: string;
  text?: string;
  media_id?: number;
  created_at: string;
};

type DocumentRow = {
  id: number;
  status: string;
  created_at: string;
  error?: string;
  media_id?: number;
  filename?: string;
};

type Analytics = {
  project_id: number;
  messages_count: number;
  documents_count: number;
  media_count: number;
  last_activity?: string;
};

type AuditLog = {
  id: number;
  action: string;
  created_at: string;
  user_id?: number;
};

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const projectId = Number(params.id);

  // Zustand store
  const currentModule = useAppStore((s) => s.currentModule);
  const setModule = useAppStore((s) => s.setModule);
  const setProject = useAppStore((s) => s.setProject);

  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState('');
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [users, setUsers] = useState<{ id: number; email: string }[]>([]);
  const [selectedUser, setSelectedUser] = useState<number | null>(null);
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [isAsking, setIsAsking] = useState(false);
  const [estimate, setEstimate] = useState('');
  const [isEstimating, setIsEstimating] = useState(false);
  const [parcelText, setParcelText] = useState('');
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const token = useMemo(() => (typeof window !== 'undefined' ? localStorage.getItem('token') : null), []);

  // Sync project ID to Zustand store
  useEffect(() => {
    setProject(projectId);
    return () => setProject(null);
  }, [projectId, setProject]);

  // Auth check on mount
  useEffect(() => {
    const storedToken = getToken();
    if (!storedToken) {
      router.push('/login');
      return;
    }
    setIsLoading(false);
  }, [router]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadMessages = async () => {
    const data = await apiFetch<Message[]>(`/projects/${projectId}/messages`);
    setMessages(data);
  };

  const loadDocuments = async () => {
    const data = await apiFetch<DocumentRow[]>(`/projects/${projectId}/documents`);
    setDocuments(data);
  };
  const loadAnalytics = async () => {
    const data = await apiFetch<Analytics>(`/projects/${projectId}/analytics`);
    setAnalytics(data);
  };
  const loadAuditLogs = async () => {
    const data = await apiFetch<AuditLog[]>(`/projects/${projectId}/audit-logs`);
    setAuditLogs(data);
  };
  const loadUsers = async () => {
    try {
      const data = await apiFetch<{ id: number; email: string }[]>('/users');
      setUsers(data);
      if (data.length) setSelectedUser(data[0].id);
    } catch {
      setUsers([]);
    }
  };

  useEffect(() => {
    loadMessages();
    loadDocuments();
    loadUsers();
    loadAnalytics();
    loadAuditLogs();
  }, [projectId]);

  useEffect(() => {
    if (!token) return;
    const ws = new WebSocket(`ws://localhost:8000/ws/projects/${projectId}?token=${token}`);
    ws.onmessage = (ev) => {
      const data = JSON.parse(ev.data);
      if (data.type === 'message') {
        setMessages((prev) => [...prev, data.message]);
      }
    };
    wsRef.current = ws;
    return () => {
      ws.close();
    };
  }, [projectId, token]);

  const sendMessage = async () => {
    if (!wsRef.current || !text.trim()) return;
    wsRef.current.send(JSON.stringify({ text }));
    setText('');
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const openMedia = async (mediaId?: number) => {
    if (!mediaId) return;
    const res = await apiFetch<{ url: string }>(`/projects/${projectId}/media/${mediaId}`);
    window.open(res.url, '_blank');
  };

  const getMediaUrl = async (mediaId?: number) => {
    if (!mediaId) return null;
    const res = await apiFetch<{ url: string }>(`/projects/${projectId}/media/${mediaId}`);
    return res.url;
  };

  const uploadFile = async (file: File, isDocument = false) => {
    const form = new FormData();
    form.append('file', file);
    const path = isDocument ? `/projects/${projectId}/documents/upload` : `/projects/${projectId}/upload`;
    await apiFetch(path, { method: 'POST', body: form });
    if (isDocument) {
      loadDocuments();
    }
    loadMessages();
    loadAnalytics();
    loadAuditLogs();
  };

  const onAsk = async () => {
    if (!question.trim()) return;
    setIsAsking(true);
    setAnswer('');
    try {
      const res = await apiFetch<{ answer: string }>(`/projects/${projectId}/ask`, {
        method: 'POST',
        body: JSON.stringify({ question }),
      });
      setAnswer(res.answer);
      loadAuditLogs();
    } finally {
      setIsAsking(false);
    }
  };

  const onEstimate = async () => {
    setIsEstimating(true);
    try {
      const res = await apiFetch<{ estimated_cost: number; estimated_profit?: number; suggestion: string }>(
        `/projects/${projectId}/cost/estimate`,
        {
          method: 'POST',
          body: JSON.stringify({
            project_id: projectId,
            total_m2: 120,
            quality_level: 'MED',
            expected_sale_price_total: 250000,
          }),
        },
      );
      setEstimate(`💰 Estimated cost: $${res.estimated_cost.toLocaleString()}\n📈 Profit: ${res.estimated_profit ? '$' + res.estimated_profit.toLocaleString() : 'N/A'}\n💡 ${res.suggestion}`);
    } finally {
      setIsEstimating(false);
    }
  };

  const onParcel = async () => {
    await apiFetch(`/projects/${projectId}/parcel-lookup`, {
      method: 'POST',
      body: JSON.stringify({ content: parcelText }),
    });
    setParcelText('');
    loadAuditLogs();
  };

  const addMember = async () => {
    if (!selectedUser) return;
    await apiFetch(`/projects/${projectId}/members`, {
      method: 'POST',
      body: JSON.stringify({ user_id: selectedUser, role_in_project: 'MEMBER' }),
    });
  };

  const startRecording = async () => {
    setIsRecording(true);
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const recorder = new MediaRecorder(stream);
    const chunks: BlobPart[] = [];
    recorder.ondataavailable = (e) => chunks.push(e.data);
    recorder.onstop = async () => {
      const blob = new Blob(chunks, { type: 'audio/webm' });
      const file = new File([blob], 'voice.webm', { type: 'audio/webm' });
      await uploadFile(file, false);
      stream.getTracks().forEach((t) => t.stop());
      setIsRecording(false);
    };
    recorder.start();
    setTimeout(() => recorder.stop(), 4000);
  };

  const previewDocument = async (doc: DocumentRow) => {
    if (!doc.media_id) {
      alert('Document file not available');
      return;
    }
    try {
      const res = await apiFetch<{ url: string; filename: string }>(`/projects/${projectId}/media/${doc.media_id}`);
      window.open(res.url, '_blank');
    } catch (error) {
      alert('Failed to load document preview');
      console.error(error);
    }
  };

  const deleteDocument = async (docId: number) => {
    if (!confirm('Are you sure you want to delete this document? This will also remove all AI analysis data for this file.')) {
      return;
    }
    try {
      await apiFetch(`/projects/${projectId}/documents/${docId}`, { method: 'DELETE' });
      await loadDocuments();
    } catch (error) {
      alert('Failed to delete document');
      console.error(error);
    }
  };

  const getStatusBadge = (status: string) => {
    const badges: Record<string, string> = {
      READY: 'badge-success',
      PENDING: 'badge-warning',
      FAILED: 'badge-error',
    };
    return badges[status] || 'badge-warning';
  };

  // Show loading while checking auth
  if (isLoading) {
    return (
      <div className="login-container">
        <div className="stack" style={{ alignItems: 'center', gap: '24px' }}>
          <div className="loading-spinner" style={{ width: '40px', height: '40px' }} />
          <p className="muted">Loading project...</p>
        </div>
      </div>
    );
  }

  /* ─── Module → content mapping ─── */
  const moduleContent: Record<ModuleKey, React.ReactNode> = {
    overview: <ProjectDashboard projectId={projectId} />,
    rfis: (
      <div className="panel stack">
        <div className="row" style={{ justifyContent: 'space-between', marginBottom: '16px' }}>
          <h3>🤖 Proje Dokümanlarına Sor</h3>
        </div>
        <p className="muted" style={{ marginBottom: '16px' }}>
          Yüklediğiniz proje dokümanları hakkında sorular sorun. AI tüm dosyaları tarayıp kaynaklarıyla birlikte yanıt verecektir.
        </p>
        <div className="row" style={{ gap: '12px' }}>
          <input
            className="input"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="örn: Dokümanlarda belirtilen güvenlik gereklilikleri nelerdir?"
            style={{ flex: 1 }}
            onKeyPress={(e) => e.key === 'Enter' && onAsk()}
          />
          <button className="button" onClick={onAsk} disabled={isAsking || !question.trim()}>
            {isAsking ? <span className="loading-spinner" /> : null}
            Sor
          </button>
        </div>
        {answer && (
          <div style={{ marginTop: '24px', padding: '20px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)', borderLeft: '4px solid var(--accent-primary)' }}>
            <div className="row" style={{ marginBottom: '12px' }}>
              <span style={{ fontWeight: '600' }}>AI Yanıtı</span>
            </div>
            <div style={{ lineHeight: '1.7' }}>{answer}</div>
          </div>
        )}
      </div>
    ),
    risks: (
      <div className="panel stack">
        <div className="row" style={{ justifyContent: 'space-between', marginBottom: '16px' }}>
          <h3>💰 Maliyet Tahmini</h3>
        </div>
        <p className="muted" style={{ marginBottom: '24px' }}>
          Alan, kalite seviyesi ve piyasa koşullarına göre AI destekli maliyet tahmini alın.
        </p>
        <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '24px' }}>
          <div style={{ padding: '16px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)' }}>
            <div className="muted" style={{ fontSize: '12px', marginBottom: '4px' }}>Toplam Alan</div>
            <div style={{ fontSize: '24px', fontWeight: '600' }}>120 m²</div>
          </div>
          <div style={{ padding: '16px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)' }}>
            <div className="muted" style={{ fontSize: '12px', marginBottom: '4px' }}>Kalite</div>
            <div style={{ fontSize: '24px', fontWeight: '600' }}>Orta</div>
          </div>
          <div style={{ padding: '16px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)' }}>
            <div className="muted" style={{ fontSize: '12px', marginBottom: '4px' }}>Beklenen Satış</div>
            <div style={{ fontSize: '24px', fontWeight: '600' }}>$250,000</div>
          </div>
        </div>
        <button className="button" onClick={onEstimate} disabled={isEstimating} style={{ alignSelf: 'flex-start' }}>
          {isEstimating ? <><span className="loading-spinner" /> Hesaplanıyor...</> : 'Tahmin Çalıştır'}
        </button>
        {estimate && (
          <div style={{ marginTop: '24px', padding: '24px', background: 'linear-gradient(135deg, rgba(59,130,246,0.1), rgba(139,92,246,0.1))', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-accent)' }}>
            <h4 style={{ marginBottom: '16px' }}>Tahmin Sonuçları</h4>
            <pre style={{ whiteSpace: 'pre-wrap', lineHeight: '1.8', color: 'var(--text-primary)' }}>{estimate}</pre>
          </div>
        )}
      </div>
    ),
    reports: (
      <div className="panel stack">
        <div className="row" style={{ justifyContent: 'space-between', marginBottom: '24px' }}>
          <h3>📊 Analitik & Denetim Günlüğü</h3>
        </div>
        {analytics && (
          <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '16px', marginBottom: '32px' }}>
            <div className="stat-card"><div className="stat-value">{analytics.messages_count}</div><div className="stat-label">Mesajlar</div></div>
            <div className="stat-card"><div className="stat-value">{analytics.documents_count}</div><div className="stat-label">Dokümanlar</div></div>
            <div className="stat-card"><div className="stat-value">{analytics.media_count}</div><div className="stat-label">Medya</div></div>
            <div className="stat-card">
              <div className="stat-value" style={{ fontSize: '14px' }}>
                {analytics.last_activity ? new Date(analytics.last_activity).toLocaleDateString() : 'N/A'}
              </div>
              <div className="stat-label">Son Aktivite</div>
            </div>
          </div>
        )}
        <h4 style={{ marginBottom: '16px' }}>Son Aktiviteler</h4>
        <div className="message-list">
          {auditLogs.length === 0 ? (
            <div className="muted" style={{ textAlign: 'center', padding: '20px' }}>Henüz aktivite kaydı yok</div>
          ) : (
            auditLogs.map((log) => (
              <div key={log.id} className="message">
                <div className="row" style={{ justifyContent: 'space-between' }}>
                  <div className="row">
                    <span className="badge badge-success">{log.action}</span>
                    <span className="muted" style={{ fontSize: '12px' }}>Kullanıcı #{log.user_id ?? 'system'}</span>
                  </div>
                  <span className="muted" style={{ fontSize: '12px' }}>{new Date(log.created_at).toLocaleString()}</span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    ),
    docs: (
      <div className="panel stack">
        <div className="row" style={{ justifyContent: 'space-between', marginBottom: '16px' }}>
          <h3>📄 Dokümanlar</h3>
          <span className="badge badge-success">{documents.length} dosya</span>
        </div>
        <label style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '12px', padding: '40px', border: '2px dashed var(--border-color)', borderRadius: 'var(--radius-lg)', cursor: 'pointer', transition: 'all 0.2s' }}>
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ color: 'var(--accent-primary)' }}>
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontWeight: '500', marginBottom: '4px' }}>Dosyaları sürükleyin veya tıklayın</div>
            <div className="muted">PDF, DOC, XLS desteklenir</div>
          </div>
          <input type="file" style={{ display: 'none' }} onChange={(e) => e.target.files && uploadFile(e.target.files[0], true)} />
        </label>
        <div className="stack" style={{ marginTop: '16px' }}>
          {documents.length === 0 ? (
            <div className="muted" style={{ textAlign: 'center', padding: '20px' }}>Henüz doküman yüklenmedi</div>
          ) : (
            documents.map((d) => (
              <div key={d.id} className="row" style={{ justifyContent: 'space-between', padding: '16px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)', transition: 'all 0.2s' }}>
                <div className="row" style={{ flex: 1, cursor: d.media_id ? 'pointer' : 'default' }} onClick={() => d.media_id && previewDocument(d)}>
                  <div style={{ width: '40px', height: '40px', background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-sm)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                  </div>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontWeight: '500', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.filename || `Doküman #${d.id}`}</div>
                    <div className="muted" style={{ fontSize: '12px' }}>{new Date(d.created_at).toLocaleDateString()}{d.media_id && ' • Önizleme için tıklayın'}</div>
                  </div>
                </div>
                <div className="row" style={{ gap: '8px', flexShrink: 0 }}>
                  <span className={`badge ${getStatusBadge(d.status)}`}>{d.status}</span>
                  <button className="button button-secondary" onClick={() => deleteDocument(d.id)} style={{ padding: '6px 12px' }} title="Dokümanı sil">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    ),
    chat: (
      <div className="panel stack">
        <div className="row" style={{ justifyContent: 'space-between', marginBottom: '16px' }}>
          <h3>💬 Ekip Sohbet</h3>
          <span className="badge badge-success">Canlı</span>
        </div>
        <div className="message-list">
          {messages.length === 0 ? (
            <div className="empty-state" style={{ padding: '40px 20px' }}>
              <div style={{ fontSize: '48px', marginBottom: '12px' }}>💬</div>
              <p className="muted">Henüz mesaj yok. Sohbeti başlatın!</p>
            </div>
          ) : (
            messages.map((m) => (
              <div key={m.id} className="message">
                <div className="meta">
                  <span className={`badge ${m.type === 'VOICE' ? 'badge-warning' : 'badge-success'}`} style={{ fontSize: '10px' }}>{m.type}</span>
                  <span>{new Date(m.created_at).toLocaleString()}</span>
                </div>
                <div style={{ marginTop: '8px' }}>{m.text}</div>
                {m.media_id && (
                  <div className="actions">
                    <button className="button button-secondary" style={{ padding: '8px 16px', fontSize: '13px' }} onClick={() => openMedia(m.media_id)}>İndir</button>
                  </div>
                )}
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>
        <div style={{ padding: '16px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)', marginTop: '16px' }}>
          <div className="row" style={{ gap: '12px' }}>
            <input className="input" value={text} onChange={(e) => setText(e.target.value)} onKeyPress={handleKeyPress} placeholder="Mesajınızı yazın..." style={{ flex: 1 }} />
            <button className="button" onClick={sendMessage} disabled={!text.trim()}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
            </button>
          </div>
          <div className="row" style={{ marginTop: '12px', gap: '12px' }}>
            <label className="button button-secondary" style={{ cursor: 'pointer', flex: 1, justifyContent: 'center' }}>
              📎 Dosya Ekle
              <input type="file" style={{ display: 'none' }} onChange={(e) => e.target.files && uploadFile(e.target.files[0])} />
            </label>
            <button className={`button ${isRecording ? 'button-danger' : 'button-secondary'}`} onClick={startRecording} disabled={isRecording} style={{ flex: 1 }}>
              🎤 {isRecording ? 'Kaydediliyor...' : 'Sesli Not'}
            </button>
          </div>
        </div>
      </div>
    ),
  };

  return (
    <div className="project-shell animate-fade-in">
      <Sidebar
        projectId={projectId}
        currentModule={currentModule}
        onModuleChange={setModule}
      />

      <PageContainer>{moduleContent[currentModule]}</PageContainer>
    </div>
  );
}
