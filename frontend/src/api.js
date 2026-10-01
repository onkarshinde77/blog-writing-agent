export const base = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

async function request(path, options = {}) {
  const response = await fetch(`${base}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch { /* Keep the status message when the server returns no JSON. */ }
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}

export const api = {
  health: () => request("/api/health"),
  auth: () => request("/api/auth/status"),
  login: (password) => request("/api/auth/login", { method: "POST", body: JSON.stringify({ password }) }),
  logout: () => request("/api/auth/logout", { method: "POST" }),
  blogs: () => request("/api/blogs"),
  blog: (id) => request(`/api/blogs/${encodeURIComponent(id)}`),
  deleteBlog: (id) => request(`/api/blogs/${encodeURIComponent(id)}`, { method: "DELETE" }),
  workflows: () => request("/api/workflows"),
  workflow: (id) => request(`/api/workflows/${encodeURIComponent(id)}`),
  createWorkflow: (brief) => request("/api/workflows", { method: "POST", body: JSON.stringify(brief) }),
  action: (id, action) => request(`/api/workflows/${encodeURIComponent(id)}/actions`, { method: "POST", body: JSON.stringify(action) }),
  publishing: () => request("/api/publishing"),
  connect: (platform) => request(`/api/publishing/${platform}/connect`, { method: "POST" }),
};
