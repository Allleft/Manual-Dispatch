import {
  DELIVERY_VEHICLE_TRIPS, deliveryVehicleKey, parseDeliveryVehicleKey,
  getDeliveryDayVehicleAssignment, getDeliveryDayVehicleDraft,
  getDeliveryDayVehicleConflictDriverNames, getDeliveryTripVehicleAssignment,
  getDeliveryVehicleConflictDriverNames,
} from "../../utils/delivery-vehicle-utils.js";

export function createDeliveryVehicleQueue(context) {
  const { api, renderWorkspace, state } = context;
  const handleWorkspaceMigrationGuard = (...args) => context.actions.handleWorkspaceMigrationGuard(...args);
  const currentDeliveryBoard = (...args) => context.actions.currentDeliveryBoard(...args);

  async function updateDeliveryVehicleSelection(deliveryDate, driverId, tripNo, vehicleId) {
    deliveryVehicleKey(deliveryDate, driverId, tripNo);
    return updateSelection(deliveryDate, driverId, tripNo, vehicleId, false);
  }

  // Only the existing single control uses this temporary, explicit day contract.
  async function updateDeliveryDayVehicleSelection(deliveryDate, driverId, vehicleId) {
    return updateSelection(deliveryDate, driverId, null, vehicleId, true);
  }

  function selectionKeys(deliveryDate, driverId, tripNo, dayCompatibility) {
    return (dayCompatibility ? DELIVERY_VEHICLE_TRIPS : [tripNo])
      .map((trip) => deliveryVehicleKey(deliveryDate, driverId, trip));
  }

  function selectionAssignment(board, deliveryDate, driverId, tripNo, dayCompatibility) {
    return dayCompatibility
      ? getDeliveryDayVehicleAssignment(board, deliveryDate, driverId)
      : getDeliveryTripVehicleAssignment(board, deliveryDate, driverId, tripNo);
  }

  function selectionConflicts(board, deliveryDate, driverId, tripNo, vehicleId, dayCompatibility) {
    const input = { board, claims: state.deliveryVehicleClaims, deliveryDate, driverId, tripNo, vehicleId };
    return dayCompatibility
      ? getDeliveryDayVehicleConflictDriverNames(input)
      : getDeliveryVehicleConflictDriverNames(input);
  }

  async function updateSelection(deliveryDate, driverId, tripNo, vehicleId, dayCompatibility) {
    const keys = selectionKeys(deliveryDate, driverId, tripNo, dayCompatibility);
    keys.forEach((key) => {
      state.deliveryVehicleDrafts = { ...(state.deliveryVehicleDrafts || {}), [key]: vehicleId };
      updateDeliveryVehicleClaim(key, vehicleId, dayCompatibility);
      clearDeliveryVehicleError(key);
    });
    renderWorkspace();
    const board = currentDeliveryBoard();
    const currentAssignment = selectionAssignment(board, deliveryDate, driverId, tripNo, dayCompatibility);
    const conflictDriverNames = selectionConflicts(board, deliveryDate, driverId, tripNo, vehicleId, dayCompatibility);
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
    return queueSelection(deliveryDate, driverId, tripNo, dayCompatibility);
  }

  function queueDeliveryVehicleUpdate(deliveryDate, driverId, tripNo) {
    return queueSelection(deliveryDate, driverId, tripNo, false);
  }

  function queueSelection(deliveryDate, driverId, tripNo, dayCompatibility) {
    const keys = selectionKeys(deliveryDate, driverId, tripNo, dayCompatibility);
    const existingEntry = context.deliveryVehicleQueues.get(keys[0]);
    if (existingEntry?.mutationVersion === context.deliveryVehicleMutationVersion
        && existingEntry.dayCompatibility === dayCompatibility) {
      return existingEntry.promise;
    }
    const entry = {
      queueId: ++context.deliveryVehicleQueueIdCounter,
      mutationVersion: context.deliveryVehicleMutationVersion,
      authSessionVersion: state.authSessionVersion,
      deliveryDate, driverId, tripNo, dayCompatibility, keys, promise: null,
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
    const { deliveryDate, driverId, tripNo, dayCompatibility, keys } = entry;
    const key = keys[0];
    while (isDeliveryVehicleQueueCurrent(key, entry)
        && keys.every((scopeKey) => Object.hasOwn(state.deliveryVehicleDrafts || {}, scopeKey))) {
      const vehicleId = dayCompatibility
        ? getDeliveryDayVehicleDraft(state.deliveryVehicleDrafts, deliveryDate, driverId)
        : state.deliveryVehicleDrafts[key];
      if (vehicleId === undefined) {
        return;
      }
      if (selectionConflicts(currentDeliveryBoard(), deliveryDate, driverId, tripNo, vehicleId, dayCompatibility).length) {
        return;
      }
      const currentAssignment = selectionAssignment(currentDeliveryBoard(), deliveryDate, driverId, tripNo, dayCompatibility);
      if (currentAssignment?.vehicle_id === vehicleId) {
        keys.forEach((scopeKey) => {
          removeDeliveryVehicleDraft(scopeKey);
          removeDeliveryVehicleClaim(scopeKey);
          clearDeliveryVehicleError(scopeKey);
        });
        return;
      }
      const payload = { delivery_date: deliveryDate, driver_id: driverId };
      if (!dayCompatibility) {
        payload.trip_no = tripNo;
      }
      let updatedBoard;
      try {
        if (dayCompatibility) {
          updatedBoard = vehicleId
            ? await api.assignDeliveryDayVehicle({ ...payload, vehicle_id: vehicleId })
            : await api.clearDeliveryDayVehicle(payload);
        } else {
          updatedBoard = vehicleId
            ? await api.assignDeliveryWorkspaceVehicle({ ...payload, vehicle_id: vehicleId })
            : await api.clearDeliveryWorkspaceVehicle(payload);
        }
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
      applyDeliveryVehicleBoardUpdate(updatedBoard, deliveryDate, driverId, tripNo, dayCompatibility);
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
        if (!selectionConflicts(currentDeliveryBoard(), deliveryDate, driverId, tripNo, claim.vehicle_id, claim.day_compatibility).length) {
          queueSelection(deliveryDate, driverId, tripNo, Boolean(claim.day_compatibility));
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

  function updateDeliveryVehicleClaim(key, vehicleId, dayCompatibility = false) {
    if (!vehicleId) {
      removeDeliveryVehicleClaim(key);
      return;
    }
    const existing = state.deliveryVehicleClaims?.[key];
    if (existing?.vehicle_id === vehicleId && Boolean(existing.day_compatibility) === dayCompatibility) {
      return;
    }
    state.deliveryVehicleClaimSequence = Number(state.deliveryVehicleClaimSequence || 0) + 1;
    state.deliveryVehicleClaims = {
      ...(state.deliveryVehicleClaims || {}),
      [key]: { vehicle_id: vehicleId, sequence: state.deliveryVehicleClaimSequence, day_compatibility: dayCompatibility },
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

  function applyDeliveryVehicleBoardUpdate(updatedBoard, deliveryDate, driverId, tripNo, dayCompatibility = false) {
    if (!updatedBoard) {
      return;
    }
    const targetBoard = currentDeliveryBoard();
    const matches = (row) => row.delivery_date === deliveryDate && row.driver_id === driverId
      && (dayCompatibility ? DELIVERY_VEHICLE_TRIPS.includes(row.trip_no) : row.trip_no === tripNo);
    const nextBoard = {
      ...(targetBoard || {}),
      driver_vehicle_assignments: (targetBoard?.driver_vehicle_assignments || []).filter((row) => !matches(row))
        .concat((updatedBoard.driver_vehicle_assignments || []).filter(matches)),
    };
    if (dayCompatibility) {
      const dayMatches = (row) => row.delivery_date === deliveryDate && row.driver_id === driverId;
      nextBoard.legacy_driver_vehicle_assignments = (targetBoard?.legacy_driver_vehicle_assignments || [])
        .filter((row) => !dayMatches(row))
        .concat((updatedBoard.legacy_driver_vehicle_assignments || []).filter(dayMatches));
    }
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
      const assignment = selectionAssignment(board, deliveryDate, driverId, tripNo, state.deliveryVehicleClaims?.[key]?.day_compatibility);
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

  return {
    updateDeliveryVehicleSelection, updateDeliveryDayVehicleSelection, queueDeliveryVehicleUpdate,
    enqueueDeliveryVehiclePhysicalWrite, processDeliveryVehicleQueue, retryAvailableDeliveryVehicleClaims,
    isDeliveryVehicleQueueCurrent, updateDeliveryVehicleClaim, removeDeliveryVehicleDraft,
    removeDeliveryVehicleClaim, clearDeliveryVehicleError, applyDeliveryVehicleBoardUpdate,
    pruneDeliveryVehicleDrafts, clearDeliveryVehicleTransientState, deliveryVehicleKey,
  };
}
