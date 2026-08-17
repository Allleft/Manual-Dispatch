import subprocess
import textwrap
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"


class DeliveryDocketFrontendTest(unittest.TestCase):
    def test_source_chooser_docket_review_and_api_contract_are_wired(self):
        renderer = (FRONTEND_ROOT / "js/render/delivery/delivery-attache-modal-renderer.js").read_text(encoding="utf-8")
        task_pool = (FRONTEND_ROOT / "js/render/delivery/delivery-task-pool-renderer.js").read_text(encoding="utf-8")
        api = (FRONTEND_ROOT / "js/api/manual-dispatch/delivery-api.js").read_text(encoding="utf-8")
        state = (FRONTEND_ROOT / "js/state/app-state.js").read_text(encoding="utf-8")

        self.assertIn("Import Delivery Document", task_pool)
        self.assertIn("Import Delivery Document", renderer)
        self.assertIn("Attaché Invoice", renderer)
        self.assertIn("Delivery Docket", renderer)
        self.assertIn("Import Delivery Docket DOCX files.", renderer)
        self.assertIn("createDeliveryDocketReviewRow", renderer)
        self.assertIn('createInlineMeta("Docket", row.docket_number)', renderer)
        self.assertIn('createFormSection("Source Information"', renderer)
        self.assertIn("deliveryDocumentImportState", state)
        self.assertIn("deliveryDocketImportState", state)
        self.assertIn("import-delivery-docket-docx-preview", api)
        self.assertIn("import-delivery-docket-docx-commit", api)

    def test_docket_actions_keep_draft_local_and_use_only_docket_api(self):
        actions_uri = (
            FRONTEND_ROOT / "js/actions/workspace/delivery-docket-actions.js"
        ).as_uri()
        script = textwrap.dedent(
            r"""
            const { createDeliveryDocketActions } = await import("__ACTIONS_URI__");
            const state = {
              workspaceRoute: "delivery/task-pool",
              activeWorkspace: "delivery",
              isLoggedIn: true,
              authSessionVersion: 1,
              dispatchDate: "2026-08-13",
              deliveryAttacheImportState: { isOpen: true },
              deliveryDocumentImportState: { isOpen: true, source: "docket" },
              deliveryDocketImportState: {
                step: "files", files: [], rows: [], expandedRowIds: {},
                search: "", filter: "ALL", error: "", success: "",
              },
            };
            let renders = 0;
            let boardGets = 0;
            let previews = 0;
            let commits = 0;
            const context = {
              state,
              renderWorkspace: () => { renders += 1; },
              api: {
                getDeliveryWorkspaceBoard: async () => { boardGets += 1; },
                previewDeliveryDockets: async (files) => {
                  previews += 1;
                  return { rows: [{
                    row_id: "DOCKET-4373", docket_number: "4373", selected: true,
                    importable: true, is_duplicate: false, company_name: "CUSTOMER",
                  }] };
                },
                commitDeliveryDockets: async (payload) => {
                  commits += 1;
                  if (payload.rows[0].company_name !== "EDITED CUSTOMER") {
                    throw new Error("commit did not send current edited row");
                  }
                  return { imported_count: 1, skipped_count: 0 };
                },
              },
              deliveryDocketPreviewRequestVersion: 0,
              actions: {},
            };
            context.actions.captureMutationContext = () => ({
              route: state.workspaceRoute,
              dispatchDate: state.dispatchDate,
              activeWorkspace: state.activeWorkspace,
              authSessionVersion: state.authSessionVersion,
            });
            context.actions.isDeliveryMutationCurrent = () => true;
            context.actions.runDeliveryAction = async (_key, callback) => callback({ route: state.workspaceRoute });
            context.actions.loadDeliveryRoute = async () => {};
            const actions = createDeliveryDocketActions(context);

            actions.updateDeliveryDocketImportFiles([
              { name: "4373.docx", type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" },
              { name: "wrong.pdf", type: "application/pdf" },
            ]);
            if (state.deliveryDocketImportState.files.length !== 1) throw new Error("DOCX filter failed");
            if (!state.deliveryDocketImportState.error.includes("non-DOCX")) throw new Error("rejection message missing");
            await actions.previewDeliveryDocketImport();
            if (previews !== 1 || state.deliveryDocketImportState.step !== "review") {
              throw new Error("Docket preview path failed");
            }
            const renderBeforeToggle = renders;
            const next = actions.toggleDeliveryDocketImportExpanded("DOCKET-4373");
            if (!next.expandedRowIds["DOCKET-4373"]) throw new Error("expand state failed");
            if (renders !== renderBeforeToggle || boardGets !== 0) {
              throw new Error("local Docket toggle rendered or fetched the board");
            }
            actions.updateDeliveryDocketImportRow("DOCKET-4373", "company_name", "EDITED CUSTOMER");
            await actions.commitDeliveryDocketImport();
            if (commits !== 1) throw new Error("Docket commit API was not called once");
            if (state.workspaceRoute !== "delivery/task-pool") throw new Error("Docket actions changed route");
            """
        ).replace("__ACTIONS_URI__", actions_uri)
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr or result.stdout)

    def test_docket_file_selection_accepts_30_and_rejects_31_without_preview(self):
        actions_uri = (
            FRONTEND_ROOT / "js/actions/workspace/delivery-docket-actions.js"
        ).as_uri()
        script = textwrap.dedent(
            r"""
            const { createDeliveryDocketActions } = await import("__ACTIONS_URI__");
            const state = {
              workspaceRoute: "delivery/task-pool",
              activeWorkspace: "delivery",
              isLoggedIn: true,
              authSessionVersion: 1,
              dispatchDate: "2026-08-13",
              deliveryAttacheImportState: { isOpen: true },
              deliveryDocumentImportState: { isOpen: true, source: "docket" },
              deliveryDocketImportState: {
                step: "files", files: [], rows: [], expandedRowIds: {}, error: "", success: "",
              },
            };
            let previewCalls = 0;
            const context = {
              state,
              renderWorkspace: () => {},
              api: {
                previewDeliveryDockets: async (files) => {
                  previewCalls += 1;
                  return { rows: files.map((_file, index) => ({
                    row_id: `ROW-${index}`, selected: true, importable: true, is_duplicate: false,
                  })) };
                },
              },
              deliveryDocketPreviewRequestVersion: 0,
              actions: {},
            };
            context.actions.captureMutationContext = () => ({
              route: state.workspaceRoute,
              dispatchDate: state.dispatchDate,
              activeWorkspace: state.activeWorkspace,
              authSessionVersion: state.authSessionVersion,
            });
            context.actions.isDeliveryMutationCurrent = () => true;
            const actions = createDeliveryDocketActions(context);
            const docx = (index) => ({
              name: `docket-${index}.docx`,
              type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            });

            actions.updateDeliveryDocketImportFiles(Array.from({ length: 30 }, (_item, index) => docx(index)));
            if (state.deliveryDocketImportState.files.length !== 30 || state.deliveryDocketImportState.error) {
              throw new Error("exactly 30 Docket files were not accepted");
            }
            await actions.previewDeliveryDocketImport();
            if (previewCalls !== 1 || state.deliveryDocketImportState.rows.length !== 30) {
              throw new Error("30-file Docket preview did not use one batch request");
            }

            actions.updateDeliveryDocketImportFiles(Array.from({ length: 31 }, (_item, index) => docx(index)));
            if (state.deliveryDocketImportState.files.length !== 0
                || state.deliveryDocketImportState.rows.length !== 0
                || state.deliveryDocketImportState.error !== "You can import up to 30 files at a time.") {
              throw new Error("31-file Docket selection was not rejected as a whole batch");
            }
            await actions.previewDeliveryDocketImport();
            if (previewCalls !== 1) throw new Error("rejected Docket batch reached Preview API");
            """
        ).replace("__ACTIONS_URI__", actions_uri)
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr or result.stdout)

    def test_source_back_preserves_separate_drafts_without_board_reload(self):
        attache_uri = (
            FRONTEND_ROOT / "js/actions/workspace/delivery-attache-actions.js"
        ).as_uri()
        docket_uri = (
            FRONTEND_ROOT / "js/actions/workspace/delivery-docket-actions.js"
        ).as_uri()
        script = textwrap.dedent(
            r"""
            const { createDeliveryAttacheActions } = await import("__ATTACHE_URI__");
            const { createDeliveryDocketActions } = await import("__DOCKET_URI__");
            const state = {
              workspaceRoute: "delivery/task-pool",
              deliveryAttacheImportState: {},
              deliveryDocketImportState: {},
            };
            let renders = 0;
            let boardGets = 0;
            const context = {
              state,
              api: { getDeliveryWorkspaceBoard: async () => { boardGets += 1; } },
              confirmAction: () => true,
              navigateWorkspaceRoute: () => { throw new Error("source selection changed route"); },
              renderWorkspace: () => { renders += 1; },
              deliveryAttachePreviewRequestVersion: 0,
              deliveryDocketPreviewRequestVersion: 0,
              actions: {},
            };
            Object.assign(context.actions, createDeliveryAttacheActions(context));
            Object.assign(context.actions, createDeliveryDocketActions(context));
            context.actions.openDeliveryAttacheImport();
            if (state.deliveryDocumentImportState.source !== "chooser") throw new Error("entry skipped chooser");
            context.actions.chooseDeliveryImportSource("docket");
            context.actions.updateDeliveryDocketImportFiles([
              { name: "4373.docx", type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" },
            ]);
            context.actions.backDeliveryImportToSources();
            if (state.deliveryDocumentImportState.source !== "chooser") throw new Error("Back missed chooser");
            if (state.deliveryDocketImportState.files[0].name !== "4373.docx") throw new Error("Back lost Docket draft");
            context.actions.chooseDeliveryImportSource("attache");
            context.actions.updateDeliveryAttacheImportFiles([
              { name: "invoice.pdf", type: "application/pdf" },
            ]);
            context.actions.backDeliveryImportToSources();
            context.actions.chooseDeliveryImportSource("docket");
            if (state.deliveryDocketImportState.files[0].name !== "4373.docx") throw new Error("Attaché draft mixed with Docket draft");
            if (state.deliveryAttacheImportState.files[0].name !== "invoice.pdf") throw new Error("Docket draft mixed with Attaché draft");
            if (state.workspaceRoute !== "delivery/task-pool") throw new Error("source flow changed route");
            if (boardGets !== 0) throw new Error("source flow fetched board");
            if (renders < 1) throw new Error("source flow did not render locally");
            """
        ).replace("__ATTACHE_URI__", attache_uri).replace("__DOCKET_URI__", docket_uri)
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr or result.stdout)

    def test_existing_local_order_search_finds_docket_note_without_api(self):
        renderer_uri = (
            FRONTEND_ROOT / "js/render/delivery/delivery-task-pool-renderer.js"
        ).as_uri()
        script = textwrap.dedent(
            r"""
            const { filterDeliveryTaskPoolOrders } = await import("__RENDERER_URI__");
            const orders = [
              { order_id: "DOCKET", urgency: "Normal", note: "Delivery Docket: 4373\nDocket Reference: 185504" },
              { order_id: "OTHER", urgency: "Normal", note: "unrelated" },
            ];
            const result = filterDeliveryTaskPoolOrders(orders, {
              search: "4373", delivery_date: "", urgency: "All",
            });
            if (result.length !== 1 || result[0].order_id !== "DOCKET") {
              throw new Error("existing local Search Orders did not index the Docket note");
            }
            """
        ).replace("__RENDERER_URI__", renderer_uri)
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr or result.stdout)

    def test_docket_expand_collapse_is_targeted_and_preserves_scroll_focus(self):
        renderer_uri = (
            FRONTEND_ROOT / "js/render/delivery/delivery-attache-modal-renderer.js"
        ).as_uri()
        actions_uri = (
            FRONTEND_ROOT / "js/actions/workspace/delivery-docket-actions.js"
        ).as_uri()
        script = textwrap.dedent(
            r"""
            class FakeNode {
              constructor(tagName, text = "") {
                this.tagName = tagName;
                this.nodeType = tagName === "#text" ? 3 : 1;
                this.children = [];
                this.parentNode = null;
                this.attributes = {};
                this.listeners = {};
                this.dataset = {};
                this.disabled = false;
                this.checked = false;
                this.value = "";
                this.type = "";
                this.scrollTop = 0;
                this._text = text;
                this._className = "";
                this.classList = {
                  add: (...tokens) => {
                    const values = new Set(this._className.split(/\s+/).filter(Boolean));
                    tokens.forEach((token) => values.add(token));
                    this._className = [...values].join(" ");
                  },
                  contains: (token) => this._className.split(/\s+/).includes(token),
                };
              }
              get className() { return this._className; }
              set className(value) { this._className = String(value || ""); }
              get textContent() { return this._text + this.children.map((child) => child.textContent || "").join(""); }
              set textContent(value) { this._text = String(value ?? ""); this.children = []; }
              append(...children) {
                children.forEach((child) => {
                  if (child === null || child === undefined) return;
                  child.parentNode = this;
                  this.children.push(child);
                });
              }
              setAttribute(name, value) { this.attributes[name] = String(value); }
              addEventListener(type, listener) { (this.listeners[type] ||= []).push(listener); }
              focus(options) { this.focusOptions = options; document.activeElement = this; }
              matches(selector) {
                if (selector.startsWith(".")) return this.classList.contains(selector.slice(1));
                return String(this.tagName).toLowerCase() === selector.toLowerCase();
              }
              closest(selector) {
                let current = this;
                while (current) {
                  if (current.matches?.(selector)) return current;
                  current = current.parentNode;
                }
                return null;
              }
              replaceWith(replacement) {
                const index = this.parentNode.children.indexOf(this);
                replacement.parentNode = this.parentNode;
                this.parentNode.children[index] = replacement;
                this.parentNode = null;
              }
              querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
              querySelectorAll(selector) {
                const result = [];
                const visit = (node) => {
                  if (node.matches?.(selector)) result.push(node);
                  node.children?.forEach(visit);
                };
                this.children.forEach(visit);
                return result;
              }
            }
            globalThis.document = {
              activeElement: null,
              createElement: (tag) => new FakeNode(tag),
              createElementNS: (_namespace, tag) => new FakeNode(tag),
              createTextNode: (text) => new FakeNode("#text", String(text)),
              createDocumentFragment: () => new FakeNode("#fragment"),
            };
            const { createDeliveryDocketReviewRow } = await import("__RENDERER_URI__");
            const { createDeliveryDocketActions } = await import("__ACTIONS_URI__");
            const row = {
              row_id: "DOCKET-4373", docket_number: "4373", docket_reference: "185504",
              invoice_number: "185504", invoice_date: "2026-08-11", order_no: "40592",
              company_name: "NOEL'S AUTO PARTS", suburb: "SUNSHINE WEST",
              delivery_address: "30 SPENCER STREET", delivery_date: "2026-08-14",
              pallet_quantity: 1, loose_bags_quantity: 0, carton_quantity: 0,
              product_lines: [], warnings: [], selected: true, importable: true,
              is_duplicate: false, note: "Delivery Docket: 4373",
            };
            const state = {
              workspaceRoute: "delivery/task-pool",
              deliveryDocketImportState: { rows: [row], expandedRowIds: {}, search: "4373", filter: "ALL" },
            };
            let renders = 0;
            let boardGets = 0;
            const actions = createDeliveryDocketActions({
              state,
              renderWorkspace: () => { renders += 1; },
              api: { getDeliveryWorkspaceBoard: async () => { boardGets += 1; } },
              actions: {},
            });
            const body = new FakeNode("div");
            body.className = "workspace-modal-body";
            const list = new FakeNode("div");
            list.append(createDeliveryDocketReviewRow(row, state.deliveryDocketImportState, actions));
            body.append(list);
            body.scrollTop = 720;
            const expected = [
              "Docket", "Invoice", "Invoice Date", "Order", "Customer", "Suburb",
              "Delivery Area", "Region", "Delivery Date", "Load",
            ];
            let card = list.children[0];
            const labels = card.querySelectorAll(".workspace-inline-meta").map((item) => item.children[0].textContent);
            if (labels.join("|") !== expected.join("|")) throw new Error(`summary order ${labels.join("|")}`);
            const click = (button) => button.listeners.click[0]({ stopPropagation: () => {} });
            let toggle = card.querySelector("button");
            click(toggle);
            card = list.children[0];
            toggle = card.querySelector("button");
            if (!card.querySelector(".workspace-docket-expanded-editor")) throw new Error("Docket did not expand");
            if (body.scrollTop !== 720) throw new Error("Docket expand reset scroll");
            if (document.activeElement !== toggle || !toggle.focusOptions?.preventScroll) throw new Error("Docket expand lost stable focus");
            actions.updateDeliveryDocketImportRow("DOCKET-4373", "company_name", "EDITED CUSTOMER");
            click(toggle);
            card = list.children[0];
            if (card.querySelector(".workspace-docket-expanded-editor")) throw new Error("Docket did not collapse");
            if (body.scrollTop !== 720) throw new Error("Docket collapse reset scroll");
            const collapsedCustomer = card.querySelectorAll(".workspace-inline-meta")
              .find((item) => item.children[0].textContent === "Customer");
            if (collapsedCustomer?.children[1].textContent !== "EDITED CUSTOMER") {
              throw new Error("Docket collapse restored stale edited values");
            }
            toggle = card.querySelector("button");
            click(toggle);
            card = list.children[0];
            const expandedCustomer = card.querySelectorAll(".workspace-inline-meta")
              .find((item) => item.children[0].textContent === "Customer");
            if (expandedCustomer?.children[1].textContent !== "EDITED CUSTOMER") {
              throw new Error("Docket re-expand restored stale edited values");
            }
            if (renders !== 0 || boardGets !== 0) throw new Error("Docket toggle rendered broadly or fetched board");
            if (state.workspaceRoute !== "delivery/task-pool") throw new Error("Docket toggle changed route");
            if (!row.selected || state.deliveryDocketImportState.search !== "4373") throw new Error("Docket toggle lost state");
            """
        ).replace("__RENDERER_URI__", renderer_uri).replace("__ACTIONS_URI__", actions_uri)
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
