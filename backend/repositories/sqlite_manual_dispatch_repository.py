from backend.repositories.sqlite.assignment_repository_mixin import SQLiteAssignmentRepositoryMixin
from backend.repositories.sqlite.auth_repository_mixin import SQLiteAuthRepositoryMixin
from backend.repositories.sqlite.base import SQLiteRepositoryBase
from backend.repositories.sqlite.legacy_repository_mixin import SQLiteLegacyRepositoryMixin
from backend.repositories.sqlite.opshop_repository_mixin import SQLiteOpShopRepositoryMixin
from backend.repositories.sqlite.order_repository_mixin import SQLiteOrderRepositoryMixin
from backend.repositories.sqlite.row_mappers import SQLiteRowMapperMixin
from backend.repositories.sqlite.snapshot_repository_mixin import SQLiteSnapshotRepositoryMixin
from backend.repositories.sqlite.specification_repository_mixin import SQLiteSpecificationRepositoryMixin
from backend.repositories.sqlite.opshop_repository_mixin import _normalize_text_key
from backend.repositories.sqlite.row_mappers import _row_value


class SQLiteManualDispatchRepository(
    SQLiteOrderRepositoryMixin,
    SQLiteAssignmentRepositoryMixin,
    SQLiteSpecificationRepositoryMixin,
    SQLiteOpShopRepositoryMixin,
    SQLiteSnapshotRepositoryMixin,
    SQLiteLegacyRepositoryMixin,
    SQLiteAuthRepositoryMixin,
    SQLiteRowMapperMixin,
    SQLiteRepositoryBase,
):
    """SQLite-backed repository for Phase 6 manual dispatch persistence."""
