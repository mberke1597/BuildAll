'use client';

import { useState, useRef, useEffect } from 'react';
import { MODULES, ModuleKey } from '../lib/store';
import { getToken } from '../lib/api';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const QUICK_SUGGESTIONS = [
  { icon: '📊', text: 'Projenin genel durumunu özetle' },
  { icon: '⚠️', text: 'Kritik riskleri ve gecikmeleri göster' },
  { icon: '💰', text: 'Bütçe durumunu analiz et' },
  { icon: '📋', text: 'Açık RFI\'ları listele' },
];

type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  isStreaming?: boolean;
};

function renderMd(text: string): string {
  return text
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="sidebar-code-block"><code>$2</code></pre>')
    .replace(/`([^`]+)`/g, '<code class="sidebar-inline-code">$1</code>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^## (.+)$/gm, '<h3>$1</h3>')
    .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
    .replace(/((?:<li>.*?<\/li>\n?)+)/g, '<ul>$1</ul>')
    .replace(/\n/g, '<br/>');
}

type SidebarProps = {
  projectId: number;
  currentModule: ModuleKey;
  onModuleChange: (key: ModuleKey) => void;
};

export default function Sidebar({
  projectId,
  currentModule,
  onModuleChange,
}: SidebarProps) {
  const [aiChatMode, setAiChatMode] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (aiChatMode) {
      setTimeout(() => textareaRef.current?.focus(), 100);
    }
  }, [aiChatMode]);

  const sendMessage = async (overrideText?: string) => {
    const text = (overrideText || input).trim();
    if (!text || isLoading) return;
    
    setInput('');
    setIsLoading(true);

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
    };
    setMessages(prev => [...prev, userMsg]);

    // Create session if needed
    let sid = sessionId;
    if (!sid) {
      try {
        const token = getToken();
        const res = await fetch(`${API_URL}/chat/sessions`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ project_id: projectId }),
        });
        if (res.ok) {
          const data = await res.json();
          sid = data.id;
          setSessionId(sid);
        }
      } catch {
        // ignore
      }
    }

    const assistantId = crypto.randomUUID();
    setMessages(prev => [...prev, {
      id: assistantId,
      role: 'assistant',
      content: '',
      isStreaming: true,
    }]);

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

      if (!res.ok || !res.body) throw new Error('Failed');

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
                setMessages(prev => prev.map(m => 
                  m.id === assistantId ? { ...m, content: accumulated } : m
                ));
              }
            } catch {
              accumulated += payload;
              setMessages(prev => prev.map(m => 
                m.id === assistantId ? { ...m, content: accumulated } : m
              ));
            }
          }
        }
      }

      setMessages(prev => prev.map(m => 
        m.id === assistantId ? { ...m, isStreaming: false } : m
      ));
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        setMessages(prev => prev.map(m => 
          m.id === assistantId 
            ? { ...m, content: 'Yanıt alınamadı. Lütfen tekrar deneyin.', isStreaming: false } 
            : m
        ));
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

  const exitAiChat = () => {
    setAiChatMode(false);
  };

  const startNewChat = () => {
    setMessages([]);
    setSessionId(null);
  };

  // AI Chat Mode
  if (aiChatMode) {
    return (
      <aside className="project-sidebar sidebar-ai-mode">
        {/* AI Header with back button */}
        <div className="sidebar-ai-header">
          <button className="sidebar-back-btn" onClick={exitAiChat}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="15 18 9 12 15 6" />
            </svg>
            Geri
          </button>
          <button className="sidebar-new-chat-btn" onClick={startNewChat} title="Yeni Sohbet">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </button>
        </div>

        <div className="sidebar-ai-title">
          <span className="sidebar-ai-icon">🤖</span>
          <span>BuildAll AI Asistan</span>
        </div>

        {/* Messages area */}
        {messages.length === 0 ? (
          <div className="sidebar-ai-empty">
            <div className="sidebar-ai-empty-text">
              Proje verilerini analiz edebilir, grafikleri açıklayabilir ve sorularınızı yanıtlayabilirim.
            </div>
            <div className="sidebar-ai-suggestions">
              {QUICK_SUGGESTIONS.map((s, i) => (
                <button
                  key={i}
                  className="sidebar-ai-suggestion"
                  onClick={() => sendMessage(s.text)}
                >
                  <span>{s.icon}</span>
                  {s.text}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="sidebar-ai-messages">
            {messages.map((m) => (
              <div key={m.id} className={`sidebar-ai-msg ${m.role}`}>
                {m.role === 'assistant' ? (
                  <>
                    <div dangerouslySetInnerHTML={{ __html: renderMd(m.content || '') }} />
                    {m.isStreaming && <span className="sidebar-ai-cursor">▌</span>}
                  </>
                ) : (
                  <div>{m.content}</div>
                )}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}

        {/* Input area */}
        <div className="sidebar-ai-input-area">
          <textarea
            ref={textareaRef}
            className="sidebar-ai-textarea"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`#${projectId} hakkında soru sor...`}
            rows={1}
            disabled={isLoading}
          />
          {isLoading ? (
            <button className="sidebar-ai-send-btn" onClick={stopGeneration} title="Durdur">
              ⬛
            </button>
          ) : (
            <button
              className="sidebar-ai-send-btn"
              onClick={() => sendMessage()}
              disabled={!input.trim()}
              title="Gönder"
            >
              ↑
            </button>
          )}
        </div>
      </aside>
    );
  }

  // Normal sidebar mode
  return (
    <aside className="project-sidebar">
      <div className="sidebar-project-header">
        <a href="/dashboard" className="sidebar-back-link">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="15 18 9 12 15 6" />
          </svg>
          Tum Projeler
        </a>
        <div className="sidebar-project-name">Proje #{projectId}</div>
      </div>

      <nav className="sidebar-nav-section">
        <div className="sidebar-nav-label">Moduller</div>
        {MODULES.map((module) => (
          <button
            key={module.key}
            type="button"
            className={`sidebar-nav-item ${currentModule === module.key ? 'active' : ''}`}
            onClick={() => onModuleChange(module.key)}
          >
            <span className="sidebar-nav-icon">{module.icon}</span>
            {module.label}
          </button>
        ))}
      </nav>

      <div className="sidebar-footer">
        <button 
          type="button" 
          className="sidebar-ai-toggle"
          onClick={() => setAiChatMode(true)}
        >
          <span className="sidebar-ai-toggle-icon">🤖</span>
          AI Asistan
        </button>
      </div>
    </aside>
  );
}

