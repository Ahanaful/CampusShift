# Phase 4 workflows and consistency

## Time off

Students submit department-scoped all-day date ranges, optionally with a reason. Both dates are inclusive. New requests are pending; only the owning student may cancel a pending request. Only a supervisor in the request's department may approve/reject a pending request or supply a decision note. Self-review is forbidden. Final decisions cannot be revised in this phase. Every record keeps its student/department, creation time, reviewer, decision note, decision time and cancellation time. UTC timestamps are normalized after SQLite round trips; requested dates are department-local calendar dates, not UTC instants.

Only approved rows are adapted into the existing scheduler's `Student.approved_time_off` input. The engine adds a hard exclusion before checking recurring availability/classes and hour limits. Date ranges are immutable pure inputs; no SQL or HTTP dependency enters the engine. Pending, rejected, and cancelled requests never block generation.

`GET /api/supervisor/schedule-conflicts` dynamically joins approved leave to existing assignments in draft/published department runs. The supervisor dashboard, time-off page and generator display these warnings. They refresh after a decision, on page navigation or manual refresh; there is no push/email delivery. Approval never modifies assignment rows, schedule status, coverage, or history. Warnings disappear from active views only after an explicit edit resolves a draft assignment or an explicit replacement publication archives the conflicting version. Historical approved requests remain available.

## Editing and validation

`schedule_editor` reserves SQLite's write lock before loading the draft. Each request supplies `expected_version`; stale requests return 409 and do not overwrite changes. Published/archived runs reject edits. An edit can change the student on a whole shift, remove a whole assignment, or add an assignment to all/part of a saved staffing window using half-hour boundaries. The target date, department, location, eligible/active student, availability, classes, approved leave, overlapping assignments, weekly minutes and per-slot headcount must all be valid.

The pure scheduler's `assignment_error` function is shared by generation, editing and publication. `summarize` evaluates fixed assignments to recalculate gaps, employee-minute coverage and employee hours; it does not assign people. Changes, summary, gaps, audit event and incremented revision commit together. A failed constraint or persistence operation rolls back. Removal is permitted even if unrelated assignments have become invalid, so a supervisor can resolve conflicts one at a time. Publishing rejects any remaining conflicts.

Saved demand remains the version's staffing reference. Adding/reassigning against a changed requirement is rejected; publication compares the full currently active demand with the generation snapshot and requires fresh generation if it changed. Student eligibility, active status, availability, classes, hour limits and approved leave are read live. The original input snapshot remains the generation record; manual audit events record before/after assignment values and revisions.

## Publication

Runs and assignment rows use draft, published and archived statuses. Publishing requires a current draft revision, no current hard-constraint conflicts, and explicit acknowledgement if employee-minutes remain uncovered. The UI also requires a separate review-confirmation checkbox. The API accepts the expected ID of the current published version, preventing an unexpectedly new publication from being superseded without refresh/review.

One transaction archives the prior published run/shift statuses, records its replacement event, publishes the reviewed draft, records actor/time/coverage acknowledgement, increments revisions and commits. A partial unique database index enforces a single published run per department/week. Failure restores the previous official version. Historical assignment identities, times, names and durations are retained. There is no in-place editing or reopening of official schedules: generate and review a replacement.

Students' `/api/students/me/schedule` selects only published runs and only their own shift rows. Monday filtering selects that week's current publication; no filter selects the newest published week. The old Phase 3 testing preview is retained at `/api/students/me/draft-schedule`, separately labeled unpublished. It is never returned by the official schedule endpoint or dashboard.

## Endpoints

All endpoints require bearer authentication and derive department/ownership from the authenticated user. Missing auth returns 401, role failures 403, inaccessible IDs 404, invalid ranges/constraints 422, and stale revisions/state or unacknowledged gaps 409.

| Method | Path | Input / result |
| --- | --- | --- |
| GET, POST | `/api/students/me/time-off` | Own history / `{start_date,end_date,reason?}` |
| GET | `/api/students/me/time-off/{id}` | Own request |
| POST | `/api/students/me/time-off/{id}/cancel` | Cancel own pending request |
| GET | `/api/supervisor/time-off` | Optional `status`, `start_date`, `end_date` overlap filters |
| GET | `/api/supervisor/time-off/{id}` | Department request |
| POST | `/api/supervisor/time-off/{id}/decision` | `{status:approved|rejected,decision_note?}` |
| GET | `/api/supervisor/schedule-conflicts` | Leave/assignment warnings in active draft/published versions |
| GET | `/api/supervisor/schedules/{id}/validation` | Current hard-constraint and staffing-change issues |
| POST | `/api/supervisor/schedules/{id}/shifts` | `{expected_version,student_id,requirement_id,shift_date,start_time,end_time}` |
| PATCH | `/api/supervisor/schedules/{id}/shifts/{shift_id}` | `{expected_version,student_id}` |
| POST | `/api/supervisor/schedules/{id}/shifts/{shift_id}/remove` | `{expected_version}` |
| POST | `/api/supervisor/schedules/{id}/publish` | `{expected_version,acknowledge_uncovered?,expected_current_published_id?}` |
| GET | `/api/supervisor/schedules/{id}/events` | Actor, UTC time, action, before/after edits and publication history |

## Migration and limits

Alembic revision `fab90f5980a1` preserves existing Phase 3 drafts and assignments. SQLite batch migration temporarily disables FK enforcement only on its migration connection and runs `foreign_key_check` afterward. Application connections retain enforcement. Downgrade refuses to erase published/archived status history. The regression suite includes data-preserving migration round trips, constraint tests, failed-write rollback, a unique-index violation, and real concurrent SQLite edits (one succeeds, one is rejected).

Approved leave is all-day only. There is no reversal of final leave decisions, fractional shifts below 30 minutes, shift swaps, push/email delivery, actual-hours/payroll tracking, or AWS deployment. Greedy generation remains heuristic; fairness history is a previous generated version, not actual hours worked. Browser interactions still require manual verification in this environment. Phase 5 should address production session controls, deployment architecture, durable notification handling and policy decisions for leave reversals or urgent published-schedule changes.
