# Documentation protocol

Doc ID: `agent_skill`

This file records the project's supplied documentation conventions.

1. Consult relevant `docs/*.md` and `docs/schema/*.csv` before assuming behavior.
2. Keep inline comments at 15 words or fewer. Put longer explanations in docs.
3. Link code to documentation with `# DOC: doc_id#anchor` or the language equivalent.
4. Update docs and schemas in the same change when contracts, configuration,
   pipeline stages, I/O, error handling, or function signatures change.
5. Use synthetic test data and keep private configuration and evidence out of Git.

## Index

| Document | Scope |
| --- | --- |
| `configuration.md` | Environment variables, private files, local setup, sample data |
| `household_projects.md` | Projects, forms, comments, attribution, migrations |
| `security.md` | Access boundary, limits, secrets, browser and AI behavior |
| `deployment.md` | Windows installation, upgrades, backup, restore, Tailscale |
| `hardening-verification.md` | Verification scope and limits |
| `schema/*.csv` | Machine-readable data and configuration contracts |

Run the checks described in `CONTRIBUTING.md`. Update the production package
allowlist when adding application files. Record live deployment evidence privately;
public docs should describe the procedure without household identifiers.
