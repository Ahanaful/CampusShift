import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import {
  ErrorMessage,
  Field,
  PageHeading,
  ResourceState,
  days,
  timeLabel,
  useResource,
} from "../components/ui";

const emptyLocation = {
  name: "",
  description: "",
  is_active: true,
  eligible_student_ids: [],
};

export function LocationManager() {
  const locations = useResource("/supervisor/locations");
  const employees = useResource("/supervisor/employees");
  const [form, setForm] = useState(emptyLocation);
  const [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [statusBusy, setStatusBusy] = useState(false);
  function reset() {
    setForm(emptyLocation);
    setEditing(null);
  }
  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api("/supervisor/locations" + (editing ? `/${editing}` : ""), {
        method: editing ? "PUT" : "POST",
        body: form,
      });
      reset();
      locations.reload();
      setNotice(
        "Location and eligibility saved. Generate a new draft to use these changes.",
      );
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
  async function changeStatus(employee) {
    setStatusBusy(true);
    setError("");
    try {
      await api(`/supervisor/employees/${employee.id}/scheduling`, {
        method: "PATCH",
        body: { is_active: !employee.is_active },
      });
      employees.reload();
    } catch (error) {
      setError(error.message);
    } finally {
      setStatusBusy(false);
    }
  }
  return (
    <>
      <PageHeading title="Places your team works.">
        Manage department locations and the students eligible to work at each
        one.
      </PageHeading>
      <ErrorMessage>{error}</ErrorMessage>
      {notice && (
        <p className="message" role="status">
          {notice}
        </p>
      )}
      <section className="panel">
        <h2>{editing ? "Edit location" : "Create location"}</h2>
        <form className="stack-form" onSubmit={submit}>
          <fieldset disabled={busy}>
            <Field
              label="Location name"
              required
              maxLength={120}
              value={form.name}
              onChange={(event) =>
                setForm({ ...form, name: event.target.value })
              }
            />
            <Field
              label="Description (optional)"
              maxLength={1000}
              value={form.description}
              onChange={(event) =>
                setForm({ ...form, description: event.target.value })
              }
            />
            <label className="check-label">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(event) =>
                  setForm({ ...form, is_active: event.target.checked })
                }
              />
              Active location
            </label>
            <div>
              <strong className="small-label">
                Eligible student employees
              </strong>
              <p className="muted">
                Only selected, active students can be assigned here. No
                selection means nobody is eligible.
              </p>
              <ResourceState resource={employees}>
                <div className="eligibility-list">
                  {employees.data?.length === 0 && (
                    <p className="muted">
                      No department students yet.{" "}
                      <Link to="/supervisor/employees">View directory</Link>.
                    </p>
                  )}
                  {employees.data?.map((employee) => (
                    <label className="check-label" key={employee.id}>
                      <input
                        type="checkbox"
                        checked={form.eligible_student_ids.includes(
                          employee.id,
                        )}
                        onChange={(event) =>
                          setForm({
                            ...form,
                            eligible_student_ids: event.target.checked
                              ? [...form.eligible_student_ids, employee.id]
                              : form.eligible_student_ids.filter(
                                  (id) => id !== employee.id,
                                ),
                          })
                        }
                      />
                      {employee.full_name}
                      {!employee.is_active && " (inactive for scheduling)"}
                    </label>
                  ))}
                </div>
              </ResourceState>
            </div>
            <div className="row-actions">
              <button className="action-button">
                {busy ? "Saving…" : "Save location"}
              </button>
              {editing && (
                <button
                  type="button"
                  className="secondary-button"
                  onClick={reset}
                >
                  Cancel
                </button>
              )}
            </div>
          </fieldset>
        </form>
      </section>
      <ResourceState resource={locations}>
        <section className="panel">
          <h2>Work locations</h2>
          {!locations.data?.length && (
            <p className="empty-state">Create your first location above.</p>
          )}
          {locations.data?.map((item) => (
            <article key={item.id} className="entry-row">
              <div>
                <strong>
                  {item.name}{" "}
                  <span className="coming-soon">
                    {item.is_active ? "Active" : "Inactive"}
                  </span>
                </strong>
                <p>
                  {item.description || "No description"} ·{" "}
                  {item.eligible_student_ids.length} eligible students
                </p>
              </div>
              <button
                className="secondary-button"
                onClick={() => {
                  setEditing(item.id);
                  const { id, department_id, ...values } = item;
                  setForm(values);
                  setError("");
                  setNotice("");
                }}
              >
                Edit / deactivate
              </button>
            </article>
          ))}
        </section>
      </ResourceState>
      <ResourceState resource={employees}>
        <section className="panel">
          <h2>Employee scheduling status</h2>
          <p className="muted">
            Inactive students receive no new assignments. Existing drafts remain
            unchanged.
          </p>
          {employees.data?.map((employee) => (
            <div className="entry-row" key={employee.id}>
              <strong>{employee.full_name}</strong>
              <button
                disabled={statusBusy}
                className="secondary-button"
                onClick={() => changeStatus(employee)}
              >
                {employee.is_active
                  ? "Deactivate for scheduling"
                  : "Activate for scheduling"}
              </button>
            </div>
          ))}
        </section>
      </ResourceState>
    </>
  );
}

const emptyRequirement = {
  location_id: "",
  day_of_week: "0",
  start_time: "09:00",
  end_time: "12:00",
  required_count: "1",
  is_active: true,
};

export function RequirementManager() {
  const locations = useResource("/supervisor/locations");
  const requirements = useResource("/supervisor/requirements");
  const [form, setForm] = useState(emptyRequirement);
  const [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  function reset() {
    setForm(emptyRequirement);
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
      requirements.reload();
      reset();
      setNotice("Staffing needs saved. Existing drafts are unchanged.");
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
      setError(
        "Start must precede end on the same day. Overnight staffing is not supported.",
      );
      return;
    }
    mutate(() =>
      api("/supervisor/requirements" + (editing ? `/${editing}` : ""), {
        method: editing ? "PUT" : "POST",
        body: {
          ...form,
          location_id: Number(form.location_id),
          day_of_week: Number(form.day_of_week),
          required_count: Number(form.required_count),
        },
      }),
    );
  }
  return (
    <>
      <PageHeading title="Staffing needs, clearly defined.">
        Set recurring weekly demand. Active windows at the same location cannot
        overlap.
      </PageHeading>
      <ErrorMessage>{error}</ErrorMessage>
      {notice && (
        <p className="message" role="status">
          {notice}
        </p>
      )}
      <section className="panel">
        <h2>
          {editing ? "Edit staffing requirement" : "Add staffing requirement"}
        </h2>
        <ResourceState resource={locations}>
          <form onSubmit={submit}>
            <fieldset disabled={busy} className="window-form">
              <Field label="Location">
                <select
                  name="location_id"
                  required
                  value={form.location_id}
                  onChange={change}
                >
                  <option value="">Select a location</option>
                  {locations.data?.map((item) => (
                    <option value={item.id} key={item.id}>
                      {item.name}
                      {!item.is_active && " (inactive)"}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Day">
                <select
                  name="day_of_week"
                  value={form.day_of_week}
                  onChange={change}
                >
                  {days.map((day, index) => (
                    <option key={day} value={index}>
                      {day}
                    </option>
                  ))}
                </select>
              </Field>
              <Field
                label="Start"
                type="time"
                step="1800"
                name="start_time"
                value={form.start_time}
                onChange={change}
                required
              />
              <Field
                label="End"
                type="time"
                step="1800"
                name="end_time"
                value={form.end_time}
                onChange={change}
                required
              />
              <Field
                label="Employees required"
                type="number"
                min="1"
                max="50"
                step="1"
                name="required_count"
                value={form.required_count}
                onChange={change}
                required
              />
              <label className="check-label">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(event) =>
                    setForm({ ...form, is_active: event.target.checked })
                  }
                />
                Active
              </label>
              <button className="action-button">
                {busy ? "Saving…" : "Save requirement"}
              </button>
              {editing && (
                <button
                  type="button"
                  className="secondary-button"
                  onClick={reset}
                >
                  Cancel
                </button>
              )}
            </fieldset>
          </form>
          {!locations.data?.length && (
            <p className="message">
              Add a <Link to="/supervisor/locations">work location</Link> first.
            </p>
          )}
        </ResourceState>
        <p className="muted">
          Times use :00 / :30 boundaries, in your department’s local time.
          Overnight windows are rejected.
        </p>
      </section>
      <ResourceState resource={requirements}>
        <section className="panel">
          <h2>Recurring weekly requirements</h2>
          {!requirements.data?.length && (
            <p className="empty-state">No staffing requirements yet.</p>
          )}
          {requirements.data?.map((item) => (
            <article className="entry-row" key={item.id}>
              <div>
                <strong>
                  {locations.data?.find(
                    (location) => location.id === item.location_id,
                  )?.name || `Location #${item.location_id}`}
                </strong>
                <p>
                  {days[item.day_of_week]} · {timeLabel(item.start_time)}–
                  {timeLabel(item.end_time)} · {item.required_count} employees ·{" "}
                  {item.is_active ? "Active" : "Inactive"}
                </p>
              </div>
              <div className="row-actions">
                <button
                  disabled={busy}
                  className="secondary-button"
                  onClick={() => {
                    setEditing(item.id);
                    const { id, department_id, ...values } = item;
                    setForm({
                      ...values,
                      location_id: String(values.location_id),
                      day_of_week: String(values.day_of_week),
                      required_count: String(values.required_count),
                      start_time: timeLabel(values.start_time),
                      end_time: timeLabel(values.end_time),
                    });
                    setError("");
                    setNotice("");
                  }}
                >
                  Edit / deactivate
                </button>
                <button
                  disabled={busy}
                  className="danger-button"
                  onClick={() => {
                    if (
                      window.confirm(
                        "Delete this requirement? Requirements used in saved drafts must be deactivated instead.",
                      )
                    )
                      mutate(() =>
                        api(`/supervisor/requirements/${item.id}`, {
                          method: "DELETE",
                        }),
                      );
                  }}
                >
                  Delete
                </button>
              </div>
            </article>
          ))}
        </section>
      </ResourceState>
    </>
  );
}
