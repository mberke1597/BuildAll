'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { apiFetch, getToken } from '../lib/api';

// ─── Types ───────────────────────────────────────────────────────────

type CitationItem = {
  ref: number;
  document_id: number;
  document_name: string;
  chunk_id: number;
  page_number: number | null;
  snippet: string;
};

type Message = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: CitationItem[];
  attachments?: { file: File; preview?: string }[];
  isStreaming?: boolean;
};

type Session = {
  id: string;
  title: string | null;
  project_id: number | null;
  created_at: string;
  updated_at: string;
};

type Project = {
  id: number;
  name: string;
};

// ─── Constants ───────────────────────────────────────────────────────

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const SUGGESTED_PROMPTS = [
  { icon: '💰', text: 'Estimate cost for a 200m² residential build' },
  { icon: '🏗️', text: 'What materials are best for coastal climates?' },
  { icon: '📋', text: 'Help me plan a project timeline' },
  { icon: '📄', text: 'Summarize my uploaded project documents' },
];

const DEFAULT_RESPONSES: Record<string, string> = {
  cost: 'For cost estimation, I recommend considering: materials (40-50%), labor (25-35%), permits & fees (5-10%), and contingency (10-15%). Log in for personalized AI help!',
  project: 'Effective project management involves: clear scope, realistic timelines, budget tracking, communication, and risk management. Log in for AI assistance!',
  material: 'Material selection depends on project type, budget, and climate. Common factors: durability, maintenance, and sustainability. Log in for detailed guidance!',
  default: 'I can help with cost estimation, project management, material selection, and more. Please log in for full AI assistance!',
};

// ─── Markdown Renderer (lightweight, no external dep) ────────────────

function renderMarkdown(text: string): string {
  let html = text
    // Code blocks (fenced)
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="md-code-block"><code class="language-$1">$2</code></pre>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code class="md-inline-code">$1</code>')
    // Bold
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // Italic
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Headers
    .replace(/^### (.+)$/gm, '<h4 class="md-h4">$1</h4>')
    .replace(/^## (.+)$/gm, '<h3 class="md-h3">$1</h3>')
    .replace(/^# (.+)$/gm, '<h2 class="md-h2">$1</h2>')
    // Horizontal rule
    .replace(/^---$/gm, '<hr class="md-hr"/>')
    // Unordered lists
    .replace(/^[-*] (.+)$/gm, '<li class="md-li">$1</li>')
    // Table rows (basic GFM)
    .replace(/^\|(.+)\|$/gm, (_, row) => {
      const cells = row.split('|').map((c: string) => c.trim()).filter(Boolean);
      const tds = cells.map((c: string) => `<td class="md-td">${c}</td>`).join('');
      return `<tr>${tds}</tr>`;
    })
    // Links
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener" class="md-link">$1</a>')
    // Line breaks
    .replace(/\n/g, '<br/>');

  // Wrap consecutive <li> in <ul>
  html = html.replace(/((?:<li class="md-li">.*?<\/li><br\/>?)+)/g, '<ul class="md-ul">$1</ul>');
  // Wrap consecutive <tr> in <table>
  html = html.replace(/((?:<tr>.*?<\/tr><br\/>?)+)/g, '<table class="md-table">$1</table>');
  // Clean up <br/> inside lists and tables
  html = html.replace(/<\/li><br\/>/g, '</li>');
  html = html.replace(/<\/tr><br\/>/g, '</tr>');

  return html;
}

// ─── Speech Recognition Hook ─────────────────────────────────────────

function useSpeechRecognition() {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const recognitionRef = useRef<any>(null);

  const startListening = useCallback(() => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = navigator.language || 'en-US';

    recognition.onresult = (event: any) => {
      let text = '';
      for (let i = 0; i < event.results.length; i++) {
        text += event.results[i][0].transcript;
      }
      setTranscript(text);
    };

    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => setIsListening(false);

    recognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
  }, []);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    setIsListening(false);
  }, []);

  const speechSupported = typeof window !== 'undefined' &&
    !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);

  return { isListening, transcript, startListening, stopListening, speechSupported, setTranscript };
}

// ─── TTS ──────────────────────────────────────────────────────────────

function speakText(text: string) {
  if (typeof window === 'undefined' || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  // Strip markdown for speech
  const clean = text.replace(/[#*`\[\]()_~|>-]/g, '').replace(/\n/g, '. ');
  const utterance = new SpeechSynthesisUtterance(clean);
  utterance.rate = 1.0;
  utterance.pitch = 1.0;
  window.speechSynthesis.speak(utterance);
}

// ─── Main Component ──────────────────────────────────────────────────

export default function AIChatbot() {
  // UI state
  const [isOpen, setIsOpen] = useState(false);
  const [showSidebar, setShowSidebar] = useState(false);

  // Chat state
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // Session state
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);

  // Feature state
  const [showSuggestions, setShowSuggestions] = useState(true);
  const [attachments, setAttachments] = useState<File[]>([]);
  const [speakingMsgId, setSpeakingMsgId] = useState<string | null>(null);

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Voice
  const { isListening, transcript, startListening, stopListening, speechSupported, setTranscript } =
    useSpeechRecognition();

  // ─── Effects ────────────────────────────────────────────────────────

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Load sessions on open
  useEffect(() => {
    if (isOpen && getToken()) {
      loadSessions();
      loadProjects();
    }
  }, [isOpen]);

  // Voice transcript → input
  useEffect(() => {
    if (transcript) {
      setInput(transcript);
    }
  }, [transcript]);

  // ─── API Helpers ────────────────────────────────────────────────────

  const loadSessions = async () => {
    try {
      const data = await apiFetch<Session[]>('/chat/sessions');
      setSessions(data);
    } catch {
      /* ignore */
    }
  };

  const loadProjects = async () => {
    try {
      const data = await apiFetch<Project[]>('/projects');
      setProjects(data);
    } catch {
      /* ignore */
    }
  };

  const loadSession = async (sid: string) => {
    try {
      const data = await apiFetch<{
        session: Session;
        messages: { id: string; role: 'user' | 'assistant'; content: string; citations?: CitationItem[] }[];
      }>(`/chat/sessions/${sid}`);
      setSessionId(sid);
      setMessages(data.messages);
      setSelectedProjectId(data.session.project_id);
      setShowSuggestions(false);
      setShowSidebar(false);
    } catch {
      /* ignore */
    }
  };

  // ─── Streaming Send ─────────────────────────────────────────────────

  const sendMessage = async (overrideMessage?: string) => {
    const text = (overrideMessage || input).trim();
    if (!text || isLoading) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: text,
      attachments: attachments.map((f) => ({ file: f, preview: f.type.startsWith('image/') ? URL.createObjectURL(f) : undefined })),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setTranscript('');
    setAttachments([]);
    setShowSuggestions(false);
    setIsLoading(true);

    const token = getToken();

    if (!token) {
      // Non-authenticated fallback
      const lowerInput = text.toLowerCase();
      let response = DEFAULT_RESPONSES.default;
      if (lowerInput.includes('cost') || lowerInput.includes('price') || lowerInput.includes('budget')) {
        response = DEFAULT_RESPONSES.cost;
      } else if (lowerInput.includes('project') || lowerInput.includes('manage')) {
        response = DEFAULT_RESPONSES.project;
      } else if (lowerInput.includes('material') || lowerInput.includes('build')) {
        response = DEFAULT_RESPONSES.material;
      }
      setMessages((prev) => [...prev, { id: (Date.now() + 1).toString(), role: 'assistant', content: response }]);
      setIsLoading(false);
      return;
    }

    // Streaming SSE via fetch
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch(`${API_URL}/chat/assistant/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          message: text,
          session_id: sessionId,
          project_id: selectedProjectId,
          attachments: [],
        }),
        signal: controller.signal,
      });

      if (!res.body) throw new Error('No response body');

      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      let assistantMsgId = (Date.now() + 1).toString();
      let fullContent = '';
      let citations: CitationItem[] = [];
      let streamStarted = false;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split('\n\n');
        buffer = events.pop() ?? '';

        for (const evt of events) {
          const line = evt.split('\n').find((l) => l.startsWith('data: '));
          if (!line) continue;

          try {
            const payload = JSON.parse(line.slice('data: '.length));

            if (payload.type === 'start') {
              if (payload.session_id) setSessionId(payload.session_id);
              assistantMsgId = payload.message_id || assistantMsgId;
              streamStarted = true;
              setMessages((prev) => [
                ...prev,
                { id: assistantMsgId, role: 'assistant', content: '', isStreaming: true },
              ]);
            }

            if (payload.type === 'token') {
              fullContent += payload.delta;
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMsgId ? { ...m, content: fullContent, isStreaming: true } : m
                )
              );
            }

            if (payload.type === 'citations') {
              citations = payload.citations || [];
            }

            if (payload.type === 'done') {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMsgId
                    ? { ...m, content: fullContent, citations, isStreaming: false }
                    : m
                )
              );
            }

            if (payload.type === 'error') {
              const errContent = fullContent || `Error: ${payload.message}`;
              if (streamStarted) {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMsgId ? { ...m, content: errContent, isStreaming: false } : m
                  )
                );
              } else {
                setMessages((prev) => [
                  ...prev,
                  { id: assistantMsgId, role: 'assistant', content: errContent },
                ]);
              }
            }
          } catch {
            /* ignore parse errors */
          }
        }
      }

      // Refresh sessions list
      loadSessions();
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        setMessages((prev) => [
          ...prev,
          {
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content: "I'm sorry, I encountered an error. Please try again.",
          },
        ]);
      }
    } finally {
      setIsLoading(false);
      abortRef.current = null;
    }
  };

  const stopGeneration = () => {
    abortRef.current?.abort();
    setIsLoading(false);
  };

  // ─── Feedback ───────────────────────────────────────────────────────

  const submitFeedback = async (messageId: string, rating: number) => {
    try {
      await apiFetch('/chat/feedback', {
        method: 'POST',
        body: JSON.stringify({ message_id: messageId, rating }),
      });
    } catch {
      /* ignore */
    }
  };

  // ─── Export ─────────────────────────────────────────────────────────

  const exportChat = async () => {
    if (!sessionId) return;
    try {
      const data = await apiFetch<{ content: string }>(`/chat/sessions/${sessionId}/export?format=markdown`);
      const blob = new Blob([data.content], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'chat-export.md';
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      /* ignore */
    }
  };

  const copyChat = () => {
    const text = messages
      .map((m) => `${m.role === 'user' ? 'You' : 'AI'}: ${m.content}`)
      .join('\n\n');
    navigator.clipboard.writeText(text);
  };

  // ─── New Chat ───────────────────────────────────────────────────────

  const startNewChat = () => {
    setSessionId(null);
    setMessages([]);
    setShowSuggestions(true);
    setShowSidebar(false);
  };

  // ─── File Upload ────────────────────────────────────────────────────

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    const allowed = files.filter(
      (f) =>
        f.type.startsWith('image/') ||
        f.type === 'application/pdf' ||
        f.type === 'text/plain' ||
        f.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    );
    setAttachments((prev) => [...prev, ...allowed].slice(0, 5));
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const removeAttachment = (index: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index));
  };

  // ─── TTS Toggle ────────────────────────────────────────────────────

  const toggleSpeak = (msgId: string, content: string) => {
    if (speakingMsgId === msgId) {
      window.speechSynthesis?.cancel();
      setSpeakingMsgId(null);
    } else {
      speakText(content);
      setSpeakingMsgId(msgId);
    }
  };

  // ─── Key Handler ────────────────────────────────────────────────────

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // ─── Auto-resize textarea ──────────────────────────────────────────

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 120) + 'px';
    }
  }, [input]);

  // ─── Render ─────────────────────────────────────────────────────────

  const isAuthenticated = !!getToken();

  return (
    <>
      {/* Floating trigger button */}
      <button
        className="chatbot-trigger"
        onClick={() => setIsOpen(!isOpen)}
        aria-label={isOpen ? 'Close AI Assistant' : 'Open AI Assistant'}
        title={isOpen ? 'Close' : 'BuildAll AI Assistant'}
      >
        {isOpen ? (
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        ) : (
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            <circle cx="12" cy="10" r="1" fill="currentColor" />
            <circle cx="8" cy="10" r="1" fill="currentColor" />
            <circle cx="16" cy="10" r="1" fill="currentColor" />
          </svg>
        )}
      </button>

      {/* Chat panel */}
      {isOpen && (
        <div className="chatbot-panel" role="dialog" aria-label="AI Assistant Chat">
          {/* Header */}
          <div className="chatbot-header">
            <div className="chatbot-header-left">
              {isAuthenticated && (
                <button
                  className="chatbot-icon-btn"
                  onClick={() => setShowSidebar(!showSidebar)}
                  aria-label="Chat history"
                  title="Chat history"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <line x1="3" y1="6" x2="21" y2="6" />
                    <line x1="3" y1="12" x2="21" y2="12" />
                    <line x1="3" y1="18" x2="21" y2="18" />
                  </svg>
                </button>
              )}
              <div className="chatbot-title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M12 16v-4" />
                  <path d="M12 8h.01" />
                </svg>
                BuildAll AI
              </div>
            </div>
            <div className="chatbot-header-right">
              {isAuthenticated && sessionId && (
                <>
                  <button className="chatbot-icon-btn" onClick={exportChat} title="Export chat" aria-label="Export chat">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="7 10 12 15 17 10" />
                      <line x1="12" y1="15" x2="12" y2="3" />
                    </svg>
                  </button>
                  <button className="chatbot-icon-btn" onClick={copyChat} title="Copy chat" aria-label="Copy chat">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                    </svg>
                  </button>
                </>
              )}
              {isAuthenticated && (
                <button className="chatbot-icon-btn" onClick={startNewChat} title="New chat" aria-label="New chat">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <line x1="12" y1="5" x2="12" y2="19" />
                    <line x1="5" y1="12" x2="19" y2="12" />
                  </svg>
                </button>
              )}
              <button className="chatbot-close" onClick={() => setIsOpen(false)} aria-label="Close chat">
                ×
              </button>
            </div>
          </div>

          {/* Project selector */}
          {isAuthenticated && projects.length > 0 && (
            <div className="chatbot-project-bar">
              <select
                className="chatbot-project-select"
                value={selectedProjectId || ''}
                onChange={(e) => setSelectedProjectId(e.target.value ? Number(e.target.value) : null)}
                aria-label="Select project for document context"
              >
                <option value="">💬 General chat</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    📁 {p.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Session sidebar */}
          {showSidebar && (
            <div className="chatbot-sidebar" role="complementary" aria-label="Chat history">
              <div className="chatbot-sidebar-header">
                <span>Chat History</span>
                <button className="chatbot-icon-btn" onClick={() => setShowSidebar(false)} aria-label="Close sidebar">
                  ×
                </button>
              </div>
              <div className="chatbot-sidebar-list">
                {sessions.map((s) => (
                  <button
                    key={s.id}
                    className={`chatbot-sidebar-item ${s.id === sessionId ? 'active' : ''}`}
                    onClick={() => loadSession(s.id)}
                  >
                    <span className="chatbot-sidebar-item-title">{s.title || 'Untitled chat'}</span>
                    <span className="chatbot-sidebar-item-date">
                      {new Date(s.updated_at).toLocaleDateString()}
                    </span>
                  </button>
                ))}
                {sessions.length === 0 && (
                  <div className="chatbot-sidebar-empty">No conversations yet</div>
                )}
              </div>
            </div>
          )}

          {/* Messages area */}
          <div className="chatbot-messages" role="log" aria-live="polite" aria-label="Chat messages">
            {/* Welcome message */}
            {messages.length === 0 && (
              <div className="chatbot-welcome">
                <div className="chatbot-welcome-icon">🤖</div>
                <h3 className="chatbot-welcome-title">BuildAll AI Assistant</h3>
                <p className="chatbot-welcome-text">
                  I can help with construction questions, cost estimation, project management, and more.
                  {selectedProjectId ? ' I can also answer questions about your project documents.' : ''}
                </p>
              </div>
            )}

            {/* Suggested prompts */}
            {showSuggestions && messages.length === 0 && (
              <div className="chatbot-suggestions">
                {SUGGESTED_PROMPTS.map((s, i) => (
                  <button
                    key={i}
                    className="chatbot-suggestion-chip"
                    onClick={() => sendMessage(s.text)}
                  >
                    <span className="chatbot-chip-icon">{s.icon}</span>
                    <span>{s.text}</span>
                  </button>
                ))}
              </div>
            )}

            {/* Message list */}
            {messages.map((msg) => (
              <div key={msg.id} className={`chatbot-message ${msg.role}`}>
                {/* Attachments (user) */}
                {msg.attachments && msg.attachments.length > 0 && (
                  <div className="chatbot-msg-attachments">
                    {msg.attachments.map((a, i) =>
                      a.preview ? (
                        <img key={i} src={a.preview} alt={a.file.name} className="chatbot-attachment-thumb" />
                      ) : (
                        <div key={i} className="chatbot-attachment-file">📄 {a.file.name}</div>
                      )
                    )}
                  </div>
                )}

                {/* Content */}
                {msg.role === 'assistant' ? (
                  <div
                    className="chatbot-markdown"
                    dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }}
                  />
                ) : (
                  <div>{msg.content}</div>
                )}

                {/* Streaming cursor */}
                {msg.isStreaming && <span className="chatbot-cursor">▌</span>}

                {/* Citations */}
                {msg.citations && msg.citations.length > 0 && (
                  <div className="chatbot-citations">
                    <div className="chatbot-citations-label">📚 Sources:</div>
                    {msg.citations.map((c) => (
                      <div key={c.ref} className="chatbot-citation-item">
                        [{c.ref}] {c.document_name}
                        {c.page_number ? ` (p.${c.page_number})` : ''}
                      </div>
                    ))}
                  </div>
                )}

                {/* Assistant message actions */}
                {msg.role === 'assistant' && !msg.isStreaming && msg.content && (
                  <div className="chatbot-msg-actions">
                    <button
                      className="chatbot-action-btn"
                      onClick={() => submitFeedback(msg.id, 1)}
                      title="Good response"
                      aria-label="Thumbs up"
                    >
                      👍
                    </button>
                    <button
                      className="chatbot-action-btn"
                      onClick={() => submitFeedback(msg.id, -1)}
                      title="Bad response"
                      aria-label="Thumbs down"
                    >
                      👎
                    </button>
                    {typeof window !== 'undefined' && window.speechSynthesis && (
                      <button
                        className="chatbot-action-btn"
                        onClick={() => toggleSpeak(msg.id, msg.content)}
                        title={speakingMsgId === msg.id ? 'Stop speaking' : 'Read aloud'}
                        aria-label={speakingMsgId === msg.id ? 'Stop speaking' : 'Read aloud'}
                      >
                        {speakingMsgId === msg.id ? '🔇' : '🔊'}
                      </button>
                    )}
                    <button
                      className="chatbot-action-btn"
                      onClick={() => navigator.clipboard.writeText(msg.content)}
                      title="Copy message"
                      aria-label="Copy message"
                    >
                      📋
                    </button>
                  </div>
                )}
              </div>
            ))}

            {/* Loading indicator (before streaming starts) */}
            {isLoading && !messages.some((m) => m.isStreaming) && (
              <div className="typing-indicator">
                <div className="typing-dot" />
                <div className="typing-dot" />
                <div className="typing-dot" />
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Attachments preview */}
          {attachments.length > 0 && (
            <div className="chatbot-attachments-bar">
              {attachments.map((f, i) => (
                <div key={i} className="chatbot-attachment-preview">
                  {f.type.startsWith('image/') ? (
                    <img src={URL.createObjectURL(f)} alt={f.name} className="chatbot-attachment-thumb-sm" />
                  ) : (
                    <span className="chatbot-attachment-name">📄 {f.name.slice(0, 15)}</span>
                  )}
                  <button className="chatbot-attachment-remove" onClick={() => removeAttachment(i)} aria-label={`Remove ${f.name}`}>
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Input area */}
          <div className="chatbot-input-container">
            {/* File upload */}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*,.pdf,.txt,.docx"
              multiple
              style={{ display: 'none' }}
              onChange={handleFileSelect}
            />
            <button
              className="chatbot-icon-btn chatbot-input-action"
              onClick={() => fileInputRef.current?.click()}
              title="Attach file"
              aria-label="Attach file"
              disabled={isLoading}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
              </svg>
            </button>

            {/* Voice input */}
            {speechSupported && (
              <button
                className={`chatbot-icon-btn chatbot-input-action ${isListening ? 'recording' : ''}`}
                onClick={isListening ? stopListening : startListening}
                title={isListening ? 'Stop recording' : 'Voice input'}
                aria-label={isListening ? 'Stop recording' : 'Voice input'}
                disabled={isLoading}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                  <line x1="12" y1="19" x2="12" y2="23" />
                  <line x1="8" y1="23" x2="16" y2="23" />
                </svg>
              </button>
            )}

            {/* Text input */}
            <textarea
              ref={textareaRef}
              className="chatbot-textarea"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isListening ? 'Listening...' : 'Ask me anything...'}
              disabled={isLoading}
              rows={1}
              aria-label="Chat message input"
            />

            {/* Send / Stop button */}
            {isLoading ? (
              <button className="chatbot-send-btn stop" onClick={stopGeneration} aria-label="Stop generation" title="Stop">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                  <rect x="6" y="6" width="12" height="12" rx="2" />
                </svg>
              </button>
            ) : (
              <button
                className="chatbot-send-btn"
                onClick={() => sendMessage()}
                disabled={!input.trim() && attachments.length === 0}
                aria-label="Send message"
                title="Send"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              </button>
            )}
          </div>
        </div>
      )}
    </>
  );
}
