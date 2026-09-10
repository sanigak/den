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

## Browser checks

The project table/modal release was exercised at 1280px and 390px using synthetic
data. Checks covered active filtering, hidden initial form, entry, validation
draft retention, editing, details, completion/reopening, keyboard focus, Escape,
and mobile overflow. The installed table/modal also passed live read-only checks.

These are recorded results for that release, not a guarantee for every future
change, browser, operating system, or household device. Recheck affected workflows.

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

The GitHub preparation changes have not been deployed as a new household release.
They do not modify the running installation, its protected owners, or live data.
