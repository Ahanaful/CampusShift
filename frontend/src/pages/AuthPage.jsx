import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { api } from "../services/api";
import { ErrorMessage, Field, useResource } from "../components/ui";

export default function AuthPage({ register = false }) {
  const { login, notice } = useAuth();
  const navigate = useNavigate();
  const departments = useResource(register ? "/departments" : null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState(false);
  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const values = Object.fromEntries(new FormData(event.currentTarget));
    try {
      if (register && !created) {
        await api("/auth/register", {
          method: "POST",
          body: { ...values, department_id: Number(values.department_id) },
        });
        setCreated(true);
      }
      const user = await login({
        email: values.email,
        password: values.password,
      });
      navigate(user.role === "student" ? "/student" : "/supervisor", {
        replace: true,
      });
    } catch (error) {
      setError(
        error.name === "AbortError"
          ? "Request timed out. Try signing in if you already registered."
          : error.message,
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="auth-shell">
      <Link className="brand" to="/">
        CampusShift<span className="brand-period">.</span>
      </Link>
      <div className="auth-card panel">
        <div className="eyebrow">WORK FITS CAMPUS LIFE</div>
        <h1>{register ? "Find your balance." : "Welcome back."}</h1>
        <p className="muted">
          {register
            ? "Create your student workspace. Supervisors receive an account from their department administrator."
            : "Sign in to your student or supervisor workspace."}
        </p>
        {notice && (
          <p className="message" role="status">
            {notice}
          </p>
        )}
        <ErrorMessage>{error}</ErrorMessage>
        {created && (
          <p className="message">
            Your account was created. Sign in to continue.
          </p>
        )}
        <form onSubmit={submit} className="stack-form">
          <fieldset disabled={busy}>
            {register && !created && (
              <>
                <Field
                  label="Full name"
                  name="full_name"
                  autoComplete="name"
                  maxLength={120}
                  required
                />
                <Field label="Department">
                  <select
                    name="department_id"
                    required
                    defaultValue=""
                    disabled={departments.loading || !!departments.error}
                  >
                    <option value="">Choose your department</option>
                    {departments.data?.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                </Field>
                {departments.loading && (
                  <p role="status">Loading departments…</p>
                )}
                {departments.error && (
                  <>
                    <ErrorMessage>{departments.error}</ErrorMessage>
                    <button
                      type="button"
                      className="text-button"
                      onClick={departments.reload}
                    >
                      Retry departments
                    </button>
                  </>
                )}
                {departments.data?.length === 0 && (
                  <p className="message">
                    No departments are available yet. Ask your supervisor to set
                    up your department.
                  </p>
                )}
              </>
            )}
            <Field
              label="Email"
              name="email"
              type="email"
              autoComplete="username"
              maxLength={254}
              required
            />
            <Field
              label="Password"
              name="password"
              type="password"
              autoComplete={
                register && !created ? "new-password" : "current-password"
              }
              minLength={register && !created ? 12 : 1}
              maxLength={128}
              required
            />
            {register && !created && (
              <p className="muted">Use 12–128 characters.</p>
            )}
            <button
              className="action-button"
              disabled={register && !created && !departments.data?.length}
            >
              {busy
                ? "Please wait…"
                : register && !created
                  ? "Create student account"
                  : "Sign in"}
            </button>
          </fieldset>
        </form>
        <p className="auth-switch">
          {register ? "Already have an account?" : "New to CampusShift?"}{" "}
          <Link to={register ? "/login" : "/register"}>
            {register ? "Sign in" : "Create an account"}
          </Link>
        </p>
        <p className="session-note">
          Sessions are short-lived. Refreshing the page signs you out.
        </p>
      </div>
    </main>
  );
}
