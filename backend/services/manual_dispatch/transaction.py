from contextlib import nullcontext
from functools import wraps


def immediate_transactional(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        transaction = getattr(self.repository, "_immediate_transaction", None)
        manager = transaction() if transaction else nullcontext()
        with manager:
            return method(self, *args, **kwargs)

    return wrapped
