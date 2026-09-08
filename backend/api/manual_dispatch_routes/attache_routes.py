from collections.abc import Callable
import logging
import time
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
    AttacheCurrentFuturePreviewItem,
    AttacheCurrentFuturePreviewResponse,
    AttacheInvoicePdfPreviewResponse,
    CommitAttacheCurrentFutureImportRequest,
    CommitAttacheInvoicePdfImportRequest,
    CreateOrderRequest,
    DirectAttacheInvoicePreviewRequest,
    to_dict,
)
from backend.integrations.attache_bridge_client import (
    AttacheBridgeAmbiguousInvoiceError,
    AttacheBridgeConfigurationError,
    AttacheBridgeInvoiceBatchTooLargeError,
    AttacheBridgeInvoiceTooLargeError,
    AttacheBridgeInvoiceNotFoundError,
    AttacheBridgeMalformedResponseError,
    AttacheBridgeTimeoutError,
    AttacheBridgeUnavailableError,
    MAX_CURRENT_FUTURE_INVOICES,
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
from backend.services.manual_dispatch.attache_current_future_payment_eligibility import (
    CURRENT_FUTURE_SOURCE,
    ELIGIBILITY_PROOF_TTL_SECONDS,
    EligibilitySnapshotError,
    PAYMENT_REQUIRED,
    PAYMENT_UNKNOWN,
    TERMS_COD,
    classify_payment_eligibility,
    create_eligibility_proof,
    normalize_terms_description,
    verify_eligibility_snapshot,
)
from backend.services.manual_dispatch.delivery_suburb_region_service import (
    apply_delivery_area_preview,
)
from .common import (
    operator_cookie_secret,
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
ATTACHE_CURRENT_FUTURE_SOURCE = CURRENT_FUTURE_SOURCE


def create_attache_router(
    get_service: Callable[[], ManualDispatchService],
    router: APIRouter = None,
) -> APIRouter:
    router = router or APIRouter()

    def _commit_attache_invoice_import(
        request,
        create_order,
        *,
        max_rows,
        limit_label,
        record_batch=None,
        import_source=None,
        proof_secret=None,
    ):
        if len(request.rows or []) > max_rows:
            raise HTTPException(
                status_code=413,
                detail=f"{limit_label} accepts at most {max_rows} rows per batch.",
            )
        created_orders = []
        skipped_rows = []
        existing_invoice_numbers = _existing_invoice_numbers()

        for row in request.rows or []:
            row_id = row.row_id or row.invoice_number or row.source_filename or "row"
            if not row.selected:
                skipped_rows.append({"row_id": row_id, "reason": "Row was not selected for import."})
                continue
            if import_source == ATTACHE_CURRENT_FUTURE_SOURCE:
                try:
                    snapshot = verify_eligibility_snapshot(
                        row, from_date=request.from_date, secret=proof_secret,
                    )
                except EligibilitySnapshotError as error:
                    skipped_rows.append({
                        "row_id": row_id,
                        "reason": str(error),
                        "refresh_required": True,
                    })
                    continue
                payment_skip_reason = _current_future_payment_skip_reason(snapshot)
                if payment_skip_reason:
                    skipped_rows.append(
                        {"row_id": row_id, "reason": payment_skip_reason}
                    )
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

    def _prepare_current_future_preview_item(
        parsed,
        payload,
        existing_invoice_numbers,
        *,
        from_date,
        issued_at,
        proof_secret,
    ):
        terms_description = normalize_terms_description(
            payload.get("terms_description")
        )
        outstanding_balance = payload.get("outstanding_balance")
        payment_eligibility = classify_payment_eligibility(
            terms_description,
            outstanding_balance,
        )
        item = AttacheCurrentFuturePreviewItem(
            **to_dict(parsed),
            terms_description=terms_description,
            outstanding_balance=outstanding_balance,
            payment_eligibility=payment_eligibility,
            issued_at=issued_at,
            expires_at=issued_at + ELIGIBILITY_PROOF_TTL_SECONDS,
        )
        item.eligibility_proof = create_eligibility_proof(
            item, from_date=from_date, secret=proof_secret,
        )
        item = _prepare_attache_preview_item(item, existing_invoice_numbers)
        if item.is_duplicate:
            return item
        warning = _current_future_payment_warning(
            terms_description,
            payment_eligibility,
        )
        if warning:
            item.warnings = [*item.warnings, warning]
            item.importable = False
            item.selected = False
        return item

    def _current_future_payment_warning(
        terms_description,
        payment_eligibility,
    ):
        if payment_eligibility == PAYMENT_REQUIRED:
            return "C.O.D. invoice payment is required before import."
        if payment_eligibility != PAYMENT_UNKNOWN:
            return None
        if terms_description == TERMS_COD:
            return (
                "C.O.D. outstanding balance is unavailable or ambiguous; "
                "payment eligibility requires review."
            )
        return (
            "Account terms are unsupported or unavailable; "
            "payment eligibility requires review."
        )

    def _current_future_payment_skip_reason(snapshot):
        terms_description = snapshot["terms_description"]
        payment_eligibility = classify_payment_eligibility(
            terms_description,
            snapshot["outstanding_balance"],
        )
        warning = _current_future_payment_warning(
            terms_description,
            payment_eligibility,
        )
        return warning

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
            raise _attache_preview_http_error(
                400,
                "invalid_invoice_number",
                "Invoice number is required.",
            )
        try:
            invoice_number = normalize_attache_invoice_number(invoice_number)
        except ValueError as error:
            raise _attache_preview_http_error(
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
            raise _attache_preview_http_error(
                502,
                "bridge_invalid_response",
                "Attaché lookup returned an invalid response. "
                "You can still use Import Attaché PDF.",
            ) from error
        except AttacheBridgeInvoiceNotFoundError as error:
            LOGGER.info("Attaché invoice not found")
            raise _attache_preview_http_error(
                404,
                "invoice_not_found",
                str(error),
            ) from error
        except AttacheBridgeAmbiguousInvoiceError as error:
            raise _attache_preview_http_error(
                409,
                "multiple_invoice_matches",
                str(error),
            ) from error
        except AttacheBridgeInvoiceTooLargeError as error:
            raise _attache_preview_http_error(
                422,
                "invoice_too_large",
                str(error),
            ) from error
        except AttacheBridgeTimeoutError as error:
            LOGGER.warning("Attaché bridge timeout")
            raise _attache_preview_http_error(
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
            raise _attache_preview_http_error(
                503,
                "bridge_unavailable",
                "Attaché lookup is currently unavailable. "
                "You can still use Import Attaché PDF.",
            ) from error
        LOGGER.info("Attaché lookup succeeded")
        return to_dict(AttacheInvoicePdfPreviewResponse(rows=[row]))

    @router.post(
        "/delivery/orders/import-attache-current-future-preview"
    )
    def preview_delivery_attache_current_future_import():
        import_date = current_melbourne_business_date()
        from_date = import_date.isoformat()
        LOGGER.info("Attaché current/future preview started from_date=%s", from_date)
        try:
            payloads = create_attache_bridge_client().lookup_invoices_from_date(
                from_date
            )
            issued_at = int(time.time())
            proof_secret = operator_cookie_secret()
            existing_invoice_numbers = _existing_invoice_numbers()
            rows = []
            for payload in payloads:
                invoice_number = normalize_attache_invoice_number(
                    payload.get("invoice_number")
                )
                parsed = normalize_direct_attache_invoice(
                    payload,
                    expected_invoice_number=invoice_number,
                    import_date=import_date,
                )
                rows.append(
                    _prepare_current_future_preview_item(
                        parsed,
                        payload,
                        existing_invoice_numbers,
                        from_date=from_date,
                        issued_at=issued_at,
                        proof_secret=proof_secret,
                    )
                )
        except AttacheBridgeInvoiceBatchTooLargeError as error:
            raise _attache_preview_http_error(
                413,
                "invoice_batch_limit_exceeded",
                "Too many current/future Attaché invoices were returned. "
                "No partial preview was created.",
            ) from error
        except AttacheBridgeInvoiceTooLargeError as error:
            raise _attache_preview_http_error(
                422,
                "invoice_too_large",
                "An Attaché invoice exceeds the supported product-line limit. "
                "No partial preview was created.",
            ) from error
        except AttacheBridgeTimeoutError as error:
            LOGGER.warning("Attaché current/future bridge timeout")
            raise _attache_preview_http_error(
                504,
                "bridge_timeout",
                "Attaché current/future invoice lookup timed out.",
            ) from error
        except (
            AttacheBridgeMalformedResponseError,
            AttacheDirectInvoicePayloadError,
            ValueError,
        ) as error:
            LOGGER.warning("Attaché current/future bridge returned malformed data")
            raise _attache_preview_http_error(
                502,
                "bridge_invalid_response",
                "Attaché current/future invoice lookup returned an invalid response.",
            ) from error
        except (
            AttacheBridgeConfigurationError,
            AttacheBridgeUnavailableError,
        ) as error:
            LOGGER.warning("Attaché current/future bridge unavailable")
            raise _attache_preview_http_error(
                503,
                "bridge_unavailable",
                "Attaché current/future invoice lookup is currently unavailable.",
            ) from error
        LOGGER.info(
            "Attaché current/future preview succeeded from_date=%s count=%d",
            from_date,
            len(rows),
        )
        return to_dict(
            AttacheCurrentFuturePreviewResponse(
                from_date=from_date,
                rows=rows,
            )
        )

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
                lambda: _commit_attache_invoice_import(
                    request,
                    service.create_delivery_order,
                    max_rows=MAX_ATTACHE_IMPORT_ROWS,
                    limit_label="Attaché PDF import",
                    record_batch=service.record_attache_import_confirmation,
                ),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post(
        "/delivery/orders/import-attache-current-future-commit"
    )
    def commit_delivery_attache_current_future_import(
        request: CommitAttacheCurrentFutureImportRequest,
        http_request: Request = None,
    ):
        service = get_service()
        try:
            service._ensure_workspace_ready("delivery")
            return with_logbook_actor(
                service,
                http_request,
                lambda: _commit_attache_invoice_import(
                    request,
                    service.create_delivery_order,
                    max_rows=MAX_CURRENT_FUTURE_INVOICES,
                    limit_label="Attaché current/future invoice import",
                    record_batch=service.record_attache_import_confirmation,
                    import_source=ATTACHE_CURRENT_FUTURE_SOURCE,
                    proof_secret=operator_cookie_secret(),
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
            lambda: _commit_attache_invoice_import(
                request,
                service.create_order,
                max_rows=MAX_ATTACHE_IMPORT_ROWS,
                limit_label="Attaché PDF import",
                record_batch=service.record_attache_import_confirmation,
            ),
        )

    return router


def _attache_preview_http_error(status_code, code, message):
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )
