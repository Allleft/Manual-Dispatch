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
        ):
            self.assertIn(label, renderer)
        self.assertNotIn("Back to lookup", renderer)
        self.assertIn('source === "attache-direct"', renderer)
        direct_modal = renderer.split(
            "export function createDeliveryDirectAttacheImportModal", 1
        )[1].split(
            "export function createDeliveryDirectAttacheLookupStep", 1
        )[0]
        self.assertIn(
            "body.append(createDeliveryDirectAttacheLookupStep(importState, actions))",
            direct_modal,
        )
        self.assertIn("showFooter: false", direct_modal)
        self.assertIn(
            "body.append(createDeliveryDirectAttacheFooter(importState, actions, hasDirectResult))",
            direct_modal,
        )
        direct_footer = renderer.split(
            "function createDeliveryDirectAttacheFooter", 1
        )[1].split(
            "export function createDeliveryDocketImportModal", 1
        )[0]
        self.assertIn('createActionButton("Back", actions.backDeliveryImportToSources)', direct_footer)
        self.assertIn('createActionButton("Cancel", actions.closeDeliveryAttacheImport)', direct_footer)
        self.assertIn("if (hasDirectResult)", direct_footer)
        self.assertIn("Confirm Import (${selectedCount} selected)", direct_footer)

        product_editor = renderer.split(
            "export function createAttacheProductLineEditor", 1
        )[1].split(
            "function deliveryDocketProductRefreshOptions", 1
        )[0]
        for contract in (
            'section.className = "workspace-product-line-editor"',
            'heading.className = "workspace-load-product-heading"',
            'scroll.className = "workspace-product-line-table-scroll"',
            'table.className = "workspace-product-line-table"',
            'lineRow.className = "workspace-product-line-table-row"',
            'className: "workspace-product-line-add"',
            'iconName: "trash"',
            "iconOnly: true",
            'className: "workspace-product-line-remove"',
            "Total Actual Quantity: ${formatProductLineTotals(lines)}",
        ):
            self.assertIn(contract, product_editor)
        for header in (
            "#",
            "Product Code",
            "Product Name",
            "Actual Quantity",
            "Actual Unit",
            "Packaging Quantity",
            "Packaging Unit",
            "Actions",
        ):
            self.assertIn(f'"{header}"', product_editor)
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
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr));", styles)

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
            let successResponse = successRequest.promise;
            const success = createHarness(async (invoiceNumber) => {{
              if (invoiceNumber !== "185479") throw new Error("wrong invoice number");
              return successResponse;
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

            const firstRows = completed.rows;
            const replacementRequest = deferred();
            successResponse = replacementRequest.promise;
            const replacementLookup = success.actions.lookupDeliveryDirectAttacheInvoice();
            if (success.state.deliveryAttacheImportState.rows !== firstRows) {{
              throw new Error("pending Direct lookup cleared the existing result");
            }}
            replacementRequest.resolve({{
              rows: [{{
                row_id: "REPLACEMENT", selected: true,
                importable: true, is_duplicate: false,
              }}],
            }});
            await replacementLookup;
            const replacementRows = success.state.deliveryAttacheImportState.rows;
            if (replacementRows.length !== 1 || replacementRows[0].row_id !== "REPLACEMENT") {{
              throw new Error("new Direct success appended instead of replacing the result");
            }}

            const failedReplacement = deferred();
            successResponse = failedReplacement.promise;
            const failedReplacementLookup = success.actions.lookupDeliveryDirectAttacheInvoice();
            if (success.state.deliveryAttacheImportState.rows !== replacementRows) {{
              throw new Error("retry pending state replaced the current Direct result");
            }}
            failedReplacement.reject(new Error("temporary lookup failure"));
            await failedReplacementLookup;
            if (success.state.deliveryAttacheImportState.rows !== replacementRows) {{
              throw new Error("failed Direct lookup removed the previous successful result");
            }}
            if (!success.state.deliveryAttacheImportState.directLookupError.includes(
              "temporary lookup failure"
            )) {{
              throw new Error("failed Direct retry did not surface its inline error");
            }}
            if (success.getBoardGets() !== 0) {{
              throw new Error("Direct retry performed a Delivery board refetch");
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

    def test_product_line_structural_changes_preserve_modal_scroll_and_review_state(self):
        actions_uri = (
            FRONTEND_ROOT
            / "js/actions/workspace/delivery-attache-actions.js"
        ).as_uri()
        order_renderer_uri = (
            FRONTEND_ROOT
            / "js/render/delivery/delivery-order-modal-renderer.js"
        ).as_uri()
        script = textwrap.dedent(
            f"""
            const {{ createDeliveryAttacheActions }} = await import({actions_uri!r});
            const {{ formatProductLineTotals }} = await import({order_renderer_uri!r});

            const displayedTotal = formatProductLineTotals([
              {{ quantity: 1, unit: "KG", package_quantity: 500 }},
              {{ quantity: 2, unit: "kg", package_quantity: 700 }},
            ]);
            if (displayedTotal !== "3 KG") {{
              throw new Error(`actual-quantity total used packaging values: ${{displayedTotal}}`);
            }}

            const row = {{
              row_id: "DIRECT-185479",
              selected: true,
              importable: true,
              is_duplicate: false,
              product_lines: [{{
                product_code: "RSING10KG",
                product_name: "COLOUR RAGS 10KG NET",
                quantity: 45,
                unit: "BAG",
                package_quantity: 45,
                package_unit: "BAG10",
              }}],
            }};
            const expandedRowIds = {{ "DIRECT-185479": true }};
            const state = {{
              deliveryAttacheImportState: {{
                rows: [row],
                expandedRowIds,
                search: "185479",
                filter: "SELECTED",
              }},
            }};
            const modalBody = {{ scrollTop: 720, scrollLeft: 19 }};
            let renders = 0;
            let committedPayload = null;
            globalThis.document = {{
              querySelector: (selector) =>
                selector === ".workspace-modal-body" ? modalBody : null,
            }};
            globalThis.requestAnimationFrame = (callback) => {{ callback(); return 1; }};
            const actions = createDeliveryAttacheActions({{
              state,
              renderWorkspace: () => {{
                renders += 1;
                modalBody.scrollTop = 0;
                modalBody.scrollLeft = 0;
              }},
              api: {{
                commitDeliveryAttacheInvoices: async (payload) => {{
                  committedPayload = payload;
                  return {{ imported_count: 1, skipped_count: 0 }};
                }},
              }},
              actions: {{
                runDeliveryAction: async (_key, operation, onError) => {{
                  try {{
                    await operation({{ route: "delivery/task-pool" }});
                  }} catch (error) {{
                    onError(error);
                  }}
                }},
                isDeliveryMutationCurrent: () => false,
              }},
            }});

            actions.updateDeliveryAttacheImportProductLine(
              "DIRECT-185479", 0, "product_name", "EDITED PRODUCT",
            );
            if (renders !== 0 || modalBody.scrollTop !== 720 || modalBody.scrollLeft !== 19) {{
              throw new Error("product typing caused a broad render or scroll change");
            }}
            if (state.deliveryAttacheImportState.rows[0].product_lines[0].product_name
                !== "EDITED PRODUCT") {{
              throw new Error("product typing did not update local state");
            }}

            actions.addDeliveryAttacheImportProductLine("DIRECT-185479");
            if (renders !== 1 || modalBody.scrollTop !== 720 || modalBody.scrollLeft !== 19) {{
              throw new Error("Add Product Line did not preserve modal scroll");
            }}
            if (state.deliveryAttacheImportState.rows[0].product_lines.length !== 2) {{
              throw new Error("Add Product Line did not append one local row");
            }}
            actions.removeDeliveryAttacheImportProductLine("DIRECT-185479", 1);
            if (renders !== 2 || modalBody.scrollTop !== 720 || modalBody.scrollLeft !== 19) {{
              throw new Error("Remove Product Line did not preserve modal scroll");
            }}
            const current = state.deliveryAttacheImportState;
            if (current.expandedRowIds !== expandedRowIds
                || current.search !== "185479"
                || current.filter !== "SELECTED") {{
              throw new Error("product mutation lost expanded/search/filter state");
            }}
            await actions.commitDeliveryAttacheImport();
            if (committedPayload?.rows?.[0]?.product_lines?.[0]?.product_name
                !== "EDITED PRODUCT") {{
              throw new Error("Confirm Import payload lost the edited product line");
            }}

            delete globalThis.document;
            delete globalThis.requestAnimationFrame;
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
