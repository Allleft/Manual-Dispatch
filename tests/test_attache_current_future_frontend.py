import subprocess
import textwrap
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"


class AttacheCurrentFutureFrontendTest(unittest.TestCase):
    def test_fourth_source_modal_api_state_and_responsive_contract_are_wired(self):
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
        actions = (
            FRONTEND_ROOT
            / "js/actions/workspace/delivery-attache-current-future-actions.js"
        ).read_text(encoding="utf-8")
        composition = (
            FRONTEND_ROOT / "js/actions/workspace-actions.js"
        ).read_text(encoding="utf-8")
        styles = (FRONTEND_ROOT / "styles.css").read_text(encoding="utf-8")

        chooser = renderer.split(
            "export function createDeliveryImportSourceChooser", 1
        )[1].split("function createImportSourceChoice", 1)[0]
        self.assertEqual(4, chooser.count("createImportSourceChoice("))
        for contract in (
            'source === "attache-current-future"',
            "Import Today & Future Invoices",
            "Load Attaché customer invoices dated today or later.",
            "Dates use the Melbourne business date.",
            "Attaché access is read-only.",
            "Load Today & Future Invoices",
            "Loading Today & Future Invoices...",
            "Today & Future Attaché Invoices",
            "Found",
            "Ready",
            "Duplicate",
            "Payment Required",
            "Needs Review",
            "Account Terms",
            "Outstanding Balance",
            "Not required",
            "Paid in full",
            "Unable to determine",
            "No Attaché invoices dated today or later were found.",
            "Refresh",
        ):
            self.assertIn(contract, renderer)
        self.assertIn("showSummary: false", renderer)
        self.assertIn("currentFutureActionAdapter(actions)", renderer)
        self.assertIn('grid-template-columns: repeat(5, minmax(0, 1fr));', styles)

        preview_api = api.split(
            "export async function apiPreviewDeliveryAttacheCurrentFutureInvoices",
            1,
        )[1].split(
            "export async function apiCommitDeliveryAttacheCurrentFutureInvoices",
            1,
        )[0]
        self.assertIn("import-attache-current-future-preview", preview_api)
        self.assertIn('method: "POST"', preview_api)
        self.assertNotIn("body:", preview_api)
        self.assertNotIn("from_date", preview_api)
        self.assertIn("import-attache-current-future-commit", api)

        for field in (
            "deliveryAttacheCurrentFutureImportState",
            "hasLoaded",
            "fromDate",
            "isLoading",
        ):
            self.assertIn(field, state)
        self.assertIn("createDeliveryAttacheCurrentFutureActions", composition)
        self.assertIn(
            "Reload invoices from Attaché? Current preview edits will be discarded.",
            actions,
        )
        self.assertIn("isDeliveryMutationCurrent(mutationContext)", actions)
        self.assertIn('source === CURRENT_FUTURE_SOURCE', actions)
        self.assertIn("requestVersion === context.deliveryAttacheCurrentFutureRequestVersion", actions)
        self.assertNotIn("getDeliveryWorkspaceBoard", actions)
        self.assertNotIn("window.location", actions)
        self.assertIn(
            "grid-template-columns: repeat(2, minmax(0, 1fr));",
            styles,
        )
        narrow = styles.split("@media (max-width: 640px)", 1)[1]
        self.assertIn(".workspace-import-source-grid", narrow)
        self.assertIn("grid-template-columns: minmax(0, 1fr);", narrow)

    def test_payment_summary_cards_selection_and_direct_source_isolation(self):
        renderer_uri = (
            FRONTEND_ROOT
            / "js/render/delivery/delivery-attache-modal-renderer.js"
        ).as_uri()
        script = textwrap.dedent(
            """
            class FakeNode {
              constructor(tagName, text = "") {
                this.tagName = tagName;
                this.children = [];
                this.parentNode = null;
                this.attributes = {};
                this.listeners = {};
                this.dataset = {};
                this.disabled = false;
                this.hidden = false;
                this.checked = false;
                this.value = "";
                this._text = text;
                this._className = "";
                this.classList = {
                  add: (...tokens) => {
                    const classes = new Set(this._className.split(/\\s+/).filter(Boolean));
                    tokens.forEach((token) => classes.add(token));
                    this._className = [...classes].join(" ");
                  },
                  contains: (token) => this._className.split(/\\s+/).includes(token),
                };
              }
              get className() { return this._className; }
              set className(value) { this._className = String(value || ""); }
              get textContent() {
                return this._text + this.children.map((child) => child.textContent || "").join("");
              }
              set textContent(value) {
                this._text = String(value ?? "");
                this.children = [];
              }
              append(...children) {
                children.forEach((child) => {
                  if (child === null || child === undefined) return;
                  child.parentNode = this;
                  this.children.push(child);
                });
              }
              setAttribute(name, value) { this.attributes[name] = String(value); }
              addEventListener(type, listener) { (this.listeners[type] ||= []).push(listener); }
              focus() {}
              matches(selector) {
                if (selector.startsWith(".")) return this.classList.contains(selector.slice(1));
                return String(this.tagName || "").toLowerCase() === selector.toLowerCase();
              }
              querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
              querySelectorAll(selector) {
                const matches = [];
                const visit = (node) => {
                  if (node.matches?.(selector)) matches.push(node);
                  node.children?.forEach(visit);
                };
                this.children.forEach(visit);
                return matches;
              }
            }

            const body = new FakeNode("body");
            globalThis.document = {
              activeElement: null,
              body,
              addEventListener() {},
              removeEventListener() {},
              createElement: (tagName) => new FakeNode(tagName),
              createElementNS: (_namespace, tagName) => new FakeNode(tagName),
              createTextNode: (text) => new FakeNode("#text", String(text)),
              createDocumentFragment: () => new FakeNode("#fragment"),
            };
            const {
              attacheRowStatus,
              createAttacheReviewRow,
              createDeliveryAttacheCurrentFutureImportModal,
            } = await import(__RENDERER_URI__);
            const base = {
              invoice_number: "186001",
              invoice_date: "2026-09-04",
              order_no: "PO-1",
              company_name: "TEST CUSTOMER",
              suburb: "HALLAM",
              delivery_date: "2026-09-07",
              pallet_quantity: 0,
              loose_bags_quantity: 0,
              carton_quantity: 0,
              product_lines: [],
              warnings: [],
              selected: true,
              importable: true,
              is_duplicate: false,
            };
            const rows = [
              { ...base, row_id: "TERMS", terms_description: "30 DAYS",
                outstanding_balance: null, payment_eligibility: "NOT_REQUIRED" },
              { ...base, row_id: "PAID", terms_description: "C.O.D.",
                outstanding_balance: 0, payment_eligibility: "PAID_IN_FULL" },
              { ...base, row_id: "PAYMENT", terms_description: "C.O.D.",
                outstanding_balance: 203.5, payment_eligibility: "PAYMENT_REQUIRED",
                importable: false, selected: false, warnings: ["Payment required"] },
              { ...base, row_id: "UNKNOWN", terms_description: null,
                outstanding_balance: null, payment_eligibility: "UNKNOWN",
                importable: false, selected: false, warnings: ["Needs review"] },
              { ...base, row_id: "DUP", terms_description: "C.O.D.",
                outstanding_balance: 203.5, payment_eligibility: "PAYMENT_REQUIRED",
                importable: false, selected: false, is_duplicate: true },
            ];
            const actions = new Proxy({}, { get: () => () => {} });
            const modal = createDeliveryAttacheCurrentFutureImportModal({
              hasLoaded: true,
              fromDate: "2026-09-04",
              rows,
              expandedRowIds: {},
              search: "",
              filter: "ALL",
            }, actions);
            const metrics = Object.fromEntries(
              modal.querySelectorAll(".workspace-metric-pill").map((pill) => [
                pill.children[0].textContent,
                Number(pill.children[1].textContent),
              ]),
            );
            const expectedMetrics = {
              Found: 5,
              Ready: 2,
              Duplicate: 1,
              "Payment Required": 1,
              "Needs Review": 1,
            };
            if (JSON.stringify(metrics) !== JSON.stringify(expectedMetrics)) {
              throw new Error(`payment summary mismatch: ${JSON.stringify(metrics)}`);
            }
            const cards = modal.querySelector(".workspace-attache-review-list").children;
            const cardFor = (rowId) => cards.find(
              (card) => card.dataset.invoiceReviewId === rowId,
            );
            const metaFor = (card) => Object.fromEntries(
              card.querySelectorAll(".workspace-inline-meta").map((item) => [
                item.children[0].textContent,
                item.children[1].textContent,
              ]),
            );
            const termsMeta = metaFor(cardFor("TERMS"));
            if (termsMeta["Account Terms"] !== "30 DAYS"
                || termsMeta.Payment !== "Not required"
                || termsMeta["Outstanding Balance"] !== undefined
                || attacheRowStatus(rows[0]) !== "Ready") {
              throw new Error("30 DAYS presentation is incorrect");
            }
            const paidMeta = metaFor(cardFor("PAID"));
            if (paidMeta["Outstanding Balance"] !== "$0.00"
                || paidMeta.Payment !== "Paid in full"
                || attacheRowStatus(rows[1]) !== "Ready") {
              throw new Error("paid C.O.D. presentation is incorrect");
            }
            const paymentCard = cardFor("PAYMENT");
            const paymentMeta = metaFor(paymentCard);
            if (paymentMeta["Outstanding Balance"] !== "$203.50"
                || paymentMeta.Payment !== "Payment required"
                || attacheRowStatus(rows[2]) !== "Payment Required"
                || !paymentCard.querySelector("input").disabled) {
              throw new Error("unpaid C.O.D. presentation or selection is unsafe");
            }
            const unknownMeta = metaFor(cardFor("UNKNOWN"));
            if (unknownMeta["Account Terms"] !== "UNKNOWN"
                || unknownMeta.Payment !== "Unable to determine"
                || attacheRowStatus(rows[3]) !== "Needs Review") {
              throw new Error("unknown terms presentation is incorrect");
            }
            if (attacheRowStatus(rows[4]) !== "Duplicate"
                || !cardFor("DUP").querySelector("input").disabled) {
              throw new Error("duplicate precedence changed");
            }
            const directRow = { ...base, row_id: "DIRECT" };
            const directCard = createAttacheReviewRow(
              directRow,
              { expandedRowIds: {}, isCommitting: false },
              actions,
            );
            const directMeta = metaFor(directCard);
            if (directMeta["Account Terms"] !== undefined
                || directMeta.Payment !== undefined
                || attacheRowStatus(directRow) !== "Ready") {
              throw new Error("Current/Future payment UI leaked into Direct Attaché");
            }
            delete globalThis.document;
            """
        ).replace("__RENDERER_URI__", repr(renderer_uri))
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr or result.stdout)

    def test_logout_clears_current_future_import_state(self):
        auth_actions_uri = (
            FRONTEND_ROOT / "js/actions/auth-actions.js"
        ).as_uri()
        script = textwrap.dedent(
            f"""
            globalThis.window = {{
              location: {{ protocol: "http:", origin: "http://127.0.0.1" }},
              sessionStorage: {{
                getItem() {{ return null; }},
                setItem() {{}},
                removeItem() {{}},
              }},
            }};
            globalThis.fetch = async () => ({{
              ok: true,
              status: 200,
              async json() {{ return {{}}; }},
            }});
            const {{ createAuthActions }} = await import({auth_actions_uri!r});
            const state = {{
              authSessionVersion: 7,
              isLoggedIn: true,
              accountName: "Operator",
              accountId: "7",
              deliveryAttacheCurrentFutureImportState: {{
                isLoading: true,
                isCommitting: true,
                hasLoaded: true,
                fromDate: "2026-09-02",
                rows: [{{ row_id: "STALE" }}],
                expandedRowIds: {{ STALE: true }},
                search: "stale",
                filter: "DUPLICATE_INVOICE",
                error: "stale error",
                success: "stale success",
              }},
            }};
            const actions = createAuthActions({{
              state,
              renderAuthGate() {{}},
              renderBoard() {{}},
            }});
            await actions.logoutAccount();
            const current = state.deliveryAttacheCurrentFutureImportState;
            if (state.isLoggedIn || state.authSessionVersion !== 8) {{
              throw new Error("logout did not invalidate the auth session");
            }}
            if (current.isLoading || current.isCommitting || current.hasLoaded
                || current.fromDate || current.rows.length
                || Object.keys(current.expandedRowIds).length
                || current.search || current.filter !== "ALL"
                || current.error || current.success) {{
              throw new Error("logout retained Current/Future import state");
            }}
            delete globalThis.window;
            delete globalThis.fetch;
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

    def test_load_refresh_empty_failure_and_stale_results_preserve_state(self):
        actions_uri = (
            FRONTEND_ROOT
            / "js/actions/workspace/delivery-attache-current-future-actions.js"
        ).as_uri()
        script = textwrap.dedent(
            f"""
            const {{ createDeliveryAttacheCurrentFutureActions }} = await import({actions_uri!r});

            function deferred() {{
              let resolve;
              let reject;
              const promise = new Promise((done, fail) => {{ resolve = done; reject = fail; }});
              return {{ promise, resolve, reject }};
            }}

            function createHarness(previewImpl) {{
              const modalBody = {{ scrollTop: 640, scrollLeft: 23 }};
              let renders = 0;
              let previewCalls = 0;
              let boardGets = 0;
              let confirmResult = true;
              const state = {{
                isLoggedIn: true,
                authSessionVersion: 4,
                workspaceRoute: "delivery/task-pool",
                activeWorkspace: "delivery",
                dispatchDate: "2026-09-02",
                deliveryAttacheImportState: {{ isOpen: true }},
                deliveryDocumentImportState: {{
                  isOpen: true,
                  source: "attache-current-future",
                }},
                deliveryAttacheCurrentFutureImportState: {{
                  isLoading: false,
                  isCommitting: false,
                  hasLoaded: false,
                  fromDate: "",
                  rows: [],
                  expandedRowIds: {{}},
                  search: "",
                  filter: "ALL",
                  error: "",
                  success: "",
                }},
              }};
              globalThis.document = {{
                querySelector: (selector) =>
                  selector === ".workspace-modal-body" ? modalBody : null,
              }};
              globalThis.requestAnimationFrame = (callback) => {{ callback(); return 1; }};
              const context = {{
                state,
                renderWorkspace: () => {{
                  renders += 1;
                  modalBody.scrollTop = 0;
                  modalBody.scrollLeft = 0;
                }},
                confirmAction: () => confirmResult,
                api: {{
                  previewDeliveryAttacheCurrentFutureInvoices: async () => {{
                    previewCalls += 1;
                    return previewImpl();
                  }},
                }},
                deliveryAttacheCurrentFutureRequestVersion: 0,
                deliveryAttacheCurrentFutureAreaClassificationVersions: {{}},
                actions: {{}},
              }};
              context.actions.captureMutationContext = () => ({{
                route: state.workspaceRoute,
                dispatchDate: state.dispatchDate,
                activeWorkspace: state.activeWorkspace,
                authSessionVersion: state.authSessionVersion,
              }});
              context.actions.isDeliveryMutationCurrent = (snapshot) => Boolean(
                state.isLoggedIn
                && snapshot
                && snapshot.route === state.workspaceRoute
                && snapshot.dispatchDate === state.dispatchDate
                && snapshot.activeWorkspace === state.activeWorkspace
                && snapshot.authSessionVersion === state.authSessionVersion
              );
              context.actions.loadDeliveryRoute = async () => {{ boardGets += 1; }};
              context.actions.runDeliveryAction = async () => {{
                throw new Error("commit is outside this harness");
              }};
              const actions = createDeliveryAttacheCurrentFutureActions(context);
              Object.assign(context.actions, actions);
              return {{
                actions,
                context,
                modalBody,
                state,
                getBoardGets: () => boardGets,
                getPreviewCalls: () => previewCalls,
                getRenders: () => renders,
                setConfirmResult: (value) => {{ confirmResult = value; }},
              }};
            }}

            const firstRequest = deferred();
            let response = firstRequest.promise;
            const harness = createHarness(() => response);
            if (harness.getPreviewCalls() !== 0) throw new Error("opening source queried Attaché");
            const firstLoad = harness.actions.loadDeliveryAttacheCurrentFutureInvoices();
            const duplicateLoad = harness.actions.loadDeliveryAttacheCurrentFutureInvoices();
            if (harness.getPreviewCalls() !== 1) throw new Error("duplicate Load started a request");
            if (!harness.state.deliveryAttacheCurrentFutureImportState.isLoading) {{
              throw new Error("load did not enter pending state");
            }}
            firstRequest.resolve({{
              from_date: "2026-09-02",
              rows: [
                {{ row_id: "READY", importable: true, is_duplicate: false, selected: true,
                   warnings: [], payment_eligibility: "NOT_REQUIRED" }},
                {{ row_id: "DUP", importable: false, is_duplicate: true, selected: true,
                   warnings: [], payment_eligibility: "PAYMENT_REQUIRED" }},
                {{ row_id: "PAID", importable: true, is_duplicate: false, selected: true,
                   warnings: [], payment_eligibility: "PAID_IN_FULL" }},
                {{ row_id: "PAYMENT", importable: false, is_duplicate: false, selected: true,
                   warnings: ["Payment required"], payment_eligibility: "PAYMENT_REQUIRED" }},
                {{ row_id: "UNKNOWN", importable: false, is_duplicate: false, selected: true,
                   warnings: ["Needs review"], payment_eligibility: "UNKNOWN" }},
                {{ row_id: "WARNING", importable: true, is_duplicate: false, selected: true,
                   warnings: ["Review address"], payment_eligibility: "NOT_REQUIRED" }},
              ],
            }});
            await Promise.all([firstLoad, duplicateLoad]);
            let current = harness.state.deliveryAttacheCurrentFutureImportState;
            if (!current.hasLoaded || current.fromDate !== "2026-09-02") {{
              throw new Error("load did not retain its server date scope");
            }}
            if (!current.rows[0].selected || current.rows[1].selected
                || !current.rows[2].selected || current.rows[3].selected
                || current.rows[4].selected || current.rows[5].selected) {{
              throw new Error("only ready payment-eligible rows were not selected");
            }}
            if (harness.modalBody.scrollTop !== 640 || harness.modalBody.scrollLeft !== 23) {{
              throw new Error("load changed modal scroll");
            }}

            harness.actions.updateDeliveryAttacheCurrentFutureSearch("saved search");
            harness.actions.updateDeliveryAttacheCurrentFutureFilter("READY");
            harness.actions.toggleDeliveryAttacheCurrentFutureExpanded("READY");
            const loadedRows = current.rows;
            harness.setConfirmResult(false);
            await harness.actions.refreshDeliveryAttacheCurrentFutureInvoices();
            if (harness.getPreviewCalls() !== 1 || current.rows !== loadedRows) {{
              throw new Error("cancelled Refresh changed preview state");
            }}

            const replacementRequest = deferred();
            response = replacementRequest.promise;
            harness.setConfirmResult(true);
            const refresh = harness.actions.refreshDeliveryAttacheCurrentFutureInvoices();
            if (harness.state.deliveryAttacheCurrentFutureImportState.rows !== loadedRows) {{
              throw new Error("pending Refresh cleared existing rows");
            }}
            replacementRequest.resolve({{
              from_date: "2026-09-03",
              rows: [{{ row_id: "NEW", importable: true, is_duplicate: false,
                        warnings: [], payment_eligibility: "PAID_IN_FULL" }}],
            }});
            await refresh;
            current = harness.state.deliveryAttacheCurrentFutureImportState;
            if (current.rows.length !== 1 || current.rows[0].row_id !== "NEW") {{
              throw new Error("successful Refresh did not atomically replace rows");
            }}
            if (current.search !== "saved search" || current.filter !== "READY") {{
              throw new Error("Refresh discarded search/filter state");
            }}
            if (Object.keys(current.expandedRowIds).length) {{
              throw new Error("Refresh retained row-specific edit expansion");
            }}

            const failedRequest = deferred();
            response = failedRequest.promise;
            const stableRows = current.rows;
            const failedRefresh = harness.actions.refreshDeliveryAttacheCurrentFutureInvoices();
            failedRequest.reject(new Error("temporary bridge failure"));
            await failedRefresh;
            current = harness.state.deliveryAttacheCurrentFutureImportState;
            if (current.rows !== stableRows || !current.error.includes("temporary bridge failure")) {{
              throw new Error("failed Refresh did not retain rows and show inline error");
            }}

            response = Promise.resolve({{ from_date: "2026-09-04", rows: [] }});
            await harness.actions.refreshDeliveryAttacheCurrentFutureInvoices();
            current = harness.state.deliveryAttacheCurrentFutureImportState;
            if (!current.hasLoaded || current.fromDate !== "2026-09-04" || current.rows.length) {{
              throw new Error("empty result was not retained as a successful loaded state");
            }}
            if (harness.getBoardGets() !== 0) {{
              throw new Error("load/refresh performed a Delivery board GET");
            }}

            async function assertStaleResultIgnored(label, mutate) {{
              const staleRequest = deferred();
              response = staleRequest.promise;
              const staleHarness = createHarness(() => response);
              const stableRows = [{{
                row_id: `${{label}}-STABLE`,
                importable: true,
                is_duplicate: false,
                selected: true,
              }}];
              staleHarness.state.deliveryAttacheCurrentFutureImportState = {{
                ...staleHarness.state.deliveryAttacheCurrentFutureImportState,
                hasLoaded: true,
                fromDate: "2026-09-04",
                rows: stableRows,
              }};
              const staleLoad =
                staleHarness.actions.loadDeliveryAttacheCurrentFutureInvoices();
              mutate(staleHarness);
              staleRequest.resolve({{
                from_date: "2026-09-05",
                rows: [{{ row_id: "STALE", importable: true, is_duplicate: false }}],
              }});
              await staleLoad;
              const staleState =
                staleHarness.state.deliveryAttacheCurrentFutureImportState;
              if (staleState.rows !== stableRows
                  || staleState.fromDate !== "2026-09-04"
                  || staleState.isLoading) {{
                throw new Error(`${{label}} stale response changed retained state`);
              }}
            }}

            await assertStaleResultIgnored("Back", (staleHarness) => {{
              staleHarness.state.deliveryDocumentImportState.source = "chooser";
              staleHarness.actions.invalidateDeliveryAttacheCurrentFutureRequests();
            }});
            await assertStaleResultIgnored("Docket switch", (staleHarness) => {{
              staleHarness.state.deliveryDocumentImportState.source = "docket";
              staleHarness.actions.invalidateDeliveryAttacheCurrentFutureRequests();
            }});
            await assertStaleResultIgnored("modal close", (staleHarness) => {{
              staleHarness.state.deliveryAttacheImportState.isOpen = false;
              staleHarness.state.deliveryDocumentImportState.isOpen = false;
              staleHarness.actions.invalidateDeliveryAttacheCurrentFutureRequests();
            }});
            await assertStaleResultIgnored("route transition", (staleHarness) => {{
              staleHarness.state.workspaceRoute = "home";
              staleHarness.actions.invalidateDeliveryAttacheCurrentFutureRequests();
            }});
            await assertStaleResultIgnored("auth session", (staleHarness) => {{
              staleHarness.state.authSessionVersion += 1;
              staleHarness.state.isLoggedIn = false;
              staleHarness.actions.invalidateDeliveryAttacheCurrentFutureRequests();
            }});
            await assertStaleResultIgnored("request version", (staleHarness) => {{
              staleHarness.actions.invalidateDeliveryAttacheCurrentFutureRequests();
            }});

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

    def test_local_product_selection_classification_and_commit_are_isolated(self):
        actions_uri = (
            FRONTEND_ROOT
            / "js/actions/workspace/delivery-attache-current-future-actions.js"
        ).as_uri()
        script = textwrap.dedent(
            f"""
            const {{ createDeliveryAttacheCurrentFutureActions }} = await import({actions_uri!r});
            const ready = {{
              row_id: "READY",
              selected: true,
              importable: true,
              is_duplicate: false,
              warnings: [],
              payment_eligibility: "NOT_REQUIRED",
              eligibility_proof: "server-proof-kept-opaque",
              issued_at: 2000000000,
              expires_at: 2000000900,
              suburb: "HALLAM",
              postcode: "3803",
              product_lines: [{{
                product_code: "RAGS",
                product_name: "RAGS",
                quantity: 10,
                unit: "KG",
                package_quantity: 1,
                package_unit: "BAG10",
              }}],
            }};
            const duplicate = {{
              row_id: "DUP",
              selected: false,
              importable: false,
              is_duplicate: true,
              warnings: [],
              payment_eligibility: "PAYMENT_REQUIRED",
              product_lines: [],
            }};
            const modalBody = {{ scrollTop: 710, scrollLeft: 17 }};
            let renders = 0;
            let previewCalls = 0;
            let boardGets = 0;
            let commitPayload = null;
            let commitResult = {{ imported_count: 1, skipped_count: 1 }};
            let classificationResolve;
            const classification = new Promise((resolve) => {{ classificationResolve = resolve; }});
            const state = {{
              isLoggedIn: true,
              authSessionVersion: 2,
              workspaceRoute: "delivery/task-pool",
              activeWorkspace: "delivery",
              dispatchDate: "2026-09-02",
              deliveryAttacheImportState: {{ isOpen: true }},
              deliveryDocumentImportState: {{
                isOpen: true,
                source: "attache-current-future",
              }},
              deliveryAttacheCurrentFutureImportState: {{
                isLoading: false,
                isCommitting: false,
                hasLoaded: true,
                fromDate: "2026-09-02",
                rows: [ready, duplicate],
                expandedRowIds: {{ READY: true }},
                search: "saved",
                filter: "SELECTED",
                error: "",
                success: "",
              }},
            }};
            globalThis.document = {{
              querySelector: (selector) =>
                selector === ".workspace-modal-body" ? modalBody : null,
            }};
            globalThis.requestAnimationFrame = (callback) => {{ callback(); return 1; }};
            const context = {{
              state,
              renderWorkspace: () => {{
                renders += 1;
                modalBody.scrollTop = 0;
                modalBody.scrollLeft = 0;
              }},
              confirmAction: () => true,
              api: {{
                previewDeliveryAttacheCurrentFutureInvoices: async () => {{
                  previewCalls += 1;
                  return {{ from_date: "2026-09-02", rows: [] }};
                }},
                commitDeliveryAttacheCurrentFutureInvoices: async (payload) => {{
                  commitPayload = payload;
                  return commitResult;
                }},
                classifyDeliveryArea: async () => classification,
              }},
              deliveryAttacheCurrentFutureRequestVersion: 0,
              deliveryAttacheCurrentFutureAreaClassificationVersions: {{}},
              actions: {{}},
            }};
            const capture = () => ({{
              route: state.workspaceRoute,
              dispatchDate: state.dispatchDate,
              activeWorkspace: state.activeWorkspace,
              authSessionVersion: state.authSessionVersion,
            }});
            context.actions.captureMutationContext = capture;
            context.actions.isDeliveryMutationCurrent = (snapshot) => Boolean(
              state.isLoggedIn
              && snapshot
              && snapshot.route === state.workspaceRoute
              && snapshot.dispatchDate === state.dispatchDate
              && snapshot.activeWorkspace === state.activeWorkspace
              && snapshot.authSessionVersion === state.authSessionVersion
            );
            context.actions.loadDeliveryRoute = async () => {{ boardGets += 1; }};
            context.actions.runDeliveryAction = async (_key, operation, onError) => {{
              try {{ await operation(capture()); }} catch (error) {{ onError(error); }}
            }};
            const actions = createDeliveryAttacheCurrentFutureActions(context);
            Object.assign(context.actions, actions);

            actions.updateDeliveryAttacheCurrentFutureProductLine(
              "READY", 0, "product_name", "EDITED RAGS",
            );
            if (renders !== 0 || state.deliveryAttacheCurrentFutureImportState
                .rows[0].product_lines[0].product_name !== "EDITED RAGS") {{
              throw new Error("product typing caused render or lost local edit");
            }}
            actions.addDeliveryAttacheCurrentFutureProductLine("READY");
            actions.removeDeliveryAttacheCurrentFutureProductLine("READY", 1);
            if (renders !== 2 || modalBody.scrollTop !== 710 || modalBody.scrollLeft !== 17) {{
              throw new Error("structural product edits did not preserve modal scroll");
            }}
            let current = state.deliveryAttacheCurrentFutureImportState;
            if (current.search !== "saved" || current.filter !== "SELECTED"
                || !current.expandedRowIds.READY) {{
              throw new Error("product edits lost review state");
            }}
            actions.toggleDeliveryAttacheCurrentFutureRow("DUP", true);
            if (state.deliveryAttacheCurrentFutureImportState.rows[1].selected) {{
              throw new Error("duplicate row became selectable");
            }}

            const areaRequest = actions.classifyDeliveryAttacheCurrentFutureRow("READY");
            actions.updateDeliveryAttacheCurrentFutureImportRow("READY", "suburb", "RICHMOND");
            classificationResolve({{
              known: true,
              auto_delivery_region: "SOUTHEAST",
              auto_delivery_area: "SOUTHEAST",
              delivery_area: "SOUTHEAST",
            }});
            await areaRequest;
            current = state.deliveryAttacheCurrentFutureImportState;
            if (current.rows[0].auto_delivery_area) {{
              throw new Error("stale area classification overwrote the edited suburb");
            }}

            await actions.commitDeliveryAttacheCurrentFutureImport();
            if (previewCalls !== 0) throw new Error("commit called Attaché preview");
            if (boardGets !== 1) throw new Error("successful commit did not refresh the board once");
            if (commitPayload?.rows?.[0]?.product_lines?.[0]?.product_name !== "EDITED RAGS") {{
              throw new Error("commit payload lost the edited product");
            }}
            if (commitPayload.from_date !== "2026-09-02"
                || commitPayload.rows[0].eligibility_proof !== "server-proof-kept-opaque"
                || commitPayload.rows[0].issued_at !== 2000000000
                || commitPayload.rows[0].expires_at !== 2000000900) {{
              throw new Error("commit did not retain the signed preview facts unchanged");
            }}
            if (!state.deliveryAttacheCurrentFutureImportState.success.includes(
              "Imported 1 Delivery Orders",
            )) {{
              throw new Error("commit result was not retained");
            }}
            if (state.deliveryAttacheCurrentFutureImportState.rows[0].selected) {{
              throw new Error("successful commit left the imported row selected");
            }}

            commitResult = {{
              imported_count: 0, skipped_count: 1,
              skipped_rows: [{{ row_id: "READY", refresh_required: true }}],
            }};
            actions.toggleDeliveryAttacheCurrentFutureRow("READY", true);
            await actions.commitDeliveryAttacheCurrentFutureImport();
            if (!state.deliveryAttacheCurrentFutureImportState.error.includes(
                "Refresh Today & Future Invoices before importing")) {{
              throw new Error("invalid/expired preview did not explain refresh requirement");
            }}
            if (previewCalls !== 0) throw new Error("expired proof triggered an automatic Attaché lookup");

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
