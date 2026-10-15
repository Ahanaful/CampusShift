import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { api } from "../services/api";
import {
  ConflictList,
  ErrorMessage,
  Field,
  PageHeading,
  ResourceState,
  WeeklyCalendar,
  days,
  timeLabel,
  useResource,
} from "../components/ui";

export function StudentDashboard() {
  const { user } = useAuth();
  const classes = useResource("/students/me/classes");
  const availability = useResource("/students/me/availability");
  const conflicts = useResource("/students/me/conflicts");
  const schedule = useResource("/students/me/schedule");
  return (
    <>
      <PageHeading title={`Welcome, ${user.full_name.split(" ")[0]}.`}>
        Let's make room for class, work, and everything in between.
      </PageHeading>
      <div className="stat-grid">
        <div className="panel">
          <span>Weekly hour limit</span>
          <strong>
            {user.max_weekly_hours}
            <small> hours</small>
          </strong>
          <Link to="/student/profile">Manage profile →</Link>
        </div>
        <div className="panel">
          <span>Recurring classes</span>
          <strong>
            {classes.loading ? "…" : (classes.data?.length ?? "—")}
          </strong>
          <Link to="/student/classes">Manage classes →</Link>
        </div>
        <div className="panel">
          <span>Availability windows</span>
          <strong>
            {availability.loading ? "…" : (availability.data?.length ?? "—")}
          </strong>
          <Link to="/student/availability">Manage availability →</Link>
        </div>
      </div>
      {[classes, availability].map((resource, index) => (
        <ResourceState key={index} resource={resource} />
      ))}
      <ResourceState resource={conflicts}>
        {conflicts.data && <ConflictList conflicts={conflicts.data} />}
      </ResourceState>
      <section className="panel">
        <h2>
          Your draft schedule <span className="coming-soon">Unpublished</span>
        </h2>
        <ResourceState resource={schedule}>
          {schedule.data?.run_id ? (
            <>
              <p className="muted">
                Week of {schedule.data.week_start} ·{" "}
                {schedule.data.assigned_hours} assigned hours ·{" "}
                {schedule.data.timezone}
              </p>
              {!schedule.data.shifts.length && (
                <p className="empty-state">
                  No assignments for you in this draft.
                </p>
              )}
              {schedule.data.shifts.slice(0, 5).map((shift) => (
                <div className="entry-row" key={shift.id}>
                  <strong>{shift.location_name}</strong>
                  <span>
                    {shift.shift_date} · {timeLabel(shift.start_time)}–
                    {timeLabel(shift.end_time)}
                  </span>
                </div>
              ))}
            </>
          ) : (
            <p className="empty-state">
              Your supervisor has not generated a draft yet.
            </p>
          )}
        </ResourceState>
        <p className="muted">
          Draft previews are for planning and are not finalized work
          assignments.
        </p>
        <Link
          className="secondary-button schedule-refresh"
          to="/student/schedule"
        >
          View your draft week →
        </Link>
      </section>
    </>
  );
}

export function StudentProfile() {
  const { user, setUser } = useAuth();
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setSaved(false);
    const values = Object.fromEntries(new FormData(event.currentTarget));
    try {
      setUser(
        await api("/students/me", {
          method: "PATCH",
          body: {
            ...values,
            max_weekly_hours: Number(values.max_weekly_hours),
          },
        }),
      );
      setSaved(true);
    } catch (error) {
      setError(
        error.name === "AbortError"
          ? "Request timed out. Check your profile before retrying."
          : error.message,
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading title="Your profile.">
        Keep your details and weekly work limit up to date.
      </PageHeading>
      <section className="panel narrow-panel">
        <h2>Student information</h2>
        <p className="muted">
          {user.email} · Department #{user.department_id}
        </p>
        <ErrorMessage>{error}</ErrorMessage>
        {saved && (
          <p role="status" className="message">
            Profile saved.
          </p>
        )}
        <form className="stack-form" onSubmit={submit}>
          <fieldset disabled={busy}>
            <Field
              label="Full name"
              name="full_name"
              defaultValue={user.full_name}
              maxLength={120}
              required
            />
            <Field
              label="Maximum weekly work hours"
              name="max_weekly_hours"
              type="number"
              min="0"
              max="40"
              step="1"
              defaultValue={user.max_weekly_hours}
              required
            />
            <button className="action-button">
              {busy ? "Saving…" : "Save profile"}
            </button>
          </fieldset>
        </form>
      </section>
    </>
  );
}

const blankWindow = {
  day_of_week: "0",
  start_time: "09:00",
  end_time: "10:00",
  course_name: "",
};

export function WindowManager({ kind }) {
  const isClass = kind === "classes";
  const path = `/students/me/${kind}`;
  const resource = useResource(path);
  const conflictResource = useResource("/students/me/conflicts");
  const [form, setForm] = useState(blankWindow);
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  function reset() {
    setForm(blankWindow);
    setEditing(null);
  }
  function change(event) {
    setForm({ ...form, [event.target.name]: event.target.value });
  }
  async function mutate(operation) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await operation();
      resource.reload();
      conflictResource.reload();
      reset();
      setNotice("Changes saved.");
    } catch (error) {
      setError(
        error.name === "AbortError"
          ? "Request timed out. Refresh the list before retrying."
          : error.message,
      );
    } finally {
      setBusy(false);
    }
  }
  function submit(event) {
    event.preventDefault();
    if (form.start_time >= form.end_time) {
      setError("Start time must be before end time.");
      return;
    }
    const body = {
      day_of_week: Number(form.day_of_week),
      start_time: form.start_time,
      end_time: form.end_time,
      ...(isClass ? { course_name: form.course_name } : {}),
    };
    mutate(() =>
      api(path + (editing ? `/${editing}` : ""), {
        method: editing ? "PUT" : "POST",
        body,
      }),
    );
  }
  return (
    <>
      <PageHeading title={isClass ? "Your classes." : "Your availability."}>
        {isClass
          ? "Keep your academic commitments in the picture."
          : "Tell your department when work fits your week. Add multiple windows per day."}
      </PageHeading>
      <section className="panel">
        <h2>
          {editing ? "Edit" : "Add"}{" "}
          {isClass ? "a class" : "an availability window"}
        </h2>
        <ErrorMessage>{error}</ErrorMessage>
        {notice && (
          <p role="status" className="message">
            {notice}
          </p>
        )}
        <form onSubmit={submit}>
          <fieldset className="window-form" disabled={busy}>
            {isClass && (
              <Field
                label="Course name"
                name="course_name"
                value={form.course_name}
                onChange={change}
                maxLength={120}
                required
              />
            )}
            <Field label="Day">
              <select
                name="day_of_week"
                value={form.day_of_week}
                onChange={change}
              >
                {days.map((day, index) => (
                  <option value={index} key={day}>
                    {day}
                  </option>
                ))}
              </select>
            </Field>
            <Field
              label="Start time"
              name="start_time"
              type="time"
              step="60"
              value={form.start_time}
              onChange={change}
              required
            />
            <Field
              label="End time"
              name="end_time"
              type="time"
              step="60"
              value={form.end_time}
              onChange={change}
              required
            />
            <button className="action-button">
              {busy
                ? "Saving…"
                : editing
                  ? "Save changes"
                  : isClass
                    ? "Add class"
                    : "Add window"}
            </button>
            {editing && (
              <button
                type="button"
                className="secondary-button"
                onClick={reset}
              >
                Cancel edit
              </button>
            )}
          </fieldset>
        </form>
        <p className="muted">
          Use local campus time. Adjacent windows are allowed; overlapping
          entries of the same type are rejected.
        </p>
      </section>
      <ResourceState resource={conflictResource}>
        {conflictResource.data && (
          <ConflictList conflicts={conflictResource.data} />
        )}
      </ResourceState>
      <ResourceState resource={resource}>
        <WeeklyCalendar
          title="Your week at a glance"
          entries={resource.data || []}
          kind={kind}
          conflicts={conflictResource.data || []}
        />
        <section className="panel">
          <h2>{isClass ? "Class entries" : "Availability windows"}</h2>
          {resource.data?.length === 0 && (
            <p className="empty-state">
              No entries yet. Add your first{" "}
              {isClass ? "class" : "availability window"} above.
            </p>
          )}
          <div className="entry-list">
            {resource.data?.map((entry) => (
              <article className="entry-row" key={entry.id}>
                <div>
                  <strong>{entry.course_name || "Available for work"}</strong>
                  <p>
                    {days[entry.day_of_week]} · {timeLabel(entry.start_time)}–
                    {timeLabel(entry.end_time)}
                  </p>
                </div>
                <div className="row-actions">
                  <button
                    className="secondary-button"
                    disabled={busy}
                    onClick={() => {
                      setEditing(entry.id);
                      setForm({
                        ...entry,
                        day_of_week: String(entry.day_of_week),
                        start_time: timeLabel(entry.start_time),
                        end_time: timeLabel(entry.end_time),
                      });
                      setError("");
                      setNotice("");
                    }}
                  >
                    Edit
                    <span className="sr-only">
                      {" "}
                      {entry.course_name || days[entry.day_of_week]}
                    </span>
                  </button>
                  <button
                    className="danger-button"
                    disabled={busy}
                    onClick={() => {
                      if (window.confirm("Delete this entry?"))
                        mutate(() =>
                          api(`${path}/${entry.id}`, { method: "DELETE" }),
                        );
                    }}
                  >
                    Delete
                    <span className="sr-only">
                      {" "}
                      {entry.course_name || days[entry.day_of_week]}
                    </span>
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      </ResourceState>
    </>
  );
}
