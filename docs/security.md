# Den security

Doc ID: `security`

## Boundary

Tailscale is the default access gate; optional LAN access admits the configured
trusted home subnet. Den intentionally has no household login. An
authorized network intruder can read, edit, export, and delete household records.
Application hardening mitigates injection and resource abuse. A restricted
Windows service identity separates Den from the owner's private profile.
This is not a VM sandbox and does not contain compromise of Windows, the
privileged Tailscale daemon, or another privileged local service.

The documentation protocol is in `docs/AGENT_SKILL.md`. Configuration examples
are public; credentials, household registries, and deployment evidence remain private.

## Configuration

See `schema/security_config.csv`. Development binds to loopback through `serve.py`
and generates a process-local secret if none is supplied. Staging requires an
external secret and absolute data-directory paths and allows loopback HTTP only. Production additionally requires
one exact HTTPS origin, without a trailing slash, credentials, path, or port.
Debug is disabled in every mode. No admin or login route is installed.

`DEN_SECRET_FILE` points to UTF-8 JSON containing `django_secret` and optional
`openrouter_api_key`. Invalid files or weak production/staging keys prevent
startup. Never log the document. Smart Export is disabled unless both an explicit
enable flag and OpenRouter API key are present. Development also accepts the
`OPENROUTER_API_KEY` process environment variable; deployed settings require the
protected file. The formerly embedded Anthropic
key must be revoked at the provider; deleting local copies is not revocation.
Never publish old backups; they may contain credentials or household information.

Waitress listens on `127.0.0.1:8082`: four threads, 32 connections, 30-second
inactive-channel timeout, 16 KiB headers, and 256 KiB bodies. Production fixes
the WSGI scheme to HTTPS because its only intended caller is the local TLS proxy.
Only the loopback proxy's X-Forwarded-For header is trusted, for comment attribution.
Other forwarding headers are removed; forwarded host/scheme remain ignored.
The Serve user login must match the device's owner in a fresh protected node map.
Identity confers no resource-limit bypass or additional Windows privileges.
Do not expose the origin listener or replace exact hosts with a wildcard.

HSTS covers this host for one year. Preload and subdomain coverage are deliberately
disabled, as requested. Only the corresponding Django checks W005 and W021 are
silenced; all other deployment warnings remain fatal during release verification.

## Home network access

LAN access is an explicit exception to the default Tailscale-only boundary.
A separate process binds one configured RFC 1918 IPv4 address and port, with a
Windows firewall allow rule scoped to the home interface and subnet. Application
middleware independently checks the actual socket peer and exact Host including
port before static files, CSRF, views, or database writes. Forwarded addresses
cannot bypass that check; Tailscale and forwarding headers are discarded.
The LAN process never trusts a proxy or assigns a comment identity.

This listener uses unencrypted HTTP and non-Secure SameSite=Strict cookies.
CSRF tokens and same-origin checks still apply to every POST. It does not trust
the HTTPS origin for LAN POSTs. The existing Tailscale process retains HTTPS,
Secure cookies, HSTS, and device-based comment attribution. Both processes share
database-backed resource limits; accessing two addresses grants no second quota.
Do not forward the LAN port to the internet or enable it on an untrusted subnet.
Configuration, lifecycle, rollback, and verification are in `deployment.md`.

## Requests and limits

CSRF middleware checks every POST before the write budget. GET/HEAD are read-only;
mutation-only routes reject them with 405. Uploaded files and requests with over
100 fields are rejected. Bodies exceeding 256 KiB return 413. Ordinary form
validation retains the form and its errors; invalid operation parameters return
400. Unknown record IDs return 404, including values outside SQLite's ID range.
Rate limits return 429 and Retry-After. Database contention returns 503.

Planner inputs are explicit ISO dates in 1900-01-01 through 2100-12-31. Generation
and shopping ranges contain 1–365 inclusive days. Omitted generation inputs retain
the existing today/60-day defaults; supplied invalid values never select defaults.
Shifts preflight all destination dates before updates. ORM queries use fixed
fields and bound parameters, never user-supplied SQL or Python.

See `schema/security_limits.csv` for exact form, row, and request limits.
Quotas and writes use SQLite IMMEDIATE transactions, obtaining the write lock
before reading counts. Bulk additions reject the entire operation at a limit.
At a cap, existing records remain editable and deletable. Existing data is not
truncated. Direct ORM writers must validate explicitly; HTTP forms are the public
write interface. Download-and-clear constructs its response and deletes only
the selected IDs inside one transaction.

## Persistent state

Migration 0007 adds field validators and a fixed, one-row `SecurityState` table;
0008 seeds its row. Both must be applied before starting the hardened service.
See `schema/security_state.csv`. The table is never reset on process startup.

The global budget permits 60 POSTs per UTC-aligned minute; expensive planner
generation and shift operations share a six-per-minute sublimit. These are fixed
windows, so a boundary may allow bursts across two windows. Spoofed client
addresses, cookies, and identity headers cannot obtain additional budgets.

## AI export

Only list text and the dedicated provider credential enter a fixed worker command.
The worker has no model tools, URL input, or shell command interface. It calls
only `https://openrouter.ai/api/v1/chat/completions`, disables environment proxies and redirects,
uses zero retries, 1,024 output tokens, and a 25-second transport timeout.
The parent enforces a 30-second process deadline and kills a timed-out worker.
Input/output are limited to 32 KiB and communicated through pipes, never command
arguments. The parent invokes Python directly without a shell.

The fixed model is `deepseek/deepseek-v4-flash-0731`. Its pinned routing uses `deepinfra/fp8` provider order, fallback disabled, required
parameter support, and reasoning disabled. The HTTP client performs no retries.
Responses are streamed into a 128 KiB maximum buffer before JSON parsing.
Empty, non-text, truncated, or oversized completions fall back to plain export.
The Anthropic SDK and its exclusive dependencies are absent from new releases.
Source settings accept no model, destination, provider, or tool selection from
an HTTP request. Routing changes require a code review, test, and deployment.

References: [OpenRouter chat API](https://openrouter.ai/docs/api/api-reference/chat/send-chat-completion-request),
[DeepSeek V4 Flash 0731](https://openrouter.ai/deepseek/deepseek-v4-flash-0731).

On Windows it invokes the base interpreter directly and explicitly supplies the
protected, pinned virtual-environment library path. The virtual-environment
launcher can spawn a child that survives termination of the launcher. A real
stalled-worker test verifies the direct process is dead after the deadline.

A SQLite lease permits one export at a time. It expires after 35 seconds to
recover from a dead parent; a token prevents an old completion releasing a newer
lease. All started attempts, including failures, count toward the global cap of
20 per UTC day. Requests rejected before acquiring a lease do not count.
Provider output is served as a Markdown attachment and never executed or rendered
as HTML. Provider errors yield the plain list, preserving stored items.

## Browser

Application JavaScript and CSS are local. The former jQuery/Bootstrap JavaScript
dependencies are replaced by small local handlers for navigation and modals.
Modal controls support Escape, focus trapping, focus restoration, and background
inertness. `DenModal.open(element, trigger = document.activeElement)` accepts the
opening control explicitly for browsers that do not focus clicked buttons.
Confirmation handlers use fixed data attributes. Form/model text is
automatically escaped and is never interpolated into scripts.

The enforced CSP allows only local script/style/font/network sources, local/data
images, same-origin forms, and no objects, frames, base URLs, or inline execution.
Permissions Policy disables camera, microphone, geolocation, payments, and USB.
HTML and downloads are no-store. Browser cookies are SameSite=Strict; production
cookies are Secure. The CSRF cookie remains readable to the existing fetch helper.
Referrer Policy is same-origin: it preserves Django's HTTPS CSRF referer checks
while withholding referrers from other sites. CSRF rejection logs contain only
a fixed origin/referer/token category, never the rejected header or token.

Local Bootstrap CSS and Nunito fonts retain their licenses. Sources and SHA-256
hashes are in `deploy/vendor-manifest.json`; no vendor JavaScript executes.

## Verification

Run tests using the locked Python environment and a temporary file-backed SQLite
test database; in-memory databases skip the real concurrency scenarios.
`myapp.test_security` covers hostile text, forms, CSRF, host/header handling,
request sizes, dates, quotas, race conditions, leases, restart persistence, and
AI fallback with a mocked provider. No live AI request is necessary for this suite.

Production settings checks, browser workflow/CSP checks, live service-account
permission probes, backup restore comparisons, and external Tailscale access tests
are separate evidence. Passing one is not evidence that another passed.

## Dependency maintenance

Runtime requirements are exact versions with distribution hashes for Python 3.14.
Local tests are verified on Windows; CI also checks Linux. The Windows service
installation remains platform-specific. The tested series is Django 6.0. Update to security patches in this
series, resolve and audit the entire dependency closure, refresh cached wheels
and hashes, then run the full verification sequence before upgrading the service.
Do not install packages or modify code from within the service account.
Check Django's support calendar before the 6.0 series reaches end of support.
