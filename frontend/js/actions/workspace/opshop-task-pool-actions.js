export function createOpShopTaskPoolActions(context) {
  const {
    api,
    confirmAction,
    navigateWorkspaceRoute,
    renderWorkspace,
    state,
  } = context;

  const loadOpShopRoute = (...args) => context.actions.loadOpShopRoute(...args);
  const runOpShopAction = (...args) => context.actions.runOpShopAction(...args);
  const dispatchMetadataForContext = (...args) => context.actions.dispatchMetadataForContext(...args);
  const isOpShopMutationCurrent = (...args) => context.actions.isOpShopMutationCurrent(...args);

  function updateOpShopAssignmentDraft(pickupTaskId, driverId) {
    state.opshopAssignmentDrafts = {
      ...state.opshopAssignmentDrafts,
      [pickupTaskId]: driverId,
    };
    renderWorkspace();
  }

  async function applyOpShopAssignmentChanges(pickups) {
    const changedPickups = changedOpShopAssignmentDrafts(pickups);
    const changedAssignments = changedPickups.map((pickup) => ({
      pickup_task_id: pickup.pickup_task_id,
      driver_id: state.opshopAssignmentDrafts[pickup.pickup_task_id] || null,
    }));
    const submittedPickupIds = new Set(
      changedAssignments.map((assignment) => assignment.pickup_task_id),
    );

    if (!changedAssignments.length) {
      state.opshopActionError = "";
      renderWorkspace();
      return;
    }

    await runOpShopAction("opshop-apply-assignments", async (context) => {
      await api.applyOpShopWorkspaceAssignments({
        ...dispatchMetadataForContext(context),
        assignments: changedAssignments,
      });
      if (isOpShopMutationCurrent(context)) {
        state.opshopAssignmentDrafts = Object.fromEntries(
          Object.entries(state.opshopAssignmentDrafts || {}).filter(
            ([pickupTaskId]) => !submittedPickupIds.has(pickupTaskId),
          ),
        );
        await loadOpShopRoute(context.route);
      }
    });
  }

  async function unassignOpShopPickup(pickupTaskId) {
    await runOpShopAction(`opshop-unassign:${pickupTaskId}`, async (context) => {
      await api.unassignOpShopWorkspacePickup({
        ...dispatchMetadataForContext(context),
        pickup_task_id: pickupTaskId,
      });
      if (isOpShopMutationCurrent(context)) {
        const { [pickupTaskId]: _removed, ...remaining } = state.opshopAssignmentDrafts;
        state.opshopAssignmentDrafts = remaining;
        await loadOpShopRoute(context.route);
      }
    });
  }

  function updateCountrysideRouteGroupDraft(routeGroupId, field, value) {
    const current = state.countrysideRouteGroupDrafts[routeGroupId] || {};
    state.countrysideRouteGroupDrafts = {
      ...state.countrysideRouteGroupDrafts,
      [routeGroupId]: {
        pickup_date: state.dispatchDate,
        assigned_driver_id: "",
        notes: "",
        ...current,
        [field]: value,
      },
    };
    renderWorkspace();
  }

  async function assignCountrysideRouteGroup(routeGroupId) {
    const draft = {
      pickup_date: state.dispatchDate,
      assigned_driver_id: "",
      notes: "",
      ...(state.countrysideRouteGroupDrafts[routeGroupId] || {}),
    };
    await runOpShopAction(`opshop-route-group:${routeGroupId}`, async (context) => {
      await api.assignOpShopWorkspaceCountrysideRouteGroup(
        routeGroupId,
        {
          dispatch_date: context.dispatchDate,
          pickup_date: draft.pickup_date,
          assigned_driver_id: draft.assigned_driver_id,
          notes: draft.notes,
        },
      );
      if (isOpShopMutationCurrent(context)) {
        const { [routeGroupId]: _removed, ...remaining } = state.countrysideRouteGroupDrafts;
        state.countrysideRouteGroupDrafts = remaining;
        await loadOpShopRoute(context.route);
      }
    });
  }

  function changedOpShopAssignmentDrafts(pickups) {
    return (pickups || []).filter((pickup) => {
      if (!Object.prototype.hasOwnProperty.call(
        state.opshopAssignmentDrafts,
        pickup.pickup_task_id,
      )) {
        return false;
      }
      return state.opshopAssignmentDrafts[pickup.pickup_task_id] !== currentOpShopDriverId(pickup);
    });
  }

  function currentOpShopDriverId(pickup) {
    return pickup?.assigned_driver_id || pickup?.driver_id || "";
  }

  return {
    updateOpShopAssignmentDraft,
    applyOpShopAssignmentChanges,
    unassignOpShopPickup,
    updateCountrysideRouteGroupDraft,
    assignCountrysideRouteGroup,
    changedOpShopAssignmentDrafts,
    currentOpShopDriverId,
  };
}
