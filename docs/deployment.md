# Windows deployment and recovery

Doc ID: `deployment`

## Installation

The source checkout is separate from the installed runtime at
`C:\ProgramData\DenHub`. The service runs as `NT SERVICE\DenHub`.
Windows service commands require an elevated PowerShell session.
Use a system-wide Python 3.14 installation whose executable and libraries cannot
be modified by the service identity. Local development does not require elevation.

Prepare your private owner mapping from `config/household-owners.example.json`.
Set `DEN_OWNERS_FILE` and `DEN_PYTHON` in the elevated shell, or provide the
corresponding explicit installer parameters. User-scoped variables are not
automatically inherited across every elevation boundary.

Cache the hash-locked wheels from the repository root:

```powershell
python -m pip download --require-hashes --only-binary=:all: -r infonet/requirements.txt --dest .hardening/wheels
./deploy/den.ps1 Install -Python $env:DEN_PYTHON -OwnersFile $env:DEN_OWNERS_FILE
./deploy/den.ps1 Status
./deploy/den.ps1 Verify
```

A fresh install creates an empty database and applies migrations. It does not
silently copy a source-tree database. To intentionally import an existing Den
database on a fresh install, pass `-ImportDatabase <absolute-path>`. The SQLite
backup API copies it and verifies table fingerprints before migration. Import is
rejected during upgrades or when an installed database already exists.

`deploy/package.py` copies the exact 72-file application allowlist in
`deploy/package-files.txt`, recording SHA-256 hashes. Tests, source archives,
configuration examples, credentials, and databases are excluded. New production
files must be added explicitly. The WinSW binary is checked against
`deploy/vendor-manifest.json`; its MIT notice is in `deploy/vendor/WinSW-LICENSE.txt`.
The installer also retains the Den and WinSW license notices in the runtime root.

## Commands

```powershell
./deploy/den.ps1 Open
./deploy/den.ps1 Status
./deploy/den.ps1 Upgrade
./deploy/den.ps1 Backup
./deploy/den.ps1 Restore -BackupFile <absolute-protected-backup-path>
./deploy/den.ps1 SyncDevices
./deploy/den.ps1 Remove
```

`Open` uses the ignored local bookmark or `DEN_PUBLIC_ORIGIN`; without either,
it opens loopback port 8082. A configured bookmark must be an exact Tailscale HTTPS
origin. `Status` is read-only; protected runtime details require administrator access.

An upgrade builds a fresh dependency environment before stopping Den. It resolves
the installed base Python when no explicit `DEN_PYTHON` is supplied, preserves
the origin and AI flag, and keeps the protected owner mapping and secrets.
It backs up the database before migrations, collects static assets, runs production
checks, then restarts the service. See `configuration.md` for timezone precedence.

If preparation fails, the running release has not been stopped. A later failure
can leave Den stopped for diagnosis; use the protected backup and previous release
for recovery. Never start the obsolete source launcher or replace live data with
a stale development copy.

## Tailscale cutover

A fresh install begins in staging on `http://127.0.0.1:8082`. Configure Tailscale
device approval and a restrictive household policy before exposing it through
Serve. Customize `config/tailscale-policy.example.json`; those addresses and
logins are examples, not working access rules for your network.

Enable HTTPS Serve to proxy to loopback port 8082. Keep Funnel, subnet routes,
exit-node routing, and Tailscale SSH disabled for this application. Use household
logins in the network policy and approve each intended device.

For a new installation with the intended data already in its protected database:

```powershell
./deploy/https-stage.ps1 -Activate
```

This derives the current node's exact Tailscale hostname, checks a supplied
`DEN_PUBLIC_ORIGIN` against it, validates production settings, restarts Den in
HTTPS mode, checks its HTTPS page, and saves the ignored local bookmark.
It changes no household data or network policy. The HTTPS check fails if Serve
has not been configured. Retrying activation after a failed HTTPS check is
documented below; do not transfer a development database to resolve a routing issue.

For historical installations transferring data from the retired port-8080
launcher, the older `https-stage.ps1` without `-Activate` and `cutover.ps1`
workflow is retained. It requires previously captured legacy process evidence.
New installations should not run that host-migration workflow.

Verify each intended device independently, including cellular access where
appropriate. Verify denial for disconnected/unapproved devices and the origin
port. Record actual results privately; one successful device is not proof for
all household devices.

## Home network access

An optional second Waitress process serves the same live database to a trusted
home subnet. Upgrade first, then run these commands in elevated PowerShell with
your server's assigned private IPv4 address:

```powershell
./deploy/den.ps1 Upgrade
./deploy/lan.ps1 Enable -Address 192.168.50.10 -Port 8080
./deploy/lan.ps1 Status
```

The example address is synthetic. The script derives the subnet from the selected
adapter, validates the configuration, and creates `DenHub-LAN`, an inbound TCP
allow rule restricted to that interface, local address, port, and remote subnet.
The rule applies across firewall profiles without changing the adapter's category
and blocks edge traversal. For port 8080 it disables only Den's retired legacy
block rule, because an explicit block would override the scoped allow rule.
No router forwarding or Tailscale policy is configured by this command.

Enabling restarts Den and checks both HTTP listeners. If enabling fails, the
script restores the previous service XML and legacy rule state, removes its new
allow rule, and restarts the original configuration. Existing configured networks
must be disabled before changing their address. Keep the host's DHCP reservation
stable and reconfigure LAN access if its assigned address or subnet changes.

The LAN worker runs under the existing restricted service account. Python's
`spawn` process mode gives it separate Django settings; it shares the same release,
database, quotas, AI lease, backup schedule, and upgrade/restore lifecycle.
A supervisor retries LAN worker failures after ten seconds while the Tailscale
worker remains available. Stopping Den stops both listeners. Log files are
separate and bounded: `requests.log` and `requests-lan.log`.

Verify the page and a form submission from an actual second home device without
Tailscale. A request from the server alone does not verify inbound firewall
traversal, Wi-Fi isolation, or a managed laptop's network policy. Confirm denied
requests from outside the configured subnet and reject spoofed identity headers
with isolated tests. Preserve live evidence privately.

To return to Tailscale-only access:

```powershell
./deploy/lan.ps1 Disable
```

This clears the optional listener configuration, removes its allow rule, restores
the legacy block if present, and restarts Den. It changes no household records.

References: [Python process isolation](https://docs.python.org/3/library/multiprocessing.html),
[Windows firewall rule precedence](https://learn.microsoft.com/en-us/windows/security/operating-system-security/network-security/windows-firewall/rules).

## Secrets

The installer generates a Django key and disables AI export. Import an existing
OpenRouter credential from an elevated shell containing its process environment
variable:

```powershell
./deploy/set-ai-key.ps1 -FromEnvironment
```

Omit the switch for a hidden prompt. `-ProtectedKeyFile` supports a CurrentUser
DPAPI handoff across elevation; the importer consumes that file. Never place
keys in arguments, repository files, or issue reports. The importer updates the
protected secret file, enables AI, and restarts Den. Revoking a retired credential
is a separate provider action. Plain export needs no key.

## Service

WinSW starts Den automatically with delayed startup. Failure restarts wait
10, 30, then 60 seconds; repeated failures retain the 60-second delay, and the
failure count resets after one hour. The only retained explicit service privilege
is SeChangeNotifyPrivilege.

Administrators and SYSTEM control the runtime root. Den reads code, dependencies,
configuration, and the device map, and writes only data, logs, and temporary files.
Backups are separately protected. Request logs contain status/timing and fixed
error categories, rotate at 2 MB, and retain four previous files. They contain no
request bodies or keys. This is a Windows access boundary, not a VM sandbox.

## Identity verification

`Verify` briefly stops Den, runs a fixed probe under the actual SCM identity,
then restores and restarts the application in a finally block. It tests denied
access to private profile/code/secret/backup/map writes and permitted temporary
and database writes. Missing targets do not count as denial proof. The report
in `C:\ProgramData\DenHub\logs\identity-probe.json` is private runtime evidence.

`verify_comments.py` derives the current host and author from Tailscale and the
protected registry. Its synthetic workflow checks attribution, forged headers,
CSRF, text escaping, timestamps, backup/restore, and cleanup. It writes temporary
records, so run it deliberately during an authorized deployment verification.

## Device map

A SYSTEM task refreshes the protected registry once per minute and at startup.
It runs only the fixed Tailscale status command with a 15-second timeout. Tagged,
unknown-owner, and removed nodes are excluded. Registry files are replaced
atomically, expire after five minutes, and cannot be changed by Den.

Fresh installation copies a validated private owner mapping into protected storage.
Upgrades preserve it. Update that protected mapping as an administrator, then run
`SyncDevices` when household membership changes. Names are configurable; login
and approved-device matching still gate attribution. Historical author snapshots
remain unchanged.

## Recovery

The SYSTEM backup task runs daily at 03:00 local time, including missed starts.
It uses SQLite's backup API, checks integrity, and records counts and complete
row hashes for shopping, recipes, meals, projects, and comments. Backups older
than 30 days are pruned. The app cannot read or modify them.

Restore accepts only a protected backup path. It creates an isolated candidate,
applies migrations, verifies fingerprints, then stops Den, takes a fresh backup,
copies the verified candidate, and restarts. Older backups without comments treat
the missing comments table as empty. Device maps regenerate separately.

`recovery-check.ps1` exercises restore, scheduled execution, and service recovery
only before production cutover. It refuses to terminate a live production service.
Removal unregisters Den and its tasks and preserves data and backups.

A failed HTTPS activation may leave production settings enabled before its network
check succeeds. Correct the Serve configuration and re-run `https-stage.ps1 -Activate`;
it accepts the same already-configured production origin for this retry.
