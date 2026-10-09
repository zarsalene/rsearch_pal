const BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");
const KEY = "research-pal-token";
const SESSION = "research-pal-session";

// Multi-user mode: sign in with email (Supabase). Without these two values the page asks for the one password.
const SUPA = (import.meta.env.VITE_SUPABASE_URL || "").replace(/\/$/, "");
const SUPA_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || "";
export const multiUser = !!(SUPA && SUPA_KEY);

const readSession = () => {
  try {
    return JSON.parse(localStorage.getItem(SESSION) || "null");
  } catch {
    return null;
  }
};

export const getToken = () => (multiUser ? readSession()?.access_token || "" : localStorage.getItem(KEY) || "");
export const setToken = (t) => {
  if (t) return localStorage.setItem(KEY, t);
  localStorage.removeItem(KEY);
  localStorage.removeItem(SESSION);
};

const saveSession = (d) =>
  localStorage.setItem(
    SESSION,
    JSON.stringify({ access_token: d.access_token, refresh_token: d.refresh_token, expires_at: Math.floor(Date.now() / 1000) + (d.expires_in || 3600) }),
  );

const NICE = {
  "Invalid login credentials": "Wrong email or password.",
  "User already registered": "This email has an account already. Sign in instead.",
  "Email not confirmed": "Confirm your email first. Check your inbox.",
};

async function supa(path, body) {
  let res;
  try {
    res = await fetch(SUPA + path, { method: "POST", headers: { apikey: SUPA_KEY, "Content-Type": "application/json" }, body: JSON.stringify(body) });
  } catch {
    throw new Error("Cannot reach the login service. Check your connection and try again.");
  }
  const d = await res.json().catch(() => ({}));
  if (!res.ok) {
    const m = d.msg || d.error_description || d.message || d.error || `Error ${res.status}`;
    throw new Error(NICE[m] || m);
  }
  return d;
}

let refreshing = null;
// A Supabase token lives one hour. Renew it one minute before the end, so a long session does not break.
async function freshToken() {
  if (!multiUser) return getToken();
  const s = readSession();
  if (!s) return "";
  if (s.expires_at - Math.floor(Date.now() / 1000) > 60) return s.access_token;
  refreshing ||= supa("/auth/v1/token?grant_type=refresh_token", { refresh_token: s.refresh_token })
    .then((d) => (saveSession(d), d.access_token))
    .catch(() => (setToken(""), ""))
    .finally(() => (refreshing = null));
  return refreshing;
}

async function request(path, { method = "GET", json, form, raw } = {}) {
  const headers = {};
  const token = await freshToken();
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
  // Email accounts (multi-user mode). signUp gives needsConfirm: true when the project asks to confirm the email first.
  signIn: async (email, password) => {
    saveSession(await supa("/auth/v1/token?grant_type=password", { email, password }));
  },
  signUp: async (email, password) => {
    const d = await supa("/auth/v1/signup", { email, password });
    if (!d.access_token) return { needsConfirm: true };
    saveSession(d);
    return { needsConfirm: false };
  },
  signOut: () => {
    const t = getToken();
    setToken("");
    if (multiUser && t) fetch(SUPA + "/auth/v1/logout", { method: "POST", headers: { apikey: SUPA_KEY, Authorization: "Bearer " + t } }).catch(() => {});
  },
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
  // Today: goals, wins, focus timer. The date is the date of the student (YYYY-MM-DD).
  today: (date) => request(`/api/today?date=${date}`),
  addGoal: (goal) => request("/api/goals", { method: "POST", json: goal }),
  updateGoal: (id, change) => request(`/api/goals/${id}`, { method: "PUT", json: change }),
  deleteGoal: (id) => request(`/api/goals/${id}`, { method: "DELETE" }),
  addWin: (win) => request("/api/wins", { method: "POST", json: win }),
  wins: (limit, before) => request(`/api/wins?limit=${limit}${before ? "&before=" + before : ""}`),
  focusStart: (body) => request("/api/focus/start", { method: "POST", json: body }),
  focusStop: () => request("/api/focus/stop", { method: "POST" }),
  // Game: points, level, streak, badges, own rewards. The page cannot write points. It only reads them.
  game: (date, tz) => request(`/api/game?date=${date}&tz=${tz}`),
  gameSettings: (settings) => request("/api/game/settings", { method: "PUT", json: settings }),
  addReward: (reward) => request("/api/rewards", { method: "POST", json: reward }),
  claimReward: (id) => request(`/api/rewards/${id}/claim`, { method: "POST" }),
  deleteReward: (id) => request(`/api/rewards/${id}`, { method: "DELETE" }),
  // Knowledge Garden (spaced review) and the Expedition map. The server picks the day of each item (FSRS).
  reviewDue: (date, tz, paperId) => request(`/api/review/due?date=${date}&tz=${tz}${paperId ? "&paper_id=" + paperId : ""}`),
  reviewGarden: (date, tz) => request(`/api/review/garden?date=${date}&tz=${tz}`),
  rateReview: (id, rating, date) => request(`/api/review/${id}`, { method: "POST", json: { rating, date } }),
  journeyMap: () => request("/api/journey/map"),
  // Find papers: add by DOI, link or title; import BibTeX or RIS; the To read list.
  fromId: (query, addToRead = false) => request("/api/papers/from-id", { method: "POST", json: { query, add_to_read: addToRead } }),
  uploadPdfFor: (id, file) => {
    const form = new FormData();
    form.append("file", file);
    return request(`/api/papers/${id}/pdf`, { method: "POST", form });
  },
  importBib: (file, pdfs = []) => {
    const form = new FormData();
    form.append("file", file);
    for (const f of pdfs) form.append("pdfs", f);
    return request("/api/import/bib", { method: "POST", form });
  },
  toRead: () => request("/api/to-read"),
  setToRead: (id, status) => request(`/api/to-read/${id}`, { method: "PUT", json: { status } }),
  readToRead: (id) => request(`/api/to-read/${id}/read`, { method: "POST" }),
  uploadToRead: (id, file) => {
    const form = new FormData();
    form.append("file", file);
    return request(`/api/to-read/${id}/upload`, { method: "POST", form });
  },
  // Gap finder, writing coach, quality check. The server checks each quote. The AI parts have the label "AI opinion".
  runGaps: (body) => request("/api/gaps", { method: "POST", json: body }),
  getGaps: (sq = "") => request(`/api/gaps?sub_question_id=${encodeURIComponent(sq)}`),
  setGapStatus: (id, status) => request(`/api/gaps/${id}`, { method: "PUT", json: { status } }),
  useGap: (id) => request(`/api/gaps/${id}/use`, { method: "POST" }),
  coach: (text) => request("/api/coach", { method: "POST", json: { text } }),
  runCritique: (pid) => request(`/api/papers/${pid}/critique`, { method: "POST" }),
  getCritique: (pid) => request(`/api/papers/${pid}/critique`),
  editCritique: (pid, answers, confirm) => request(`/api/papers/${pid}/critique`, { method: "PUT", json: { answers, confirm } }),
  // Duck Island. The server makes the questions, keeps the answers and the coins.
  play: () => request("/api/play"),
  newRound: (game) => request("/api/play/rounds", { method: "POST", json: { game } }),
  finishRound: (id, answers) => request(`/api/play/rounds/${id}/finish`, { method: "POST", json: { answers } }),
  buyItem: (code) => request("/api/play/buy", { method: "POST", json: { code } }),
  placeItem: (code, x, y) => request(`/api/play/items/${code}`, { method: "PUT", json: { x, y } }),
  // Quests, bosses, Duck. The server checks the conditions. The page only shows them.
  quests: (date, tz) => request(`/api/quests?date=${date}&tz=${tz}`),
  chooseQuest: (code, date) => request(`/api/quests/${code}/choose?date=${date}`, { method: "POST" }),
  dropQuest: (code, date) => request(`/api/quests/${code}/drop?date=${date}`, { method: "POST" }),
  setBoss: (id, boss) => request(`/api/papers/${id}/boss`, { method: "POST", json: { boss } }),
  bosses: () => request("/api/bosses"),
  companion: (event, seed = "") => request(`/api/companion?event=${event}&seed=${encodeURIComponent(seed)}`),
  // Citations and the literature review. The server checks the metadata against the PDF. You write the text.
  extractMeta: (id) => request(`/api/papers/${id}/meta/extract`, { method: "POST" }),
  editMeta: (id, meta) => request(`/api/papers/${id}/meta`, { method: "PUT", json: meta }),
  cite: (id, page, style) => request(`/api/papers/${id}/cite?page=${page || ""}&style=${style}`),
  reviewDoc: (style) => request(`/api/review-doc?style=${style}`),
  makeOutline: () => request("/api/review-doc/outline", { method: "POST" }),
  saveSection: (id, body) => request(`/api/review-doc/sections/${id}`, { method: "PUT", json: body }),
  addSection: (heading) => request("/api/review-doc/sections", { method: "POST", json: { heading } }),
  deleteSection: (id) => request(`/api/review-doc/sections/${id}`, { method: "DELETE" }),
  orderSections: (ids) => request("/api/review-doc/order", { method: "PUT", json: { ids } }),
  // Save a file that the server makes (BibTeX, RIS, Markdown, Word)
  async download(path, filename) {
    const res = await request(path, { raw: true });
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  },
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
