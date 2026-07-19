from contextlib import contextmanager
from contextvars import ContextVar


LOGBOOK_ACTOR_CONTEXT = ContextVar("manual_dispatch_logbook_actor", default=None)


class AuditContext:
    """Own the current Manual Dispatch Logbook actor."""

    @contextmanager
    def actor(self, actor):
        token = LOGBOOK_ACTOR_CONTEXT.set(actor or None)
        try:
            yield
        finally:
            LOGBOOK_ACTOR_CONTEXT.reset(token)

    @staticmethod
    def current_actor():
        return LOGBOOK_ACTOR_CONTEXT.get() or "Unknown"
