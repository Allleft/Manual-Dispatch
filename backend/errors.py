class StateChangedConflictError(ValueError):
    """The requested mutation lost a commit-time state race."""
