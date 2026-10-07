import {
  DELIVERY_VEHICLE_TRIPS, deliveryVehicleKey, parseDeliveryVehicleKey,
  getDeliveryTripVehicleAssignment,
  getDeliveryVehicleConflictDriverNames,
} from "../../utils/delivery-vehicle-utils.js";

export function createDeliveryVehicleQueue(context) {
  const { api, renderWorkspace, state } = context;
  const handleWorkspaceMigrationGuard = (...args) => context.actions.handleWorkspaceMigrationGuard(...args);
  const currentDeliveryBoard = (...args) => context.actions.currentDeliveryBoard(...args);

  async function updateDeliveryVehicleSelection(deliveryDate, driverId, tripNo, vehicleId) {
    deliveryVehicleKey(deliveryDate, driverId, tripNo);
    return updateSelection(deliveryDate, driverId, tripNo, vehicleId);
  }

  function selectionKeys(deliveryDate, driverId, tripNo) {
    return [deliveryVehicleKey(deliveryDate, driverId, tripNo)];
  }

  function selectionAssignment(board, deliveryDate, driverId, tripNo) {
    return getDeliveryTripVehicleAssignment(board, deliveryDate, driverId, tripNo);
  }

  function selectionConflicts(board, deliveryDate, driverId, tripNo, vehicleId) {
    const input = { board, claims: state.deliveryVehicleClaims, deliveryDate, driverId, tripNo, vehicleId };
    return getDeliveryVehicleConflictDriverNames(input);
  }

  async function updateSelection(deliveryDate, driverId, tripNo, vehicleId) {
    const keys = selectionKeys(deliveryDate, driverId, tripNo);
    keys.forEach((key) => {
      state.deliveryVehicleDrafts = { ...(state.deliveryVehicleDrafts || {}), [key]: vehicleId };
      updateDeliveryVehicleClaim(key, vehicleId);
      clearDeliveryVehicleError(key);
    });
    renderWorkspace();
    const board = currentDeliveryBoard();
    const currentAssignment = selectionAssignment(board, deliveryDate, driverId, tripNo);
    const conflictDriverNames = selectionConflicts(board, deliveryDate, driverId, tripNo, vehicleId);
    if (conflictDriverNames.length) {
      return;
    }
    if (!vehicleId && !currentAssignment && !keys.some((key) =>
      context.deliveryVehicleQueues.has(key) || context.deliveryVehiclePhysicalTails.has(key))) {
      keys.forEach(removeDeliveryVehicleDraft);
      renderWorkspace();
      retryAvailableDeliveryVehicleClaims();
      return;
    }
    return queueSelection(deliveryDate, driverId, tripNo);
  }

  function queueDeliveryVehicleUpdate(deliveryDate, driverId, tripNo) {
    return queueSelection(deliveryDate, driverId, tripNo);
  }

  function queueSelection(deliveryDate, driverId, tripNo) {
    const keys = selectionKeys(deliveryDate, driverId, tripNo);
    const existingEntry = context.deliveryVehicleQueues.get(keys[0]);
    if (existingEntry?.mutationVersion === context.deliveryVehicleMutationVersion) {
      return existingEntry.promise;
    }
    const entry = {
      queueId: ++context.deliveryVehicleQueueIdCounter,
      mutationVersion: context.deliveryVehicleMutationVersion,
      authSessionVersion: state.authSessionVersion,
      deliveryDate, driverId, tripNo, keys, promise: null,
    };
    keys.forEach((key) => {
      state.deliveryVehiclePendingKeys = { ...(state.deliveryVehiclePendingKeys || {}), [key]: true };
      context.deliveryVehicleQueues.set(key, entry);
    });
    renderWorkspace();
    entry.promise = enqueueDeliveryVehiclePhysicalWrite(keys, () => processDeliveryVehicleQueue(entry))
      .catch((error) => {
        if (isDeliveryVehicleQueueCurrent(keys[0], entry)) {
          keys.forEach((key) => {
            state.deliveryVehicleErrors = { ...(state.deliveryVehicleErrors || {}), [key]: error.message || "Unable to update Vehicle." };
          });
        }
      })
      .finally(() => {
        keys.forEach((key) => {
          if (context.deliveryVehicleQueues.get(key) !== entry) {
            return;
          }
          context.deliveryVehicleQueues.delete(key);
          const { [key]: _removed, ...remaining } = state.deliveryVehiclePendingKeys || {};
          state.deliveryVehiclePendingKeys = remaining;
        });
        if (entry.mutationVersion === context.deliveryVehicleMutationVersion
            && state.isLoggedIn && state.activeWorkspace === "delivery"
            && state.workspaceRoute === "delivery/trip-summary") {
          renderWorkspace();
        }
      });
    return entry.promise;
  }

  function enqueueDeliveryVehiclePhysicalWrite(keys, operation) {
    const scopedKeys = Array.isArray(keys) ? keys : [keys];
    const tails = scopedKeys.map((key) => context.deliveryVehiclePhysicalTails.get(key)).filter(Boolean);
    const operationPromise = tails.length
      ? Promise.all(tails.map((tail) => tail.catch(() => {}))).then(operation)
      : Promise.resolve(operation());
    const settledTail = operationPromise.catch(() => {});
    scopedKeys.forEach((key) => context.deliveryVehiclePhysicalTails.set(key, settledTail));
    settledTail.finally(() => {
      scopedKeys.forEach((key) => {
        if (context.deliveryVehiclePhysicalTails.get(key) === settledTail) {
          context.deliveryVehiclePhysicalTails.delete(key);
        }
      });
    });
    return operationPromise;
  }

  async function processDeliveryVehicleQueue(entry) {
    const { deliveryDate, driverId, tripNo, keys } = entry;
    const key = keys[0];
    while (isDeliveryVehicleQueueCurrent(key, entry)
        && keys.every((scopeKey) => Object.hasOwn(state.deliveryVehicleDrafts || {}, scopeKey))) {
      const vehicleId = state.deliveryVehicleDrafts[key];
      if (vehicleId === undefined) {
        return;
      }
      if (selectionConflicts(currentDeliveryBoard(), deliveryDate, driverId, tripNo, vehicleId).length) {
        return;
      }
      const currentAssignment = selectionAssignment(currentDeliveryBoard(), deliveryDate, driverId, tripNo);
      if (currentAssignment?.vehicle_id === vehicleId) {
        keys.forEach((scopeKey) => {
          removeDeliveryVehicleDraft(scopeKey);
          removeDeliveryVehicleClaim(scopeKey);
          clearDeliveryVehicleError(scopeKey);
        });
        return;
      }
      const payload = { delivery_date: deliveryDate, driver_id: driverId, trip_no: tripNo };
      let updatedBoard;
      try {
        updatedBoard = vehicleId
          ? await api.assignDeliveryWorkspaceVehicle({ ...payload, vehicle_id: vehicleId })
          : await api.clearDeliveryWorkspaceVehicle(payload);
      } catch (error) {
        if (!isDeliveryVehicleQueueCurrent(key, entry)) {
          return;
        }
        if (await handleWorkspaceMigrationGuard(error)) {
          return;
        }
        if (keys.every((scopeKey) => state.deliveryVehicleDrafts?.[scopeKey] === vehicleId)) {
          keys.forEach((scopeKey) => {
            state.deliveryVehicleErrors = { ...(state.deliveryVehicleErrors || {}), [scopeKey]: error.message };
          });
          return;
        }
        continue;
      }
      if (!isDeliveryVehicleQueueCurrent(key, entry)) {
        return;
      }
      applyDeliveryVehicleBoardUpdate(updatedBoard, deliveryDate, driverId, tripNo);
      if (keys.every((scopeKey) => state.deliveryVehicleDrafts?.[scopeKey] === vehicleId)) {
        keys.forEach((scopeKey) => {
          removeDeliveryVehicleDraft(scopeKey);
          removeDeliveryVehicleClaim(scopeKey);
          clearDeliveryVehicleError(scopeKey);
        });
        retryAvailableDeliveryVehicleClaims(key);
        return;
      }
    }
  }

  function retryAvailableDeliveryVehicleClaims(excludedKey) {
    Object.entries(state.deliveryVehicleClaims || {})
      .sort((left, right) => Number(left[1].sequence) - Number(right[1].sequence))
      .forEach(([key, claim]) => {
        const scope = parseDeliveryVehicleKey(key);
        if (!scope || !claim?.vehicle_id || key === excludedKey || context.deliveryVehicleQueues.has(key)) {
          return;
        }
        const { deliveryDate, driverId, tripNo } = scope;
        if (!selectionConflicts(currentDeliveryBoard(), deliveryDate, driverId, tripNo, claim.vehicle_id).length) {
          queueSelection(deliveryDate, driverId, tripNo);
        }
      });
  }

  function isDeliveryVehicleQueueCurrent(key, entry) {
    return context.deliveryVehicleQueues.get(key) === entry
      && entry.keys.every((scopeKey) => context.deliveryVehicleQueues.get(scopeKey) === entry)
      && entry.mutationVersion === context.deliveryVehicleMutationVersion
      && entry.authSessionVersion === state.authSessionVersion
      && state.isLoggedIn && state.workspaceRoute === "delivery/trip-summary"
      && state.activeWorkspace === "delivery"
      && (state.deliveryTripSummaryDate || entry.deliveryDate) === entry.deliveryDate;
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
      [key]: { vehicle_id: vehicleId, sequence: state.deliveryVehicleClaimSequence },
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

  function applyDeliveryVehicleBoardUpdate(updatedBoard, deliveryDate, driverId, tripNo) {
    if (!updatedBoard) {
      return;
    }
    const targetBoard = currentDeliveryBoard();
    const matches = (row) => row.delivery_date === deliveryDate && row.driver_id === driverId
      && row.trip_no === tripNo;
    const nextBoard = {
      ...(targetBoard || {}),
      driver_vehicle_assignments: (targetBoard?.driver_vehicle_assignments || []).filter((row) => !matches(row))
        .concat((updatedBoard.driver_vehicle_assignments || []).filter(matches)),
    };
    if (state.workspaceRoute === "delivery/trip-summary" && state.deliveryTripSummaryBoard) {
      state.deliveryTripSummaryBoard = nextBoard;
    } else {
      state.deliveryBoard = nextBoard;
    }
  }

  function pruneDeliveryVehicleDrafts(board = currentDeliveryBoard()) {
    const validKeys = new Set();
    const addScope = (date, driver, trip) => {
      if (date && driver && DELIVERY_VEHICLE_TRIPS.includes(trip)) {
        validKeys.add(deliveryVehicleKey(date, driver, trip));
      }
    };
    (board?.driver_vehicle_assignments || []).forEach((row) => addScope(row.delivery_date, row.driver_id, row.trip_no));
    (board?.assignments || []).forEach((assignment) => {
      const order = (board?.orders || []).find((item) => item.order_id === assignment.task_id);
      addScope(order?.delivery_date, assignment.driver_id, assignment.trip_no);
    });
    (board?.drivers || []).forEach((driver) =>
      DELIVERY_VEHICLE_TRIPS.forEach((trip) => addScope(state.deliveryTripSummaryDate || state.dispatchDate, driver.driver_id, trip)));
    state.deliveryVehicleDrafts = Object.fromEntries(Object.entries(state.deliveryVehicleDrafts || {}).filter(([key, vehicleId]) => {
      const scope = parseDeliveryVehicleKey(key);
      if (!scope || !validKeys.has(key)) {
        return false;
      }
      const { deliveryDate, driverId, tripNo } = scope;
      const assignment = selectionAssignment(board, deliveryDate, driverId, tripNo);
      return assignment?.vehicle_id !== vehicleId;
    }));
    state.deliveryVehicleClaims = Object.fromEntries(Object.entries(state.deliveryVehicleClaims || {}).filter(([key, claim]) =>
      validKeys.has(key) && state.deliveryVehicleDrafts?.[key] === claim?.vehicle_id));
    state.deliveryVehicleErrors = Object.fromEntries(Object.entries(state.deliveryVehicleErrors || {}).filter(([key]) => validKeys.has(key)));
    state.deliveryVehiclePendingKeys = Object.fromEntries(Object.entries(state.deliveryVehiclePendingKeys || {}).filter(([key]) =>
      validKeys.has(key) && context.deliveryVehicleQueues.has(key)));
  }

  function clearDeliveryVehicleTransientState() {
    context.deliveryVehicleMutationVersion += 1;
    context.deliveryVehicleQueues.clear();
    state.deliveryVehicleDrafts = {};
    state.deliveryVehicleClaims = {};
    state.deliveryVehicleErrors = {};
    state.deliveryVehiclePendingKeys = {};
  }

  async function ensureDeliveryVehicleSelectionSettled(deliveryDate, driverId, tripNo) {
    const key = deliveryVehicleKey(deliveryDate, driverId, tripNo);
    const mutationVersion = context.deliveryVehicleMutationVersion;
    const authSessionVersion = state.authSessionVersion;
    const isCurrent = () => mutationVersion === context.deliveryVehicleMutationVersion
      && authSessionVersion === state.authSessionVersion && state.isLoggedIn
      && state.activeWorkspace === "delivery" && state.workspaceRoute === "delivery/trip-summary"
      && (state.deliveryTripSummaryDate || state.dispatchDate) === deliveryDate;
    while (isCurrent()) {
      const pending = context.deliveryVehicleQueues.get(key)?.promise
        || context.deliveryVehiclePhysicalTails.get(key);
      if (!pending) {
        break;
      }
      await pending;
    }
    if (!isCurrent()) {
      throw new Error("Delivery context changed. Review the trip again.");
    }
    const error = state.deliveryVehicleErrors?.[key];
    if (error) {
      throw new Error(error);
    }
    if (state.deliveryVehiclePendingKeys?.[key]) {
      throw new Error("Vehicle update is still pending.");
    }
    const persisted = selectionAssignment(currentDeliveryBoard(), deliveryDate, driverId, tripNo)?.vehicle_id || "";
    const selected = state.deliveryVehicleDrafts?.[key] ?? persisted;
    if (selectionConflicts(currentDeliveryBoard(), deliveryDate, driverId, tripNo, selected).length) {
      throw new Error("Selected vehicle conflicts with another driver in this trip.");
    }
    if (selected !== persisted) {
      throw new Error("Vehicle selection has not been saved. Retry the vehicle update.");
    }
    return persisted;
  }

  return {
    updateDeliveryVehicleSelection, queueDeliveryVehicleUpdate, ensureDeliveryVehicleSelectionSettled,
    enqueueDeliveryVehiclePhysicalWrite, processDeliveryVehicleQueue, retryAvailableDeliveryVehicleClaims,
    isDeliveryVehicleQueueCurrent, updateDeliveryVehicleClaim, removeDeliveryVehicleDraft,
    removeDeliveryVehicleClaim, clearDeliveryVehicleError, applyDeliveryVehicleBoardUpdate,
    pruneDeliveryVehicleDrafts, clearDeliveryVehicleTransientState, deliveryVehicleKey,
  };
}
