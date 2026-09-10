# Den

A small, self-hosted household hub for meal planning, shopping lists, recipes,
and projects. Built with Django, SQLite, and plain HTML, CSS, and JavaScript.

- Generate meal plans from your recipe rotation, with manual choices and skip days.
- Keep a shared shopping list and download it as text or optional AI-organized Markdown.
- Track household projects in an active-first table, with details and comments.
- Run privately on Windows behind Tailscale, or try it locally with sample data.

**Den is designed for one trusted household. It has no application login.**
Everyone admitted through the network boundary can read and change shared data.
Keep the household instance private. Use a separate, disposable database for demos.

## Run locally

Use Python 3.14. From the repository root on Windows:

```powershell
py -3.14 -m venv .venv
.venv/Scripts/python.exe -m pip install --require-hashes -r infonet/requirements.txt
.venv/Scripts/python.exe scripts/dev.py
```

On macOS or Linux, use `python3.14 -m venv .venv`, then `.venv/bin/python` for
the same commands. The app's local workflow uses Python's development server;
the protected Windows service is documented separately.

Open [localhost:8085](http://127.0.0.1:8085/). The launcher applies migrations
to a separate `.local/data/db.sqlite3`, prepares local static assets, checks the
app, and binds to loopback.
Stop it with Ctrl+C. Choose another port with `--port 8086`.
The initial database is empty. No API key, cloud account, or Tailscale setup is
needed to try projects, shopping, recipes, and the planner locally.

### Optional sample data

Initialize the development database, then seed it before starting the server:

```powershell
.venv/Scripts/python.exe scripts/dev.py --check
$env:DEN_DATA_DIR = Join-Path (Get-Location) '.local/data'
.venv/Scripts/python.exe infonet/manage.py seed_demo
.venv/Scripts/python.exe scripts/dev.py
```

The sample command accepts only an empty development database. It refuses to
overwrite existing records or run in staging/production. Comment attribution
requires an enrolled Tailscale device, so anonymous local previews show comments
without enabling posting.

## Your configuration

Copy `config/local.example.ps1` to the ignored `config/local.ps1`, and edit your
copy. Load it in the same PowerShell session before running Den or its installer:

```powershell
. ./config/local.ps1
.venv/Scripts/python.exe scripts/dev.py
```

Environment variables select private files and non-secret settings. API keys and
the Django production key belong in a private JSON file selected by
`DEN_SECRET_FILE`. Household login-to-name mappings belong in a private JSON file
selected by `DEN_OWNERS_FILE` during installation. Only `.example` configuration
files are shared. Files are not automatically loaded as shell code or `.env` files.

The Windows service receives explicit environment settings from its installer;
it does not inherit your interactive user's environment. Existing protected
owners, secrets, and data are preserved on upgrades.

See [configuration](docs/configuration.md), [Windows deployment](docs/deployment.md),
and the [security boundary](docs/security.md). AI export is off by default and
requires an explicit enable flag plus an OpenRouter key. When enabled, shopping
list text is sent to that provider; basic text export works without it.

## Checks and contributions

```powershell
.venv/Scripts/python.exe scripts/check.py
.venv/Scripts/python.exe scripts/repository_check.py
```

Tests use a temporary file-backed SQLite database and mocked AI responses.
They do not modify household records or call a paid provider. CI runs the same
checks on Windows and Linux. See [contributing](CONTRIBUTING.md) for code and docs
conventions, and [verification](docs/hardening-verification.md) for the distinction
between automated checks and live deployment evidence.

## Project layout

| Directory | Contents |
| --- | --- |
| `infonet/` | Django application, migrations, tests, templates, and static assets |
| `config/` | Public examples and ignored local configuration |
| `deploy/` | Windows service installer, backup tools, and deployment allowlist |
| `scripts/` | Local development and repository checks |
| `docs/` | Architecture, security, and data-contract references |

Databases, backups, credentials, local runtime evidence, caches, and unrelated
material are excluded by `.gitignore`. Before publishing, review the exact
candidate files with `scripts/repository_check.py`; do not upload the entire
working directory as a ZIP.

## License

Original project code is available under the [MIT license](LICENSE).
Bundled dependencies retain their own licenses; see [third-party notices](THIRD_PARTY_NOTICES.md).
