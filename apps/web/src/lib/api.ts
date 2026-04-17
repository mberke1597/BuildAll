const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('token');
}

export function setToken(token: string) {
  if (typeof window === 'undefined') return;
  localStorage.setItem('token', token);
}

export function clearToken() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem('token');
}

export async function apiFetch<T>(path: string, options: RequestInit = {}) {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }
  
  console.log('🚀 [API] Request:', {
    url: `${API_URL}${path}`,
    method: options.method || 'GET',
    headers: { ...headers, Authorization: token ? 'Bearer ***' : undefined },
    body: options.body instanceof FormData ? '<FormData>' : options.body,
  });
  
  try {
    const res = await fetch(`${API_URL}${path}`, {
      ...options,
      headers,
    });
    
    console.log('🚀 [API] Response:', {
      url: path,
      status: res.status,
      statusText: res.statusText,
      headers: Object.fromEntries(res.headers.entries()),
    });
    
    if (!res.ok) {
      const text = await res.text();
      let errorDetail = text;
      try {
        const json = JSON.parse(text);
        errorDetail = json.detail || json.message || text;
      } catch {
        // text is not JSON, use as is
      }
      console.error('❌ [API] Error response:', {
        status: res.status,
        statusText: res.statusText,
        detail: errorDetail,
      });
      throw new Error(errorDetail || 'Request failed');
    }
    
    const data = await res.json();
    console.log('✅ [API] Success:', { url: path, dataKeys: Object.keys(data) });
    return data as T;
  } catch (error) {
    console.error('❌ [API] Fetch failed:', {
      url: `${API_URL}${path}`,
      error: error instanceof Error ? error.message : String(error),
      stack: error instanceof Error ? error.stack : undefined,
    });
    throw error;
  }
}
