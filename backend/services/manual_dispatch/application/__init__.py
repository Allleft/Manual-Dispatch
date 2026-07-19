class FacadeApplicationService:
    """Compatibility bridge for behavior-preserving orchestration extraction."""

    def __init__(self, facade):
        self._facade = facade

    def __getattr__(self, name):
        return getattr(self._facade, name)
