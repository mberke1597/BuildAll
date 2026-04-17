'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { apiFetch, getToken } from '../lib/api';
import { useAppStore, ChatMessage, ChatSessionMeta, MODULES } from '../lib/store';
import { extractActions, stripActionBlock, executeActionBlock, formatToolResults } from '../lib/actions';

/* ─── Constants ─── */
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const QUICK_SUGGESTIONS = [
  { icon: '📊', text: 'Projenin genel durumunu özetle' },
  { icon: '⚠️', text: 'Kritik riskleri ve gecikmeleri göster' },
  { icon: '💰', text: 'Bütçe durumunu analiz et' },
  { icon: '📋', text: 'Açık RFI\'ları listele' },
];

/* ─── Mini Markdown ─── */
function renderMd(text: string): string {
  return text
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="md-code-block"><code>$2</code></pre>')
    .replace(/`([^`]+)`/g, '<code class="md-inline-code">$1</code>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^## (.+)$/gm, '<h3>$1</h3>')
    .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
    .replace(/((?:<li>.*?<\/li>\n?)+)/g, '<ul>$1</ul>')
    .replace(/\n/g, '<br/>');
}

/* ─── Component ─── */
export default function CopilotPanel() {
  const {
    copilotOpen, copilotWidth, copilotFocusMode,
    setCopilotOpen, setCopilotWidth, setCopilotFocusMode,
    projectId, sessions, setSessions, activeSessionId, setActiveSession,
    messages, setMessages, addMessage, updateLastAssistant,
  } = useAppStore();

  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showSessions, setShowSessions] = useState(false);
  const [projects, setProjects] = useState<{ id: number; name: string }[]>([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const isResizingRef = useRef(false);

  /* ─── Effects ─── */

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Load sessions + projects when panel opens
  useEffect(() => {
    if (copilotOpen && getToken()) {
      loadSessions();
      loadProjects();
    }
  }, [copilotOpen]);

  // Keyboard shortcuts: Ctrl+K to toggle, Escape to close
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setCopilotOpen(!copilotOpen);
      }
      if (e.key === 'Escape' && copilotOpen && !copilotFocusMode) {
        setCopilotOpen(false);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [copilotOpen, copilotFocusMode, setCopilotOpen]);

  // Focus textarea when panel opens
  useEffect(() => {
    if (copilotOpen) {
      setTimeout(() => textareaRef.current?.focus(), 300);
    }
  }, [copilotOpen]);

  /* ─── Resize Logic ─── */
  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isResizingRef.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const onMove = (ev: MouseEvent) => {
      if (!isResizingRef.current) return;
      const newWidth = ev.clientX;
      setCopilotWidth(newWidth);
    };

    const onUp = () => {
      isResizingRef.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }, [setCopilotWidth]);

  /* ─── API Helpers ─── */
  const loadSessions = async () => {
    try {
      const data = await apiFetch<ChatSessionMeta[]>('/chat/sessions');
      setSessions(data);
    } catch { /* ignore */ }
  };

  const loadProjects = async () => {
    try {
      const data = await apiFetch<{ id: number; name: string }[]>('/projects');
      setProjects(data);
    } catch { /* ignore */ }
  };

  const loadSessionMessages = async (sid: string) => {
    try {
      const data = await apiFetch<{
        session: ChatSessionMeta;
        messages: { id: string; role: 'user' | 'assistant'; content: string; citations?: any[] }[];
      }>(`/chat/sessions/${sid}`);
      setActiveSession(sid);
      setMessages(data.messages.map((m) => ({ ...m, created_at: new Date().toISOString() })));
      setShowSessions(false);
    } catch { /* ignore */ }
  };

  const createSession = async () => {
    try {
      const body: any = {};
      if (projectId) body.project_id = projectId;
      const data = await apiFetch<{ id: string; title: string | null; project_id: number | null; created_at: string; updated_at: string }>(
        '/chat/sessions',
        { method: 'POST', body: JSON.stringify(body) },
      );
      setActiveSession(data.id);
      setMessages([]);
      await loadSessions();
      setShowSessions(false);
    } catch { /* ignore */ }
  };

  /* ─── Streaming Send ─── */
  const sendMessage = async (overrideText?: string) => {
    const text = (overrideText || input).trim();
    if (!text || isLoading) return;
    setInput('');
    setIsLoading(true);

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    };
    addMessage(userMsg);

    // Create session if none
    let sid = activeSessionId;
    if (!sid) {
      try {
        const body: any = {};
        if (projectId) body.project_id = projectId;
        const s = await apiFetch<ChatSessionMeta>('/chat/sessions', {
          method: 'POST',
          body: JSON.stringify(body),
        });
        sid = s.id;
        setActiveSession(sid);
        await loadSessions();
      } catch (err) {
        addMessage({
          id: crypto.randomUUID(),
          role: 'assistant',
          content: 'Oturum oluşturulamadı. Lütfen tekrar deneyin.',
          created_at: new Date().toISOString(),
        });
        setIsLoading(false);
        return;
      }
    }

    // Placeholder for streaming
    const assistantId = crypto.randomUUID();
    addMessage({
      id: assistantId,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
      isStreaming: true,
    });

    try {
      const token = getToken();
      const controller = new AbortController();
      abortRef.current = controller;

      const res = await fetch(`${API_URL}/chat/sessions/${sid}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ content: text }),
        signal: controller.signal,
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      if (!res.body) throw new Error('No response body');

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let accumulated = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const payload = line.slice(6);
            if (payload === '[DONE]') break;
            try {
              const parsed = JSON.parse(payload);
              if (parsed.token) {
                accumulated += parsed.token;
                updateLastAssistant(accumulated);
              }
              if (parsed.citations) {
                // Store citations — skip for now
              }
            } catch {
              // Non-JSON SSE — accumulate raw
              accumulated += payload;
              updateLastAssistant(accumulated);
            }
          }
        }
      }

      // Finalize message
      const finalContent = accumulated;
      useAppStore.getState().setMessages(
        useAppStore.getState().messages.map((m) =>
          m.id === assistantId ? { ...m, content: finalContent, isStreaming: false } : m,
        ),
      );

      // Check for tool actions in the response
      const actionBlock = extractActions(finalContent);
      if (actionBlock) {
        const results = await executeActionBlock(actionBlock);
        const toolSummary = formatToolResults(results);

        // Add tool result as system message
        addMessage({
          id: crypto.randomUUID(),
          role: 'system',
          content: toolSummary,
          created_at: new Date().toISOString(),
        });

        // Clean the visible assistant message
        const cleanContent = stripActionBlock(finalContent);
        useAppStore.getState().setMessages(
          useAppStore.getState().messages.map((m) =>
            m.id === assistantId ? { ...m, content: cleanContent || finalContent } : m,
          ),
        );

        // If there's data to explain, send a follow-up
        const explainResult = results.find((r) => r.action === 'explain_widget' && r.success);
        if (explainResult?.data) {
          // Auto-send the data back for AI to explain
          const followUp = `İşte widget verisi:\n\`\`\`json\n${JSON.stringify(explainResult.data, null, 2)}\n\`\`\`\nBu veriyi analiz edip kullanıcıya açıkla.`;
          // We don't recurse — just send another streaming message
          setTimeout(() => sendMessage(followUp), 500);
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        useAppStore.getState().setMessages(
          useAppStore.getState().messages.map((m) =>
            m.id === assistantId
              ? { ...m, content: 'Yanıt alınamadı. Lütfen tekrar deneyin.', isStreaming: false }
              : m,
          ),
        );
      }
    } finally {
      setIsLoading(false);
      abortRef.current = null;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const stopGeneration = () => {
    abortRef.current?.abort();
    setIsLoading(false);
  };

  /* ─── Render ─── */

  return (
    <>
      {/* Focus mode overlay */}
      {copilotOpen && copilotFocusMode && (
        <div className="copilot-focus-overlay" onClick={() => setCopilotFocusMode(false)} />
      )}

      {/* Side Panel */}
      <div
        ref={panelRef}
        className={`copilot-panel ${copilotOpen ? 'open' : ''}`}
        style={{ width: copilotWidth }}
      >
        {/* Resize handle */}
        <div className="copilot-resize-handle" onMouseDown={startResize} />

        {/* Header */}
        <div className="copilot-header">
          <div className="copilot-header-title">
            <span>🤖</span>
            BuildAll AI Asistan
          </div>
          <div className="copilot-header-actions">
            <button
              className={`copilot-header-btn ${showSessions ? 'active' : ''}`}
              onClick={() => setShowSessions(!showSessions)}
              title="Oturumlar"
            >
              📋
            </button>
            <button
              className={`copilot-header-btn ${copilotFocusMode ? 'active' : ''}`}
              onClick={() => setCopilotFocusMode(!copilotFocusMode)}
              title="Odak Modu"
            >
              🎯
            </button>
            <button
              className="copilot-header-btn"
              onClick={() => setCopilotOpen(false)}
              title="Kapat (Esc)"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Session list */}
        <div className={`copilot-sessions ${showSessions ? 'visible' : ''}`}>
          <button className="copilot-new-session" onClick={createSession}>
            + Yeni Oturum
          </button>
          {sessions.length === 0 ? (
            <div style={{ padding: '12px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
              Henüz oturum yok
            </div>
          ) : (
            sessions.map((s) => (
              <button
                key={s.id}
                className={`copilot-session-item ${activeSessionId === s.id ? 'active' : ''}`}
                onClick={() => loadSessionMessages(s.id)}
              >
                <span className="copilot-session-title">{s.title || 'Adsız Oturum'}</span>
                {s.project_id && (
                  <span className="copilot-session-scope">
                    P#{s.project_id}
                  </span>
                )}
              </button>
            ))
          )}
        </div>

        {/* Messages */}
        {messages.length === 0 ? (
          <div className="copilot-empty">
            <div className="copilot-empty-icon">🤖</div>
            <div className="copilot-empty-title">BuildAll AI Asistan</div>
            <div className="copilot-empty-subtitle">
              Proje verilerini analiz edebilir, grafikleri açıklayabilir ve modüller arası gezinmenize yardımcı olabilirim.
            </div>
            <div className="copilot-suggestions" style={{ width: '100%', paddingTop: '12px' }}>
              {QUICK_SUGGESTIONS.map((s, i) => (
                <button
                  key={i}
                  className="copilot-suggestion"
                  onClick={() => sendMessage(s.text)}
                >
                  <span>{s.icon}</span>
                  {s.text}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="copilot-messages">
            {messages.map((m) => (
              <div
                key={m.id}
                className={`copilot-msg ${m.role}${m.role === 'system' ? ' tool-result' : ''}`}
              >
                {m.role === 'assistant' ? (
                  <>
                    <div dangerouslySetInnerHTML={{ __html: renderMd(m.content || '') }} />
                    {m.isStreaming && <span className="copilot-cursor">▌</span>}
                  </>
                ) : m.role === 'system' ? (
                  <div style={{ fontFamily: 'monospace', whiteSpace: 'pre-wrap', fontSize: '11px' }}>
                    {m.content}
                  </div>
                ) : (
                  <div>{m.content}</div>
                )}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}

        {/* Input */}
        <div className="copilot-input-area">
          <textarea
            ref={textareaRef}
            className="copilot-textarea"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={projectId ? `Proje #${projectId} hakkında soru sor...` : 'Bir soru yazın...'}
            rows={1}
            disabled={isLoading}
          />
          {isLoading ? (
            <button className="copilot-send-btn" onClick={stopGeneration} title="Durdur">
              ⬛
            </button>
          ) : (
            <button
              className="copilot-send-btn"
              onClick={() => sendMessage()}
              disabled={!input.trim()}
              title="Gönder (Enter)"
            >
              ↑
            </button>
          )}
        </div>
      </div>
    </>
  );
}
