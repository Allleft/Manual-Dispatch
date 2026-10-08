class StateChangedConflictError(ValueError):
    """The requested mutation lost a commit-time state race."""


class DeliveryRunSheetLockedError(StateChangedConflictError):
    """The selected Delivery scope has an immutable Run Sheet."""
