import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// api.js reads the Supabase settings when it loads, so each test loads a fresh copy after it sets them.
async function load(env = { VITE_SUPABASE_URL: "https://x.supabase.co", VITE_SUPABASE_ANON_KEY: "anon" }) {
  vi.resetModules();
  for (const [k, v] of Object.entries(env)) vi.stubEnv(k, v);
  return import("./api.js");
}

const json = (body, status = 200) => Promise.resolve({ ok: status < 300, status, json: () => Promise.resolve(body) });

beforeEach(() => localStorage.clear());
afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

describe("email sign-in (multi-user mode)", () => {
  it("is on when both Supabase values are set, and off when they are empty", async () => {
    expect((await load()).multiUser).toBe(true);
    expect((await load({ VITE_SUPABASE_URL: "", VITE_SUPABASE_ANON_KEY: "" })).multiUser).toBe(false);
  });

  it("signIn saves the session and the API gets the token", async () => {
    const { api, getToken } = await load();
    const f = vi.fn().mockImplementation((url) => (url.includes("/auth/v1/token") ? json({ access_token: "T1", refresh_token: "R1", expires_in: 3600 }) : json([])));
    vi.stubGlobal("fetch", f);
    await api.signIn("a@b.com", "password1");
    expect(getToken()).toBe("T1");
    await api.papers();
    const call = f.mock.calls.find((c) => c[0].endsWith("/api/papers"));
    expect(call[1].headers.Authorization).toBe("Bearer T1");
  });

  it("renews a token that is about to end", async () => {
    const { api } = await load();
    localStorage.setItem("research-pal-session", JSON.stringify({ access_token: "OLD", refresh_token: "R1", expires_at: Math.floor(Date.now() / 1000) + 10 }));
    const f = vi.fn().mockImplementation((url) => (url.includes("grant_type=refresh_token") ? json({ access_token: "NEW", refresh_token: "R2", expires_in: 3600 }) : json([])));
    vi.stubGlobal("fetch", f);
    await api.papers();
    expect(f.mock.calls.find((c) => c[0].endsWith("/api/papers"))[1].headers.Authorization).toBe("Bearer NEW");
  });

  it("shows a clear message for a wrong password", async () => {
    const { api } = await load();
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(json({ msg: "Invalid login credentials" }, 400)));
    await expect(api.signIn("a@b.com", "bad")).rejects.toThrow("Wrong email or password.");
  });

  it("signUp says when the email must be confirmed", async () => {
    const { api } = await load();
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(json({ id: "u1", email: "a@b.com" })));
    expect(await api.signUp("a@b.com", "password1")).toEqual({ needsConfirm: true });
  });

  it("signOut removes the session", async () => {
    const { api, getToken } = await load();
    localStorage.setItem("research-pal-session", JSON.stringify({ access_token: "T", refresh_token: "R", expires_at: 9999999999 }));
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(json({})));
    api.signOut();
    expect(getToken()).toBe("");
  });
});
