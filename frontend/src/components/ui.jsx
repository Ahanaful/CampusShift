import { useCallback, useEffect, useState } from "react";
import { api } from "../services/api";

export const days = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];
export const timeLabel = (value) => value?.slice(0, 5);

export function useResource(path) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const reload = useCallback(() => setRevision((value) => value + 1), []);
  useEffect(() => {
    if (!path) {
      setLoading(false);
      setData([]);
      setError("");
      return;
    }
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError("");
    setData(null);
    api(path, { signal: controller.signal })
      .then((value) => {
        if (active) setData(value);
      })
      .catch((error) => {
        if (active)
          setError(
            error.name === "AbortError"
              ? "The request timed out. Please retry."
              : error.message,
          );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [path, revision]);
  return { data, error, loading, reload };
}

export function ErrorMessage({ children }) {
  return children ? (
    <div className="message error-message" role="alert">
      {children}
    </div>
  ) : null;
}

export function ResourceState({ resource, children }) {
  if (resource.loading)
    return (
      <p className="message" role="status">
        Loading your workspace…
      </p>
    );
  if (resource.error)
    return (
      <>
        <ErrorMessage>{resource.error}</ErrorMessage>
        <button className="secondary-button" onClick={resource.reload}>
          Try again
        </button>
      </>
    );
  return children;
}

export function Field({ label, children, ...props }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children || <input {...props} />}
    </label>
  );
}

export function PageHeading({
  eyebrow = "YOUR CAMPUS WORKSPACE",
  title,
  children,
}) {
  return (
    <div className="dashboard-heading">
      <div className="eyebrow">{eyebrow}</div>
      <h1>{title}</h1>
      {children && <p>{children}</p>}
    </div>
  );
}

export function WeeklyCalendar({
  entries,
  title,
  conflicts = [],
  kind = "availability",
}) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      <p className="muted">Recurring weekly · Local campus time</p>
      <div className="week-grid">
        {days.map((day, index) => (
          <div className="week-day" key={day}>
            <h3>{day}</h3>
            {entries.filter((entry) => entry.day_of_week === index).length ===
              0 && <p className="empty-day">No entries</p>}
            {entries
              .filter((entry) => entry.day_of_week === index)
              .map((entry) => {
                const conflict = conflicts.some(
                  (item) =>
                    item[
                      kind === "classes" ? "class_id" : "availability_id"
                    ] === entry.id,
                );
                return (
                  <div
                    key={entry.id}
                    className={`time-block ${conflict ? "time-conflict" : ""}`}
                  >
                    <strong>{entry.course_name || "Available"}</strong>
                    <span>
                      {timeLabel(entry.start_time)}–{timeLabel(entry.end_time)}
                    </span>
                    {conflict && <span>Class / work conflict</span>}
                  </div>
                );
              })}
          </div>
        ))}
      </div>
    </section>
  );
}

export function ConflictList({ conflicts }) {
  if (!conflicts.length) return null;
  return (
    <section
      className="message conflict-message"
      aria-label="Class and availability conflicts"
    >
      <strong>These windows conflict with classes</strong>
      <p>
        Edit a class or availability window to resolve each conflict. Your
        entries have been kept as entered.
      </p>
      <ul>
        {conflicts.map((item) => (
          <li key={`${item.class_id}-${item.availability_id}`}>
            {days[item.day_of_week]} · {item.course_name} ·{" "}
            {timeLabel(item.start_time)}–{timeLabel(item.end_time)}
          </li>
        ))}
      </ul>
    </section>
  );
}
