class FacadeAuditRecorder:
    """Compatibility bridge for behavior-preserving audit extraction."""

    def __init__(self, facade):
        self._facade = facade

    def __getattr__(self, name):
        return getattr(self._facade, name)
