/**
 * BuildAll App Store — Zustand
 *
 * Single store for:
 *  - Current project context (projectId, dateRange)
 *  - Horizontal module navigation (currentModule index)
 *  - Copilot side-panel state (open/close, width, focus mode)
 *  - Chat sessions + messages
 *  - Tool action dispatcher results
 */
import { create } from 'zustand';

/* ─── Module Definitions ─── */
export const MODULES = [
  { key: 'overview', label: 'Genel Bakış', icon: '📊' },
  { key: 'rfis', label: 'RFI / Talepler', icon: '📋' },
  { key: 'risks', label: 'Riskler', icon: '⚠️' },
  { key: 'reports', label: 'Raporlar', icon: '📝' },
  { key: 'docs', label: 'Dokümanlar', icon: '📄' },
  { key: 'chat', label: 'Ekip Sohbet', icon: '💬' },
] as const;

export type ModuleKey = (typeof MODULES)[number]['key'];

/* ─── Types ─── */
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  citations?: any[];
  created_at: string;
  isStreaming?: boolean;
}

export interface ChatSessionMeta {
  id: string;
  title: string | null;
  project_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface ToolAction {
  action: string;
  params: Record<string, any>;
}

export interface ToolResult {
  action: string;
  success: boolean;
  data?: any;
  error?: string;
}

/* ─── Store State ─── */
interface AppState {
  // Project context
  projectId: number | null;
  dateFrom: string;
  dateTo: string;
  setProject: (id: number | null) => void;
  setDateRange: (from: string, to: string) => void;

  // Horizontal nav
  currentModule: ModuleKey;
  setModule: (key: ModuleKey) => void;

  // Copilot panel
  copilotOpen: boolean;
  copilotWidth: number;
  copilotFocusMode: boolean;
  toggleCopilot: () => void;
  setCopilotOpen: (open: boolean) => void;
  setCopilotWidth: (px: number) => void;
  setCopilotFocusMode: (on: boolean) => void;

  // Chat sessions
  sessions: ChatSessionMeta[];
  activeSessionId: string | null;
  messages: ChatMessage[];
  setSessions: (s: ChatSessionMeta[]) => void;
  setActiveSession: (id: string | null) => void;
  setMessages: (m: ChatMessage[]) => void;
  addMessage: (m: ChatMessage) => void;
  updateLastAssistant: (content: string) => void;

  // Tool results (ephemeral)
  lastToolResult: ToolResult | null;
  setToolResult: (r: ToolResult | null) => void;

  // Selected widget (for copilot "explain this chart")
  selectedWidgetId: string | null;
  setSelectedWidget: (id: string | null) => void;
}

const COPILOT_WIDTH_KEY = 'buildall_copilot_width';
const getStoredWidth = (): number => {
  if (typeof window === 'undefined') return 420;
  const stored = localStorage.getItem(COPILOT_WIDTH_KEY);
  return stored ? Math.max(320, Math.min(700, parseInt(stored, 10))) : 420;
};

export const useAppStore = create<AppState>((set) => ({
  // Project context
  projectId: null,
  dateFrom: '',
  dateTo: '',
  setProject: (id) => set({ projectId: id }),
  setDateRange: (from, to) => set({ dateFrom: from, dateTo: to }),

  // Horizontal nav
  currentModule: 'overview',
  setModule: (key) => set({ currentModule: key }),

  // Copilot panel
  copilotOpen: false,
  copilotWidth: getStoredWidth(),
  copilotFocusMode: false,
  toggleCopilot: () => set((s) => ({ copilotOpen: !s.copilotOpen })),
  setCopilotOpen: (open) => set({ copilotOpen: open }),
  setCopilotWidth: (px) => {
    const clamped = Math.max(320, Math.min(700, px));
    if (typeof window !== 'undefined') localStorage.setItem(COPILOT_WIDTH_KEY, String(clamped));
    set({ copilotWidth: clamped });
  },
  setCopilotFocusMode: (on) => set({ copilotFocusMode: on }),

  // Chat sessions
  sessions: [],
  activeSessionId: null,
  messages: [],
  setSessions: (sessions) => set({ sessions }),
  setActiveSession: (id) => set({ activeSessionId: id }),
  setMessages: (messages) => set({ messages }),
  addMessage: (m) => set((s) => ({ messages: [...s.messages, m] })),
  updateLastAssistant: (content) =>
    set((s) => {
      const msgs = [...s.messages];
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].role === 'assistant') {
          msgs[i] = { ...msgs[i], content, isStreaming: true };
          break;
        }
      }
      return { messages: msgs };
    }),

  // Tool results
  lastToolResult: null,
  setToolResult: (r) => set({ lastToolResult: r }),

  // Selected widget
  selectedWidgetId: null,
  setSelectedWidget: (id) => set({ selectedWidgetId: id }),
}));
