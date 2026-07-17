from backend.repositories.in_memory.assignment_repository_mixin import InMemoryAssignmentRepositoryMixin
from backend.repositories.in_memory.auth_repository_mixin import InMemoryAuthRepositoryMixin
from backend.repositories.in_memory.base import InMemoryRepositoryBase
from backend.repositories.in_memory.legacy_repository_mixin import InMemoryLegacyRepositoryMixin
from backend.repositories.in_memory.opshop_repository_mixin import InMemoryOpShopRepositoryMixin
from backend.repositories.in_memory.order_repository_mixin import InMemoryOrderRepositoryMixin
from backend.repositories.in_memory.snapshot_repository_mixin import InMemorySnapshotRepositoryMixin
from backend.repositories.in_memory.specification_repository_mixin import InMemorySpecificationRepositoryMixin
from backend.repositories.in_memory.opshop_repository_mixin import _normalize_text_key


class InMemoryManualDispatchRepository(
    InMemoryOrderRepositoryMixin,
    InMemoryAssignmentRepositoryMixin,
    InMemorySpecificationRepositoryMixin,
    InMemoryOpShopRepositoryMixin,
    InMemorySnapshotRepositoryMixin,
    InMemoryLegacyRepositoryMixin,
    InMemoryAuthRepositoryMixin,
    InMemoryRepositoryBase,
):
    """Temporary in-memory data store for Phase 5.

    This is not persistence. Data resets whenever the backend process restarts.
    """
