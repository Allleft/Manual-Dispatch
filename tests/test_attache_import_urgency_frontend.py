import subprocess
import textwrap
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"


NODE_HARNESS = r"""
import assert from "node:assert/strict";

class FakeNode {
  constructor(tagName, text = "") {
    this.tagName = tagName;
    this.nodeType = tagName === "#text" ? 3 : tagName === "#fragment" ? 11 : 1;
    this.children = [];
    this.parentNode = null;
    this.attributes = {};
    this.listeners = {};
    this.dataset = {};
    this.value = "";
    this._text = text;
    this.className = "";
    this.classList = {
      add: (...tokens) => {
        const classes = new Set(this.className.split(/\s+/).filter(Boolean));
        tokens.forEach((token) => classes.add(token));
        this.className = [...classes].join(" ");
      },
      contains: (token) => this.className.split(/\s+/).includes(token),
    };
  }
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
  async trigger(type) {
    for (const listener of this.listeners[type] || []) {
      await listener({ target: this, preventDefault() {}, stopPropagation() {} });
    }
  }
  focus() {}
  closest(selector) {
    for (let node = this; node; node = node.parentNode) {
      if (node.matches(selector)) return node;
    }
    return null;
  }
  replaceWith(replacement) {
    assert.ok(this.parentNode);
    const index = this.parentNode.children.indexOf(this);
    assert.ok(index >= 0);
    replacement.parentNode = this.parentNode;
    this.parentNode.children[index] = replacement;
    this.parentNode = null;
  }
  matches(selector) {
    if (selector.startsWith(".")) return this.classList.contains(selector.slice(1));
    return this.tagName.toLowerCase() === selector.toLowerCase();
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  querySelectorAll(selector) {
    const matches = [];
    const visit = (node) => {
      if (node.matches(selector)) matches.push(node);
      node.children.forEach(visit);
    };
    this.children.forEach(visit);
    return matches;
  }
}

globalThis.document = {
  activeElement: null,
  body: new FakeNode("body"),
  addEventListener() {},
  removeEventListener() {},
  createElement: (tagName) => new FakeNode(tagName),
  createElementNS: (_namespace, tagName) => new FakeNode(tagName),
  createTextNode: (text) => new FakeNode("#text", String(text)),
  createDocumentFragment: () => new FakeNode("#fragment"),
};

const {
  attacheRowStatus,
  createAttacheExpandedEditor,
  createAttacheReviewRow,
  createAttacheSummaryStrip,
  createDeliveryAttacheImportModal,
} = await import(__RENDERER_URI__);
const { createDeliveryAttacheActions } = await import(__ACTIONS_URI__);

function section(root, title) {
  const found = root.querySelectorAll(".workspace-form-section").find(
    (node) => node.querySelector("h4")?.textContent === title,
  );
  assert.ok(found, `Missing form section: ${title}`);
  return found;
}

function field(root, label) {
  const found = root.querySelectorAll("label").find(
    (node) => node.children[0]?.textContent === label,
  );
  assert.ok(found, `Missing form field: ${label}`);
  return found;
}

function urgencySelect(modal) {
  return field(modal.querySelector(".workspace-attache-review-summary"), "Urgency")
    .querySelector("select");
}

async function toggleExpanded(modal) {
  const button = modal.querySelector(".workspace-attache-review-header")
    .querySelector("button");
  assert.ok(button);
  await button.trigger("click");
}

function metric(strip, title) {
  const pill = strip.querySelectorAll(".workspace-metric-pill").find(
    (node) => node.querySelector("span")?.textContent === title,
  );
  assert.ok(pill, `Missing summary metric: ${title}`);
  return pill.querySelector("strong").textContent;
}

async function createHarness(urgency, overrides = {}) {
  const row = {
    row_id: "DIRECT-185479",
    invoice_number: "185479",
    invoice_date: "2026-09-04",
    order_no: "PO-1",
    company_name: "TEST CUSTOMER",
    phone: "0300000000",
    delivery_address: "1 TEST STREET",
    suburb: "HALLAM",
    postcode: "3803",
    delivery_date: "2026-09-07",
    delivery_area: "SOUTHEAST",
    auto_delivery_region: "SOUTHEAST",
    delivery_area_source: "AUTO",
    selected: true,
    importable: true,
    is_duplicate: false,
    pallet_quantity: 1,
    loose_bags_quantity: 2,
    carton_quantity: 3,
    product_lines: [{ product_code: "TEST", product_name: "TEST PRODUCT", quantity: 1 }],
    warnings: ["Review contact details."],
    note: "TEST NOTE",
    ...overrides,
  };
  if (urgency !== undefined) row.urgency = urgency;
  const state = { workspaceRoute: "delivery/task-pool" };
  const commits = [];
  const loadedRoutes = [];
  const discardPrompts = [];
  let allowDiscard = true;
  let renders = 0;
  const context = {
    state,
    renderWorkspace: () => { renders += 1; },
    confirmAction: (message) => { discardPrompts.push(message); return allowDiscard; },
    deliveryAttachePreviewRequestVersion: 0,
    deliveryAttacheDirectLookupRequestVersion: 0,
    api: {
      previewDirectAttacheInvoice: async (invoiceNumber) => {
        assert.equal(invoiceNumber, row.invoice_number);
        return { rows: [row] };
      },
      commitDeliveryAttacheInvoices: async (payload) => {
        commits.push(payload);
        return { imported_count: 1, skipped_count: 0 };
      },
    },
    actions: {
      captureMutationContext: () => ({ route: state.workspaceRoute }),
      isDeliveryMutationCurrent: () => true,
      loadDeliveryRoute: async (route) => { loadedRoutes.push(route); },
      runDeliveryAction: async (_key, operation, onError) => {
        try { await operation({ route: state.workspaceRoute }); }
        catch (error) { onError(error); }
      },
    },
  };
  const actions = createDeliveryAttacheActions(context);
  actions.openDeliveryAttacheImport();
  actions.chooseDeliveryImportSource("attache-direct");
  const lookupModal = createDeliveryAttacheImportModal(state, actions);
  assert.equal(lookupModal.querySelector(".workspace-modal").attributes["aria-label"],
    "Import from Attaché");
  assert.ok(lookupModal.querySelectorAll("button").some(
    (button) => button.textContent === "Find Invoice",
  ));
  actions.updateDeliveryDirectAttacheInvoiceNumber(row.invoice_number);
  await actions.lookupDeliveryDirectAttacheInvoice();
  const renderReview = () => createDeliveryAttacheImportModal(state, actions);
  return {
    state, actions, row, commits, loadedRoutes, discardPrompts, renderReview,
    modal: renderReview(),
    getRenders: () => renders,
    setAllowDiscard: (value) => { allowDiscard = value; },
  };
}
"""


class AttacheImportUrgencyFrontendTest(unittest.TestCase):
    def _run_node(self, body):
        renderer_uri = (
            FRONTEND_ROOT / "js/render/delivery/delivery-attache-modal-renderer.js"
        ).as_uri()
        actions_uri = (
            FRONTEND_ROOT / "js/actions/workspace/delivery-attache-actions.js"
        ).as_uri()
        script = NODE_HARNESS.replace("__RENDERER_URI__", repr(renderer_uri)).replace(
            "__ACTIONS_URI__", repr(actions_uri)
        ) + textwrap.dedent(body)
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
        self.assertEqual(0, result.returncode, result.stderr or result.stdout)

    def test_collapsed_summary_replaces_only_area_metadata_with_urgency(self):
        self._run_node(
            """
            const { modal } = await createHarness();
            assert.equal(modal.querySelector(".workspace-attache-expanded-editor"), null);
            const summary = modal.querySelector(".workspace-attache-review-summary");
            assert.doesNotMatch(summary.textContent, /Delivery Area|Region/);
            assert.deepEqual(summary.querySelectorAll(".workspace-inline-meta").map(
              (item) => item.children[0].textContent,
            ), ["Invoice", "Invoice Date", "Order", "Customer", "Suburb", "Urgency",
                "Delivery Date", "Load"]);
            assert.equal(summary.querySelectorAll("select").length, 1);
            assert.equal(urgencySelect(modal).value, "Normal");
            """
        )

    def test_expanded_editor_keeps_original_sections_area_region_and_urgency(self):
        self._run_node(
            """
            const { modal, row } = await createHarness("Urgent");
            await toggleExpanded(modal);
            const editor = modal.querySelector(".workspace-attache-expanded-editor");
            assert.ok(editor);
            assert.deepEqual(editor.querySelectorAll(".workspace-form-section").map(
              (item) => item.querySelector("h4").textContent,
            ), ["Customer and Invoice", "Delivery Details", "Delivery Area", "Load", "Notes"]);
            assert.doesNotMatch(editor.textContent, /General Information/);
            const area = section(editor, "Delivery Area");
            assert.deepEqual(area.querySelectorAll(".workspace-inline-meta").map(
              (item) => item.children[0].textContent,
            ), ["Effective Area", "Region", "Source"]);
            assert.match(area.textContent, /Effective AreaSouth East/);
            assert.match(area.textContent, /RegionSouth East/);
            assert.match(area.textContent, /SourceAutomatic/);
            const delivery = section(editor, "Delivery Details");
            assert.equal(field(delivery, "Urgency").querySelector("select").value, "Urgent");
            assert.equal(delivery.querySelectorAll("label").at(-1).children[0].textContent,
              "Urgency");
            assert.equal(editor.querySelectorAll("select").length, 1);
            for (const [label, value] of [
              ["Invoice Number", row.invoice_number], ["Invoice Date", row.invoice_date],
              ["Order Number", row.order_no], ["Company Name", row.company_name],
              ["Phone", row.phone], ["Delivery Address", row.delivery_address],
              ["Suburb", row.suburb], ["Postcode", row.postcode],
              ["Delivery Date", row.delivery_date],
            ]) {
              assert.equal(field(editor, label).querySelector("input").value, value);
            }
            assert.equal(field(editor, "Notes").querySelector("textarea").value, row.note);
            assert.ok(editor.querySelectorAll("input").some(
              (input) => input.value === row.product_lines[0].product_name,
            ));
            assert.match(modal.textContent, /Review contact details/);
            """
        )

    def test_urgency_is_a_native_select_with_exactly_normal_and_urgent_options(self):
        self._run_node(
            """
            const { modal } = await createHarness();
            const select = urgencySelect(modal);
            assert.equal(select.tagName, "select");
            assert.deepEqual(select.querySelectorAll("option").map(
              (option) => [option.value, option.textContent],
            ), [["Normal", "Normal"], ["Urgent", "Urgent"]]);
            assert.equal(select.attributes.multiple, undefined);
            """
        )

    def test_missing_urgency_defaults_to_normal_in_form_and_state(self):
        self._run_node(
            """
            for (const urgency of [undefined, null, ""]) {
              const { modal, state } = await createHarness(urgency);
              assert.equal(urgencySelect(modal).value, "Normal");
              assert.equal(state.deliveryAttacheImportState.rows[0].urgency, "Normal");
            }
            """
        )

    def test_existing_urgency_is_preserved_using_project_value_conventions(self):
        self._run_node(
            """
            for (const [urgency, expected] of [
              ["Normal", "Normal"], ["Urgent", "Urgent"], ["urgent", "Urgent"],
            ]) {
              const { modal, state } = await createHarness(urgency);
              assert.equal(urgencySelect(modal).value, expected);
              assert.equal(state.deliveryAttacheImportState.rows[0].urgency, expected);
            }
            """
        )

    def test_changing_select_updates_only_the_matching_row_and_survives_render(self):
        self._run_node(
            """
            const harness = await createHarness();
            const { modal, state, row } = harness;
            const otherRow = { ...row, row_id: "OTHER", urgency: "Normal" };
            state.deliveryAttacheImportState.rows.push(otherRow);
            const renders = harness.getRenders();
            const select = urgencySelect(modal);
            select.value = "Urgent";
            await select.trigger("change");
            assert.equal(state.deliveryAttacheImportState.rows[0].urgency, "Urgent");
            assert.equal(state.deliveryAttacheImportState.rows[1], otherRow);
            assert.equal(otherRow.urgency, "Normal");
            assert.equal(harness.getRenders(), renders);
            assert.equal(urgencySelect(harness.renderReview()).value, "Urgent");
            """
        )

    def test_summary_change_survives_expand_and_updates_visible_detail_select(self):
        self._run_node(
            """
            const harness = await createHarness();
            const { modal, state } = harness;
            const body = modal.querySelector(".workspace-modal-body");
            body.scrollTop = 720;
            const renders = harness.getRenders();
            let summarySelect = urgencySelect(modal);
            summarySelect.value = "Urgent";
            await summarySelect.trigger("change");
            assert.equal(summarySelect.value, "Urgent");
            await toggleExpanded(modal);
            const editor = modal.querySelector(".workspace-attache-expanded-editor");
            const detailSelect = field(section(editor, "Delivery Details"), "Urgency")
              .querySelector("select");
            assert.equal(detailSelect.value, "Urgent");
            summarySelect = urgencySelect(modal);
            summarySelect.value = "Normal";
            await summarySelect.trigger("change");
            assert.equal(detailSelect.value, "Normal");
            assert.equal(state.deliveryAttacheImportState.rows[0].urgency, "Normal");
            assert.equal(body.scrollTop, 720);
            assert.equal(harness.getRenders(), renders);
            """
        )

    def test_detail_change_updates_summary_immediately_and_survives_collapse(self):
        self._run_node(
            """
            const { modal, state } = await createHarness("Urgent");
            await toggleExpanded(modal);
            const editor = modal.querySelector(".workspace-attache-expanded-editor");
            const detailSelect = field(section(editor, "Delivery Details"), "Urgency")
              .querySelector("select");
            detailSelect.value = "Normal";
            await detailSelect.trigger("change");
            assert.equal(state.deliveryAttacheImportState.rows[0].urgency, "Normal");
            assert.equal(urgencySelect(modal).value, "Normal");
            await toggleExpanded(modal);
            assert.equal(modal.querySelector(".workspace-attache-expanded-editor"), null);
            assert.equal(urgencySelect(modal).value, "Normal");
            await toggleExpanded(modal);
            assert.equal(field(section(modal, "Delivery Details"), "Urgency")
              .querySelector("select").value, "Normal");
            """
        )

    def test_area_warnings_and_readiness_do_not_change_with_summary_urgency(self):
        self._run_node(
            """
            const warning = "Delivery area could not be determined from suburb/postcode. Needs Review.";
            const { modal, state } = await createHarness("Normal", {
              delivery_area: null, auto_delivery_region: null, warnings: [warning],
            });
            const rows = state.deliveryAttacheImportState.rows;
            const before = createAttacheSummaryStrip(rows);
            assert.equal(attacheRowStatus(rows[0]), "Warning");
            assert.equal(metric(before, "Ready to import"), "0");
            assert.equal(metric(before, "Warnings / parse issues"), "1");
            const select = urgencySelect(modal);
            select.value = "Urgent";
            await select.trigger("change");
            const current = state.deliveryAttacheImportState.rows;
            assert.deepEqual(current[0].warnings, [warning]);
            assert.equal(attacheRowStatus(current[0]), "Warning");
            assert.equal(createAttacheSummaryStrip(current).textContent, before.textContent);
            assert.ok(modal.querySelector(".workspace-attache-warning-summary")
              .textContent.includes(warning));
            await toggleExpanded(modal);
            assert.ok(modal.querySelector(".workspace-attache-expanded-editor")
              .textContent.includes(warning));
            assert.match(section(modal, "Delivery Area").textContent, /Needs Review/);

            const ready = await createHarness("Normal", { warnings: [] });
            const readyBefore = createAttacheSummaryStrip(ready.state.deliveryAttacheImportState.rows);
            assert.equal(metric(readyBefore, "Ready to import"), "1");
            assert.equal(metric(readyBefore, "Warnings / parse issues"), "0");
            const readySelect = urgencySelect(ready.modal);
            readySelect.value = "Urgent";
            await readySelect.trigger("change");
            assert.equal(attacheRowStatus(ready.state.deliveryAttacheImportState.rows[0]), "Ready");
            assert.equal(createAttacheSummaryStrip(ready.state.deliveryAttacheImportState.rows)
              .textContent, readyBefore.textContent);
            """
        )

    def test_confirm_import_includes_selected_urgency_and_keeps_success_flow(self):
        self._run_node(
            """
            const { modal, state, row, commits, loadedRoutes } = await createHarness();
            const select = urgencySelect(modal);
            select.value = "Urgent";
            await select.trigger("change");
            const confirm = modal.querySelectorAll("button").find(
              (button) => button.textContent.startsWith("Confirm Import"),
            );
            assert.ok(confirm);
            assert.equal(Boolean(confirm.disabled), false);
            await confirm.trigger("click");
            assert.equal(commits.length, 1);
            assert.equal(commits[0].rows[0].urgency, "Urgent");
            assert.equal(commits[0].rows[0].invoice_number, row.invoice_number);
            assert.equal(commits[0].rows[0].delivery_area, row.delivery_area);
            assert.equal(commits[0].rows[0].auto_delivery_region, row.auto_delivery_region);
            assert.deepEqual(commits[0].rows[0].product_lines, row.product_lines);
            assert.deepEqual(commits[0].rows[0].warnings, row.warnings);
            assert.equal(state.deliveryAttacheImportState.rows[0].urgency, "Urgent");
            assert.equal(state.deliveryAttacheImportState.rows[0].selected, false);
            assert.equal(state.deliveryAttacheImportState.isCommitting, false);
            assert.match(state.deliveryAttacheImportState.success, /Imported 1 Delivery Orders/);
            assert.deepEqual(loadedRoutes, ["delivery/task-pool"]);
            """
        )

    def test_confirm_defaults_older_drafts_without_urgency_to_normal(self):
        self._run_node(
            """
            const { actions, state, commits } = await createHarness();
            delete state.deliveryAttacheImportState.rows[0].urgency;
            await actions.commitDeliveryAttacheImport();
            assert.equal(commits.length, 1);
            assert.equal(commits[0].rows[0].urgency, "Normal");
            """
        )

    def test_cancel_preserves_declined_draft_then_closes_without_importing(self):
        self._run_node(
            """
            const harness = await createHarness();
            const { modal, state, commits, discardPrompts } = harness;
            const select = urgencySelect(modal);
            select.value = "Urgent";
            await select.trigger("change");
            const cancel = modal.querySelectorAll("button").find(
              (button) => button.textContent === "Cancel",
            );
            assert.ok(cancel);
            harness.setAllowDiscard(false);
            await cancel.trigger("click");
            assert.equal(state.deliveryAttacheImportState.isOpen, true);
            assert.equal(state.deliveryAttacheImportState.rows[0].urgency, "Urgent");
            harness.setAllowDiscard(true);
            await cancel.trigger("click");
            assert.equal(discardPrompts.length, 2);
            assert.equal(state.deliveryAttacheImportState.isOpen, false);
            assert.equal(state.deliveryDocumentImportState.isOpen, false);
            assert.deepEqual(state.deliveryAttacheImportState.rows, []);
            assert.equal(harness.renderReview().tagName, "#fragment");
            assert.equal(commits.length, 0);
            """
        )

    def test_shared_pdf_current_future_and_docket_editor_layouts_remain_unchanged(self):
        self._run_node(
            """
            const { row, actions } = await createHarness("Urgent");
            for (const reviewSource of [undefined, "attache", "attache-current-future"]) {
              const card = createAttacheReviewRow(row, {
                reviewSource, expandedRowIds: { [row.row_id]: true },
              }, actions);
              const summary = card.querySelector(".workspace-attache-review-summary");
              assert.match(summary.textContent, /Delivery Area/);
              assert.match(summary.textContent, /Region/);
              assert.equal(summary.querySelector("select"), null);
              const editor = card.querySelector(".workspace-attache-expanded-editor");
              assert.match(section(editor, "Delivery Area").textContent, /Region/);
              const select = field(section(editor, "Delivery Details"), "Urgency")
                .querySelector("select");
              assert.equal(select.value, "Urgent");
              assert.equal(editor.querySelectorAll("select").length, 1);
              assert.doesNotMatch(editor.textContent, /General Information/);
            }
            const sharedEditor = createAttacheExpandedEditor(row, actions);
            assert.match(section(sharedEditor, "Delivery Area").textContent, /Region/);
            assert.equal(field(section(sharedEditor, "Delivery Details"), "Urgency")
              .querySelector("select").value, "Urgent");
            """
        )


if __name__ == "__main__":
    unittest.main()
