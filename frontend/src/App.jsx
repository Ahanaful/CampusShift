import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "./services/api";

function CampusMark() {
  return (
    <svg viewBox="0 0 48 48" fill="none" aria-hidden="true">
      <path
        d="m8 18 16-9 16 9-16 9L8 18Zm6 9v12h20V27M24 30v9"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ConnectionStatus() {
  const [status, setStatus] = useState("checking");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const timeout = setTimeout(() => controller.abort(), 6000);
    setStatus("checking");
    async function checkHealth() {
      try {
        const data = await api("/health", {
          signal: controller.signal,
        });
        if (data.status !== "healthy" || data.application !== "CampusShift")
          throw new Error("Unexpected health response");
        if (active) setStatus("connected");
      } catch {
        if (active) setStatus("unavailable");
      } finally {
        clearTimeout(timeout);
      }
    }
    checkHealth();
    return () => {
      active = false;
      clearTimeout(timeout);
      controller.abort();
    };
  }, [attempt]);

  return (
    <section className="connection" aria-label="Backend connection">
      <div role="status" aria-live="polite" className="connection-copy">
        <span className={`status-dot ${status}`} />
        <div>
          <strong>
            {status === "connected"
              ? "Backend connected"
              : status === "checking"
                ? "Checking connection…"
                : "Backend unavailable"}
          </strong>
          <p>
            {status === "connected"
              ? "CampusShift API is healthy and ready."
              : status === "checking"
                ? "Reaching the CampusShift API."
                : "Start the local backend on port 8000, then try again."}
          </p>
        </div>
      </div>
      <button
        className="retry"
        onClick={() => setAttempt((value) => value + 1)}
        disabled={status === "checking"}
      >
        Check again <span aria-hidden="true">↻</span>
      </button>
    </section>
  );
}

function WorkspaceCard({ number, title, description, items }) {
  return (
    <article className="workspace-card">
      <div className="card-top">
        <span className="card-number">{number}</span>
        <span className="coming-soon">Ready for you</span>
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
      <ul>
        {items.map((item) => (
          <li key={item}>
            <span aria-hidden="true">↗</span>
            {item}
          </li>
        ))}
      </ul>
      <div className="card-foot">
        <Link to="/login">
          Open your workspace <span aria-hidden="true">→</span>
        </Link>
      </div>
    </article>
  );
}

export default function App() {
  return (
    <div className="page-shell">
      <header className="site-header">
        <a className="brand" href="#">
          <span className="brand-mark">
            <CampusMark />
          </span>
          CampusShift<span className="brand-period">.</span>
        </a>
        <div className="landing-nav">
          <Link className="nav-link" to="/login">
            Sign in ↗
          </Link>
          <Link className="secondary-button" to="/register">
            Join CampusShift
          </Link>
        </div>
      </header>
      <main>
        <section className="hero">
          <div className="hero-copy">
            <div className="eyebrow">
              <span /> BUILT FOR CAMPUS LIFE
            </div>
            <h1>
              Good work.
              <br />
              Great balance.
            </h1>
            <p className="hero-description">
              A little more harmony between class time and clocking in. Student
              employee scheduling, built for the rhythm of your university.
            </p>
            <Link className="primary-link" to="/register">
              Create your workspace <span aria-hidden="true">↗</span>
            </Link>
            <div className="hero-note">
              <span className="note-line" /> One campus. A better way to work.
            </div>
          </div>
          <div
            className="campus-art"
            role="img"
            aria-label="Illustration of a university building beneath the sun"
          >
            <div className="art-grid" />
            <div className="art-caption">ROOM TO LEARN. SPACE TO WORK.</div>
            <div className="sun" />
            <svg
              className="building"
              viewBox="0 0 440 340"
              fill="none"
              aria-hidden="true"
            >
              <path
                d="M42 309h356M65 291h310v18H65z"
                stroke="currentColor"
                strokeWidth="3"
              />
              <path
                d="M86 153 220 75l134 78v20H86v-20Z"
                fill="#dbe5bd"
                stroke="currentColor"
                strokeWidth="3"
              />
              <path
                d="m123 148 97-56 97 56H123Z"
                stroke="currentColor"
                strokeWidth="2"
              />
              <path
                d="M99 174h242v116H99z"
                fill="#edeee0"
                stroke="currentColor"
                strokeWidth="3"
              />
              {[114, 175, 236, 297].map((x) => (
                <g key={x}>
                  <path
                    d={`M${x} 185h26v93h-26z`}
                    fill="#f9f7ed"
                    stroke="currentColor"
                    strokeWidth="3"
                  />
                  <path
                    d={`M${x - 4} 179h34v8h-34zm0 98h34v8h-34z`}
                    fill="#dbe5bd"
                    stroke="currentColor"
                    strokeWidth="2"
                  />
                </g>
              ))}
              <path
                d="M220 74V40m0 0h44l-10 13 10 13h-44"
                stroke="currentColor"
                strokeWidth="3"
              />
              <path
                d="M47 290v-42m0 16c-42-14-30-55-8-51 13-31 40-9 35 12 27 10 10 46-27 39ZM390 290v-42m0 16c-42-14-30-55-8-51 13-31 40-9 35 12 27 10 10 46-27 39Z"
                fill="#7c9c70"
                stroke="currentColor"
                strokeWidth="3"
              />
            </svg>
            <div className="art-label">
              <span aria-hidden="true">✳</span> Work fits campus life.
            </div>
            <div className="art-index">CAMPUSSHIFT / 02</div>
          </div>
        </section>
        <section id="workspaces" className="workspaces">
          <div className="section-heading">
            <div>
              <div className="eyebrow">TWO ROLES. ONE CONNECTED CAMPUS.</div>
              <h2>A place for everyone.</h2>
            </div>
            <p>
              Your campus work, connected.
              <br />
              Your dedicated workspace is ready.
            </p>
          </div>
          <div className="workspace-grid">
            <WorkspaceCard
              number="01 / STUDENTS"
              title="Make room for what matters."
              description="Your home for managing work around your education."
              items={[
                "Share your availability",
                "Keep classes in the picture",
                "Keep your weekly profile up to date",
              ]}
            />
            <WorkspaceCard
              number="02 / SUPERVISORS"
              title="Bring your team together."
              description="Your home for understanding your department’s student team."
              items={[
                "Understand team availability",
                "Review student class schedules",
                "Review weekly hour limits",
              ]}
            />
          </div>
        </section>
        <ConnectionStatus />
      </main>
      <footer>
        <span>
          CampusShift <span aria-hidden="true">/</span> Made for the campus
          community.
        </span>
        <span>Phase 02 · Campus workspaces</span>
      </footer>
    </div>
  );
}
