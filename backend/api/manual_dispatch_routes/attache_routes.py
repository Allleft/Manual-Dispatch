from collections.abc import Callable
import logging
from typing import List
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
)
from backend.schemas import (
    AttacheInvoicePdfPreviewResponse,
    CommitAttacheInvoicePdfImportRequest,
    CreateOrderRequest,
    DirectAttacheInvoicePreviewRequest,
    to_dict,
)
from backend.integrations.attache_bridge_client import (
    AttacheBridgeAmbiguousInvoiceError,
    AttacheBridgeConfigurationError,
    AttacheBridgeInvoiceTooLargeError,
    AttacheBridgeInvoiceNotFoundError,
    AttacheBridgeMalformedResponseError,
    AttacheBridgeTimeoutError,
    AttacheBridgeUnavailableError,
    create_attache_bridge_client,
    normalize_attache_invoice_number,
)
from backend.services.manual_dispatch_service import ManualDispatchService
from backend.services.manual_dispatch.workspace_migration_readiness_service import WorkspaceMigrationRequiredError
from backend.services.manual_dispatch.attache_invoice_pdf_parser import (
    current_melbourne_business_date,
    parse_attache_invoice_pdf_bytes,
    with_duplicate_warning,
)
from backend.services.manual_dispatch.attache_direct_invoice_normalizer import (
    AttacheDirectInvoicePayloadError,
    normalize_direct_attache_invoice,
)
from backend.services.manual_dispatch.delivery_suburb_region_service import (
    apply_delivery_area_preview,
)
from .common import (
    require_legacy_mutations_enabled,
    to_http_exception,
    with_logbook_actor,
)


MAX_ATTACHE_PDF_FILES = 30
MAX_ATTACHE_IMPORT_ROWS = 30
MAX_ATTACHE_PDF_FILE_BYTES = 10 * 1024 * 1024
SUPPORTED_ATTACHE_PDF_CONTENT_TYPES = {
    "application/pdf",
    "application/x-pdf",
    "application/octet-stream",
}
LOGGER = logging.getLogger(__name__)


def create_attache_router(
    get_service: Callable[[], ManualDispatchService],
    router: APIRouter = None,
) -> APIRouter:
    router = router or APIRouter()

    def _commit_attache_invoice_pdf_import(request, create_order, record_batch=None):
        if len(request.rows or []) > MAX_ATTACHE_IMPORT_ROWS:
            raise HTTPException(
                status_code=413,
                detail=f"Attaché PDF import accepts at most {MAX_ATTACHE_IMPORT_ROWS} rows per batch.",
            )
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

    def _prepare_attache_preview_item(item, existing_invoice_numbers):
        if (
            item.invoice_number
            and item.invoice_number in existing_invoice_numbers
        ):
            item = with_duplicate_warning(item)
        return apply_delivery_area_preview(item)

    async def _preview_attache_invoice_pdf_import(files):
        if not files:
            raise HTTPException(status_code=400, detail="At least one PDF file is required.")
        if len(files) > MAX_ATTACHE_PDF_FILES:
            raise HTTPException(
                status_code=413,
                detail=f"Attaché PDF import accepts at most {MAX_ATTACHE_PDF_FILES} files per batch.",
            )

        rows = []
        existing_invoice_numbers = _existing_invoice_numbers()
        import_date = current_melbourne_business_date()

        for uploaded_file in files:
            filename = uploaded_file.filename or "invoice.pdf"
            try:
                _validate_attache_upload_type(uploaded_file, filename)
                payload = await uploaded_file.read(MAX_ATTACHE_PDF_FILE_BYTES + 1)
                if len(payload) > MAX_ATTACHE_PDF_FILE_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            f"Attaché PDF file exceeds the {MAX_ATTACHE_PDF_FILE_BYTES} byte limit: "
                            f"{filename}"
                        ),
                    )
                if not payload:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Attaché PDF file is empty: {filename}",
                    )
                if b"%PDF-" not in payload[:1024]:
                    raise ValueError("PDF header is missing")
                parsed = parse_attache_invoice_pdf_bytes(
                    payload,
                    source_filename=filename,
                    import_date=import_date,
                )
                rows.append(
                    _prepare_attache_preview_item(
                        parsed,
                        existing_invoice_numbers,
                    )
                )
            except ValueError as error:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid Attaché PDF file {filename}: {error}",
                ) from error
            finally:
                await uploaded_file.close()

        return AttacheInvoicePdfPreviewResponse(rows=rows)

    @router.post("/delivery/orders/import-attache-direct-preview")
    def preview_delivery_attache_invoice_direct_import(
        request: DirectAttacheInvoicePreviewRequest,
    ):
        invoice_number = str(request.invoice_number or "").strip()
        if not invoice_number:
            raise _direct_preview_http_error(
                400,
                "invalid_invoice_number",
                "Invoice number is required.",
            )
        try:
            invoice_number = normalize_attache_invoice_number(invoice_number)
        except ValueError as error:
            raise _direct_preview_http_error(
                400,
                "invalid_invoice_number",
                str(error),
            ) from error
        LOGGER.info("Attaché lookup started")
        try:
            payload = create_attache_bridge_client().lookup_invoice(
                invoice_number
            )
            parsed = normalize_direct_attache_invoice(
                payload,
                expected_invoice_number=invoice_number,
                import_date=current_melbourne_business_date(),
            )
            row = _prepare_attache_preview_item(
                parsed,
                _existing_invoice_numbers(),
            )
        except (
            AttacheBridgeMalformedResponseError,
            AttacheDirectInvoicePayloadError,
        ) as error:
            LOGGER.warning("Attaché bridge returned malformed data")
            raise _direct_preview_http_error(
                502,
                "bridge_invalid_response",
                "Attaché lookup returned an invalid response. "
                "You can still use Import Attaché PDF.",
            ) from error
        except AttacheBridgeInvoiceNotFoundError as error:
            LOGGER.info("Attaché invoice not found")
            raise _direct_preview_http_error(
                404,
                "invoice_not_found",
                str(error),
            ) from error
        except AttacheBridgeAmbiguousInvoiceError as error:
            raise _direct_preview_http_error(
                409,
                "multiple_invoice_matches",
                str(error),
            ) from error
        except AttacheBridgeInvoiceTooLargeError as error:
            raise _direct_preview_http_error(
                422,
                "invoice_too_large",
                str(error),
            ) from error
        except AttacheBridgeTimeoutError as error:
            LOGGER.warning("Attaché bridge timeout")
            raise _direct_preview_http_error(
                504,
                "bridge_timeout",
                "Attaché lookup timed out. "
                "You can still use Import Attaché PDF.",
            ) from error
        except (
            AttacheBridgeConfigurationError,
            AttacheBridgeUnavailableError,
        ) as error:
            LOGGER.warning("Attaché bridge unavailable")
            raise _direct_preview_http_error(
                503,
                "bridge_unavailable",
                "Attaché lookup is currently unavailable. "
                "You can still use Import Attaché PDF.",
            ) from error
        LOGGER.info("Attaché lookup succeeded")
        return to_dict(AttacheInvoicePdfPreviewResponse(rows=[row]))

    def _validate_attache_upload_type(uploaded_file, filename):
        content_type = (uploaded_file.content_type or "").split(";", 1)[0].strip().lower()
        if not filename.lower().endswith(".pdf") or (
            content_type and content_type not in SUPPORTED_ATTACHE_PDF_CONTENT_TYPES
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported Attaché upload type; PDF files are required: {filename}",
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

    @router.post(
        "/orders/import-attache-pdf-commit",
        dependencies=[Depends(require_legacy_mutations_enabled)],
    )
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


def _direct_preview_http_error(status_code, code, message):
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )
