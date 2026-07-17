from collections.abc import Callable
from hashlib import sha1
from typing import List
from fastapi import (
    APIRouter,
    File,
    Request,
    UploadFile,
)
from backend.schemas import (
    AttacheInvoicePdfPreviewResponse,
    CommitAttacheInvoicePdfImportRequest,
    CreateOrderRequest,
    to_dict,
)
from backend.services.manual_dispatch_service import ManualDispatchService
from backend.services.manual_dispatch.workspace_migration_readiness_service import WorkspaceMigrationRequiredError
from backend.services.manual_dispatch.attache_invoice_pdf_parser import (
    parse_attache_invoice_pdf_bytes,
    with_duplicate_warning,
)
from .common import (
    to_http_exception,
    with_logbook_actor,
)


def create_attache_router(
    get_service: Callable[[], ManualDispatchService],
    router: APIRouter = None,
) -> APIRouter:
    router = router or APIRouter()

    def _commit_attache_invoice_pdf_import(request, create_order, record_batch=None):
        created_orders = []
        skipped_rows = []
        existing_invoice_numbers = _existing_invoice_numbers()

        for row in request.rows or []:
            row_id = row.row_id or row.invoice_number or row.source_filename or "row"
            if not row.selected:
                skipped_rows.append({"row_id": row_id, "reason": "Row was not selected for import."})
                continue
            if not row.importable or row.is_duplicate:
                skipped_rows.append({"row_id": row_id, "reason": "Row is not importable."})
                continue
            if row.invoice_number and row.invoice_number in existing_invoice_numbers:
                skipped_rows.append({"row_id": row_id, "reason": "Duplicate invoice number already exists."})
                continue

            try:
                created = create_order(
                    CreateOrderRequest(
                        invoice_number=row.invoice_number,
                        order_no=row.order_no,
                        company_name=row.company_name,
                        phone=row.phone,
                        delivery_address=row.delivery_address,
                        suburb=row.suburb,
                        postcode=row.postcode,
                        delivery_date=row.delivery_date,
                        zone=row.zone,
                        urgency=row.urgency,
                        preferred_driver_id=row.preferred_driver_id,
                        pallet_quantity=row.pallet_quantity,
                        loose_bags_quantity=row.loose_bags_quantity,
                        start_time=row.start_time,
                        end_time=row.end_time,
                        note=row.note,
                        product_lines=row.product_lines,
                    )
                )
                created_orders.append(to_dict(created))
                if created.invoice_number:
                    existing_invoice_numbers.add(created.invoice_number)
            except WorkspaceMigrationRequiredError:
                raise
            except ValueError as error:
                skipped_rows.append({"row_id": row_id, "reason": str(error)})

        result = {
            "created_orders": created_orders,
            "skipped_rows": skipped_rows,
            "imported_count": len(created_orders),
            "skipped_count": len(skipped_rows),
        }
        if record_batch is not None:
            record_batch(request.rows or [], result)
        return result

    def _existing_invoice_numbers():
        service = get_service()
        return {
            order.invoice_number
            for order in service.repository.list_orders()
            if order.invoice_number
        }

    async def _preview_attache_invoice_pdf_import(files):
        rows = []
        existing_invoice_numbers = _existing_invoice_numbers()

        for uploaded_file in files:
            filename = uploaded_file.filename or "invoice.pdf"
            try:
                parsed = parse_attache_invoice_pdf_bytes(
                    await uploaded_file.read(),
                    source_filename=filename,
                )
                if parsed.invoice_number and parsed.invoice_number in existing_invoice_numbers:
                    parsed = with_duplicate_warning(parsed)
                rows.append(parsed)
            except ValueError as error:
                rows.append(
                    _failed_attache_preview_row(
                        filename,
                        str(error),
                    )
                )

        return AttacheInvoicePdfPreviewResponse(rows=rows)

    def _failed_attache_preview_row(source_filename, message):
        from backend.schemas import AttacheInvoicePdfPreviewItem

        return AttacheInvoicePdfPreviewItem(
            row_id=f"ATTACHE-FAILED-{sha1(source_filename.encode('utf-8')).hexdigest()[:12]}",
            source_filename=source_filename,
            warnings=[message],
            importable=False,
            selected=False,
        )

    @router.post("/delivery/orders/import-attache-pdf-preview")
    async def preview_delivery_attache_invoice_pdf_import(files: List[UploadFile] = File(...)):
        service = get_service()
        return to_dict(await _preview_attache_invoice_pdf_import(files))

    @router.post("/delivery/orders/import-attache-pdf-commit")
    def commit_delivery_attache_invoice_pdf_import(
        request: CommitAttacheInvoicePdfImportRequest,
        http_request: Request = None,
    ):
        service = get_service()
        try:
            service._ensure_workspace_ready("delivery")
            return with_logbook_actor(
                service,
                http_request,
                lambda: _commit_attache_invoice_pdf_import(
                    request,
                    service.create_delivery_order,
                    service.record_attache_import_confirmation,
                ),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/orders/import-attache-pdf-preview")
    async def preview_attache_invoice_pdf_import(files: List[UploadFile] = File(...)):
        service = get_service()
        return to_dict(await _preview_attache_invoice_pdf_import(files))

    @router.post("/orders/import-attache-pdf-commit")
    def commit_attache_invoice_pdf_import(
        request: CommitAttacheInvoicePdfImportRequest,
        http_request: Request = None,
    ):
        service = get_service()
        return with_logbook_actor(
            service,
            http_request,
            lambda: _commit_attache_invoice_pdf_import(
                request,
                service.create_order,
                service.record_attache_import_confirmation,
            ),
        )

    return router
