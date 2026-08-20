import subprocess
import textwrap
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"


class AttacheDirectFrontendTest(unittest.TestCase):
    def test_source_chooser_direct_form_and_api_contract_are_additive(self):
        renderer = (
            FRONTEND_ROOT
            / "js/render/delivery/delivery-attache-modal-renderer.js"
        ).read_text(encoding="utf-8")
        api = (
            FRONTEND_ROOT / "js/api/manual-dispatch/delivery-api.js"
        ).read_text(encoding="utf-8")
        state = (FRONTEND_ROOT / "js/state/app-state.js").read_text(
            encoding="utf-8"
        )
        styles = (FRONTEND_ROOT / "styles.css").read_text(encoding="utf-8")

        for label in (
            "Import Attaché PDF",
            "Import Delivery Docket",
            "Import from Attaché",
            "Invoice Number",
            "Find Invoice",
            "Looking up invoice...",
            "Back to lookup",
        ):
            self.assertIn(label, renderer)
        self.assertIn('source === "attache-direct"', renderer)
        self.assertIn(
            "If lookup is unavailable, go back and use Import Attaché PDF.",
            renderer,
        )
        self.assertIn("import-attache-pdf-preview", api)
        self.assertIn("import-delivery-docket-docx-preview", api)
        self.assertIn("import-attache-direct-preview", api)
        self.assertIn("body: { invoice_number: invoiceNumber }", api)
        self.assertIn("directInvoiceNumber", state)
        self.assertIn("isDirectLookupPending", state)
        self.assertIn("directLookupError", state)
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr));", styles)

    def test_deployment_keeps_odbc_out_of_linux_container_configuration(self):
        compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        environment_example = (PROJECT_ROOT / ".env.example").read_text(
            encoding="utf-8"
        )
        documentation = (
            PROJECT_ROOT / "docs/attache-direct-invoice-lookup.md"
        ).read_text(encoding="utf-8")

        for variable in (
            "ATTACHE_BRIDGE_URL",
            "ATTACHE_BRIDGE_API_TOKEN",
            "ATTACHE_BRIDGE_TIMEOUT_SECONDS",
        ):
            self.assertIn(variable, compose)
            self.assertIn(variable, environment_example)
        self.assertNotIn("ATTACHE_ODBC_CONNECTION_STRING", compose)
        self.assertNotIn("ATTACHE_ODBC_CONNECTION_STRING", environment_example)
        self.assertIn("ATTACHE_ODBC_CONNECTION_STRING", documentation)
        self.assertIn("read-only", documentation)
        self.assertIn("Import Attaché PDF", documentation)
        for runbook_contract in (
            'Set-Location "<Manual Dispatch repository>"',
            "py -3.12 -m venv .venv-attache-bridge",
            ".\\.venv-attache-bridge\\Scripts\\Activate.ps1",
            "python -m pip install -r attache_bridge\\requirements.txt",
            "python -m uvicorn attache_bridge.main:app --host 127.0.0.1 --port 8787",
            '$env:ATTACHE_BRIDGE_URL = "http://127.0.0.1:8787"',
            'Invoke-RestMethod -Uri "http://127.0.0.1:8787/health"',
            "python -m tools.smoke_test_attache_bridge --invoice-number 185479",
            'Test-NetConnection "<REMOTE_BRIDGE_HOST>" -Port 8787',
            "Network/firewall exposure required from IT/hosting provider.",
        ):
            self.assertIn(runbook_contract, documentation)
        self.assertNotIn("--host 0.0.0.0", documentation)

    def test_direct_lookup_state_is_bounded_and_preserves_pdf_draft_on_failure(self):
        actions_uri = (
            FRONTEND_ROOT
            / "js/actions/workspace/delivery-attache-actions.js"
        ).as_uri()
        script = textwrap.dedent(
            f"""
            const {{ createDeliveryAttacheActions }} = await import({actions_uri!r});

            function deferred() {{
              let resolve;
              let reject;
              const promise = new Promise((done, fail) => {{
                resolve = done;
                reject = fail;
              }});
              return {{ promise, resolve, reject }};
            }}

            function createHarness(lookupImpl) {{
              const pdfFiles = [{{ name: "saved.pdf", type: "application/pdf" }}];
              const pdfRows = [{{
                row_id: "PDF-DRAFT",
                selected: true,
                importable: true,
                is_duplicate: false,
              }}];
              const state = {{
                isLoggedIn: true,
                authSessionVersion: 4,
                workspaceRoute: "delivery/task-pool",
                activeWorkspace: "delivery",
                dispatchDate: "2026-08-20",
                deliveryDocumentImportState: {{ isOpen: true, source: "attache-direct" }},
                deliveryAttacheImportState: {{
                  isOpen: true,
                  isPreviewing: false,
                  isCommitting: false,
                  isDirectLookupPending: false,
                  step: "review",
                  reviewSource: "attache",
                  files: pdfFiles,
                  rows: pdfRows,
                  directInvoiceNumber: "185479",
                  directLookupError: "",
                  expandedRowIds: {{ "PDF-DRAFT": true }},
                  search: "saved search",
                  filter: "READY",
                  error: "",
                  success: "",
                }},
              }};
              let lookupCalls = 0;
              let boardGets = 0;
              let renders = 0;
              const context = {{
                state,
                renderWorkspace: () => {{ renders += 1; }},
                confirmAction: () => true,
                api: {{
                  previewDirectAttacheInvoice: async (invoiceNumber) => {{
                    lookupCalls += 1;
                    return lookupImpl(invoiceNumber);
                  }},
                  getDeliveryWorkspaceBoard: async () => {{ boardGets += 1; }},
                }},
                deliveryAttachePreviewRequestVersion: 0,
                deliveryAttacheDirectLookupRequestVersion: 0,
                deliveryAttacheAreaClassificationVersions: {{}},
                actions: {{}},
              }};
              context.actions.captureMutationContext = () => ({{
                route: state.workspaceRoute,
                dispatchDate: state.dispatchDate,
                activeWorkspace: state.activeWorkspace,
                authSessionVersion: state.authSessionVersion,
              }});
              context.actions.isDeliveryMutationCurrent = (snapshot) =>
                state.isLoggedIn
                && snapshot.route === state.workspaceRoute
                && snapshot.dispatchDate === state.dispatchDate
                && snapshot.activeWorkspace === state.activeWorkspace
                && snapshot.authSessionVersion === state.authSessionVersion;
              return {{
                actions: createDeliveryAttacheActions(context),
                context,
                getBoardGets: () => boardGets,
                getLookupCalls: () => lookupCalls,
                getRenders: () => renders,
                pdfFiles,
                pdfRows,
                state,
              }};
            }}

            const successRequest = deferred();
            const success = createHarness(async (invoiceNumber) => {{
              if (invoiceNumber !== "185479") throw new Error("wrong invoice number");
              return successRequest.promise;
            }});
            const firstLookup = success.actions.lookupDeliveryDirectAttacheInvoice();
            const duplicateLookup = success.actions.lookupDeliveryDirectAttacheInvoice();
            if (success.getLookupCalls() !== 1) {{
              throw new Error("duplicate Find Invoice click started another request");
            }}
            if (!success.state.deliveryAttacheImportState.isDirectLookupPending) {{
              throw new Error("Direct lookup did not enter loading state");
            }}
            successRequest.resolve({{
              rows: [
                {{ row_id: "DIRECT", selected: true, importable: true, is_duplicate: false }},
                {{ row_id: "DUP", selected: true, importable: true, is_duplicate: true }},
              ],
            }});
            await Promise.all([firstLookup, duplicateLookup]);
            const completed = success.state.deliveryAttacheImportState;
            if (completed.isDirectLookupPending) throw new Error("loading state was not cleared");
            if (completed.step !== "review" || completed.reviewSource !== "attache-direct") {{
              throw new Error("Direct lookup did not enter the shared review path");
            }}
            if (!completed.rows[0].selected || completed.rows[1].selected) {{
              throw new Error("Direct rows did not reuse preview selection eligibility");
            }}
            if (completed.files !== success.pdfFiles) {{
              throw new Error("successful Direct lookup unexpectedly cleared PDF files");
            }}
            if (completed.search !== "saved search" || completed.filter !== "READY") {{
              throw new Error("Direct lookup reset review controls");
            }}
            if (success.getBoardGets() !== 0) {{
              throw new Error("Direct preview performed a Delivery board refetch");
            }}

            const failure = createHarness(async () => {{
              throw new Error(
                "Invoice 185479 was not found in Attaché. You can still use Import Attaché PDF.",
              );
            }});
            await failure.actions.lookupDeliveryDirectAttacheInvoice();
            const failed = failure.state.deliveryAttacheImportState;
            if (failed.files !== failure.pdfFiles || failed.rows !== failure.pdfRows) {{
              throw new Error("failed Direct lookup changed the PDF draft");
            }}
            if (failed.step !== "review" || failed.reviewSource !== "attache") {{
              throw new Error("failed Direct lookup changed the PDF review position");
            }}
            if (!failed.directLookupError.includes("Import Attaché PDF")) {{
              throw new Error("failed Direct lookup omitted the PDF fallback message");
            }}
            if (failed.error) {{
              throw new Error("failed Direct lookup polluted the PDF error state");
            }}

            const unavailable = createHarness(async () => {{
              throw new Error(
                "Attaché lookup is currently unavailable. You can still use Import Attaché PDF.",
              );
            }});
            await unavailable.actions.lookupDeliveryDirectAttacheInvoice();
            if (!unavailable.state.deliveryAttacheImportState.directLookupError.includes(
              "Attaché lookup is currently unavailable",
            )) {{
              throw new Error("service-unavailable state was not shown");
            }}
            if (unavailable.getBoardGets() !== 0) {{
              throw new Error("failed Direct lookup performed a Delivery board refetch");
            }}

            const invalid = createHarness(async () => ({{ rows: [] }}));
            invalid.actions.updateDeliveryDirectAttacheInvoiceNumber("");
            await invalid.actions.lookupDeliveryDirectAttacheInvoice();
            if (invalid.getLookupCalls() !== 0) {{
              throw new Error("empty Direct invoice number reached the API");
            }}
            if (invalid.state.deliveryAttacheImportState.directLookupError
                !== "Invoice number is required.") {{
              throw new Error("empty Direct invoice number did not show validation");
            }}

            const staleRequest = deferred();
            const stale = createHarness(async () => staleRequest.promise);
            const staleLookup = stale.actions.lookupDeliveryDirectAttacheInvoice();
            stale.actions.chooseDeliveryImportSource("attache");
            staleRequest.resolve({{
              rows: [{{ row_id: "STALE", selected: true, importable: true }}],
            }});
            await staleLookup;
            if (stale.state.deliveryAttacheImportState.rows !== stale.pdfRows) {{
              throw new Error("source-stale Direct response replaced the PDF rows");
            }}
            if (stale.state.deliveryAttacheImportState.isDirectLookupPending) {{
              throw new Error("source change left Direct lookup pending");
            }}
            if (stale.state.deliveryDocumentImportState.source !== "attache") {{
              throw new Error("source change was not retained");
            }}

            const opened = createHarness(async () => ({{ rows: [] }}));
            opened.state.deliveryDocumentImportState.source = "chooser";
            opened.actions.chooseDeliveryImportSource("attache-direct");
            if (opened.state.deliveryDocumentImportState.source !== "attache-direct") {{
              throw new Error("Direct Attaché choice did not open its source state");
            }}
            """
        )
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
