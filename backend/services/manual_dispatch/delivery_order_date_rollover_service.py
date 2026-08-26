from backend.services.manual_dispatch.delivery_import_date import (
    current_melbourne_business_date,
    next_weekday_after,
)
from backend.services.manual_dispatch.normalization import (
    clean_required_iso_date,
    clean_required_text,
)
from backend.services.manual_dispatch.transaction import immediate_transactional


class DeliveryOrderDateRolloverService:
    def __init__(self, repository, today_provider=None):
        self.repository = repository
        self.today_provider = today_provider or current_melbourne_business_date

    @immediate_transactional
    def roll_forward_eligible_unassigned_delivery_orders(self, event_collector=None):
        return self._roll_forward(None, event_collector)

    @immediate_transactional
    def roll_forward_eligible_unassigned_delivery_order(
        self,
        order_id,
        event_collector=None,
    ):
        return self._roll_forward(
            clean_required_text(order_id, "order_id"),
            event_collector,
        )

    def _roll_forward(self, order_id, event_collector):
        current_date = clean_required_iso_date(
            self.today_provider(),
            "current_melbourne_date",
        )
        target_date = next_weekday_after(current_date).isoformat()
        changes = self.repository.roll_forward_unassigned_delivery_order_dates(
            current_date=current_date,
            target_date=target_date,
            order_id=order_id,
        )
        if event_collector is not None:
            event_collector.extend(changes)
        return changes
