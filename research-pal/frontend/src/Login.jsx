import { useEffect, useState } from "react";
import { api, setToken } from "./api.js";
import { Icon, Logo } from "./icons.jsx";
import ThemeToggle from "./ThemeToggle.jsx";

export default function Login({ onDone }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [awake, setAwake] = useState(null);

  useEffect(() => {
    let alive = true;
    api.health().then((ok) => alive && setAwake(ok));
    return () => {
      alive = false;
    };
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const { token } = await api.login(password);
      setToken(token);
      onDone();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login">
      <div className="login-theme">
        <ThemeToggle />
      </div>
      <div className="login-card">
        <Logo size={72} />
        <h1>Research Pal</h1>
        <p className="tag">Read less. Know where every claim comes from.</p>
        <form onSubmit={submit} className="panel">
          <label htmlFor="pw" className="field-label">
            Password
          </label>
          <input id="pw" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} autoFocus />
          {error && (
            <p className="err small" role="alert" style={{ margin: 0 }}>
              {error}
            </p>
          )}
          <button className="btn" disabled={busy || !password}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p className="note">
          <Icon name="lock" size={13} /> Your papers stay on your server.
        </p>
        {awake === null && <p className="note">Checking the server. A free server needs up to one minute to wake up.</p>}
        {awake === false && <p className="note">The server does not answer yet. Wait one minute, then try again.</p>}
      </div>
    </div>
  );
}
