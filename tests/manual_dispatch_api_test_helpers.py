from dataclasses import replace

from backend.schemas import RegisterOperatorAccountRequest


TEST_PASSWORD = "secret123"


def authenticate_test_client(
    client,
    service,
    identity=None,
    account_name="H1 API Test Operator",
):
    if identity is not None:
        account_name = identity.account_name
    account = service.repository.get_operator_account_by_name(account_name)
    if account is None:
        identity = service.register_operator_account(
            RegisterOperatorAccountRequest(
                account_name=account_name,
                password=TEST_PASSWORD,
                confirm_password=TEST_PASSWORD,
            )
        )
    response = client.post(
        "/api/manual-dispatch/auth/login",
        json={"account_name": account_name, "password": TEST_PASSWORD},
    )
    if response.status_code != 200:
        raise AssertionError(
            f"Test client login failed with {response.status_code}: {response.text}"
        )
    return response.json()


def assign_equal_trip_vehicle_fixture(assign, request):
    """Explicit equal trip fixture; neither selection is inferred from NULL."""
    result = None
    for trip_no in ("trip1", "trip2"):
        result = assign(replace(request, trip_no=trip_no))
    return result


def create_legacy_combined_delivery_fixture(service, delivery_date, driver_id, dispatch_date=None):
    """Seed a historical NULL snapshot without invoking new generation."""
    from datetime import datetime, timezone
    from uuid import uuid4
    from backend.schemas import DeliveryRunSheet

    trips = [service.delivery_run_sheet_service._build_trip(delivery_date, driver_id, trip)
             for trip in ("trip1", "trip2")]
    orders = [row for trip in trips for row in trip.orders]
    selection = next((row for row in service.repository.list_driver_vehicle_assignments_for_delivery_date(delivery_date)
                      if row.driver_id == driver_id), None)
    vehicle = service.repository.get_vehicle(selection.vehicle_id) if selection else None
    sheet = DeliveryRunSheet(
        run_sheet_id=f"LEGACY-DRS-{uuid4().hex.upper()}",
        dispatch_date=dispatch_date or delivery_date, delivery_date=delivery_date,
        driver_id=driver_id, driver_name_snapshot=service.repository.get_driver(driver_id).name,
        vehicle_id=selection.vehicle_id if selection else None,
        vehicle_rego_snapshot=vehicle.rego if vehicle else None,
        total_pallets=sum(row.pallet_quantity_snapshot for row in orders),
        total_loose_bags=sum(row.loose_bags_quantity_snapshot for row in orders),
        total_cartons=sum(row.carton_quantity_snapshot for row in orders),
        status="GENERATED", generated_at=datetime.now(timezone.utc).isoformat(),
        saved_at=None, saved_by_account_name=None, saved_by_account_id=None,
        legacy_summary_id=None, trip_no=None, trips=trips,
    )
    sheet = service.repository.create_delivery_run_sheet(sheet)
    service.delivery_application_service._record_delivery_run_sheet_event("DELIVERY_RUN_SHEET_GENERATED", sheet)
    return sheet
