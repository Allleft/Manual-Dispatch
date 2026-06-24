class WorkspaceMigrationRequiredError(ValueError):
    """Raised when legacy snapshots must be reconciled before scoped workspace use."""


class WorkspaceMigrationReadinessService:
    def __init__(self, repository):
        self.repository = repository

    def get_status(self):
        return self.repository.get_workspace_migration_status()

    def ensure_ready(self, workspace):
        status = self.get_status()
        ready_field, label = _workspace_config(workspace)
        if status[ready_field]:
            return status
        if status["legacy_generated_summary_count"]:
            raise WorkspaceMigrationRequiredError(
                "Legacy generated Final Trip Summaries must be resolved before using "
                f"{label}. Resolve generated legacy records before running the migration."
            )
        raise WorkspaceMigrationRequiredError(
            f"Workspace migration is required before using {label}. "
            "Run the legacy snapshot migration during a maintenance window."
        )


def _workspace_config(workspace):
    if workspace == "delivery":
        return "delivery_ready", "Order Delivery"
    if workspace == "opshop":
        return "opshop_ready", "OP SHOP Pickup"
    raise ValueError(f"Unknown workspace: {workspace}")
