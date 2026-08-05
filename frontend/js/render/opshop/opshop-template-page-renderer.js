import { createOpShopTemplateManagementPanel } from "../opshop-template-management-modal-renderer.js";

import { createCountrysideRouteManagementPanel } from "../opshop-countryside-pickup-list-modal-renderer.js";

import {
  createRouteActionLink,
  createSectionHeading,
  createEmptyState,
} from "./opshop-renderer-utils.js";

export function createTemplateManagementPage(state, actions) {
  if (!state.opshopBoard) {
    return createEmptyState("No OP SHOP template data loaded.", "store");
  }
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-stack";
  const toolbar = document.createElement("section");
  toolbar.className = "workspace-context-panel workspace-context-panel-opshop workspace-template-toolbar";
  toolbar.append(
    createSectionHeading("Manage OP SHOP Templates"),
    createRouteActionLink(
      "Back to Task Pool",
      `#${state.opshopTaskPoolReturnRoute || "opshop/task-pool/regular"}`,
    ),
  );
  wrapper.append(
    toolbar,
    createOpShopTemplateManagementPanel({
      onCancelForm: actions.cancelTemplateForm,
      onConfirmDisable: actions.disableTemplate,
      onSave: actions.saveTemplate,
      onSelectTab: actions.selectTemplateTab,
      onStartAdd: actions.startAddTemplate,
      onStartDisable: actions.startDisableTemplate,
      onStartEdit: actions.startEditTemplate,
      onToggleIncludeInactive: actions.toggleTemplateIncludeInactive,
      onUpdateForm: actions.updateTemplateForm,
    }),
    createSectionHeading(
      "Countryside Route Management",
      "Create and maintain route groups and their ON_CALL + COUNTRYSIDE template memberships.",
    ),
    createCountrysideRouteManagementPanel({
      onAddRouteTemplate: actions.addCountrysideRouteTemplate,
      onCancelRouteGroupForm: actions.cancelCountrysideRouteGroupForm,
      onCancelRouteTemplateForm: actions.cancelCountrysideRouteTemplateForm,
      onCloseRouteTemplateDetail: actions.closeCountrysideRouteTemplateDetail,
      onCreateRouteGroup: actions.createCountrysideRouteGroup,
      onDisableRouteGroup: actions.disableCountrysideRouteGroup,
      onMoveRouteTemplate: actions.moveCountrysideRouteTemplate,
      onOpenRouteTemplateDetail: actions.openCountrysideRouteTemplateDetail,
      onRemoveRouteTemplate: actions.removeCountrysideRouteTemplate,
      onRenameRouteGroup: actions.renameCountrysideRouteGroup,
      onSelectRouteGroup: actions.selectCountrysideRouteGroup,
      onStartAddRouteTemplate: actions.startAddCountrysideRouteTemplate,
      onStartDisableRouteGroup: actions.startDisableCountrysideRouteGroup,
      onStartMoveRouteTemplate: actions.startMoveCountrysideRouteTemplate,
      onStartNewRouteGroup: actions.startNewCountrysideRouteGroup,
      onStartRemoveRouteTemplate: actions.startRemoveCountrysideRouteTemplate,
      onStartRenameRouteGroup: actions.startRenameCountrysideRouteGroup,
      onUpdateRouteGroupForm: actions.updateCountrysideRouteGroupForm,
      onUpdateRouteTemplateForm: actions.updateCountrysideRouteTemplateForm,
    }),
  );
  return wrapper;
}
