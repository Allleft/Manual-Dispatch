from collections.abc import Callable
from typing import List

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from backend.schemas import (
    CommitDeliveryDocketDocxImportRequest,
    CreateOrderRequest,
    DeliveryDocketDocxPreviewResponse,
    to_dict,
)
from backend.services.manual_dispatch.delivery_docket_docx_parser import (
    current_melbourne_business_date,
    parse_delivery_docket_docx_bytes,
    with_duplicate_warning,
)
from backend.services.manual_dispatch.workspace_migration_readiness_service import (
    WorkspaceMigrationRequiredError,
)
from backend.services.manual_dispatch_service import ManualDispatchService

from .common import to_http_exception, with_logbook_actor


MAX_DELIVERY_DOCKET_DOCX_FILES = 30
MAX_DELIVERY_DOCKET_IMPORT_ROWS = 30
MAX_DELIVERY_DOCKET_DOCX_FILE_BYTES = 10 * 1024 * 1024
SUPPORTED_DELIVERY_DOCKET_DOCX_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/octet-stream",
    "application/zip",
}


def create_delivery_docket_router(
    get_service: Callable[[], ManualDispatchService],
    router: APIRouter = None,
) -> APIRouter:
    router = router or APIRouter()

    def _existing_invoice_numbers():
        service = get_service()
        return {
            order.invoice_number
            for order in service.repository.list_orders()
            if order.invoice_number
        }

    async def _preview_delivery_docket_docx_import(files):
        if not files:
            raise HTTPException(status_code=400, detail="At least one DOCX file is required.")
        if len(files) > MAX_DELIVERY_DOCKET_DOCX_FILES:
            raise HTTPException(
                status_code=413,
                detail=(
                    "Delivery Docket DOCX import accepts at most "
                    f"{MAX_DELIVERY_DOCKET_DOCX_FILES} files per batch."
                ),
            )

        rows = []
        existing_invoice_numbers = _existing_invoice_numbers()
        import_date = current_melbourne_business_date()
        for uploaded_file in files:
            filename = uploaded_file.filename or "delivery-docket.docx"
            try:
                _validate_delivery_docket_upload_type(uploaded_file, filename)
                payload = await uploaded_file.read(
                    MAX_DELIVERY_DOCKET_DOCX_FILE_BYTES + 1
                )
                if len(payload) > MAX_DELIVERY_DOCKET_DOCX_FILE_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            "Delivery Docket DOCX file exceeds the "
                            f"{MAX_DELIVERY_DOCKET_DOCX_FILE_BYTES} byte limit: {filename}"
                        ),
                    )
                if not payload:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Delivery Docket DOCX file is empty: {filename}",
                    )
                if not payload.startswith(b"PK"):
                    raise ValueError("DOCX ZIP header is missing")
                parsed = parse_delivery_docket_docx_bytes(
                    payload,
                    source_filename=filename,
                    import_date=import_date,
                )
                if parsed.invoice_number and parsed.invoice_number in existing_invoice_numbers:
                    parsed = with_duplicate_warning(parsed)
                rows.append(parsed)
            except ValueError as error:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid Delivery Docket DOCX file {filename}: {error}",
                ) from error
            finally:
                await uploaded_file.close()
        return DeliveryDocketDocxPreviewResponse(rows=rows)

    def _commit_delivery_docket_docx_import(request, create_order):
        if len(request.rows or []) > MAX_DELIVERY_DOCKET_IMPORT_ROWS:
            raise HTTPException(
                status_code=413,
                detail=(
                    "Delivery Docket DOCX import accepts at most "
                    f"{MAX_DELIVERY_DOCKET_IMPORT_ROWS} rows per batch."
                ),
            )
        created_orders = []
        skipped_rows = []
        existing_invoice_numbers = _existing_invoice_numbers()
        for row in request.rows or []:
            row_id = row.row_id or row.docket_number or row.source_filename or "row"
            if not row.selected:
                skipped_rows.append({"row_id": row_id, "reason": "Row was not selected for import."})
                continue
            if not row.importable or row.is_duplicate:
                skipped_rows.append({"row_id": row_id, "reason": "Row is not importable."})
                continue
            if row.invoice_number and row.invoice_number in existing_invoice_numbers:
                skipped_rows.append({
                    "row_id": row_id,
                    "reason": "Duplicate invoice number already exists.",
                })
                continue
            try:
                created = create_order(
                    CreateOrderRequest(
                        invoice_number=row.invoice_number,
                        invoice_date=row.invoice_date,
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
                        carton_quantity=row.carton_quantity,
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

        return {
            "created_orders": created_orders,
            "skipped_rows": skipped_rows,
            "imported_count": len(created_orders),
            "skipped_count": len(skipped_rows),
        }

    @router.post(
        "/delivery/orders/import-delivery-docket-docx-preview",
    )
    async def preview_delivery_docket_docx_import(
        files: List[UploadFile] = File(...),
    ):
        return to_dict(await _preview_delivery_docket_docx_import(files))

    @router.post(
        "/delivery/orders/import-delivery-docket-docx-commit",
    )
    def commit_delivery_docket_docx_import(
        request: CommitDeliveryDocketDocxImportRequest,
        http_request: Request = None,
    ):
        service = get_service()
        try:
            service._ensure_workspace_ready("delivery")
            return with_logbook_actor(
                service,
                http_request,
                lambda: _commit_delivery_docket_docx_import(
                    request,
                    service.create_delivery_order,
                ),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    return router


def _validate_delivery_docket_upload_type(uploaded_file, filename):
    content_type = (uploaded_file.content_type or "").split(";", 1)[0].strip().lower()
    if not filename.lower().endswith(".docx") or (
        content_type
        and content_type not in SUPPORTED_DELIVERY_DOCKET_DOCX_CONTENT_TYPES
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported Delivery Docket upload type; DOCX files are required: "
                f"{filename}"
            ),
        )
