from . import FacadeApplicationService


class AttacheImportApplicationService(FacadeApplicationService):
    """Own attache import application orchestration."""

    def record_attache_import_confirmation(self, rows, outcome):
        return self._facade.delivery_event_recorder.record_attache_import_confirmation(rows, outcome)
