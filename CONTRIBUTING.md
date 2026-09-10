# Contributing to Den

Doc ID: `contributing`

Start with the local setup in [README.md](README.md). Keep changes focused and
include a short description of the problem, resulting behavior, and verification.

## Checks

Run `python scripts/check.py` using the project's virtual environment. It runs
Django system checks, migration drift checks, all application tests, and the
deployment source/vendor audit. A temporary file-backed database exercises real
SQLite locking; tests and AI mocks are isolated from household data and services.

Run `python scripts/repository_check.py` before committing. It checks the actual
Git candidate file set, obvious credential patterns, and forbidden private files.
When Git has not been initialized, it evaluates `.gitignore` using temporary Git
metadata. Findings show paths and categories, never credential values. Review
the staged diff yourself too: pattern checks cannot prove that arbitrary text
contains no personal information.

GitHub Actions runs these checks on Python 3.14 for Windows and Linux, without
deployment credentials or a production connection. Dependabot proposes updates
to dependencies and Actions. Python lock-file hashes must be regenerated from
the selected distribution files before dependency updates can merge.
Vendored browser files retain their exact bytes through `.gitattributes`; preserve
that rule so checkout line endings do not invalidate their recorded checksums.

## Code and documentation

Read [docs/AGENT_SKILL.md](docs/AGENT_SKILL.md) before making changes. Keep inline
comments at 15 words or fewer. Longer explanations belong in a referenced doc.
Update related documentation and schema CSVs alongside changes to contracts,
configuration, signatures, I/O, pipeline stages, or error behavior.

Add a forward migration for schema changes. Preserve historical comment authors
and timestamps. Do not weaken the network boundary, CSRF checks, protected device
attribution, or resource limits to simplify a demo.

New production application files must be added to `deploy/package-files.txt`.
This deployment allowlist differs from the repository: tests, examples, and
contributor tools belong in source control but not in the installed service.

## Sharing and security

Use synthetic data in screenshots, fixtures, and issue reports. Never attach a
household database, runtime dump, device registry, secret file, or old project ZIP.
See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

Contributions are provided under the repository's MIT license. Preserve all
existing third-party attribution and license notices.
