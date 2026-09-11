# Configuration

Doc ID: `configuration`

## Local settings

Environment variables point to private files and choose non-secret settings.
Den does not load arbitrary .env files or shell scripts automatically. For
PowerShell, copy `config/local.example.ps1` to `config/local.ps1`, customize it,
then dot-source it in the session used to run commands. The real file is ignored.

Only example files in `config/` are included in Git. Private owner mappings,
secrets, data, runtime logs, and bookmarks are excluded. Existing installations
may retain ignored `deploy/household-owners.json`, `deploy/tailscale-policy.json`,
and `deploy/live-url.txt` for local compatibility.

Do not put secrets in machine-wide environment variables. Use `DEN_SECRET_FILE`
to point to a protected JSON file. Environment variables are a configuration
interface, not an encryption or access-control mechanism.

## Development

`python scripts/dev.py` creates a separate development data directory, applies
migrations, collects local static assets, runs system checks, and starts Django on `127.0.0.1:8085`.
Use `--port` to select another local port or `--check` to initialize without
starting the server. It refuses staging/production mode and the legacy source
database directory or a DenHub runtime path. `DEN_DATA_DIR` may select another
dedicated development directory; otherwise it uses `.local/data`.

The development server uses `--insecure` solely to serve local static assets
while DEBUG stays false. It is bound to loopback and is not the production server.
The application cannot distinguish an arbitrary renamed copy of private data:
always choose a dedicated development database.

## Household owners

Copy `config/household-owners.example.json` to a private JSON file and replace
the example logins and names. Set `DEN_OWNERS_FILE` or pass `-OwnersFile` to the
Windows installer. It validates and copies the mapping into protected
`C:\ProgramData\DenHub\identity\owners.json` during initial installation.

A mapping has 1–64 lowercase, printable, trimmed login keys, each 1–254 characters,
and printable, trimmed display names of 1–64 characters. Duplicate display names
are allowed, because one person may use multiple accounts. The map grants no
Tailscale access; the network policy and device approval remain separate.

On upgrade, the existing protected mapping wins and is not overwritten by source
examples, environment changes, or a new input file. Change that protected file
deliberately as an administrator when household membership changes, then run
`deploy/den.ps1 SyncDevices`. Historical comments keep their saved author names.

### Device-specific names

Devices sharing one Tailscale login can have different comment names. Optional
`C:\ProgramData\DenHub\identity\device-owners.json` maps stable enrolled node IDs
to an expected `login` and an `author`. Use `config/device-owners.example.json`
as a format reference; its node ID is synthetic. Configure the real file as an
administrator, then run `SyncDevices`. Never edit generated `devices.json` directly.

Assignments override only the selected node's display name. The node must still
have a recognized household login, remain enrolled, and have no tags. Its actual
login must match the assignment's expected login; a mismatch excludes that node
until an administrator corrects the assignment. Other nodes retain their account
defaults. Renaming a device or changing its IP does not change its stable-ID
assignment; re-enrollment under a new node ID requires a new assignment.

The file may be absent or contain an empty object. At most 64 assignments are
accepted, with the same login/name validation used for household owners. Invalid
assignments fail the map refresh; the previous map then expires normally. The
application cannot write this protected file, and upgrades preserve it. Historical
comment authors remain unchanged. Validate a proposed file with
`python deploy/sync_devices.py --validate-device-owners <private-file>`.

## Environment variables

See `schema/security_config.csv` for the full contract.

| Variable | Purpose |
| --- | --- |
| `DEN_ENV` | development, staging, production, or the supervised lan worker |
| `DEN_DATA_DIR` | Directory containing the SQLite database |
| `DEN_PUBLIC_ORIGIN` | Exact production HTTPS origin; also an optional launcher bookmark |
| `DEN_LAN_ORIGIN` | Optional exact private IPv4 HTTP origin for the additional LAN worker |
| `DEN_LAN_SUBNET` | Canonical RFC 1918 IPv4 subnet allowed to reach the LAN worker |
| `DEN_SECRET_FILE` | Private JSON containing `django_secret` and optional `openrouter_api_key` |
| `DEN_OWNERS_FILE` | Private owner mapping used only on initial Windows installation |
| `DEN_PYTHON` | Absolute system-wide Python executable for Windows installation |
| `DEN_DEVICE_MAP_FILE` | Protected registry generated from enrolled Tailscale devices |
| `DEN_DISPLAY_TIME_ZONE` | IANA time zone used to display comments; defaults to America/New_York |
| `DEN_AI_ENABLED` | 1 enables optional AI export only when a key is also present |
| `OPENROUTER_API_KEY` | Development-only environment override, or input to the protected key importer |

The service does not inherit interactive user variables. The installer writes
explicit environment settings into the protected WinSW configuration. Upgrades
preserve the installed origin, AI flag, existing owners, secrets, and data.
An explicit `DEN_DISPLAY_TIME_ZONE` changes the service's display zone during
upgrade; otherwise its saved zone is retained, with the historical default used
for older installations. UTC storage never changes.
The optional LAN origin and subnet are also preserved on upgrades. Configure them
through `deploy/lan.ps1`; the installer does not import an interactive LAN override.

The standard Windows runtime path is fixed deliberately so service ACLs, backup
tasks, and recovery tools share one boundary. It is not a household identifier.

## Home network access

LAN access is optional and disabled by default. `deploy/lan.ps1 Enable` records an
explicit HTTP origin such as `http://192.168.50.10:8080` and the selected adapter's
subnet in protected service configuration. Use your own assigned home address.
The origin must contain an RFC 1918 IPv4 address and port 1024–65535 except 8082;
credentials, paths, queries, fragments, hostnames, wildcard binds, network/broadcast
addresses, and noncanonical subnets are rejected. The address must belong to the
configured private subnet. Both values are required together.

The service starts a separate process with `DEN_ENV=lan`, sharing the installed
release, secret file, database, write budgets, and AI lease. It uses HTTP cookies
without the Secure flag and never enables HSTS or HTTPS redirects. The production
worker keeps its HTTPS-only settings and separate cookies at the Tailscale host.
LAN is a deployed mode: external strong secrets and an absolute data directory
remain mandatory; development seeding and environment API-key overrides are refused.

LAN clients can use household features and read comments. They cannot post named
comments because there is no verified Tailscale identity. Forwarded identity
headers are discarded, and comments fail closed even if a client supplies them.
HTTP traffic is unencrypted. Enable this only for a trusted home network; Den has
no login and all admitted devices can edit shared records.

## Secrets and optional AI

The example secret file contains empty values and cannot start staging or
production. The Windows installer generates a strong Django secret automatically.
For a custom staging environment, generate one with
`python -c "import secrets; print(secrets.token_urlsafe(64))"` and place it in
your private file without committing it.

AI export is disabled by default. The deployed service reads only its protected
secret file; importing a key is described in `deployment.md`. The local
`OPENROUTER_API_KEY` override is ignored in staging and production. Never put a
real key into a checked-in example, issue, screenshot, or command argument.

## Sample data

`python infonet/manage.py seed_demo` uses `DEN_DATA_DIR` and accepts only an
empty development database. It inserts synthetic projects, groceries, and
recipes inside one transaction. Existing household rows or staging/production
mode cause an error before any write. Repeating the command on seeded data also
fails without duplicating or replacing records.

## Verification

Run `python scripts/check.py`. Tests exercise configured author names, invalid
registry labels, display zones, protected metadata, and safe demo initialization.
A clean source snapshot should pass installation, migrations, tests, and static
source checks without any local household files. These checks do not certify a
new Windows service deployment or a public internet exposure.
