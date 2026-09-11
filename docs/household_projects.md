# Household projects

Doc ID: `household_projects`

## Scope

The Django project lives in `infonet/`; its application is `infonet/myapp/`.
The Projects navigation link and home card open `/projects/`. The page uses
the existing Den layout and shared SQLite database. Records are shared by
everyone who can access this household app, consistent with its existing pages.
The hardened deployment's access boundary and shared limits are in `security.md`.

## Data contract

`HouseholdProject` stores the six entry fields plus completion state and creation
time in `myapp_householdproject`. See `schema/household_projects.csv` for field
types, defaults, choices, and limits. Type means the project category;
both small tasks and larger projects use the same record. Choices are Maintenance,
Repair, Cleaning, Organization, App/Tech Idea, AMA, and Other. App/Tech Idea and
AMA replace the retired Home improvement and Yard & garden options.

Records sort by active before completed, urgency descending, scheduled start
ascending with unscheduled records last, then creation time and ID descending.
Scheduled start is a date, without a time or timezone. Estimated days is a manual
estimate, supports tenths of a day, and does not calculate an end date.

## Project screens

The projects home screen shows only the project list, with Active selected by
default. Completed and All remain explicit filters. A full-width table shows
name, type, urgency, scheduled start, estimated time, and comment count. Project
names and row clicks open the detail page; comment links open its comments.
On narrow screens the table scrolls horizontally within its own region.

The upper-right Add task button opens the entry form in the existing Den modal.
The form is hidden on a normal list visit. Cancel, Close, Escape, or the backdrop
closes it; the shared modal traps focus and restores it to the opening control.
Edit URLs open the same modal with saved values. Invalid submissions reopen it
with the draft, errors, and focus on the first invalid field. Successful writes
return to the list with the modal closed. Closing a creation draft keeps its
values until navigation or a successful submission.

The detail page shows the description, schedule, estimate, category, urgency,
completion state, and comment thread. Edit, completion/reopening, and confirmed
deletion are available there. These actions no longer appear on list rows.
The existing data, ordering, write endpoints, and comment attribution are unchanged.
See `schema/project_screens.csv` for the screen and form-state contract.

## Request flow

- `household_projects(request, project_id=None)`: GET `/projects/` lists records
  with an initially hidden creation modal; POST validates and creates a record. GET or POST
  `/projects/<project_id>/edit/` loads or updates the specified record using
  the same page with the form modal open. Editing does not change completion state.
- `status=active|completed|all` controls the visible list. Invalid status falls
  back to active. Editing a completed record defaults to the completed list.
- Successful creation or editing redirects to the list and shows a success
  message. Completed edits redirect to `?status=completed`. Refreshing the
  redirected page does not repeat the write.
- `project_set_completion(request, project_id)`: POST
  `/projects/<project_id>/completion/` accepts `is_completed=true|false`.
  It sets the requested state, making repeated completion requests idempotent.
- `project_delete(request, project_id)`: POST
  `/projects/<project_id>/delete/` permanently deletes one record. The UI asks
  for confirmation before submitting. Completing or deleting redirects to active.

All forms include Django CSRF protection. Completion and deletion reject GET
with 405; list and edit accept only GET and POST. Missing IDs return 404.
Project comments additionally use the protected Tailscale device map described below.

## Comments

Project titles and comment-count links open `/projects/<project_id>/`. This page
shows a shared, chronological comment thread, including completed projects.
Comments are paginated at 50 per page; opening a project shows the latest page.
POST `/projects/<project_id>/comments/` accepts only `body`. The server assigns
the author, device ID, and creation timestamp. Successful posts redirect to the
new comment. Refreshing that page does not resubmit the comment.

`ProjectComment` stores plain text, the author snapshot from the protected owner mapping,
the enrolled Tailscale node ID, and an immutable UTC timestamp. The interface
displays dates and times in `DEN_DISPLAY_TIME_ZONE` (America/New_York by default),
with the applicable timezone abbreviation shown explicitly.
The author and timestamp cannot be selected or overridden through the form.
Comments are append-only through the app. Deleting a project also deletes its
comments; the existing deletion confirmation explicitly includes comments.

Bodies must contain non-whitespace text and may have at most 4,000 characters.
Newlines are preserved and all text is escaped, without Markdown or HTML execution.
There are caps of 200 comments per project and 10,000 across the household,
checked inside the existing IMMEDIATE SQLite transaction. Global POST budgets,
request-body limits, upload rejection, and CSRF checks apply unchanged.

Malformed comment bodies or exceeded quotas render the thread and draft with
400. Unidentified devices render the draft with 403 and cannot submit a comment.
Missing projects or invalid path IDs return 404; non-POST comment writes return
405. Exhausted global write budgets return 429 with Retry-After. Database
contention returns the existing controlled 503. Viewing comments requires only
the existing household network access; identity is required for attribution.

## Device attribution

Tailscale Serve overwrites forwarding and user-identity headers. Production
Waitress trusts only the immediate loopback proxy's X-Forwarded-For value, using
one proxy hop, and discards other forwarding headers. HTTPS remains fixed by
production configuration; forwarded host/scheme cannot change it.

The app matches the resulting source address to an enrolled device in
`DEN_DEVICE_MAP_FILE`, then cross-checks the Serve user login against that
device's owner. It records the node ID, not a hardware address or browser cookie.
Both IPv4 and IPv6 addresses are supported. The map must be well formed,
unique by node ID/address, at most 64 devices/64 KiB, and no older than five
minutes. Missing, stale, malformed, mismatched, tagged, or unknown identity
fails closed for commenting. Funnel requests and non-HTTPS requests are rejected.

The protected owner mapping translates enrolled login identities to household
display names. Owners are configured outside source control; see `configuration.md`. A SYSTEM task refreshes enrolled node IDs and
addresses every minute; no Tailscale control or credential access is granted
to Den. New approved household devices appear without an app login or restart.
There can be up to one refresh interval before enrollment/removal is reflected.
Tailscale access policy and device approval still gate incoming requests.
The optional LAN worker admits its configured home subnet for ordinary household
features, but always returns no comment identity, even for supplied HTTPS or
Tailscale headers. Existing comments remain readable through either address.

The label uses the account default or an administrator's stable-node assignment,
not whoever physically holds the device. A node assignment still requires the
expected enrolled login. Historical authors remain unchanged after device removal,
display-name changes, or reassignment.
Local Windows processes could forge proxy headers by contacting loopback; this
retains the existing Windows/Tailscale host trust boundary. Identity cannot bypass
the global resource limits or grant additional computer permissions.

## Comment verification

Migration `0009_projectcomment` adds the comment table and database author
constraint. Existing household tables are unchanged. Backup and restore
fingerprints now include comments; backups from before this migration treat the
missing comment table as empty for migration comparisons.

Automated checks cover both authors, server-only metadata, local timestamps,
escaping, limits, CSRF, unsupported methods, missing IDs, global budgets,
pagination, completion, cascade deletion, and simultaneous posts at capacity.
Device-map checks cover IPv6, stale/malformed maps, mismatched owners, excluded
devices, and the narrow forwarding-header trust configuration. Browser and live
service verification are recorded separately in `hardening-verification.md`.

## Validation

`HouseholdProjectForm` accepts only the six entry fields. Name, type, and urgency
are required; description, scheduled start, and estimated days can be blank.
Descriptions are limited to 10,000 characters and stored projects to 2,000.
Creation checks capacity in an IMMEDIATE SQLite transaction; editing and deletion
remain available at the cap. Global POST budgets also apply.
Type defaults to Other and urgency to Normal in a new form. Django strips outer
whitespace and rejects an empty name, invalid choices, malformed dates, and
estimates outside 0.1–9999.9 days or with more than one decimal place. Past start
dates are allowed so existing work can be entered.

Invalid forms render with entered values and field errors, without saving.
Invalid completion values return 400 without changing the record. Estimate
limits are enforced by model/form validation; direct ORM writers must call
`full_clean()` before saving. User text is template-escaped and is never
interpolated into JavaScript.

## Author migration

Migration `0009_projectcomment` was sanitized before the first public repository
snapshot: its initial state accepts a non-empty author label up to 64 characters.
The private installation originally used a fixed-name constraint under the same
constraint name. Migration `0010_configurable_comment_authors` explicitly drops
that legacy constraint, widens the author field, and installs the generic
non-empty constraint. It works with both original private databases and fresh
public installations; no author, body, device ID, or timestamp is rewritten.

Apply 0010 when upgrading an installation that previously used fixed names.
Do not restore a database into old application code after writing new author
names. Keep the pre-upgrade protected backup for rollback.

Names in a device registry must be printable, trimmed, non-empty strings of at
most 64 characters. The registry remains protected and server-selected; request
fields cannot choose an author. Changing a configured name affects future
comments only. This relaxes the fixed household labels without granting another
identity access to the application or its protected files.

## Migration and verification

Run `python scripts/check.py` from the repository root using its virtual
environment. The helper uses an isolated file-backed test database. Apply actual
installation migrations only through the documented upgrade procedure after a
backup. Migration 0005 creates projects, 0006 updates category choices, 0009
creates comments, and 0010 generalizes author labels.

The project test suite covers creation, updates, blank optional fields, invalid
input, completion/reopening, list ordering/filtering, deletion, escaping, and
CSRF. Comment tests cover attribution, draft retention, limits, concurrency,
backup/restore, and configured names. Browser workflows and deployment identity
checks are separate from unit-test results; see `hardening-verification.md`.
