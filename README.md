# Manual Dispatch

Manual Dispatch is an operational dispatch system for planning deliveries and
OP SHOP pickups, allocating drivers and vehicles, and keeping run-sheet history.
It combines a browser workspace, a FastAPI backend, SQLite-backed state, and
optional read-only Attaché invoice integration.

## Overview

The application separates two business workspaces:

| Workspace | Operational unit | Planning and history |
| --- | --- | --- |
| Delivery | Customer delivery order | Delivery Task Pool, driver trips, Delivery Run Sheets and closeout |
| OP SHOP | Pickup task from a schedule or manual request | Regular, Oncall and Countryside planning, Pickup Collections |

Operators review tasks, allocate work, generate documents and save historical
snapshots. Delivery and pickup dates determine their respective Trip Summaries;
these are not simply summaries of when a record was created.

## Key Features

### Delivery

- Create and edit orders, delivery details, urgency, product lines and load totals.
- Filter the Delivery Task Pool and prioritize urgent orders.
- Classify delivery areas as South East or Local from suburb/postcode data.
  Unresolved locations remain visible in Needs Area Review.
- Move orders between areas with a persistent manual override. Changing the
  actual suburb/postcode clears that override; unrelated edits preserve it.
- Assign and unassign orders to driver/date/trip allocations with vehicle details.
- Generate Delivery Run Sheets, review them, save them, and reopen Saved History.
- Export individual or daily/multi-driver run sheets to Excel.
- View delivery-date-scoped Trip Summaries.

On Delivery board load, eligible ACTIVE, unassigned orders dated today or earlier
roll forward to the next weekday after the Melbourne business date. Reserved
orders are excluded. This is request-driven, not a midnight background scheduler;
the weekday calculation does not include a public-holiday calendar.

#### Run-sheet lifecycle and closeout

Generating a run sheet captures a document snapshot and reserves its orders.
Saving retains that snapshot in history. Generated sheets can be cancelled;
reserved work cannot be freely reassigned while the sheet remains active.

A saved, open run sheet can be closed once with an outcome for every row:

| Outcome | Effect on live work |
| --- | --- |
| `DELIVERED` | Finalizes the order and removes its live assignment; a note is optional |
| `RETURN_TO_POOL` | Returns the order to ACTIVE/unassigned status with a return reason and later delivery date |

The next delivery date must be later than the sheet's original date. The
`OTHER` return reason requires a note. Closeout stores outcomes separately and
does not rewrite the saved document rows. A closed sheet remains historical
evidence, while its returned orders can be planned again.

### OP SHOP

- Regular pickup schedules with source weekday, frequency and route sequence.
- Oncall pickup requests created when work is needed, not automatically recurring.
- Countryside route groups and group-oriented assignment workflows.
- Driver/date/trip planning and pickup-date-scoped Trip Summaries.
- Pickup Collection generation, saving, Saved History and Excel export.

Regular generation follows each schedule's source weekday. Weekly and twice-weekly
rules use the available source schedule rows; monthly rules with a supported
ordinal weekday generate on that occurrence. Missing or unknown frequency rules
are skipped with warnings rather than guessed.

**Fortnight limitation:** current REGULAR schedules marked Fortnight remain
visible every week, preserving their original frequency label. They are not
automatically hidden on alternate weeks. Legacy STANDARD schedules have separate
A/B fortnight handling; do not treat these two generation paths as equivalent.

Generated Pickup Collections reserve their tasks but allow operational entry
updates: clothing/shoe weights, time in/out, trolley counts, toy counts and bag
counts. Saving makes those entries read-only in history. Generated collections
can be cancelled. This differs from Delivery closeout; a Pickup Collection is
not a Delivery Run Sheet.

### Import Workflows

These are four separate workflows, not one combined parser:

| Workflow | Input | Purpose |
| --- | --- | --- |
| Import Attaché PDF | Uploaded invoice PDFs | Extract and review invoice/order data before selected import |
| Import Delivery Docket | Uploaded DOCX dockets | Parse delivery instructions, addresses, products and loads |
| Import from Attaché | A single invoice number | Direct lookup through the configured read-only Bridge |
| Import Today & Future Invoices | A date-scoped Bridge preview | Review and import eligible current/future invoices in a batch |

Preview and operator review precede import. Duplicate checks protect against
re-importing existing invoice identities. Imports create Manual Dispatch records;
they do not update the source invoice in Attaché.

#### Today & Future Invoices

The preview starts from the Melbourne business date and includes invoices dated
on or after that date, with a maximum batch of **200 invoices**.

Account Terms determine payment eligibility:

- `30 DAYS`: payment is not required for this import gate.
- `C.O.D.` (including normalized `COD`): the invoice outstanding balance must
  be paid in full. The implemented decimal tolerance is `0.005`; a balance at
  or below it, including a credit balance, qualifies.
- Unsupported terms or an unavailable/invalid required balance fail closed.

Preview rows distinguish Ready, Duplicate, Payment Required and Needs Review.
Select all ready only selects eligible rows; payment-blocked and review-required
rows are not made eligible by a browser checkbox.

The server signs a 15-minute eligibility snapshot covering source, invoice
number, customer code, terms, outstanding balance, preview/from date and timing.
Commit verifies that proof, rechecks eligibility and local duplicates, and
rejects missing, altered or expired proofs. Commit does not reconnect to
Bridge/ODBC. The proof attests to the preview snapshot, not a fresh balance read
at commit time. This gate is specific to Today & Future; it does not change
PDF, Docket or single-invoice Direct import semantics.

#### Delivery Docket Import

The DOCX parser uses document structure rather than a list of customer-specific
templates. It handles physical delivery/drop-off sections, ON FORWARD and final
customer sections, inline address layouts, customer/contact extraction, and
product/load information including pallets, bags and cartons.

Physical drop-off details are distinguished from the final customer's identity.
Ambiguous or unsupported values are surfaced for review instead of silently
inventing an address or quantity. Preview corrections remain subject to
revalidation before import.

## Architecture

```text
Browser: HTML/CSS + JavaScript modules
  -> FastAPI routes
     -> Application/domain services
        -> Repository interfaces and SQLite implementation
           -> SQLite database
        -> File-based operational Logbook

Manual Dispatch backend
  -> HTTP Bridge client
     -> Attaché Bridge on Windows
        -> ODBC
           -> Attaché / FairCom (SELECT-only queries)
```

- **Frontend:** same-origin static files served by FastAPI; API clients, actions,
  state and render modules implement the workspaces without a frontend build step.
- **API:** `backend/api/manual_dispatch.py` composes authentication and protected
  route factories under `/api/manual-dispatch`.
- **Services:** the service facade delegates business workflows, validation,
  snapshots and audit recording to focused modules.
- **Repositories:** SQLite persists application state; an in-memory implementation
  supports isolated tests. Repository boundaries keep storage out of UI code.
- **Bridge:** a separate process isolates Windows ODBC dependencies from the
  Manual Dispatch application host. It is not bundled into the application image.

## Repository Structure

```text
backend/
  api/manual_dispatch_routes/   HTTP route factories
  services/manual_dispatch/    Business rules and application services
  repositories/                SQLite and in-memory repositories
  db/                          Schema and connection/upgrade helpers
  integrations/                Server-side integration clients
  data/                        Versioned reference data, not the live database
attache_bridge/                Read-only invoice API, ODBC adapter and launcher
frontend/
  js/                          API, action, state, render and utility modules
  styles.css                   Shared styling
tests/                         Backend, integration and frontend contract tests
tools/                         Migration, validation, audit and deployment helpers
docs/                          Specifications and operational runbooks
.github/workflows/             CI configuration
```

`Dockerfile`, `docker-compose.yml`, dependency files and
`attache-bridge.spec` live at the repository root. Runtime `data/`, local
workbooks, logs, databases, build outputs and temporary QA files are not source
architecture and must not be committed.

## Data and Persistence

The default SQLite database is `data/manual_dispatch.sqlite3`, configurable
with `MANUAL_DISPATCH_DB_PATH`. SQLite stores orders, pickups, assignments,
operator accounts and document snapshots. Attaché integration is query-driven:
selected imports become application records, not a wholesale copy of Attaché.

Repository initialization creates the schema and applies compatibility upgrades.
Existing database transitions also have explicit migration tools for legacy
workspace separation and H5 invariants. Startup is not a substitute for a
reviewed migration plan, and not every compatibility upgrade is purely additive.
Back up and rehearse against a disposable copy before upgrading existing data.

Connections enable foreign keys, WAL and a busy timeout. Mutating workflows use
transactions, including immediate transactions where required, and report
state-change conflicts rather than silently overwriting competing assignments.

The Logbook is a separate append-oriented, monthly JSON-lines text audit trail.
Its default directory is `data/logbook`, configurable with
`MANUAL_DISPATCH_LOGBOOK_DIR`. Audit writes are best-effort and failures are
logged; the Logbook is not a replacement for database backups.

## Authentication and Security

Business API routes require an authenticated operator. Registration/login and
the public health endpoint have separate access rules. Operator passwords are
stored as salted PBKDF2 hashes. Sessions use a signed, expiring HttpOnly cookie
with SameSite=Lax; secure-cookie behavior is configurable.

Set a stable, private `MANUAL_DISPATCH_AUTH_COOKIE_SECRET` for deployment.
The process-local random fallback is for unconfigured development, not a
production configuration: restarting changes the signing key and invalidates
sessions and outstanding preview proofs.

Registration is disabled by default. Password reset requires the separately
configured `MANUAL_DISPATCH_ADMIN_RESET_CODE`. API documentation is disabled
unless explicitly enabled. These controls do not replace TLS, network access
restrictions or host security.

The backend authenticates Bridge requests with a shared token. Invoice query
paths are designed to be SELECT-only, and invalid authorization, ambiguous
results or eligibility uncertainty fail closed.

## Local Development

Python **3.12** is used by CI and the Docker image. Node.js **20** is used for
JavaScript validation, not for serving or building the frontend.

From the repository root, in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Use disposable local storage, separate from any operational checkout:

```powershell
$DevRoot = Join-Path $env:TEMP "manual-dispatch-dev"
$env:MANUAL_DISPATCH_DB_PATH = Join-Path $DevRoot "manual_dispatch.sqlite3"
$env:MANUAL_DISPATCH_LOGBOOK_DIR = Join-Path $DevRoot "logbook"
$env:MANUAL_DISPATCH_AUTH_COOKIE_SECRET = & .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
$env:MANUAL_DISPATCH_SEED_DEMO_DATA = "false"
$env:MANUAL_DISPATCH_ALLOW_REGISTRATION = "true"
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open [the local workspace](http://127.0.0.1:8000/frontend/), register the initial
local operator and sign in. Stop the server, set
`MANUAL_DISPATCH_ALLOW_REGISTRATION=false`, then restart with the same secret.
The example secret is generated in memory; never print, commit or share its value.

Plain Uvicorn uses the command-line host/port above. The Docker launcher consumes
`MANUAL_DISPATCH_HOST` and `MANUAL_DISPATCH_PORT` instead. Environment settings
must be provided to the process; the plain Uvicorn command does not load a
project `.env` automatically.

Other supported application settings include:

| Variable | Purpose |
| --- | --- |
| `MANUAL_DISPATCH_AUTH_COOKIE_SECURE` | Enable secure cookies behind HTTPS |
| `MANUAL_DISPATCH_ADMIN_RESET_CODE` | Enable the operator password-reset code |
| `MANUAL_DISPATCH_ENABLE_API_DOCS` | Opt in to API documentation |
| `MANUAL_DISPATCH_ENABLE_LEGACY_MUTATIONS` | Opt in to legacy mutation endpoints |

## Attaché Bridge Setup

Direct and Today & Future imports require a separately configured Windows Bridge
with compatible Python/ODBC architecture, the FairCom ODBC driver and an approved
read-only connection configuration. PDF and DOCX upload parsing do not need ODBC.

Configure these names through private environment configuration; no real values
belong in source control:

| Process | Environment variables |
| --- | --- |
| Manual Dispatch | `ATTACHE_BRIDGE_URL`, `ATTACHE_BRIDGE_API_TOKEN`, `ATTACHE_BRIDGE_TIMEOUT_SECONDS` |
| Bridge | `ATTACHE_ODBC_CONNECTION_STRING`, `ATTACHE_BRIDGE_API_TOKEN`, `ATTACHE_BRIDGE_CONNECTION_TIMEOUT_SECONDS`, `ATTACHE_BRIDGE_QUERY_TIMEOUT_SECONDS` |

The shared API token must agree on both sides. In a separate Windows environment,
install and run the Bridge after configuring those variables:

```powershell
python -m pip install -r attache_bridge/requirements.txt
python -m attache_bridge.launcher --host 127.0.0.1 --port 8787
```

The tracked PyInstaller specification also supports a Windows executable build:

```powershell
python -m pip install -r attache_bridge/requirements-build.txt
python -m PyInstaller attache-bridge.spec
```

Keep the Bridge on an approved private network path; do not expose it publicly.
See the [Attaché integration guide](docs/attache-direct-invoice-lookup.md) for
configuration, packaging, controlled smoke tests and failure behavior.

**Schema validation boundary:** Current/Future SQL currently reads
`admin.invoice_header.termsdescription`. A real SELECT-only discovery of
`admin.InvoiceHeader.termsdescription` does not prove that the underscored object
is equivalent. Validate the exact deployed object/column combination through an
authorized SELECT-only smoke test before relying on this workflow operationally.

## Running Tests

Use a disposable checkout with no business database or Logbook. Install
`requirements-dev.txt` first. The full unittest discovery bootstraps isolated
test storage; do not point tests at production data or a live Bridge.

Focused parser regression suite:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_delivery_docket_docx_parser.py" -v
```

Full suite and the static checks used by CI:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall backend tests tools
Get-ChildItem frontend -Recurse -Filter *.js | ForEach-Object {
    node --check $_.FullName
    if ($LASTEXITCODE -ne 0) { throw "JavaScript syntax check failed" }
}
git diff --check
```

The suite includes backend behavior, repository/integration tests and frontend
contracts. Attaché-facing tests use fake/injected infrastructure; normal tests
do not require live Attaché. Automated tests are distinct from a manual browser
test, a frozen Bridge EXE test, or an authorized real ODBC smoke test.

## Deployment and Operational Safety

The Docker image runs FastAPI and serves the frontend. Compose provides the
application service, persistent database/Logbook storage and backup mounts.
The Bridge remains a separate Windows service/process. Deployment commonly uses
an internal NAS host and a controlled reverse proxy.

- Provide stable secrets privately and configure secure cookies with HTTPS.
- Stop relevant application processes before maintenance; coordinate database
  backups and migrations rather than copying a live SQLite main file alone.
- Use SQLite Backup API backups that include committed WAL contents, verify
  integrity and rehearse migrations on copies before touching operational data.
- Do not use production databases or the formal Logbook for tests.
- Never commit SQLite files, Logbook contents, business DOCX/PDF/workbooks,
  connection strings, tokens or packaged Bridge executables.
- Attaché access remains read-only, but Bridge/ODBC sessions may still count as
  active company access for Attaché Archive. Stop the Bridge before Archive and
  coordinate the operation with the responsible operator.
- Validate local application behavior, network access and the exact ODBC query
  path separately. A passing automated suite does not prove deployment readiness.

Follow the deployment and migration runbooks below; this README is not an
authorization to migrate data, expose a service or deploy to a production host.

## Documentation

- [Code structure](docs/manual-dispatch-board-code-structure.md)
- [Delivery / OP SHOP workspace specification](docs/separate-delivery-and-opshop-workspaces-spec.md)
- [Workspace migration](docs/separate-delivery-and-opshop-workspaces-migration.md)
- [Attaché integration and Bridge](docs/attache-direct-invoice-lookup.md)
- [OP SHOP workspace smoke checklist](docs/opshop-workspace-smoke-test-checklist.md)
- [OP SHOP Collection / summary smoke checklist](docs/opshop-final-summary-smoke-test-checklist.md)
- [H5 invariants and migration hardening](docs/final-production-hardening-h5.md)
- [NAS deployment and internal DNS](docs/nas-cpanel-internal-dns-deployment.md)
- [NAS validation checklist](docs/nas-deployment-validation-checklist.md)
- [NAS release update checklist](docs/nas-release-update-checklist.md)
- [Logbook reader](tools/read_logbook.py) and [integrity checker](tools/check_logbook_integrity.py)
- [CI workflow](.github/workflows/ci.yml)

Phase-specific documents preserve historical decisions and may describe older
screens or rollout states. Check the current code and target release before
executing a historical operational procedure.

## Status

The repository implements the two workspaces, saved document lifecycles, Delivery
closeout, four import paths and read-only Bridge integration described above.
Automated regression coverage accompanies these features. Real environment
validation, operational data review and deployment approval remain separate
release activities; no blanket production-readiness claim is implied.
