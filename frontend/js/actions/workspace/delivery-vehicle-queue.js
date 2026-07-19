import { getDeliveryVehicleConflictDriverNames } from "../../utils/delivery-vehicle-utils.js";

export function createDeliveryVehicleQueue(context) {
  const {
    api,
    confirmAction,
    navigateWorkspaceRoute,
    renderWorkspace,
    state,
  } = context;

  const handleWorkspaceMigrationGuard = (...args) => context.actions.handleWorkspaceMigrationGuard(...args);
  const currentDeliveryBoard = (...args) => context.actions.currentDeliveryBoard(...args);
  const captureMutationContext = (...args) => context.actions.captureMutationContext(...args);

  async function updateDeliveryVehicleSelection(deliveryDate, driverId, vehicleId) {
    const key = deliveryVehicleKey(deliveryDate, driverId);
    state.deliveryVehicleDrafts = {
      ...(state.deliveryVehicleDrafts || {}),
      [key]: vehicleId,
    };
    updateDeliveryVehicleClaim(key, vehicleId);
    clearDeliveryVehicleError(key);
    renderWorkspace();
    const currentAssignment = (state.deliveryBoard?.driver_vehicle_assignments || []).find(
      (assignment) =>
        assignment.delivery_date === deliveryDate && assignment.driver_id === driverId,
    );
    const conflictDriverNames = getDeliveryVehicleConflictDriverNames({
      board: state.deliveryBoard,
      claims: state.deliveryVehicleClaims,
      deliveryDate,
      driverId,
      vehicleId,
    });
    if (conflictDriverNames.length) {
      renderWorkspace();
      return;
    }
    if (
      !vehicleId
      && !currentAssignment
      && !context.deliveryVehicleQueues.has(key)
      && !context.deliveryVehiclePhysicalTails.has(key)
    ) {
      removeDeliveryVehicleDraft(key);
      renderWorkspace();
      retryAvailableDeliveryVehicleClaims(key);
      return;
    }
    return queueDeliveryVehicleUpdate(deliveryDate, driverId);
  }

  function queueDeliveryVehicleUpdate(deliveryDate, driverId) {
    const key = deliveryVehicleKey(deliveryDate, driverId);
    const existingEntry = context.deliveryVehicleQueues.get(key);
    if (existingEntry?.mutationVersion === context.deliveryVehicleMutationVersion) {
      return existingEntry.promise;
    }
    const entry = {
      queueId: ++context.deliveryVehicleQueueIdCounter,
      mutationVersion: context.deliveryVehicleMutationVersion,
      deliveryDate,
      promise: null,
    };
    state.deliveryVehiclePendingKeys = {
      ...(state.deliveryVehiclePendingKeys || {}),
      [key]: true,
    };
    renderWorkspace();
    context.deliveryVehicleQueues.set(key, entry);
    entry.promise = enqueueDeliveryVehiclePhysicalWrite(
      key,
      () => processDeliveryVehicleQueue(entry, deliveryDate, driverId),
    )
      .catch((error) => {
        if (isDeliveryVehicleQueueCurrent(key, entry)) {
          state.deliveryVehicleErrors = {
            ...(state.deliveryVehicleErrors || {}),
            [key]: error.message || "Unable to update Vehicle.",
          };
        }
      })
      .finally(() => {
        if (context.deliveryVehicleQueues.get(key) !== entry) {
          return;
        }
        context.deliveryVehicleQueues.delete(key);
        const { [key]: _removed, ...remaining } = state.deliveryVehiclePendingKeys || {};
        state.deliveryVehiclePendingKeys = remaining;
        if (
          entry.mutationVersion === context.deliveryVehicleMutationVersion
          && state.isLoggedIn
          && state.activeWorkspace === "delivery"
          && state.workspaceRoute === "delivery/trip-summary"
        ) {
          renderWorkspace();
        }
      });
    return entry.promise;
  }

  function enqueueDeliveryVehiclePhysicalWrite(key, operation) {
    const previousTail = context.deliveryVehiclePhysicalTails.get(key);
    const operationPromise = previousTail
      ? previousTail.catch(() => {}).then(operation)
      : Promise.resolve(operation());
    const settledTail = operationPromise.catch(() => {});
    context.deliveryVehiclePhysicalTails.set(key, settledTail);
    settledTail.finally(() => {
      if (context.deliveryVehiclePhysicalTails.get(key) === settledTail) {
        context.deliveryVehiclePhysicalTails.delete(key);
      }
    });
    return operationPromise;
  }

  async function processDeliveryVehicleQueue(entry, deliveryDate, driverId) {
    const key = deliveryVehicleKey(deliveryDate, driverId);
    while (
      isDeliveryVehicleQueueCurrent(key, entry)
      && Object.prototype.hasOwnProperty.call(state.deliveryVehicleDrafts || {}, key)
    ) {
      const vehicleId = state.deliveryVehicleDrafts[key];
      const conflicts = getDeliveryVehicleConflictDriverNames({
        board: currentDeliveryBoard(),
        claims: state.deliveryVehicleClaims,
        deliveryDate,
        driverId,
        vehicleId,
      });
      if (conflicts.length) {
        return;
      }
      const currentAssignment = (currentDeliveryBoard()?.driver_vehicle_assignments || []).find(
        (assignment) =>
          assignment.delivery_date === deliveryDate && assignment.driver_id === driverId,
      );
      if (currentAssignment?.vehicle_id === vehicleId) {
        removeDeliveryVehicleDraft(key);
        removeDeliveryVehicleClaim(key);
        clearDeliveryVehicleError(key);
        return;
      }
      const context = {
        ...captureMutationContext(),
        deliveryDate: state.deliveryTripSummaryDate,
      };
      let updatedBoard;
      try {
        updatedBoard = vehicleId
          ? await api.assignDeliveryWorkspaceVehicle({
            delivery_date: deliveryDate,
            driver_id: driverId,
            vehicle_id: vehicleId,
          })
          : await api.clearDeliveryWorkspaceVehicle({
            delivery_date: deliveryDate,
            driver_id: driverId,
          });
      } catch (error) {
        if (!isDeliveryVehicleQueueCurrent(key, entry)) {
          return;
        }
        if (await handleWorkspaceMigrationGuard(error)) {
          return;
        }
        if (state.deliveryVehicleDrafts?.[key] === vehicleId) {
          state.deliveryVehicleErrors = {
            ...(state.deliveryVehicleErrors || {}),
            [key]: error.message,
          };
          return;
        }
        continue;
      }
      if (!isDeliveryVehicleQueueCurrent(key, entry)) {
        return;
      }
      applyDeliveryVehicleBoardUpdate(updatedBoard, deliveryDate, driverId);
      if (state.deliveryVehicleDrafts?.[key] === vehicleId) {
        removeDeliveryVehicleDraft(key);
        removeDeliveryVehicleClaim(key);
        clearDeliveryVehicleError(key);
        retryAvailableDeliveryVehicleClaims(key);
        return;
      }
    }
  }

  function retryAvailableDeliveryVehicleClaims(excludedKey) {
    Object.entries(state.deliveryVehicleClaims || {})
      .sort((left, right) => Number(left[1].sequence) - Number(right[1].sequence))
      .forEach(([key, claim]) => {
        if (!claim?.vehicle_id || key === excludedKey || context.deliveryVehicleQueues.has(key)) {
          return;
        }
        const separatorIndex = key.indexOf("|");
        if (separatorIndex < 0) {
          return;
        }
        const deliveryDate = key.slice(0, separatorIndex);
        const driverId = key.slice(separatorIndex + 1);
        const conflicts = getDeliveryVehicleConflictDriverNames({
          board: currentDeliveryBoard(),
          claims: state.deliveryVehicleClaims,
          deliveryDate,
          driverId,
          vehicleId: claim.vehicle_id,
        });
        if (!conflicts.length) {
          queueDeliveryVehicleUpdate(deliveryDate, driverId);
        }
      });
  }

  function isDeliveryVehicleQueueCurrent(key, entry) {
    return (
      context.deliveryVehicleQueues.get(key) === entry
      && entry.mutationVersion === context.deliveryVehicleMutationVersion
      && state.isLoggedIn
      && state.workspaceRoute === "delivery/trip-summary"
      && state.activeWorkspace === "delivery"
      && (state.deliveryTripSummaryDate || entry.deliveryDate) === entry.deliveryDate
    );
  }

  function updateDeliveryVehicleClaim(key, vehicleId) {
    if (!vehicleId) {
      removeDeliveryVehicleClaim(key);
      return;
    }
    const existing = state.deliveryVehicleClaims?.[key];
    if (existing?.vehicle_id === vehicleId) {
      return;
    }
    state.deliveryVehicleClaimSequence = Number(state.deliveryVehicleClaimSequence || 0) + 1;
    state.deliveryVehicleClaims = {
      ...(state.deliveryVehicleClaims || {}),
      [key]: {
        vehicle_id: vehicleId,
        sequence: state.deliveryVehicleClaimSequence,
      },
    };
  }

  function removeDeliveryVehicleDraft(key) {
    const { [key]: _removed, ...remaining } = state.deliveryVehicleDrafts || {};
    state.deliveryVehicleDrafts = remaining;
  }

  function removeDeliveryVehicleClaim(key) {
    const { [key]: _removed, ...remaining } = state.deliveryVehicleClaims || {};
    state.deliveryVehicleClaims = remaining;
  }

  function clearDeliveryVehicleError(key) {
    const { [key]: _removed, ...remaining } = state.deliveryVehicleErrors || {};
    state.deliveryVehicleErrors = remaining;
  }

  function applyDeliveryVehicleBoardUpdate(updatedBoard, deliveryDate, driverId) {
    if (!updatedBoard) {
      return;
    }
    const targetBoard = currentDeliveryBoard();
    const otherAssignments = (targetBoard?.driver_vehicle_assignments || []).filter(
      (assignment) =>
        assignment.delivery_date !== deliveryDate || assignment.driver_id !== driverId,
    );
    const updatedAssignment = (updatedBoard.driver_vehicle_assignments || []).filter(
      (assignment) =>
        assignment.delivery_date === deliveryDate && assignment.driver_id === driverId,
    );
    const nextBoard = {
      ...(targetBoard || {}),
      driver_vehicle_assignments: otherAssignments.concat(updatedAssignment),
    };
    if (state.workspaceRoute === "delivery/trip-summary" && state.deliveryTripSummaryBoard) {
      state.deliveryTripSummaryBoard = nextBoard;
    } else {
      state.deliveryBoard = nextBoard;
    }
  }

  function pruneDeliveryVehicleDrafts(board = state.deliveryBoard) {
    const vehicleKeys = new Set();
    (board?.driver_vehicle_assignments || []).forEach((assignment) => {
      vehicleKeys.add(deliveryVehicleKey(assignment.delivery_date, assignment.driver_id));
    });
    (board?.assignments || []).forEach((assignment) => {
      const order = (board?.orders || []).find(
        (item) => item.order_id === assignment.task_id,
      );
      if (order?.delivery_date) {
        vehicleKeys.add(deliveryVehicleKey(order.delivery_date, assignment.driver_id));
      }
    });
    (board?.drivers || []).forEach((driver) => {
      vehicleKeys.add(deliveryVehicleKey(
        state.deliveryTripSummaryDate || state.dispatchDate,
        driver.driver_id,
      ));
    });
    state.deliveryVehicleDrafts = Object.fromEntries(
      Object.entries(state.deliveryVehicleDrafts || {}).filter(([key, vehicleId]) => {
        if (!vehicleKeys.has(key)) {
          return false;
        }
        const separatorIndex = key.indexOf("|");
        const deliveryDate = key.slice(0, separatorIndex);
        const driverId = key.slice(separatorIndex + 1);
        return !(board?.driver_vehicle_assignments || []).some(
          (assignment) =>
            assignment.delivery_date === deliveryDate
            && assignment.driver_id === driverId
            && assignment.vehicle_id === vehicleId,
        );
      }),
    );
    state.deliveryVehicleClaims = Object.fromEntries(
      Object.entries(state.deliveryVehicleClaims || {}).filter(([key, claim]) =>
        vehicleKeys.has(key)
        && state.deliveryVehicleDrafts?.[key] === claim?.vehicle_id,
      ),
    );
    state.deliveryVehicleErrors = Object.fromEntries(
      Object.entries(state.deliveryVehicleErrors || {}).filter(([key]) =>
        vehicleKeys.has(key),
      ),
    );
    state.deliveryVehiclePendingKeys = Object.fromEntries(
      Object.entries(state.deliveryVehiclePendingKeys || {}).filter(([key]) =>
        vehicleKeys.has(key) && context.deliveryVehicleQueues.has(key),
      ),
    );
  }

  function clearDeliveryVehicleTransientState() {
    context.deliveryVehicleMutationVersion += 1;
    context.deliveryVehicleQueues.clear();
    state.deliveryVehicleDrafts = {};
    state.deliveryVehicleClaims = {};
    state.deliveryVehicleErrors = {};
    state.deliveryVehiclePendingKeys = {};
  }

  function deliveryVehicleKey(deliveryDate, driverId) {
    return `${deliveryDate || ""}|${driverId || ""}`;
  }

  return {
    updateDeliveryVehicleSelection,
    queueDeliveryVehicleUpdate,
    enqueueDeliveryVehiclePhysicalWrite,
    processDeliveryVehicleQueue,
    retryAvailableDeliveryVehicleClaims,
    isDeliveryVehicleQueueCurrent,
    updateDeliveryVehicleClaim,
    removeDeliveryVehicleDraft,
    removeDeliveryVehicleClaim,
    clearDeliveryVehicleError,
    applyDeliveryVehicleBoardUpdate,
    pruneDeliveryVehicleDrafts,
    clearDeliveryVehicleTransientState,
    deliveryVehicleKey,
  };
}
