# Verification scope

Doc ID: `hardening_verification`

## Automated checks

Run `python scripts/check.py` in the pinned Python environment. It uses temporary
file-backed SQLite, exercises the application and security suite, checks model/
migration consistency, and validates local browser assets and vendor hashes.
AI responses are mocked and no deployment secrets are needed.

The suite covers project forms and filtering, comments and configured author
names, protected metadata, CSRF, hostile text, resource limits, concurrent writes,
AI leases/deadlines/fallbacks, sample-data guards, and backup/restore fingerprints.
Repository publication checks run separately through `scripts/repository_check.py`.

The public configuration cleanup passed 75 application tests on Windows with
Python 3.14 and Django 6.0.8. System checks and migration drift checks passed.
GitHub Actions is configured for Windows and Linux; a configured workflow is not
evidence of a completed hosted CI run.

The optional LAN listener passed 80 application tests on Windows. Its isolated
two-process test covered shared database writes, separate HTTP/HTTPS cookies,
CSRF and Host checks, static files, rejection of forged comment attribution,
LAN worker recovery while HTTPS remains available, and complete shutdown.
These checks use synthetic data and do not establish work-laptop connectivity.

## Browser checks

The project table/modal release was exercised at 1280px and 390px using synthetic
data. Checks covered active filtering, hidden initial form, entry, validation
draft retention, editing, details, completion/reopening, keyboard focus, Escape,
and mobile overflow. The installed table/modal also passed live read-only checks.

These are recorded results for that release, not a guarantee for every future
change, browser, operating system, or household device. Recheck affected workflows.

The September 2026 responsive review exercised 11 pages at 10 viewport sizes
(320–1920 CSS pixels) in Chromium, Firefox, and WebKit: 330 page/viewport checks.
The final checks found no page overflow or clipped action regions. They included
all seven weekday headers, long synthetic content, narrow/short modal scrolling,
past/future meal details, restored focus, mobile navigation, and table scrolling.
Chromium and WebKit also passed saving meals, cancelling/confirming skips,
Enter/Space activation, 21 enlarged-text layouts each, the empty planner, and a
six-week month. WebKit-specific native-select overflow and click-focus behavior
were corrected during this review. See `responsive_layout.md` for the procedure.

The source changes passed 84 application tests, system/migration checks, the
72-file deployment source audit, all eight vendor hashes, and the repository
candidate audit. Tests used isolated synthetic databases. These results do not
establish physical-device acceptance or deployment to the installed household
service; screenshots and detailed runtime receipts remain in ignored local storage.

## Migration compatibility

Migration 0010 must preserve original author/body/device/timestamp values when
upgrading a private fixed-author database, and must also work after the sanitized
0009 definition in a fresh public checkout. Validate both routes against isolated
databases before deploying. Keep source and database backups for recovery.
An isolated database built by the original private code passed this migration:
both synthetic legacy comments retained every saved field, and the upgraded
database accepted a new longer display name.

## Live deployment evidence

Service ACLs, actual SCM identity, scheduled backups, service recovery, Tailscale
device access/denial, and production configuration require separate live checks.
The procedures are in `deployment.md` and `security.md`.

Keep receipts, hostnames, household identifiers, device registries, logs, and
backup fingerprints in ignored local evidence or protected runtime storage.
Public documentation must not contain household records or invite links.
A source-code check cannot certify those operational properties.

The source checkout and installed service are separate. Confirm the installed
release and scoped firewall against private deployment receipts after each rollout.
Verify access from the intended household devices separately from server-side checks.
