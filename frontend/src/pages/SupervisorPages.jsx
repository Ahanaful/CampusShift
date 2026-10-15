import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { api } from "../services/api";
import {
  ConflictList,
  ErrorMessage,
  Field,
  PageHeading,
  ResourceState,
  WeeklyCalendar,
  useResource,
} from "../components/ui";

export function SupervisorDashboard() {
  const { user } = useAuth();
  const department = useResource("/supervisor/department");
  const employees = useResource("/supervisor/employees");
  return (
    <>
      <PageHeading
        eyebrow="YOUR DEPARTMENT WORKSPACE"
        title={`Welcome, ${user.full_name.split(" ")[0]}.`}
      >
        Bring your student team’s work and campus commitments together.
      </PageHeading>
      <ResourceState resource={department}>
        {department.data && (
          <section className="panel">
            <span className="eyebrow">DEPARTMENT OVERVIEW</span>
            <h2>{department.data.name}</h2>
            <p className="muted">{department.data.description}</p>
          </section>
        )}
      </ResourceState>
      <ResourceState resource={employees}>
        <div className="stat-grid">
          <div className="panel">
            <span>Student employees</span>
            <strong>{employees.data?.length || 0}</strong>
            <Link to="/supervisor/employees">Explore your team →</Link>
          </div>
          <div className="panel">
            <span>Combined weekly hour limits</span>
            <strong>
              {employees.data?.reduce(
                (sum, employee) => sum + employee.max_weekly_hours,
                0,
              ) || 0}
              <small> hours</small>
            </strong>
            <p className="muted">
              Profile limits, before availability constraints.
            </p>
          </div>
        </div>
      </ResourceState>
      <section className="panel">
        <h2>Weekly scheduling</h2>
        <div className="empty-state">
          <strong>A better week starts with the basics.</strong>
          <p>
            Review your team’s classes and availability in the directory.
            Scheduling and assigned shifts will arrive in a later phase.
          </p>
        </div>
      </section>
    </>
  );
}

export function EmployeeDirectory() {
  const employees = useResource("/supervisor/employees");
  const [search, setSearch] = useState("");
  const matches = employees.data?.filter((user) =>
    `${user.full_name} ${user.email}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  return (
    <>
      <PageHeading title="Your student team.">
        Profiles, class commitments, and availability for your department.
      </PageHeading>
      <section className="panel">
        <Field
          label="Find an employee"
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search by name or email"
        />
        <ResourceState resource={employees}>
          {!employees.data?.length ? (
            <p className="empty-state">
              No students in your department yet. Students appear here after
              registering for your department.
            </p>
          ) : !matches.length ? (
            <p className="empty-state">No employees match your search.</p>
          ) : (
            <div className="entry-list">
              {matches.map((user) => (
                <Link
                  className="entry-row employee-link"
                  key={user.id}
                  to={`/supervisor/employees/${user.id}`}
                >
                  <div>
                    <strong>{user.full_name}</strong>
                    <p>{user.email}</p>
                  </div>
                  <span>{user.max_weekly_hours} hrs / week →</span>
                </Link>
              ))}
            </div>
          )}
        </ResourceState>
      </section>
    </>
  );
}

export function EmployeeProfile() {
  const { id } = useParams();
  const employee = useResource(`/supervisor/employees/${id}`);
  const classes = useResource(`/supervisor/employees/${id}/classes`);
  const availability = useResource(`/supervisor/employees/${id}/availability`);
  const conflicts = useResource(`/supervisor/employees/${id}/conflicts`);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setSaved(false);
    const hours = Number(
      new FormData(event.currentTarget).get("max_weekly_hours"),
    );
    try {
      await api(`/supervisor/employees/${id}`, {
        method: "PATCH",
        body: { max_weekly_hours: hours },
      });
      employee.reload();
      setSaved(true);
    } catch (error) {
      setError(
        error.name === "AbortError"
          ? "Request timed out. Reload to check the saved value."
          : error.message,
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Link className="back-link" to="/supervisor/employees">
        ← Employee directory
      </Link>
      <PageHeading title={employee.data?.full_name || "Employee profile"}>
        Department employee details and weekly commitments.
      </PageHeading>
      <ResourceState resource={employee}>
        {employee.data && (
          <section className="panel">
            <h2>Profile</h2>
            <p className="muted">{employee.data.email} · Student employee</p>
            <ErrorMessage>{error}</ErrorMessage>
            {saved && (
              <p className="message" role="status">
                Weekly limit saved.
              </p>
            )}
            <form onSubmit={save} className="window-form">
              <Field
                label="Maximum weekly hours"
                name="max_weekly_hours"
                type="number"
                min="0"
                max="40"
                step="1"
                defaultValue={employee.data.max_weekly_hours}
                required
              />
              <button disabled={busy} className="action-button">
                {busy ? "Saving…" : "Update limit"}
              </button>
            </form>
          </section>
        )}
      </ResourceState>
      <ResourceState resource={conflicts}>
        {conflicts.data && <ConflictList conflicts={conflicts.data} />}
      </ResourceState>
      <ResourceState resource={classes}>
        <WeeklyCalendar
          title="Weekly class schedule"
          entries={classes.data || []}
          kind="classes"
          conflicts={conflicts.data || []}
        />
      </ResourceState>
      <ResourceState resource={availability}>
        <WeeklyCalendar
          title="Weekly work availability"
          entries={availability.data || []}
          conflicts={conflicts.data || []}
        />
      </ResourceState>
    </>
  );
}
