# Direct Attaché Invoice Lookup

Direct Attaché Invoice Lookup is an optional acquisition path for Delivery
Orders. It does not replace PDF import and does not add an Attaché driver to the
Linux Manual Dispatch container.

## Architecture

The browser sends only an invoice number to the authenticated Manual Dispatch
API. The Manual Dispatch backend calls a small internal HTTP bridge running on
Windows, and that bridge uses six fixed, read-only ODBC statement shapes:

1. `SELECT docnum FROM admin.invoiceheader WHERE 1 = 0` performs zero-row
   schema discovery through `cursor.description`.
2. `admin.invoiceheader` is queried by the Attaché Customer Invoice document
   type (`doctype = 1`) and a bounded sequence of exact `docnum` candidates,
   selecting only `doctype`, `internaldocnum`, and `docnum` for identity.
3. `admin.invoice_header` is queried by that resolved identity for the required
   historical invoice snapshot.
4. `admin.invoiceheaderextension` is queried by the same identity for optional
   historical `deliverypostcode` enrichment.
5. `admin.invoiceheaderextension2` is queried by the same identity for optional
   historical `deliveryaddr2` enrichment.
6. `admin.invoicedetailproduct` is queried by the same identity, ordered by
   `linenum`; product quantity remains `qtyinv`.

The bridge validates the zero-row description's reported `docnum` internal
width and uses it only as an upper bound. Starting with the validated digits,
it generates candidates from no leading spaces through the maximum allowed
leading spaces. Every candidate uses the same parameterized equality predicate;
the bridge never uses wildcard matching, `LIKE` or `TRIM` on `docnum`. Matching
rows are de-duplicated by `doctype` plus `internaldocnum`, and distinct matches
remain a controlled ambiguity. Detail quantities use `qtyinv`.

The historical street, raw delivery suburb, delivery description and customer
fields come only from `admin.invoice_header`. Delivery postcode comes only from
`invoiceheaderextension`, never the billing/customer `invoice_header.postcode`.
Address line 2 comes only from `invoiceheaderextension2`. Either extension row
may be absent; its value then remains blank for manual review. An actual ODBC
failure while querying an extension is still a safe operational failure.
`admin.deliveryaddress` is deliberately excluded because it represents current
master data rather than the invoice-time snapshot. `deliverycountry` is not
mapped because it is not a reliable country field in this Attaché installation.
The Bridge returns the historical `deliverysuburb` text unchanged and does not
invent state data.

`doctype = 1` is an intentional Attaché data-model discriminator, represented
in code as `CUSTOMER_INVOICE_DOCUMENT_TYPE`. A visible document number may also
exist on another document class, such as a credit note; Direct Invoice Lookup
does not broaden the search to those classes or guess between them.

### Observed header lookup performance

A read-only diagnostic in the real FairCom environment found that exact
invoice-number lookups against `admin.invoice_header` returned the correct
record but took approximately 12.8 seconds. The same lookup against
`admin.invoiceheader` returned the same record in approximately 0.1 seconds.
Parameterized and literal versions had equivalent performance within each
source, so parameter binding was not the cause of the difference. Direct
Invoice Number lookup therefore uses `admin.invoiceheader` only as its fast
identity source while retaining parameterized exact equality. After identity
resolution, `admin.invoice_header` is queried by `doctype` plus
`internaldocnum` for the historical snapshot; authorized diagnostics measured
that identity-key lookup at approximately 10–82 ms. The two objects have
distinct responsibilities and are not treated as aliases.

Further read-only diagnostics found that the zero-row schema statement above
completed in approximately 28 ms and reported `docnum` `ColumnSize=9`. That
reported size is not a direct padding width: for invoice `185479`, the value
`"   185479"` produced by padding to length 9 did not match, and the unpadded
value `"185479"` also did not match. The exact value `"  185479"` did match
whether its parameter was declared CHAR(8), CHAR(9), or VARCHAR(8). The Bridge
therefore treats 9 only as the upper bound for the four exact candidates
`"185479"`, `" 185479"`, `"  185479"`, and `"   185479"`; it does not infer a
vendor-specific explanation for the observed representation.

Runtime `cursor.columns(...)` discovery is not used because it produced a fast
HYT00-style failure in the real FairCom environment. Metadata instead comes
from the zero-row SELECT's DB-API `cursor.description`.

Pyodbc 5.3.0 exposes bounded query timeout configuration through
`Connection.timeout`, not `Cursor.timeout`. The Bridge sets the validated query
timeout on the open connection before creating its cursor, so pyodbc can apply
the statement timeout during cursor creation. Both the setter and cursor
creation remain driver operations and are tracked as the dedicated
`timeout_configuration_start/done` stage.

Every fixed ODBC operation and each dynamically generated exact candidate has
an internal stage. After `identity_resolved`, the historical operations are
reported as `historical_header_*`, `header_extension_*`, and
`header_extension2_*` before `detail_execute_*`. On unexpected ODBC failure,
the Windows console receives one
safe structured warning containing only the current stage, elapsed milliseconds,
sanitized exception class, an exact five-character SQLSTATE when available, and
a structured integer native code when available. Raw exception text,
credentials, tokens, connection strings, addresses and SQL are never logged.
Timeout classification requires exact SQLSTATE `HYT00` or `HYT01`; an arbitrary
message containing the word "timeout" is not treated as a query timeout.

The detail source remains `admin.invoicedetailproduct`, queried by `doctype`
and `internaldocnum`; the same diagnostic returned the six detail rows in
approximately 55 ms.

The returned structured invoice is normalized through the same charge,
product, packaging and load rules used by Attaché PDF import. It then enters the
existing duplicate check, Delivery Area classification, editable preview and
`import-attache-pdf-commit` confirmation path. Preview alone never creates an
Order.

## Windows source setup (developer/build machine only)

The target Attaché Remote Desktop does not have Python and must use the portable
`attache-bridge.exe` package plus its `REMOTE-SMOKE-TEST.txt`; do not install
Python there. The commands in this section are only for a Windows developer or
build machine that already has Python. Do not install the ODBC dependency in the
Linux Manual Dispatch container.

```powershell
Set-Location "<Manual Dispatch repository>"

py -3.12 -m venv .venv-attache-bridge
.\.venv-attache-bridge\Scripts\Activate.ps1

python -m pip install -r attache_bridge\requirements.txt
```

Set the Bridge variables for the current PowerShell session only. Use a
dedicated least-privilege Attaché identity with SELECT access only to
`admin.invoiceheader`, `admin.invoice_header`, `admin.invoiceheaderextension`,
`admin.invoiceheaderextension2`, and `admin.invoicedetailproduct`.

```powershell
$env:ATTACHE_ODBC_CONNECTION_STRING = "DSN=<read-only-user-dsn>;UID=<read-only-user>;PWD=<secret>"
$env:ATTACHE_BRIDGE_API_TOKEN = "<long-random-shared-token>"
$env:ATTACHE_BRIDGE_CONNECTION_TIMEOUT_SECONDS = "5"
$env:ATTACHE_BRIDGE_QUERY_TIMEOUT_SECONDS = "10"
```

The ODBC identity must be read-only and limited to the required invoice header
and detail tables. Store the connection string and token in the process or
service environment, never in Git, command output, screenshots or application
logs.

Start the first smoke test on loopback only. This is the supported Bridge startup
command:

```powershell
python -m uvicorn attache_bridge.main:app --host 127.0.0.1 --port 8787
```

When the NAS-hosted backend must reach the Windows bridge, bind to a specific
private interface and restrict the Windows firewall rule to the Manual Dispatch
host. Use TLS or a trusted internal reverse proxy if the traffic crosses an
untrusted network. The `/health` endpoint reports configuration presence only;
it deliberately does not open ODBC.

## Manual Dispatch backend setup

Set these variables for the Manual Dispatch backend/container:

```text
ATTACHE_BRIDGE_URL=http://<windows-private-host>:8787
ATTACHE_BRIDGE_API_TOKEN=<same-shared-token>
ATTACHE_BRIDGE_TIMEOUT_SECONDS=5
```

Do not place the ODBC connection string in Docker Compose or the Linux
container. If the URL or token is missing, the application still starts and PDF
and Delivery Docket import remain available; only Direct lookup returns a safe
configuration error.

## Verification

All automated Bridge tests use injected fake ODBC connections. They verify the
bounded exact candidate parameters, both query keys, line ordering, `qtyinv`
mapping, resource cleanup and safe error classes without contacting Attaché.

For source-development verification on a Windows machine that already has
Python, leave the Bridge running and open a second PowerShell window:

```powershell
Set-Location "<Manual Dispatch repository>"
.\.venv-attache-bridge\Scripts\Activate.ps1

$env:ATTACHE_BRIDGE_URL = "http://127.0.0.1:8787"
$env:ATTACHE_BRIDGE_API_TOKEN = "<same-long-random-shared-token>"
$env:ATTACHE_BRIDGE_TIMEOUT_SECONDS = "5"

Invoke-RestMethod -Uri "http://127.0.0.1:8787/health"
python -m tools.smoke_test_attache_bridge --invoice-number 185479
```

`/health` intentionally requires no token and never opens ODBC; it returns only
service/configuration status. The invoice command sends the shared token in the
server-to-server `X-Attache-Bridge-Token` header. Missing or invalid tokens fail
closed. The smoke tool prints only whitelisted invoice/customer/reference and
product-line fields. It never prints the token, ODBC password, connection string
or delivery address.

For the manually authorized validation target, compare the output with:

```text
Invoice Number: 185479
Invoice Date: 2026-08-10 (Attaché source display: 10/08/2026)
Customer Code: ROTTHO
Customer Name: ROTARY TOOLS
Reference: 45954

RWORK   WORKSHOP MIX #29                  qtyinv=300
BAG10   PLASTIC BAG 10 kg                 qtyinv=30
RWCOTT  WHITE COTTON #1                   qtyinv=200
BAG10   PLASTIC BAG 10 kg                 qtyinv=20
PAL     PALLET                            qtyinv=1
DEL     DELIVERY /FUEL LEVY CHARGE        qtyinv=1
```

This is an opt-in manual smoke target only. Normal automated tests continue to
use fake/injected ODBC dependencies and never connect to Attaché.

### Verified real frozen smoke — PASS

On 2026-08-20, the frozen Windows x64 Bridge completed an authorized localhost
lookup through real FairCom Attaché ODBC for invoice `185479`. The request
returned HTTP 200 in 549 ms with the correct historical delivery street, raw
suburb and delivery postcode, plus six raw product lines. The verified Bridge
query path remained SELECT-only. Real Attaché frozen Bridge localhost smoke
status: **PASS**.

## Optional local-to-remote network check

Keep the first proof on `127.0.0.1`. Only after IT has explicitly approved a
private network path should the operator restart uvicorn with
`--host <WINDOWS_PRIVATE_IP>` and a Windows firewall rule restricted to the
Manual Dispatch NAS/backend source. Do not use broad public exposure.

From the Manual Dispatch host, test only the approved endpoint:

```powershell
Test-NetConnection "<REMOTE_BRIDGE_HOST>" -Port 8787
```

If `TcpTestSucceeded` is `True`, configure the Manual Dispatch backend variables
with the approved private URL/token and perform one Direct Lookup through the
authenticated application UI. If it is `False`, stop and report:

```text
Network/firewall exposure required from IT/hosting provider.
```

Do not modify firewall rules as part of application setup. Use TLS or a trusted
internal reverse proxy if the traffic crosses an untrusted network.

## Failure and fallback behavior

- Not found, multiple matches, timeout, authorization, unavailable and invalid
  response cases return controlled messages.
- Raw ODBC errors and connection strings are not returned to the browser.
- A failed Direct lookup leaves any PDF selection/preview draft intact.
- Staff can go back and use **Import Attaché PDF** at any time.
- Existing PDF and Delivery Docket endpoints and confirmation behavior are
  unchanged.
