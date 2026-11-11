import { useState } from "react";
import { Link } from "react-router-dom";
import ScheduleEditor from "../components/ScheduleEditor";
import { ScheduleConflictNotice } from "./TimeOffPages";
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

function mondayISO(timezone) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const values = Object.fromEntries(
    parts.map((part) => [part.type, part.value]),
  );
  const value = new Date(
    `${values.year}-${values.month}-${values.day}T12:00:00`,
  );
  value.setDate(value.getDate() - ((value.getDay() + 6) % 7));
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
}

function weekDates(monday) {
  // Calendar-only arithmetic: never shift campus dates via UTC conversions.
  return days.map((_, index) => {
    const value = new Date(`${monday}T12:00:00`);
    value.setDate(value.getDate() + index);
    return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
  });
}

export function DraftCalendar({ weekStart, shifts, gaps = [] }) {
  if (!weekStart) return null;
  const dates = weekDates(weekStart);
  return (
    <div className="schedule-week">
      {days.map((day, index) => (
        <section className="schedule-day" key={day}>
          <h3>
            {day}
            <span>{dates[index]}</span>
          </h3>
          {!shifts.some((shift) => shift.shift_date === dates[index]) &&
            !gaps.some((gap) => gap.shift_date === dates[index]) && (
              <p className="empty-day">No assignments</p>
            )}
          {[
            ...shifts
              .filter((shift) => shift.shift_date === dates[index])
              .map((shift) => ({ ...shift, type: "shift" })),
            ...gaps
              .filter((gap) => gap.shift_date === dates[index])
              .map((gap) => ({ ...gap, type: "gap" })),
          ]
            .sort(
              (a, b) =>
                a.start_time.localeCompare(b.start_time) ||
                a.location_id - b.location_id ||
                a.id - b.id,
            )
            .map((item) => (
              <article
                className={`time-block ${item.type === "gap" ? "time-conflict" : ""}`}
                key={`${item.type}-${item.id}`}
              >
                <strong>
                  {timeLabel(item.start_time)}–{timeLabel(item.end_time)}
                </strong>
                <span>{item.location_name}</span>
                <span>
                  {item.type === "gap"
                    ? `${item.missing_count} employee(s) needed`
                    : item.student_name}
                </span>
                {item.type === "gap" && <span>{item.reason}</span>}
              </article>
            ))}
        </section>
      ))}
    </div>
  );
}

export function ScheduleGenerator() {
  const runs = useResource("/supervisor/schedules");
  const department = useResource("/supervisor/department");
  const [chosenWeek, setWeek] = useState(null);
  const week =
    chosenWeek ?? mondayISO(department.data?.timezone || "America/Chicago");
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [location, setLocation] = useState("");
  const [student, setStudent] = useState("");
  const activeId = selected || runs.data?.[0]?.id;
  const detail = useResource(
    activeId ? `/supervisor/schedules/${activeId}` : null,
  );
  async function submit(event) {
    event.preventDefault();
    setError("");
    if (new Date(`${week}T12:00:00`).getDay() !== 1) {
      setError("Select a Monday for the start of your week.");
      return;
    }
    setBusy(true);
    try {
      const run = await api("/supervisor/schedules", {
        method: "POST",
        body: { week_start: week },
      });
      setSelected(String(run.id));
      setLocation("");
      setStudent("");
      runs.reload();
      detail.reload();
    } catch (error) {
      setError(
        error.name === "AbortError"
          ? "Generation timed out. Check saved drafts before retrying; a completed run may already be saved."
          : error.message,
      );
      runs.reload();
    } finally {
      setBusy(false);
    }
  }
  const run = detail.data?.id ? detail.data : null;
  const locationOptions = [
    ...new Map(
      [...(run?.shifts || []), ...(run?.unfilled || [])].map((item) => [
        String(item.location_id),
        item.location_name,
      ]),
    ).entries(),
  ];
  const visibleShifts =
    run?.shifts.filter(
      (shift) =>
        (!location || String(shift.location_id) === location) &&
        (!student || String(shift.student_id) === student),
    ) || [];
  // Gaps belong to the location, never to a particular employee.
  const visibleGaps =
    run?.unfilled.filter(
      (gap) => !location || String(gap.location_id) === location,
    ) || [];
  return (
    <>
      <PageHeading title="A balanced week starts here.">
        Generate and compare weekly drafts. Every generation saves a new
        version; existing drafts are preserved.
      </PageHeading>
      <ScheduleConflictNotice refreshKey={run?.version || 0} />
      <section className="panel">
        <h2>Generate a draft</h2>
        <ErrorMessage>{error}</ErrorMessage>
        <form className="window-form" onSubmit={submit}>
          <Field
            label="Week starts Monday"
            type="date"
            value={week}
            onChange={(event) => setWeek(event.target.value)}
            required
          />
          <button disabled={busy} className="action-button">
            {busy ? "Generating…" : "Generate new draft"}
          </button>
        </form>
        <p className="muted">
          30-minute staffing slots · Availability, classes, eligibility and
          weekly hour limits are enforced. Drafts are unpublished and do not
          combine with assignments from other versions.
        </p>
      </section>
      <ResourceState resource={runs}>
        <section className="panel">
          <Field label="Schedule version history">
            <select
              value={activeId || ""}
              onChange={(event) => {
                setSelected(event.target.value);
                setLocation("");
                setStudent("");
              }}
            >
              <option value="">Choose a saved draft</option>
              {runs.data?.map((item) => (
                <option key={item.id} value={item.id}>
                  Week {item.week_start} · {item.status} #{item.id} ·{" "}
                  {item.summary.coverage_percent}% coverage
                </option>
              ))}
            </select>
          </Field>
          {!runs.data?.length && (
            <p className="empty-state">
              No drafts yet. Add locations and staffing requirements, then
              generate your first week.
            </p>
          )}
        </section>
      </ResourceState>
      {activeId && (
        <ResourceState resource={detail}>
          {run && (
            <>
              <div className="message draft-notice">
                <strong>
                  <span className={`status-badge ${run.status}`}>
                    {run.status}
                  </span>{" "}
                  Schedule #{run.id}
                </strong>
                <p>
                  Week of {run.week_start} · {run.summary.timezone} ·{" "}
                  {run.status === "draft"
                    ? "Unpublished: review and publish to make assignments official."
                    : run.status === "published"
                      ? "Current official schedule for this week. Assignments are read-only."
                      : "Historical schedule, superseded by a newer published version."}
                </p>
              </div>
              <div className="stat-grid">
                <div className="panel">
                  <span>Staffing coverage</span>
                  <strong>{run.summary.coverage_percent}%</strong>
                  <p className="muted">Weighted by employee minutes required</p>
                </div>
                <div className="panel">
                  <span>Total assigned</span>
                  <strong>
                    {run.summary.total_assigned_hours}
                    <small> hours</small>
                  </strong>
                </div>
                <div className="panel">
                  <span>Unfilled 30-minute positions</span>
                  <strong>{run.summary.unfilled_slot_positions}</strong>
                  <p className="muted">
                    {run.summary.unfilled_staff_minutes / 60} employee-hours
                    uncovered
                  </p>
                </div>
              </div>
              {!run.summary.required_staff_minutes && (
                <p className="message">
                  No active staffing demand at active locations for this draft.
                  Coverage is 100% by convention; there are no assignments.
                </p>
              )}
              <section className="panel">
                <h2>Weekly schedule</h2>
                <div className="window-form">
                  <Field label="Filter by location">
                    <select
                      value={location}
                      onChange={(event) => setLocation(event.target.value)}
                    >
                      <option value="">All locations</option>
                      {locationOptions.map(([id, name]) => (
                        <option key={id} value={id}>
                          {name}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Filter by student">
                    <select
                      value={student}
                      onChange={(event) => setStudent(event.target.value)}
                    >
                      <option value="">All students</option>
                      {Object.entries(run.summary.employee_names).map(
                        ([id, name]) => (
                          <option key={id} value={id}>
                            {name}
                          </option>
                        ),
                      )}
                    </select>
                  </Field>
                </div>
                <p className="muted">
                  Amber periods show understaffing. Location gaps remain visible
                  when filtering by employee. Metrics above describe the entire
                  draft.
                </p>
                <DraftCalendar
                  weekStart={run.week_start}
                  shifts={visibleShifts}
                  gaps={visibleGaps}
                />
              </section>
              <ScheduleEditor
                key={`${run.id}-${run.version}`}
                run={run}
                runs={runs.data || []}
                onChange={() => {
                  detail.reload();
                  runs.reload();
                }}
              />
              <section className="panel">
                <h2>Unfilled staffing periods</h2>
                {!run.unfilled.length && (
                  <p className="empty-state">
                    All requested staffing slots are filled.
                  </p>
                )}
                {run.unfilled.map((gap) => (
                  <article className="entry-row" key={gap.id}>
                    <div>
                      <strong>
                        {gap.shift_date} · {gap.location_name} ·{" "}
                        {timeLabel(gap.start_time)}–{timeLabel(gap.end_time)}
                      </strong>
                      <p>
                        {gap.missing_count} missing · {gap.reason}
                      </p>
                    </div>
                  </article>
                ))}
              </section>
              <section className="panel">
                <h2>Assigned hours by employee</h2>
                {Object.entries(run.summary.employee_minutes).map(
                  ([id, minutes]) => (
                    <div className="entry-row" key={id}>
                      <strong>{run.summary.employee_names[id]}</strong>
                      <span>{minutes / 60} hours</span>
                    </div>
                  ),
                )}
              </section>
            </>
          )}
        </ResourceState>
      )}
    </>
  );
}

export function StudentSchedule({ draft = false }) {
  const [week, setWeek] = useState("");
  const schedule = useResource(
    (draft ? "/students/me/draft-schedule" : "/students/me/schedule") +
      (week ? `?week_start=${encodeURIComponent(week)}` : ""),
  );
  const locations = useResource("/students/me/locations");
  return (
    <>
      <PageHeading
        title={draft ? "Draft preview — unpublished." : "My schedule."}
      >
        {draft
          ? "Testing preview only. These are not official work assignments."
          : "Your current published work assignments. Previous versions remain in your department's history."}
      </PageHeading>
      <section className="panel">
        <Field
          label={
            draft
              ? "Week starts Monday (empty for latest draft)"
              : "Week starts Monday (empty for latest published week)"
          }
          type="date"
          value={week}
          onChange={(event) => setWeek(event.target.value)}
        />
        <button
          className="secondary-button schedule-refresh"
          onClick={schedule.reload}
        >
          Refresh preview
        </button>
      </section>
      <ResourceState resource={schedule}>
        {schedule.data?.run_id ? (
          <>
            <div className="message draft-notice">
              <strong>
                {draft ? "Draft / unpublished" : "Published schedule"} #
                {schedule.data.run_id}
              </strong>
              <p>
                Week of {schedule.data.week_start} · {schedule.data.timezone}.
                {draft
                  ? "Your supervisor may generate a newer draft. These shifts are not finalized."
                  : "These are your official assignments. Contact your supervisor if approved leave overlaps a published shift."}
              </p>
            </div>
            <section className="panel">
              <h2>
                {schedule.data.assigned_hours} assigned {draft ? "draft " : ""}
                hours
              </h2>
              {!schedule.data.shifts.length && (
                <p className="empty-state">
                  No shifts assigned to you in this{" "}
                  {draft ? "draft" : "published week"}.
                </p>
              )}
              <DraftCalendar
                weekStart={schedule.data.week_start}
                shifts={schedule.data.shifts}
              />
            </section>
          </>
        ) : (
          <section className="panel">
            <p className="empty-state">
              No {draft ? "draft" : "published schedule"} is available for this
              week yet.
            </p>
          </section>
        )}
      </ResourceState>
      {!draft && (
        <Link className="secondary-button" to="/student/draft-schedule">
          View testing draft preview (unpublished)
        </Link>
      )}
      <ResourceState resource={locations}>
        <section className="panel">
          <h2>Your eligible work locations</h2>
          {!locations.data?.length && (
            <p className="muted">
              Your supervisor has not assigned you to an active location yet.
            </p>
          )}
          {locations.data?.map((item) => (
            <div className="entry-row" key={item.id}>
              <div>
                <strong>{item.name}</strong>
                <p>{item.description}</p>
              </div>
            </div>
          ))}
        </section>
      </ResourceState>
    </>
  );
}
