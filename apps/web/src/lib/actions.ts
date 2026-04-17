/**
 * Copilot Tool/Action Dispatcher
 *
 * When the AI assistant returns a JSON action block, this module:
 *  1. Parses the action schema
 *  2. Executes the action (navigation, data fetch, UI state change)
 *  3. Returns a TOOL_RESULT back so the AI can continue
 *
 * Action JSON Schema (from assistant response):
 * {
 *   "actions": [
 *     { "action": "navigate_module", "params": { "module_key": "overview" } },
 *     { "action": "fetch_widget_data", "params": { "widget_id": "kpis" } }
 *   ]
 * }
 */
import { apiFetch } from './api';
import { useAppStore, ModuleKey, MODULES, ToolResult } from './store';

/* ─── Action Schema Types ─── */
export interface CopilotAction {
  action: string;
  params: Record<string, any>;
}

export interface CopilotActionBlock {
  actions: CopilotAction[];
}

/* ─── Parse action blocks from assistant message ─── */
export function extractActions(content: string): CopilotActionBlock | null {
  // Look for ```json ... ``` blocks or raw JSON with "actions" key
  const jsonBlockRe = /```json\s*(\{[\s\S]*?"actions"[\s\S]*?\})\s*```/;
  const match = content.match(jsonBlockRe);
  if (match) {
    try {
      return JSON.parse(match[1]) as CopilotActionBlock;
    } catch { return null; }
  }
  // Try raw JSON starting with {"actions":
  const rawRe = /(\{"actions"\s*:\s*\[[\s\S]*?\]\s*\})/;
  const rawMatch = content.match(rawRe);
  if (rawMatch) {
    try {
      return JSON.parse(rawMatch[1]) as CopilotActionBlock;
    } catch { return null; }
  }
  return null;
}

/* ─── Strip action JSON from visible message ─── */
export function stripActionBlock(content: string): string {
  return content
    .replace(/```json\s*\{[\s\S]*?"actions"[\s\S]*?\}\s*```/g, '')
    .replace(/\{"actions"\s*:\s*\[[\s\S]*?\]\s*\}/g, '')
    .trim();
}

/* ─── Execute a single action ─── */
export async function executeAction(action: CopilotAction): Promise<ToolResult> {
  const store = useAppStore.getState();
  const { action: name, params } = action;

  try {
    switch (name) {
      case 'open_copilot':
        store.setCopilotOpen(true);
        return { action: name, success: true };

      case 'close_copilot':
        store.setCopilotOpen(false);
        return { action: name, success: true };

      case 'set_copilot_width':
        store.setCopilotWidth(params.width_px || 420);
        return { action: name, success: true };

      case 'set_project': {
        store.setProject(params.project_id);
        return { action: name, success: true, data: { project_id: params.project_id } };
      }

      case 'set_date_range': {
        store.setDateRange(params.from || '', params.to || '');
        return { action: name, success: true, data: { from: params.from, to: params.to } };
      }

      case 'navigate_module': {
        const key = params.module_key as ModuleKey;
        if (!MODULES.find((m) => m.key === key)) {
          return { action: name, success: false, error: `Unknown module: ${key}` };
        }
        store.setModule(key);
        return { action: name, success: true, data: { module_key: key } };
      }

      case 'select_widget': {
        store.setSelectedWidget(params.widget_id);
        return { action: name, success: true, data: { widget_id: params.widget_id } };
      }

      case 'fetch_widget_data': {
        const projectId = params.project_id || store.projectId;
        if (!projectId) return { action: name, success: false, error: 'No project selected' };
        const widgetId = params.widget_id;
        let qs = '';
        if (params.from) qs += `from=${params.from}&`;
        if (params.to) qs += `to=${params.to}&`;
        const result = await apiFetch<any>(
          `/projects/${projectId}/widgets/${widgetId}/data${qs ? '?' + qs : ''}`,
        );
        store.setToolResult({ action: name, success: true, data: result });
        return { action: name, success: true, data: result };
      }

      case 'explain_widget': {
        // First fetch the data, then the AI will explain it
        const pid = params.project_id || store.projectId;
        if (!pid) return { action: name, success: false, error: 'No project selected' };
        const wid = params.widget_id;
        const res = await apiFetch<any>(`/projects/${pid}/widgets/${wid}/data`);
        return {
          action: name,
          success: true,
          data: {
            widget_id: wid,
            summary: res.summary,
            data: res.data,
            instruction: 'Please explain this data to the user with insights, risks, and recommended actions.',
          },
        };
      }

      default:
        return { action: name, success: false, error: `Unknown action: ${name}` };
    }
  } catch (err: any) {
    return { action: name, success: false, error: err.message || 'Action failed' };
  }
}

/* ─── Execute all actions in a block and return combined results ─── */
export async function executeActionBlock(block: CopilotActionBlock): Promise<ToolResult[]> {
  const results: ToolResult[] = [];
  for (const action of block.actions) {
    const result = await executeAction(action);
    results.push(result);
  }
  return results;
}

/* ─── Format tool results for sending back to AI as context ─── */
export function formatToolResults(results: ToolResult[]): string {
  return results
    .map((r) => {
      if (r.success) {
        return `TOOL_RESULT [${r.action}]: SUCCESS\n${r.data ? JSON.stringify(r.data, null, 2) : ''}`;
      }
      return `TOOL_RESULT [${r.action}]: ERROR — ${r.error}`;
    })
    .join('\n\n');
}
