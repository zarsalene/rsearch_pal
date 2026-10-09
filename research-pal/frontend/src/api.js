const BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");
const KEY = "research-pal-token";

export const getToken = () => localStorage.getItem(KEY) || "";
export const setToken = (t) => (t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY));

async function request(path, { method = "GET", json, form, raw } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = "Bearer " + token;
  let body;
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (form) body = form;
  let res;
  try {
    res = await fetch(BASE + path, { method, headers, body });
  } catch {
    throw new Error("Cannot reach the server. On a free plan, the server may be waking up. Wait 30 seconds and try again.");
  }
  if (res.status === 401 && path !== "/api/login") {
    setToken("");
    window.dispatchEvent(new Event("rp-logout"));
    throw new Error("Your session ended. Sign in again.");
  }
  if (!res.ok) {
    let msg = `Error ${res.status}`;
    try {
      const d = await res.json();
      if (typeof d.detail === "string") msg = d.detail;
    } catch {}
    throw new Error(msg);
  }
  return raw ? res : res.json();
}

export const api = {
  health: () => fetch(BASE + "/api/health").then((r) => r.ok).catch(() => false),
  login: (password) => request("/api/login", { method: "POST", json: { password } }),
  config: () => request("/api/config"),
  saveSettings: (thesis_question) => request("/api/settings", { method: "PUT", json: { thesis_question } }),
  papers: () => request("/api/papers"),
  paper: (id) => request(`/api/papers/${id}`),
  upload: (file, purpose, focus) => {
    const form = new FormData();
    form.append("file", file);
    form.append("purpose", purpose || "");
    form.append("focus", focus || "");
    return request("/api/papers", { method: "POST", form });
  },
  // A field you leave out (undefined) keeps its saved value. An empty string clears it.
  // fresh: true asks the AI again. Without it, the same request gets its saved answer.
  regenerate: (id, { purpose, focus, fresh } = {}) => request(`/api/papers/${id}/regenerate`, { method: "POST", json: { purpose, focus, fresh: !!fresh } }),
  clearCache: () => request("/api/cache", { method: "DELETE" }),
  // Simple mode: the simple version of a text of the card (the server reads the text itself) or of any text of the AI.
  simplifyField: (id, field, cardId = "") => request(`/api/papers/${id}/simplify`, { method: "POST", json: { field, card_id: cardId || "" } }),
  simplifyText: (text) => request("/api/simplify", { method: "POST", json: { text } }),
  // Word helper and glossary. The server makes the explanation. The page sends only the word and the paper.
  define: (id, term) => request(`/api/papers/${id}/define`, { method: "POST", json: { term } }),
  glossary: () => request("/api/glossary"),
  addGlossary: (term, paper_id) => request("/api/glossary", { method: "POST", json: { term, paper_id } }),
  deleteGlossary: (id) => request(`/api/glossary/${id}`, { method: "DELETE" }),
  aiLog: (limit = 1) => request(`/api/ai-log?limit=${limit}`),
  // Understand: Feynman check, like I am 12, quiz. The server marks each claim and checks each quote.
  explain: (id, text, cardId = "") => request(`/api/papers/${id}/explain`, { method: "POST", json: { text, card_id: cardId || "" } }),
  explanations: (id, cardId = "") => request(`/api/papers/${id}/explanations?card_id=${encodeURIComponent(cardId || "")}`),
  deleteExplanation: (eid) => request(`/api/explanations/${eid}`, { method: "DELETE" }),
  eli12: (id, field, cardId = "") => request(`/api/papers/${id}/eli12`, { method: "POST", json: { field, card_id: cardId || "" } }),
  makeQuiz: (id, cardId = "") => request(`/api/papers/${id}/quiz`, { method: "POST", json: { card_id: cardId || "" } }),
  quizList: (id) => request(`/api/papers/${id}/quiz`),
  answerQuiz: (rid, answer) => request(`/api/quiz/${rid}/answer`, { method: "POST", json: { answer } }),
  // Feature switches. setFeatures({ chat: false }) switches one feature off. The answer is the full list.
  features: () => request("/api/features"),
  setFeatures: (features) => request("/api/features", { method: "PUT", json: { features } }),
  patchCard: (id, fields, verdict) => request(`/api/papers/${id}/card`, { method: "PATCH", json: { fields, verdict } }),
  remove: (id) => request(`/api/papers/${id}`, { method: "DELETE" }),
  makeMindmap: (id) => request(`/api/papers/${id}/mindmap`, { method: "POST" }),
  deleteMindmap: (id) => request(`/api/papers/${id}/mindmap`, { method: "DELETE" }),
  explainLink: (a, b, refresh = false) => request("/api/links/explain", { method: "POST", json: { a, b, refresh } }),
  chat: (question, paper_ids, history) => request("/api/chat", { method: "POST", json: { question, paper_ids, history } }),
  addNote: (id, note) => request(`/api/papers/${id}/notes`, { method: "POST", json: note }),
  deleteNote: (id, noteId) => request(`/api/papers/${id}/notes/${noteId}`, { method: "DELETE" }),
  search: (q) => request(`/api/search?q=${encodeURIComponent(q)}&limit=10`),
  graph: () => request("/api/graph"),
  exportAll: () => request("/api/export"),
  importAll: (data) => request("/api/import", { method: "POST", json: data }),
  // Open the PDF at one page. The window opens first, so the browser does not block it.
  async openPdf(id, page) {
    const w = window.open("", "_blank");
    try {
      const res = await request(`/api/papers/${id}/pdf`, { raw: true });
      const url = URL.createObjectURL(await res.blob());
      if (w) w.location.href = url + (page ? `#page=${page}` : "");
      else window.location.href = url;
    } catch (e) {
      if (w) w.close();
      throw e;
    }
  },
  // Choose the AI: { primary, fallbacks: [], models: { provider: "model name" } }. The keys stay on the server.
  setAi: (choice) => request("/api/ai", { method: "PUT", json: choice }),
  resetAi: () => request("/api/ai", { method: "DELETE" }),
  addCard: (id, { focus, purpose }) => request(`/api/papers/${id}/cards`, { method: "POST", json: { focus: focus || "", purpose: purpose || "" } }),
  // The thesis. saveProject({ title, question, stage }): a field that you leave out keeps its saved value.
  project: () => request("/api/project"),
  saveProject: (changes) => request("/api/project", { method: "PUT", json: changes }),
  projectHistory: () => request("/api/project/history"),
  // The AI helpers only suggest. They save nothing.
  questionCheck: (question) => request("/api/project/question-check", { method: "POST", json: { question } }),
  splitQuestion: (question) => request("/api/project/split", { method: "POST", json: { question } }),
  coverage: () => request("/api/project/coverage"),
  subQuestions: () => request("/api/sub-questions"),
  addSubQuestion: (text) => request("/api/sub-questions", { method: "POST", json: { text } }),
  editSubQuestion: (id, change) => request(`/api/sub-questions/${id}`, { method: "PUT", json: change }),
  deleteSubQuestion: (id) => request(`/api/sub-questions/${id}`, { method: "DELETE" }),
  // Link one card of a paper to sub-questions. cardId "" is the first card. The new list replaces the old list.
  setTags: (paperId, cardId, ids) => request(`/api/papers/${paperId}/tags`, { method: "PUT", json: { card_id: cardId || "", sub_question_ids: ids } }),
};

// The calls of one card. cid "" is the first card of the paper. Another cid is one more card of the same paper.
export function cardApi(id, cid) {
  if (!cid) {
    return {
      load: () => api.paper(id),
      patch: (fields) => api.patchCard(id, fields),
      regenerate: (change) => api.regenerate(id, change),
      makeMindmap: () => api.makeMindmap(id),
      deleteMindmap: () => api.deleteMindmap(id),
      fill: (fields) => request(`/api/papers/${id}/fill`, { method: "POST", json: { fields: fields?.length ? fields : null } }),
    };
  }
  const base = `/api/papers/${id}/cards/${cid}`;
  return {
    load: () => request(base),
    patch: (fields) => request(base, { method: "PATCH", json: { fields } }),
    regenerate: ({ purpose, focus, fresh } = {}) => request(base + "/regenerate", { method: "POST", json: { purpose, focus, fresh: !!fresh } }),
    makeMindmap: () => request(base + "/mindmap", { method: "POST" }),
    deleteMindmap: () => request(base + "/mindmap", { method: "DELETE" }),
    fill: (fields) => request(base + "/fill", { method: "POST", json: { fields: fields?.length ? fields : null } }),
    remove: () => request(base, { method: "DELETE" }),
  };
}
