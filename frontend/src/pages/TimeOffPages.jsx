import { useState } from "react";
import { api } from "../services/api";
import {
  ErrorMessage,
  Field,
  PageHeading,
  ResourceState,
  timeLabel,
  useResource,
} from "../components/ui";

export function ScheduleConflictNotice({ refreshKey = 0 }) {
  const resource = useResource(
    `/supervisor/schedule-conflicts?refresh=${refreshKey}`,
  );
  return (
    <div>
      <button className="text-button" type="button" onClick={resource.reload}>
        Refresh leave conflict warnings
      </button>
      <ResourceState resource={resource}>
        {!!resource.data?.length && (
          <section className="message conflict-message">
            <strong>Approved leave overlaps existing assignments</strong>
            <p>
              Published assignments remain unchanged. Resolve draft conflicts
              before publishing; generate and publish a replacement to fix a
              published week.
            </p>
            {resource.data.map((item) => (
              <p key={`${item.request_id}-${item.shift_id}`}>
                {item.student_name} · {item.shift_date}{" "}
                {timeLabel(item.start_time)}–{timeLabel(item.end_time)} ·{" "}
                {item.location_name} · {item.run_status} #{item.run_id}
              </p>
            ))}
          </section>
        )}
      </ResourceState>
    </div>
  );
}

export function TimeOffPage({ supervisor = false }) {
  const [status, setStatus] = useState(supervisor ? "pending" : "");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [revision, setRevision] = useState(0);
  const filter = new URLSearchParams();
  if (status) filter.set("status", status);
  if (start) filter.set("start_date", start);
  if (end) filter.set("end_date", end);
  const requests = useResource(
    supervisor ? `/supervisor/time-off?${filter}` : "/students/me/time-off",
  );
  const employees = useResource(supervisor ? "/supervisor/employees" : null);
  async function mutate(path, body, message) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api(path, {
        method: "POST",
        ...(body !== undefined ? { body } : {}),
      });
      requests.reload();
      setRevision((value) => value + 1);
      setNotice(message);
      return true;
    } catch (error) {
      setError(
        error.name === "AbortError"
          ? "Request timed out. Refresh the history before retrying."
          : error.message,
      );
      requests.reload();
      return false;
    } finally {
      setBusy(false);
    }
  }
  async function submit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    if (values.start_date > values.end_date) {
      setError("End date must be on or after start date.");
      return;
    }
    if (
      await mutate(
        "/students/me/time-off",
        values,
        "Request submitted for supervisor review.",
      )
    )
      form.reset();
  }
  return (
    <>
      <PageHeading title={supervisor ? "Time-off management." : "My time off."}>
        {supervisor
          ? "Review department requests. Approved leave blocks new assignments and flags conflicts with existing schedules."
          : "Request full calendar days away from work. Both the start and end date are included."}
      </PageHeading>
      <ErrorMessage>{error}</ErrorMessage>
      {notice && (
        <p className="message" role="status">
          {notice}
        </p>
      )}
      {supervisor ? (
        <>
          <ScheduleConflictNotice refreshKey={revision} />
          <section className="panel window-form">
            <Field label="Status">
              <select
                value={status}
                onChange={(event) => setStatus(event.target.value)}
              >
                <option value="">All statuses</option>
                {["pending", "approved", "rejected", "cancelled"].map(
                  (value) => (
                    <option key={value}>{value}</option>
                  ),
                )}
              </select>
            </Field>
            <Field
              label="Overlaps date from"
              type="date"
              value={start}
              onChange={(event) => setStart(event.target.value)}
            />
            <Field
              label="Through date"
              type="date"
              value={end}
              onChange={(event) => setEnd(event.target.value)}
            />
          </section>
        </>
      ) : (
        <section className="panel">
          <h2>Request time off</h2>
          <form onSubmit={submit}>
            <fieldset className="window-form" disabled={busy}>
              <Field label="First day" name="start_date" type="date" required />
              <Field
                label="Last day (inclusive)"
                name="end_date"
                type="date"
                required
              />
              <Field label="Reason (optional)" name="reason" maxLength={1000} />
              <button className="action-button">
                {busy ? "Submitting…" : "Submit request"}
              </button>
            </fieldset>
          </form>
        </section>
      )}
      <ResourceState resource={requests}>
        <section className="panel">
          <h2>{supervisor ? "Department requests" : "Request history"}</h2>
          <button className="secondary-button" onClick={requests.reload}>
            Refresh history
          </button>
          {!requests.data?.length && (
            <p className="empty-state">No requests match this view.</p>
          )}
          {requests.data?.map((item) => (
            <article className="leave-entry" key={item.id}>
              <div className="entry-row">
                <div>
                  <strong>
                    {supervisor
                      ? employees.data?.find(
                          (employee) => employee.id === item.student_id,
                        )?.full_name || `Student #${item.student_id}`
                      : "Time off"}{" "}
                    · {item.start_date}–{item.end_date}
                  </strong>
                  <p>{item.reason || "No reason provided"}</p>
                </div>
                <span className={`status-badge ${item.status}`}>
                  {item.status}
                </span>
              </div>
              {item.decision_note && (
                <p className="muted">Decision note: {item.decision_note}</p>
              )}
              <p className="muted">
                Submitted {new Date(item.created_at).toLocaleString()}
                {item.reviewed_at &&
                  ` · Reviewed ${new Date(item.reviewed_at).toLocaleString()} by #${item.reviewer_id}`}
                {item.cancelled_at &&
                  ` · Cancelled ${new Date(item.cancelled_at).toLocaleString()}`}
              </p>
              {item.status === "pending" &&
                (supervisor ? (
                  <form
                    className="window-form"
                    onSubmit={(event) => {
                      event.preventDefault();
                      const form = event.currentTarget;
                      const decision = event.nativeEvent.submitter?.value;
                      if (!decision) return;
                      mutate(
                        `/supervisor/time-off/${item.id}/decision`,
                        {
                          status: decision,
                          decision_note: new FormData(form).get(
                            "decision_note",
                          ),
                        },
                        "Decision recorded. Review any assignment warnings above.",
                      );
                    }}
                  >
                    <Field
                      label="Decision note (optional)"
                      name="decision_note"
                      maxLength={1000}
                    />
                    <button
                      disabled={busy}
                      className="action-button"
                      value="approved"
                    >
                      Approve
                    </button>
                    <button
                      disabled={busy}
                      className="danger-button"
                      value="rejected"
                    >
                      Reject
                    </button>
                  </form>
                ) : (
                  <button
                    disabled={busy}
                    className="secondary-button schedule-refresh"
                    onClick={() =>
                      mutate(
                        `/students/me/time-off/${item.id}/cancel`,
                        undefined,
                        "Pending request cancelled.",
                      )
                    }
                  >
                    Cancel pending request
                  </button>
                ))}
            </article>
          ))}
        </section>
      </ResourceState>
    </>
  );
}
