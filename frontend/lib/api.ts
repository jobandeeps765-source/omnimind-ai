const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("omnimind_token");
}

export function setToken(token: string) {
  localStorage.setItem("omnimind_token", token);
}

export function clearToken() {
  localStorage.removeItem("omnimind_token");
}

async function request(path: string, options: RequestInit = {}) {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export const api = {
  signup: (email: string, password: string, name: string) =>
    request("/auth/signup", { method: "POST", body: JSON.stringify({ email, password, name }) }),

  login: (email: string, password: string) =>
    request("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),

  me: () => request("/auth/me"),

  listChats: () => request("/chat/list"),

  history: (chatId: string) => request(`/chat/history/${chatId}`),

  send: (message: string, chatId?: string, activeFilePath?: string) =>
    request("/chat/send", {
      method: "POST",
      body: JSON.stringify({ message, chat_id: chatId, active_file_path: activeFilePath }),
    }),

  listFiles: () => request("/files"),

  deleteFile: (id: string) => request(`/files/${id}`, { method: "DELETE" }),

  listMemory: () => request("/memory"),

  addMemory: (text: string) => request("/memory", { method: "POST", body: JSON.stringify({ text }) }),

  deleteMemory: (id: string) => request(`/memory/${id}`, { method: "DELETE" }),
};

export async function uploadFile(file: File) {
  const token = getToken();
  const formData = new FormData();
  formData.append("upload", file);

  const res = await fetch(`${API_URL}/files/upload`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });
  if (!res.ok) throw new Error("Upload failed");
  return res.json();
}

/**
 * Streams a chat response via SSE. Calls onEvent for each parsed event
 * ({type: 'routing'|'delta'|'done', data}) so the UI can show the agent
 * badge immediately and render tokens as they arrive.
 */
export async function streamChat(
  message: string,
  chatId: string | undefined,
  activeFilePath: string | undefined,
  onEvent: (type: string, data: any) => void
) {
  const token = getToken();
  const res = await fetch(`${API_URL}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message, chat_id: chatId, active_file_path: activeFilePath }),
  });

  if (!res.ok || !res.body) throw new Error("Stream failed to start");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const events = buffer.split("\n\n");
    buffer = events.pop() || "";

    for (const raw of events) {
      const lines = raw.split("\n");
      const eventLine = lines.find((l) => l.startsWith("event: "));
      const dataLine = lines.find((l) => l.startsWith("data: "));
      if (!eventLine || !dataLine) continue;

      const type = eventLine.replace("event: ", "");
      const data = JSON.parse(dataLine.replace("data: ", ""));
      onEvent(type, data);
    }
  }
}
