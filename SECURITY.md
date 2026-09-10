# Security

Den is a private, single-household application. It has no built-in login or
per-record permissions. All people admitted through its network boundary can
read, edit, export, and delete household data.

Use the documented loopback/Tailscale setup for a household deployment. Do not
publish the origin port, enable Funnel for household data, or use the development
server as a public production service. Public demonstrations need their own
disposable data and a separately reviewed access and abuse-control design.

## Report a vulnerability

Use GitHub's private vulnerability reporting feature when enabled for this
repository. If it is unavailable, open an issue asking for a private reporting
channel without posting exploit details, credentials, or household information.
There is no guaranteed response time or commercial support commitment.

## Credentials and updates

Keep keys in private files outside Git. `.gitignore` and the repository checker
help prevent accidents, but cannot revoke an exposed credential. Rotate or revoke
any exposed key at its provider and review affected repository history.

Install dependencies using the hash-locked requirements. Test updates before
deploying and follow Django's supported-release policy. The security model,
limits, and deployment assumptions are documented in [docs/security.md](docs/security.md).
