import { useEffect, useState } from "react";
import { api, multiUser, setToken } from "./api.js";
import { Icon, Logo } from "./icons.jsx";
import ThemeToggle from "./ThemeToggle.jsx";

export default function Login({ onDone }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [signup, setSignup] = useState(false); // multi-user mode: create an account, or sign in
  const [info, setInfo] = useState("");
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
    setInfo("");
    setBusy(true);
    try {
      if (multiUser) {
        const mail = email.trim();
        if (signup && password.length < 8) throw new Error("Use a password of at least 8 characters.");
        if (signup) {
          const { needsConfirm } = await api.signUp(mail, password);
          if (needsConfirm) {
            setInfo("Account created. Check your email to confirm it, then sign in.");
            setSignup(false);
            return;
          }
        } else await api.signIn(mail, password);
      } else {
        const { token } = await api.login(password);
        setToken(token);
      }
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
          {multiUser && (
            <>
              <label htmlFor="em" className="field-label">
                Email
              </label>
              <input id="em" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus />
            </>
          )}
          <label htmlFor="pw" className="field-label">
            Password
          </label>
          <input
            id="pw"
            type="password"
            autoComplete={signup ? "new-password" : "current-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoFocus={!multiUser}
          />
          {info && (
            <p className="small" role="status" style={{ margin: 0 }}>
              {info}
            </p>
          )}
          {error && (
            <p className="err small" role="alert" style={{ margin: 0 }}>
              {error}
            </p>
          )}
          <button className="btn" disabled={busy || !password || (multiUser && !email.trim())}>
            {busy ? (signup ? "Creating…" : "Signing in…") : signup ? "Create account" : "Sign in"}
          </button>
        </form>
        {multiUser && (
          <button
            type="button"
            className="login-switch"
            onClick={() => {
              setSignup(!signup);
              setError("");
              setInfo("");
            }}
          >
            {signup ? "I have an account. Sign in" : "New here? Create an account"}
          </button>
        )}
        <p className="note">
          <Icon name="lock" size={13} /> {multiUser ? "Your papers are private to your account." : "Your papers stay on your server."}
        </p>
        {awake === null && <p className="note">Checking the server. A free server needs up to one minute to wake up.</p>}
        {awake === false && <p className="note">The server does not answer yet. Wait one minute, then try again.</p>}
      </div>
    </div>
  );
}
