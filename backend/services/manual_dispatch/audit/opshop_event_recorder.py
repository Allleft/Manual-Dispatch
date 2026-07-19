from . import FacadeAuditRecorder


class OpShopEventRecorder(FacadeAuditRecorder):
    """Record opshop event recorder events without changing semantics."""

    def _record_opshop_assignment_change(
        self,
        dispatch_date,
        pickup_task_id,
        before,
        after,
    ):
        if before == after:
            return
        pickup_name = self._opshop_pickup_name(pickup_task_id)
        pickup_date = self._opshop_pickup_date(pickup_task_id)
        dispatch_date = (
            (after or before or {}).get("dispatch_date")
            or dispatch_date
            or pickup_date
        )
        metadata = {
            "before": self._assignment_log_metadata(before),
            "after": self._assignment_log_metadata(after),
        }
        if before and not after:
            self._record_logbook(
                result="SUCCESS",
                workspace="OPSHOP",
                action="OPSHOP_TASK_UNASSIGNED",
                entity_type="OPSHOP_PICKUP",
                entity_id=pickup_task_id,
                summary=(
                    f"OP SHOP pickup {pickup_name} was unassigned from "
                    f"{self._assignment_label(before)}."
                ),
                dispatch_date=dispatch_date,
                pickup_date=pickup_date,
                driver=before.get("driver"),
                metadata=metadata,
            )
            return
        if not after:
            return
        if before:
            self._record_logbook(
                result="SUCCESS",
                workspace="OPSHOP",
                action="OPSHOP_TASK_REASSIGNED",
                entity_type="OPSHOP_PICKUP",
                entity_id=pickup_task_id,
                summary=(
                    f"OP SHOP pickup {pickup_name} was reassigned from "
                    f"{self._assignment_label(before)} to "
                    f"{self._assignment_label(after)}."
                ),
                dispatch_date=dispatch_date,
                pickup_date=pickup_date,
                driver=after.get("driver"),
                metadata=metadata,
            )
            return
        self._record_logbook(
            result="SUCCESS",
            workspace="OPSHOP",
            action="OPSHOP_TASK_ASSIGNED",
            entity_type="OPSHOP_PICKUP",
            entity_id=pickup_task_id,
            summary=(
                f"OP SHOP pickup {pickup_name} was assigned to "
                f"{self._assignment_label(after)}."
            ),
            dispatch_date=dispatch_date,
            pickup_date=pickup_date,
            driver=after.get("driver"),
            metadata=metadata,
        )

    @staticmethod
    def _opshop_collection_counts(collection):
        counts = {"REGULAR": 0, "ON_CALL": 0, "COUNTRYSIDE": 0}
        for pickup in collection.pickups:
            category = str(pickup.pickup_category_snapshot or "").upper()
            run_type = str(pickup.run_type_snapshot or "").upper()
            if category == "COUNTRYSIDE":
                counts["COUNTRYSIDE"] += 1
            elif run_type == "REGULAR":
                counts["REGULAR"] += 1
            else:
                counts["ON_CALL"] += 1
        return counts

    def record_opshop_pickup_collection_export(self, collection, filename):
        counts = self._opshop_collection_counts(collection)
        self._record_logbook(
            result="SUCCESS",
            workspace="OPSHOP",
            action="PICKUP_COLLECTION_EXPORTED",
            entity_type="PICKUP_COLLECTION",
            entity_id=collection.collection_id,
            summary=(
                "OP SHOP Pickup Collection Excel export was generated for "
                f"{collection.driver_name_snapshot} on {collection.pickup_date}."
            ),
            dispatch_date=collection.dispatch_date,
            pickup_date=collection.pickup_date,
            driver=collection.driver_name_snapshot,
            collection_id=collection.collection_id,
            metadata={
                "export_scope": "single",
                "status": collection.status,
                "pickup_count": len(collection.pickups),
                "regular_count": counts["REGULAR"],
                "oncall_count": counts["ON_CALL"],
                "countryside_count": counts["COUNTRYSIDE"],
                "filename": filename,
            },
        )

    def record_opshop_pickup_collections_daily_export(
        self,
        collections,
        pickup_date,
        filename,
        dispatch_date=None,
        status=None,
    ):
        statuses = [str(collection.status or "").upper() for collection in collections]
        metadata = {
            "export_scope": "daily",
            "collection_count": len(collections),
            "saved_count": statuses.count("SAVED"),
            "generated_count": statuses.count("GENERATED"),
            "filename": filename,
        }
        if status is not None:
            metadata["status_filter"] = status
        if dispatch_date is not None:
            metadata["dispatch_date_filter"] = dispatch_date
        collection_label = (
            "Collection" if len(collections) == 1 else "Collections"
        )
        self._record_logbook(
            result="SUCCESS",
            workspace="OPSHOP",
            action="PICKUP_COLLECTIONS_DAILY_EXPORTED",
            entity_type="PICKUP_COLLECTION_BATCH",
            entity_id=pickup_date,
            summary=(
                "Daily OP SHOP Pickup Collections Excel export was generated for "
                f"{pickup_date} with {len(collections)} {collection_label}."
            ),
            pickup_date=pickup_date,
            dispatch_date=dispatch_date,
            metadata=metadata,
        )

    def _record_opshop_collection_event(self, action, collection, actor=None):
        counts = self._opshop_collection_counts(collection)
        pickup_count = len(collection.pickups)
        verb = {
            "PICKUP_COLLECTION_GENERATED": "generated",
            "PICKUP_COLLECTION_CANCELLED": "cancelled",
            "PICKUP_COLLECTION_SAVED": "saved",
        }.get(action, "updated")
        self._record_logbook(
            result="SUCCESS",
            workspace="OPSHOP",
            actor=actor,
            action=action,
            entity_type="OPSHOP_PICKUP_COLLECTION",
            entity_id=collection.collection_id,
            summary=(
                f"Pickup Collection was {verb} for "
                f"{collection.driver_name_snapshot} on {collection.pickup_date} "
                f"with {pickup_count} pickup tasks."
            ),
            dispatch_date=collection.dispatch_date,
            pickup_date=collection.pickup_date,
            driver=collection.driver_name_snapshot,
            collection_id=collection.collection_id,
            metadata={
                "pickup_count": pickup_count,
                "regular_count": counts["REGULAR"],
                "oncall_count": counts["ON_CALL"],
                "countryside_count": counts["COUNTRYSIDE"],
                "status": collection.status,
            },
        )

    def _record_opshop_task_event(self, action, task):
        if not task:
            return
        name = self._opshop_pickup_name(task.pickup_task_id)
        verb = {
            "OPSHOP_TASK_CREATED": "created",
            "OPSHOP_TASK_UPDATED": "updated",
            "OPSHOP_TASK_CANCELLED": "cancelled",
        }.get(action, "updated")
        self._record_logbook(
            result="SUCCESS",
            workspace="OPSHOP",
            action=action,
            entity_type="OPSHOP_PICKUP",
            entity_id=task.pickup_task_id,
            summary=f"OP SHOP pickup {name} was {verb}.",
            dispatch_date=task.dispatch_date,
            pickup_date=task.pickup_date,
            driver=self._driver_name(task.driver_id),
            metadata={
                "pickup_task_id": task.pickup_task_id,
                "schedule_id": task.schedule_id,
                "status": task.status,
                "generated_from": task.generated_from,
            },
        )

    def _opshop_pickup_name(self, pickup_task_id):
        task = (
            self.repository.get_opshop_pickup_task(pickup_task_id)
            if pickup_task_id
            else None
        )
        location = self.repository.get_opshop_location(task.opshop_id) if task else None
        return location.name if location else (pickup_task_id or "Unknown")

    def _opshop_pickup_date(self, pickup_task_id):
        task = (
            self.repository.get_opshop_pickup_task(pickup_task_id)
            if pickup_task_id
            else None
        )
        return task.pickup_date if task else None

    def _opshop_assignment_pickup_date(self, assignments):
        for item in assignments or []:
            if not isinstance(item, dict):
                continue
            pickup_date = self._opshop_pickup_date(item.get("pickup_task_id"))
            if pickup_date:
                return pickup_date
        return None

    def _route_group_name(self, route_group_id):
        route_group = (
            self.repository.get_countryside_route_group(route_group_id)
            if route_group_id
            else None
        )
        return route_group.route_group_name if route_group else route_group_id

    @staticmethod
    def _template_business_snapshot(template):
        fields = (
            "run_type",
            "run_day",
            "name",
            "suburb",
            "street_address",
            "area_region",
            "primary_contact",
            "primary_phone",
            "secondary_contact",
            "secondary_phone",
            "pickup_frequency",
            "time_window",
            "call_before_arrival",
            "call_timing",
            "access_type",
            "key_required",
            "trailer_restriction",
            "status_notes",
            "default_driver_id",
            "default_driver_name",
            "pickup_category",
            "route_group_id",
        )
        return {field: getattr(template, field, None) for field in fields}

    def _find_opshop_template(self, schedule_id):
        return next(
            (
                template
                for template in self.opshop_template_service.list_opshop_templates(
                    include_inactive=True
                )
                if template.schedule_id == schedule_id
            ),
            None,
        )

    @staticmethod
    def _template_category(template):
        if str(template.run_type or "").upper() == "REGULAR":
            return "REGULAR", "Regular"
        return "ONCALL", "Oncall"

    def _record_template_event(
        self,
        suffix,
        template,
        before=None,
        after=None,
    ):
        action_category, label = self._template_category(template)
        metadata = {
            "pickup_category": template.run_type,
            "company_name": template.name,
            "suburb": template.suburb,
            "run_day": template.run_day,
            "default_driver": template.default_driver_name,
        }
        if before is not None and after is not None:
            changed = [
                field
                for field in before
                if before.get(field) != after.get(field)
            ]
            if not changed:
                return
            metadata = {
                "pickup_category": template.run_type,
                "before": {field: before[field] for field in changed},
                "after": {field: after[field] for field in changed},
            }
        elif suffix == "DISABLED":
            metadata.update(
                {
                    "previous_status": before.get("status"),
                    "new_status": template.status,
                }
            )
        metadata = {key: value for key, value in metadata.items() if value is not None}
        verb = {
            "CREATED": "created",
            "UPDATED": "updated",
            "DISABLED": "disabled",
        }[suffix]
        self._record_logbook(
            result="SUCCESS",
            workspace="OPSHOP",
            action=f"{action_category}_TEMPLATE_{suffix}",
            entity_type="OPSHOP_TEMPLATE",
            entity_id=template.schedule_id,
            summary=f"{label} OP SHOP template for {template.name} was {verb}.",
            metadata=metadata,
        )
