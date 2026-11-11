import { useState } from "react";
import { api } from "../services/api";
import {
  ErrorMessage,
  Field,
  ResourceState,
  timeLabel,
  useResource,
} from "./ui";

export default function ScheduleEditor({ run, runs, onChange }) {
  const employees = useResource("/supervisor/employees");
  const validation = useResource(
    `/supervisor/schedules/${run.id}/validation?version=${run.version}`,
  );
  const events = useResource(
    `/supervisor/schedules/${run.id}/events?version=${run.version}`,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [acknowledge, setAcknowledge] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const current = runs.find(
    (item) => item.status === "published" && item.week_start === run.week_start,
  );
  async function mutate(path, body, method = "POST") {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api(path, {
        method,
        body: { ...body, expected_version: run.version },
      });
      setNotice("Schedule updated.");
      setConfirmed(false);
      setAcknowledge(false);
      onChange();
      events.reload();
      validation.reload();
    } catch (error) {
      setError(
        error.name === "AbortError"
          ? "Request timed out. Refresh the schedule before retrying."
          : error.message,
      );
      validation.reload();
    } finally {
      setBusy(false);
    }
  }
  function employeeSelect(name, defaultValue = "") {
    return (
      <select name={name} defaultValue={defaultValue} required>
        <option value="">Choose an employee</option>
        {employees.data?.map((employee) => (
          <option key={employee.id} value={employee.id}>
            {employee.full_name}
            {!employee.is_active && " (inactive)"}
          </option>
        ))}
      </select>
    );
  }
  return (
    <section className="panel">
      <h2>
        Review and{" "}
        {run.status === "draft" ? "edit draft" : "publication history"}
      </h2>
      <p className="muted">
        {run.status} · Revision {run.version}
        {run.published_at &&
          ` · Published ${new Date(run.published_at).toLocaleString()} by #${run.published_by}`}
      </p>
      <ErrorMessage>{error}</ErrorMessage>
      <button
        type="button"
        className="secondary-button"
        disabled={busy}
        onClick={onChange}
      >
        Refresh schedule and versions
      </button>
      {notice && (
        <p className="message" role="status">
          {notice}
        </p>
      )}
      <ResourceState resource={validation}>
        {!!validation.data?.length && (
          <div className="message conflict-message">
            <strong>Current constraint conflicts</strong>
            {validation.data.map((issue, index) => (
              <p key={index}>
                {issue.student_name} · Shift #{issue.shift_id}: {issue.message}
              </p>
            ))}
          </div>
        )}
      </ResourceState>
      {run.status !== "draft" ? (
        <p className="message">
          This schedule is read-only. Generate a new draft to make a
          replacement; publication archives the previous version without losing
          assignments.
        </p>
      ) : (
        <>
          <ResourceState resource={employees}>
            <h3>Assigned employees</h3>
            {!run.shifts.length && (
              <p className="muted">
                No assignments yet. Fill a staffing gap below.
              </p>
            )}
            {run.shifts.map((shift) => (
              <form
                key={`${shift.id}-${shift.student_id}`}
                className="edit-shift-row"
                onSubmit={(event) => {
                  event.preventDefault();
                  mutate(
                    `/supervisor/schedules/${run.id}/shifts/${shift.id}`,
                    {
                      student_id: Number(
                        new FormData(event.currentTarget).get("student_id"),
                      ),
                    },
                    "PATCH",
                  );
                }}
              >
                <div>
                  <strong>
                    {shift.shift_date} · {shift.location_name} ·{" "}
                    {timeLabel(shift.start_time)}–{timeLabel(shift.end_time)}
                  </strong>
                  <p className="muted">Currently: {shift.student_name}</p>
                </div>
                <Field label="Reassign to">
                  {employeeSelect("student_id", shift.student_id)}
                </Field>
                <button disabled={busy} className="secondary-button">
                  Reassign
                </button>
                <button
                  type="button"
                  disabled={busy}
                  className="danger-button"
                  onClick={() => {
                    if (
                      window.confirm(
                        "Remove this assignment from the draft? It will become an uncovered staffing position.",
                      )
                    )
                      mutate(
                        `/supervisor/schedules/${run.id}/shifts/${shift.id}/remove`,
                        {},
                      );
                  }}
                >
                  Remove
                </button>
              </form>
            ))}
            <h3>Add an employee to a gap</h3>
            {!run.unfilled.length && (
              <p className="muted">No staffing gaps remain.</p>
            )}
            {run.unfilled.map((gap) => (
              <form
                key={`${gap.id}-${run.version}`}
                className="edit-shift-row"
                onSubmit={(event) => {
                  event.preventDefault();
                  const values = Object.fromEntries(
                    new FormData(event.currentTarget),
                  );
                  mutate(`/supervisor/schedules/${run.id}/shifts`, {
                    student_id: Number(values.student_id),
                    requirement_id: gap.staffing_requirement_id,
                    shift_date: gap.shift_date,
                    start_time: values.start_time,
                    end_time: values.end_time,
                  });
                }}
              >
                <div>
                  <strong>
                    {gap.shift_date} · {gap.location_name} · {gap.missing_count}{" "}
                    missing
                  </strong>
                  <p className="muted">
                    Gap {timeLabel(gap.start_time)}–{timeLabel(gap.end_time)}.
                    Fill all or part in 30-minute intervals.
                  </p>
                </div>
                <Field label="Employee">{employeeSelect("student_id")}</Field>
                <Field
                  label="Start"
                  name="start_time"
                  type="time"
                  step="1800"
                  min={timeLabel(gap.start_time)}
                  max={timeLabel(gap.end_time)}
                  defaultValue={timeLabel(gap.start_time)}
                  required
                />
                <Field
                  label="End"
                  name="end_time"
                  type="time"
                  step="1800"
                  min={timeLabel(gap.start_time)}
                  max={timeLabel(gap.end_time)}
                  defaultValue={timeLabel(gap.end_time)}
                  required
                />
                <button disabled={busy} className="action-button">
                  Add assignment
                </button>
              </form>
            ))}
          </ResourceState>
          <div className="publish-review">
            <h3>Publish this week</h3>
            <p className="muted">
              Publishing makes this version official for students.
              {current
                ? ` Current published version #${current.id} will be archived.`
                : " No version is currently published for this week."}
            </p>
            {!!run.summary.unfilled_staff_minutes && (
              <label className="check-label">
                <input
                  type="checkbox"
                  checked={acknowledge}
                  onChange={(event) => setAcknowledge(event.target.checked)}
                />
                I acknowledge {run.summary.unfilled_staff_minutes / 60}{" "}
                uncovered employee-hours and accept the staffing gaps.
              </label>
            )}
            <label className="check-label">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(event) => setConfirmed(event.target.checked)}
              />
              I have reviewed this schedule and confirm publication.
            </label>
            <button
              className="action-button"
              disabled={
                busy ||
                !confirmed ||
                validation.loading ||
                !!validation.error ||
                !!validation.data?.length ||
                (!!run.summary.unfilled_staff_minutes && !acknowledge)
              }
              onClick={() =>
                mutate(`/supervisor/schedules/${run.id}/publish`, {
                  acknowledge_uncovered: acknowledge,
                  expected_current_published_id: current?.id || null,
                })
              }
            >
              {busy ? "Publishing…" : "Publish reviewed schedule"}
            </button>
          </div>
        </>
      )}
      <ResourceState resource={events}>
        <details className="schedule-refresh">
          <summary>Schedule audit history</summary>
          {!events.data?.length && (
            <p className="muted">
              No manual edits or publishing events recorded.
            </p>
          )}
          {events.data?.map((item) => (
            <p className="muted" key={item.id}>
              {new Date(item.created_at).toLocaleString()} · {item.action} ·
              Supervisor #{item.actor_id}
            </p>
          ))}
        </details>
      </ResourceState>
    </section>
  );
}
