import { useEffect, useState } from "react";
import { api } from "../services/api";
import {
  ErrorMessage,
  Field,
  PageHeading,
  ResourceState,
  useResource,
} from "../components/ui";

function stamp(value, timezone) {
  return value
    ? new Intl.DateTimeFormat("en-US", {
        timeZone: timezone,
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
        timeZoneName: "short",
      }).format(new Date(value))
    : "—";
}
const hours = (value) => Number(value || 0).toFixed(2);

function AuditHistory({ path, timezone }) {
  const audit = useResource(path);
  return (
    <ResourceState resource={audit}>
      {audit.data?.map((event) => (
        <div className="attendance-audit" key={event.id}>
          <strong>
            {event.action} · {stamp(event.occurred_at, timezone)} · User #
            {event.actor_id}
          </strong>
          <p>
            Before:{" "}
            {stamp(
              event.details.before?.clock_in_at ||
                event.details.original?.clock_in_at,
              timezone,
            )}{" "}
            →{" "}
            {stamp(
              event.details.before?.clock_out_at ||
                event.details.original?.clock_out_at,
              timezone,
            )}
          </p>
          <p>
            After:{" "}
            {stamp(
              event.details.after?.clock_in_at ||
                event.details.proposed_clock_in,
              timezone,
            )}{" "}
            →{" "}
            {stamp(
              event.details.after?.clock_out_at ||
                event.details.proposed_clock_out,
              timezone,
            )}
          </p>
        </div>
      ))}
    </ResourceState>
  );
}

function RecordTable({ records, timezone, supervisor = false }) {
  const [auditId, setAuditId] = useState(null);
  return (
    <>
      <div className="attendance-table-wrap">
        <table className="attendance-table">
          <thead>
            <tr>
              {[
                "Employee / shift",
                "Scheduled",
                "Clock in",
                "Clock out",
                "Actual hours",
                "Status",
                "Audit",
              ].map((label) => (
                <th key={label}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {records.map((row) => (
              <tr key={row.id}>
                <td>
                  <strong>{row.student_name}</strong>
                  <span>
                    {row.shift_date} · {row.location_name}
                  </span>
                  <span>
                    Shift #{row.assigned_shift_id} · {row.schedule_status}
                  </span>
                </td>
                <td>
                  {hours(row.scheduled_hours)} h
                  <span>
                    {stamp(row.scheduled_start, timezone)} →{" "}
                    {stamp(row.scheduled_end, timezone)}
                  </span>
                </td>
                <td>
                  {stamp(row.clock_in_at, timezone)}
                  {row.late && (
                    <span className="status-badge pending">Late</span>
                  )}
                </td>
                <td>
                  {row.clock_out_at
                    ? stamp(row.clock_out_at, timezone)
                    : row.status === "active"
                      ? "Still clocked in"
                      : "—"}
                </td>
                <td>
                  {hours(row.actual_hours)}
                  {row.status === "active" && <span>Running snapshot</span>}
                </td>
                <td>
                  <span className={`status-badge ${row.status}`}>
                    {row.status}
                  </span>
                </td>
                <td>
                  <button
                    className="text-button"
                    onClick={() =>
                      setAuditId(auditId === row.id ? null : row.id)
                    }
                  >
                    View #{row.id}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!records.length && (
        <p className="empty-state">No attendance records match this view.</p>
      )}
      {auditId && (
        <section className="message">
          <strong>Audit for record #{auditId}</strong>
          <AuditHistory
            path={`/${supervisor ? "supervisor" : "students/me"}/attendance/${auditId}/audit`}
            timezone={timezone}
          />
        </section>
      )}
    </>
  );
}

function CorrectionList({ resource, timezone, supervisor, busy, onDecision }) {
  return (
    <ResourceState resource={resource}>
      {!resource.data?.length && (
        <p className="empty-state">No correction requests in this view.</p>
      )}
      {resource.data?.map((item) => (
        <article className="leave-entry" key={item.id}>
          <div className="entry-row">
            <div>
              <strong>
                {item.student_name} · Shift #{item.assigned_shift_id}
              </strong>
              <p>
                {stamp(item.proposed_clock_in, timezone)} →{" "}
                {stamp(item.proposed_clock_out, timezone)}
              </p>
              <p>{item.reason}</p>
            </div>
            <span className={`status-badge ${item.status}`}>{item.status}</span>
          </div>
          <p className="muted">
            Requested {stamp(item.created_at, timezone)}
            {item.reviewed_at &&
              ` · Reviewed ${stamp(item.reviewed_at, timezone)} by #${item.reviewed_by}`}
          </p>
          {item.reviewer_note && (
            <p className="muted">Reviewer note: {item.reviewer_note}</p>
          )}
          {supervisor && item.status === "pending" && (
            <form
              className="window-form"
              onSubmit={(event) => {
                event.preventDefault();
                const decision = event.nativeEvent.submitter?.value;
                if (decision)
                  onDecision(item.id, {
                    status: decision,
                    reviewer_note: new FormData(event.currentTarget).get(
                      "reviewer_note",
                    ),
                  });
              }}
            >
              <Field
                label="Reviewer note (optional)"
                name="reviewer_note"
                maxLength={1000}
              />
              <button
                className="action-button"
                disabled={busy}
                value="approved"
              >
                Approve correction
              </button>
              <button
                className="danger-button"
                disabled={busy}
                value="rejected"
              >
                Reject
              </button>
            </form>
          )}
        </article>
      ))}
    </ResourceState>
  );
}

export default function AttendancePage({ supervisor = false }) {
  const [student, setStudent] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [status, setStatus] = useState("");
  const [correctionStatus, setCorrectionStatus] = useState(
    supervisor ? "pending" : "",
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const filters = new URLSearchParams();
  if (student) filters.set("student_id", student);
  if (start) filters.set("start_date", start);
  if (end) filters.set("end_date", end);
  if (status) filters.set("status", status);
  const root = supervisor
    ? "/supervisor/attendance"
    : "/students/me/attendance";
  const report = useResource(root + (supervisor ? `?${filters}` : ""));
  const corrections = useResource(
    root +
      "/corrections" +
      (supervisor && correctionStatus ? `?status=${correctionStatus}` : ""),
  );
  const employees = useResource(supervisor ? "/supervisor/employees" : null);
  useEffect(() => {
    const timer = setInterval(report.reload, 30000);
    return () => clearInterval(timer);
  }, [report.reload]);
  const [lastReport, setLastReport] = useState(null);
  useEffect(() => {
    if (report.data) setLastReport(report.data);
  }, [report.data]);
  // Keep correction options stable while the live report refreshes.
  const data = report.data || lastReport;
  const timezone = data?.timezone || "America/Chicago";
  function refresh() {
    report.reload();
    corrections.reload();
  }
  async function mutate(path, body, message) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api(path, { method: "POST", body });
      setNotice(message);
      refresh();
      return true;
    } catch (error) {
      setError(
        error.name === "AbortError"
          ? "Request timed out. Refresh attendance before retrying."
          : error.message,
      );
      refresh();
      return false;
    } finally {
      setBusy(false);
    }
  }
  async function submitCorrection(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    const body = {
      ...values,
      assigned_shift_id: Number(values.assigned_shift_id),
      clock_in_fold: Number(values.clock_in_fold),
      clock_out_fold: Number(values.clock_out_fold),
    };
    if (
      await mutate(
        root + "/corrections",
        body,
        "Correction submitted for supervisor review. Original attendance remains unchanged.",
      )
    )
      form.reset();
  }
  async function download() {
    setBusy(true);
    setError("");
    try {
      const text = await api(`/supervisor/attendance/export.csv?${filters}`, {
        responseType: "text",
      });
      const url = URL.createObjectURL(
        new Blob([text], { type: "text/csv;charset=utf-8" }),
      );
      const link = document.createElement("a");
      link.href = url;
      link.download = "campusshift-attendance.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }
  function ShiftCard({ shift }) {
    return (
      <article className="entry-row">
        <div>
          <strong>
            {shift.location_name} · {shift.shift_date}
          </strong>
          <p>
            {stamp(shift.scheduled_start, timezone)} →{" "}
            {stamp(shift.scheduled_end, timezone)}
          </p>
          <p className="muted">
            {hours(shift.scheduled_hours)} scheduled hours · Clock-in opens{" "}
            {stamp(shift.clock_in_opens, timezone)}
          </p>
          {shift.timing_issue && (
            <ErrorMessage>{shift.timing_issue}</ErrorMessage>
          )}
        </div>
        <button
          disabled={
            busy || !shift.can_clock_in || !!data?.active_records.length
          }
          className="action-button"
          onClick={() =>
            mutate(
              root + "/clock-in",
              { assigned_shift_id: shift.id },
              "Clocked in using the server time.",
            )
          }
        >
          {shift.attendance_record_id
            ? "Attendance recorded"
            : shift.can_clock_in
              ? "Clock in"
              : "Outside clock-in window"}
        </button>
      </article>
    );
  }
  return (
    <>
      <PageHeading
        title={supervisor ? "Time and attendance." : "My attendance."}
      >
        {supervisor
          ? "Department attendance, correction review, and scheduled versus actual work."
          : "Clock in for published shifts, track actual hours, and request corrections."}
      </PageHeading>
      <ErrorMessage>{error}</ErrorMessage>
      {notice && (
        <p className="message" role="status">
          {notice}
        </p>
      )}
      <div className="window-form">
        <button className="secondary-button" onClick={refresh} disabled={busy}>
          Refresh attendance
        </button>
        <p className="muted">
          Updates every 30 seconds · {timezone}
          {data && ` · Observed ${stamp(data.server_now, timezone)}`}
        </p>
      </div>
      {supervisor && (
        <section className="panel window-form">
          <Field label="Student">
            <select
              value={student}
              onChange={(event) => setStudent(event.target.value)}
            >
              <option value="">All employees</option>
              {employees.data?.map((employee) => (
                <option key={employee.id} value={employee.id}>
                  {employee.full_name}
                </option>
              ))}
            </select>
          </Field>
          <Field
            label="Shift date from"
            type="date"
            value={start}
            onChange={(event) => setStart(event.target.value)}
          />
          <Field
            label="Through"
            type="date"
            value={end}
            onChange={(event) => setEnd(event.target.value)}
          />
          <Field label="Record status">
            <select
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              <option value="">All statuses</option>
              {["active", "completed", "corrected", "missing"].map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </Field>
          <button
            disabled={busy || report.loading || !!report.error}
            className="action-button"
            onClick={download}
          >
            Export records CSV
          </button>
        </section>
      )}
      <ResourceState resource={report}>
        {data && (
          <>
            <div className="stat-grid">
              <div className="panel">
                <span>
                  {supervisor
                    ? "Current published scheduled hours (date/student filters)"
                    : "Published scheduled hours (all weeks)"}
                </span>
                <strong>{hours(data.scheduled_hours)}</strong>
              </div>
              <div className="panel">
                <span>
                  Actual hours in record history{" "}
                  {supervisor ? "(filters applied)" : ""}
                </span>
                <strong>{hours(data.total_actual_hours)}</strong>
              </div>
              <div className="panel">
                <span>Actual this local week · {data.week_start}</span>
                <strong>{hours(data.actual_weekly_hours)}</strong>
                <p className="muted">
                  Includes running attendance, clipped to this local week.
                  Independent of date/status filters.
                </p>
              </div>
            </div>
            <section className="panel">
              <h2>
                {supervisor
                  ? "Employees currently clocked in"
                  : "Current clock-in status"}
              </h2>
              <p className="muted">
                Active records remain visible across date/status filters and
                schedule replacements.
              </p>
              {!data.active_records.length && (
                <p className="empty-state">
                  {supervisor
                    ? "Nobody is currently clocked in."
                    : "You are not clocked in."}
                </p>
              )}
              {data.active_records.map((row) => (
                <div className="entry-row" key={row.id}>
                  <div>
                    <strong>
                      {row.student_name} · {row.location_name}
                    </strong>
                    <p>
                      Since {stamp(row.clock_in_at, timezone)} ·{" "}
                      {hours(row.actual_hours)} actual hours so far
                    </p>
                  </div>
                  {!supervisor && (
                    <button
                      className="action-button"
                      disabled={busy}
                      onClick={() =>
                        mutate(
                          `${root}/${row.id}/clock-out`,
                          {},
                          "Clocked out. Actual attendance has been recorded.",
                        )
                      }
                    >
                      Clock out
                    </button>
                  )}
                </div>
              ))}
            </section>
            {!supervisor && (
              <>
                <section className="panel">
                  <h2>Next published shift</h2>
                  {data.next_shift ? (
                    <ShiftCard shift={data.next_shift} />
                  ) : (
                    <p className="empty-state">
                      No upcoming published shift needs a clock-in.
                    </p>
                  )}
                  <p className="muted">
                    Clock-in is permitted {data.clock_in_early_minutes} minutes
                    before through {data.clock_in_late_minutes} minutes after
                    the scheduled start, and before the shift ends.
                  </p>
                </section>
                <section className="panel">
                  <h2>Today's published shifts</h2>
                  {!data.today_shifts.length && (
                    <p className="empty-state">No published shifts today.</p>
                  )}
                  {data.today_shifts.map((shift) => (
                    <ShiftCard key={shift.id} shift={shift} />
                  ))}
                </section>
              </>
            )}
            <section className="panel">
              <h2>Attendance history</h2>
              <p className="muted">
                Scheduled hours are planned local wall-clock duration; actual
                hours use elapsed UTC time and include active snapshots.
              </p>
              <RecordTable
                records={data.records}
                timezone={timezone}
                supervisor={supervisor}
              />
            </section>
            {supervisor && (
              <section className="panel">
                <h2>Shift attendance indicators</h2>
                <p className="muted">
                  {data.late_count} late recorded clock-ins ·{" "}
                  {data.missed_count} missed current published shifts. Late
                  means more than {data.late_grace_minutes} minutes after
                  scheduled start. Missed means ended without recorded clock-in.
                </p>
                {!data.shifts.length && (
                  <p className="empty-state">No shifts in this view.</p>
                )}
                {data.shifts.map((shift) => (
                  <div className="entry-row" key={shift.id}>
                    <div>
                      <strong>
                        {shift.student_name} · {shift.shift_date} ·{" "}
                        {shift.location_name}
                      </strong>
                      <p>
                        {stamp(shift.scheduled_start, timezone)} →{" "}
                        {stamp(shift.scheduled_end, timezone)} ·{" "}
                        {shift.schedule_status}
                      </p>
                      {shift.timing_issue && <p>{shift.timing_issue}</p>}
                    </div>
                    <span
                      className={`status-badge ${shift.missed ? "rejected" : ""}`}
                    >
                      {shift.missed
                        ? "Missed"
                        : shift.attendance_record_id
                          ? "Attendance on file"
                          : "Not yet recorded"}
                    </span>
                  </div>
                ))}
              </section>
            )}
          </>
        )}
      </ResourceState>
      {!supervisor && (
        <section className="panel">
          <h2>Request an attendance correction</h2>
          <p className="muted">
            Enter times in {timezone}. Explain missed or incorrect clock-in/out.
            Clock-in may start on the shift date or preceding night when work
            continues into the shift. Clock-out may be after midnight, within
            24 elapsed hours. Future attendance is not allowed.
            For a missing clock-in/out, wait until the scheduled shift has
            ended.
          </p>
          <form onSubmit={submitCorrection}>
            <fieldset className="window-form" disabled={busy || !data}>
              <Field label="Original published shift">
                <select name="assigned_shift_id" required defaultValue="">
                  <option value="">Choose a shift</option>
                  {data?.shifts
                    .filter(
                      (shift) =>
                        shift.scheduled_start &&
                        new Date(shift.scheduled_start) <=
                          new Date(data.server_now),
                    )
                    .map((shift) => (
                      <option key={shift.id} value={shift.id}>
                        {shift.shift_date} · {shift.location_name} · #{shift.id}{" "}
                        ({shift.schedule_status})
                      </option>
                    ))}
                </select>
              </Field>
              <Field
                label="Proposed clock-in"
                name="proposed_clock_in"
                type="datetime-local"
                required
              />
              <Field
                label="Proposed clock-out"
                name="proposed_clock_out"
                type="datetime-local"
                required
              />
              <Field label="Clock-in during repeated DST hour">
                <select name="clock_in_fold" defaultValue="0">
                  <option value="0">First occurrence (usual)</option>
                  <option value="1">Second occurrence</option>
                </select>
              </Field>
              <Field label="Clock-out during repeated DST hour">
                <select name="clock_out_fold" defaultValue="0">
                  <option value="0">First occurrence (usual)</option>
                  <option value="1">Second occurrence</option>
                </select>
              </Field>
              <Field label="Reason" name="reason" maxLength={1000} required />
              <button className="action-button">
                {busy ? "Submitting…" : "Request correction"}
              </button>
            </fieldset>
          </form>
        </section>
      )}
      <section className="panel">
        <h2>
          {supervisor
            ? "Attendance correction review"
            : "My correction requests"}
        </h2>
        {supervisor && (
          <Field label="Correction status">
            <select
              value={correctionStatus}
              onChange={(event) => setCorrectionStatus(event.target.value)}
            >
              <option value="">All statuses</option>
              {["pending", "approved", "rejected"].map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </Field>
        )}
        <CorrectionList
          resource={corrections}
          timezone={timezone}
          supervisor={supervisor}
          busy={busy}
          onDecision={(id, body) =>
            mutate(
              `/supervisor/attendance/corrections/${id}/decision`,
              body,
              "Correction decision saved with an audit trail.",
            )
          }
        />
      </section>
    </>
  );
}
