PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS manual_orders (
    order_id TEXT PRIMARY KEY,
    invoice_number TEXT,
    invoice_date TEXT,
    order_no TEXT,
    company_name TEXT,
    phone TEXT,
    delivery_address TEXT,
    suburb TEXT NOT NULL,
    postcode TEXT,
    delivery_date TEXT,
    zone TEXT,
    urgency TEXT,
    preferred_driver_id TEXT,
    pallet_quantity INTEGER NOT NULL DEFAULT 0,
    loose_bags_quantity INTEGER NOT NULL DEFAULT 0,
    carton_quantity INTEGER NOT NULL DEFAULT 0,
    start_time TEXT,
    end_time TEXT,
    note TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS order_product_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL,
    line_no INTEGER NOT NULL,
    product_name TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit TEXT NOT NULL,
    product_code TEXT,
    package_quantity INTEGER,
    package_unit TEXT,
    UNIQUE(order_id, line_no),
    CHECK(quantity > 0),
    CHECK(length(TRIM(unit)) BETWEEN 1 AND 20),
    CHECK(product_code IS NULL OR length(product_code) <= 40),
    CHECK(package_quantity IS NULL OR package_quantity >= 0),
    CHECK(package_unit IS NULL OR length(package_unit) <= 20),
    FOREIGN KEY(order_id) REFERENCES manual_orders(order_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS delivery_order_area_overrides (
    order_id TEXT PRIMARY KEY,
    delivery_area TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by TEXT,
    CHECK(delivery_area IN ('SOUTHEAST', 'LOCAL')),
    FOREIGN KEY(order_id) REFERENCES manual_orders(order_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS manual_drivers (
    driver_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    license_no TEXT,
    email TEXT,
    phone_number TEXT,
    start_time TEXT,
    end_time TEXT,
    is_available INTEGER NOT NULL DEFAULT 1,
    preferred_zone TEXT,
    pallet_only INTEGER NOT NULL DEFAULT 0,
    is_deleted INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS manual_vehicles (
    vehicle_id TEXT PRIMARY KEY,
    rego TEXT NOT NULL,
    type TEXT,
    is_available INTEGER NOT NULL DEFAULT 1,
    pallet_capacity INTEGER NOT NULL DEFAULT 0,
    tub_capacity INTEGER NOT NULL DEFAULT 0,
    trolley_capacity INTEGER NOT NULL DEFAULT 0,
    stillage_capacity INTEGER NOT NULL DEFAULT 0,
    is_deleted INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS manual_dispatch_assignments (
    assignment_id TEXT PRIMARY KEY,
    dispatch_date TEXT NOT NULL,
    task_type TEXT NOT NULL,
    task_id TEXT NOT NULL,
    driver_id TEXT NOT NULL,
    trip_no TEXT NOT NULL,
    assigned_at TEXT,
    updated_at TEXT,
    UNIQUE(dispatch_date, task_type, task_id),
    CHECK(trip_no IN ('trip1', 'trip2')),
    FOREIGN KEY(driver_id) REFERENCES manual_drivers(driver_id)
);

CREATE TABLE IF NOT EXISTS manual_driver_vehicle_assignments (
    dispatch_date TEXT NOT NULL,
    delivery_date TEXT NOT NULL,
    driver_id TEXT NOT NULL,
    vehicle_id TEXT NOT NULL,
    created_at TEXT,
    updated_at TEXT,
    PRIMARY KEY(dispatch_date, delivery_date, driver_id),
    FOREIGN KEY(driver_id) REFERENCES manual_drivers(driver_id),
    FOREIGN KEY(vehicle_id) REFERENCES manual_vehicles(vehicle_id)
);

CREATE TABLE IF NOT EXISTS opshop_locations (
    opshop_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    suburb TEXT,
    street_address TEXT,
    area_region TEXT,
    primary_contact TEXT,
    primary_phone TEXT,
    secondary_contact TEXT,
    secondary_phone TEXT,
    access_type TEXT,
    key_required INTEGER NOT NULL DEFAULT 0,
    trailer_restriction TEXT,
    status_notes TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_opshop_locations_dedupe_key
ON opshop_locations (
    lower(trim(name)),
    lower(trim(COALESCE(suburb, ''))),
    lower(trim(COALESCE(street_address, '')))
);

CREATE TABLE IF NOT EXISTS opshop_countryside_route_groups (
    route_group_id TEXT PRIMARY KEY,
    route_group_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Active',
    active_flag INTEGER NOT NULL DEFAULT 1,
    display_order INTEGER NOT NULL DEFAULT 0,
    source_marker TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_opshop_countryside_route_groups_name
ON opshop_countryside_route_groups (
    lower(trim(route_group_name))
);

CREATE TABLE IF NOT EXISTS opshop_pickup_schedules (
    schedule_id TEXT PRIMARY KEY,
    opshop_id TEXT NOT NULL,
    run_day TEXT,
    run_type TEXT NOT NULL,
    pickup_category TEXT NOT NULL DEFAULT 'NORMAL',
    route_group_id TEXT,
    pickup_frequency TEXT,
    time_window TEXT,
    call_before_arrival INTEGER NOT NULL DEFAULT 0,
    call_timing TEXT,
    status TEXT NOT NULL DEFAULT 'Active',
    active_flag INTEGER NOT NULL DEFAULT 1,
    fortnight_group TEXT,
    review_required INTEGER NOT NULL DEFAULT 0,
    review_reason TEXT,
    default_driver_id TEXT,
    default_driver_alias TEXT,
    default_driver_name_snapshot TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK(run_type IN ('STANDARD', 'REGULAR', 'ON_CALL')),
    CHECK(pickup_category IN ('NORMAL', 'COUNTRYSIDE')),
    CHECK(
        run_day IS NULL
        OR run_day IN ('MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY')
    ),
    CHECK(run_day IS NOT NULL OR run_type = 'ON_CALL' OR review_required = 1),
    CHECK(fortnight_group IS NULL OR fortnight_group IN ('A', 'B')),
    FOREIGN KEY(opshop_id) REFERENCES opshop_locations(opshop_id),
    FOREIGN KEY(route_group_id) REFERENCES opshop_countryside_route_groups(route_group_id)
);

CREATE TABLE IF NOT EXISTS opshop_pickup_tasks (
    pickup_task_id TEXT PRIMARY KEY,
    schedule_id TEXT,
    opshop_id TEXT NOT NULL,
    pickup_date TEXT NOT NULL,
    task_type TEXT NOT NULL DEFAULT 'OPSHOP_PICKUP',
    generated_from TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    dispatch_date TEXT,
    driver_id TEXT,
    trip_no TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK(task_type = 'OPSHOP_PICKUP'),
    CHECK(generated_from IN ('STANDARD', 'REGULAR', 'ON_CALL', 'MANUAL')),
    CHECK(status IN ('ACTIVE', 'ASSIGNED', 'CANCELLED', 'COMPLETED')),
    CHECK(trip_no IS NULL OR trip_no IN ('trip1', 'trip2')),
    FOREIGN KEY(schedule_id) REFERENCES opshop_pickup_schedules(schedule_id),
    FOREIGN KEY(opshop_id) REFERENCES opshop_locations(opshop_id),
    FOREIGN KEY(driver_id) REFERENCES manual_drivers(driver_id)
);

CREATE TABLE IF NOT EXISTS operator_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS final_trip_summaries (
    summary_id TEXT PRIMARY KEY,
    dispatch_date TEXT NOT NULL,
    delivery_date TEXT NOT NULL,
    driver_id TEXT NOT NULL,
    driver_name_snapshot TEXT NOT NULL,
    vehicle_id TEXT,
    vehicle_rego_snapshot TEXT,
    total_pallets INTEGER NOT NULL DEFAULT 0,
    total_loose_bags INTEGER NOT NULL DEFAULT 0,
    total_cartons INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'SAVED',
    generated_at TEXT,
    saved_at TEXT NOT NULL,
    saved_by_account_name TEXT NOT NULL DEFAULT 'Unknown',
    saved_by_account_id INTEGER,
    FOREIGN KEY(saved_by_account_id) REFERENCES operator_accounts(id)
);

CREATE TABLE IF NOT EXISTS final_trip_summary_rows (
    row_id TEXT PRIMARY KEY,
    summary_id TEXT NOT NULL,
    trip_no TEXT NOT NULL,
    row_no INTEGER NOT NULL,
    task_type TEXT NOT NULL,
    task_id TEXT NOT NULL,
    order_id_snapshot TEXT,
    invoice_number_snapshot TEXT,
    order_no_snapshot TEXT,
    company_name_snapshot TEXT,
    suburb_snapshot TEXT,
    delivery_address_snapshot TEXT,
    product_snapshot TEXT,
    product_details_snapshot TEXT NOT NULL DEFAULT '[]',
    estimated_distance_km_from_warehouse_snapshot REAL,
    pallet_quantity_snapshot INTEGER NOT NULL DEFAULT 0,
    loose_bags_quantity_snapshot INTEGER NOT NULL DEFAULT 0,
    carton_quantity_snapshot INTEGER NOT NULL DEFAULT 0,
    note_snapshot TEXT,
    CHECK(trip_no IN ('trip1', 'trip2')),
    FOREIGN KEY(summary_id) REFERENCES final_trip_summaries(summary_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS final_trip_summary_opshop_pickup_rows (
    row_id TEXT PRIMARY KEY,
    summary_id TEXT NOT NULL,
    row_no INTEGER NOT NULL,
    pickup_task_id_snapshot TEXT,
    opshop_name_snapshot TEXT,
    suburb_snapshot TEXT,
    street_address_snapshot TEXT,
    area_region_snapshot TEXT,
    pickup_date_snapshot TEXT,
    run_type_snapshot TEXT,
    pickup_category_snapshot TEXT,
    route_group_id_snapshot TEXT,
    route_group_name_snapshot TEXT,
    pickup_frequency_snapshot TEXT,
    time_window_snapshot TEXT,
    primary_contact_snapshot TEXT,
    primary_phone_snapshot TEXT,
    secondary_contact_snapshot TEXT,
    secondary_phone_snapshot TEXT,
    access_type_snapshot TEXT,
    key_required_snapshot INTEGER,
    trailer_restriction_snapshot TEXT,
    notes_snapshot TEXT,
    status_snapshot TEXT,
    FOREIGN KEY(summary_id) REFERENCES final_trip_summaries(summary_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS delivery_run_sheets (
    run_sheet_id TEXT PRIMARY KEY,
    dispatch_date TEXT NOT NULL,
    delivery_date TEXT NOT NULL,
    driver_id TEXT NOT NULL,
    driver_name_snapshot TEXT NOT NULL,
    vehicle_id TEXT,
    vehicle_rego_snapshot TEXT,
    total_pallets INTEGER NOT NULL DEFAULT 0,
    total_loose_bags INTEGER NOT NULL DEFAULT 0,
    total_cartons INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    saved_at TEXT,
    saved_by_account_name TEXT,
    saved_by_account_id INTEGER,
    legacy_summary_id TEXT,
    execution_status TEXT NOT NULL DEFAULT 'OPEN',
    closed_at TEXT,
    closed_by_account_id INTEGER,
    closed_by_account_name TEXT,
    UNIQUE(dispatch_date, delivery_date, driver_id),
    CHECK(status IN ('GENERATED', 'SAVED')),
    CHECK(execution_status IN ('OPEN', 'CLOSED')),
    FOREIGN KEY(saved_by_account_id) REFERENCES operator_accounts(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_delivery_run_sheets_legacy_summary
ON delivery_run_sheets (legacy_summary_id)
WHERE legacy_summary_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS delivery_run_sheet_rows (
    row_id TEXT PRIMARY KEY,
    run_sheet_id TEXT NOT NULL,
    trip_no TEXT NOT NULL,
    row_no INTEGER NOT NULL,
    task_type TEXT NOT NULL DEFAULT 'ORDER',
    task_id TEXT NOT NULL,
    order_id_snapshot TEXT,
    invoice_number_snapshot TEXT,
    order_no_snapshot TEXT,
    company_name_snapshot TEXT,
    suburb_snapshot TEXT,
    delivery_address_snapshot TEXT,
    product_snapshot TEXT,
    product_details_snapshot TEXT NOT NULL DEFAULT '[]',
    estimated_distance_km_from_warehouse_snapshot REAL,
    pallet_quantity_snapshot INTEGER NOT NULL DEFAULT 0,
    loose_bags_quantity_snapshot INTEGER NOT NULL DEFAULT 0,
    carton_quantity_snapshot INTEGER NOT NULL DEFAULT 0,
    note_snapshot TEXT,
    UNIQUE(run_sheet_id, trip_no, row_no),
    CHECK(task_type = 'ORDER'),
    CHECK(trip_no IN ('trip1', 'trip2')),
    FOREIGN KEY(run_sheet_id) REFERENCES delivery_run_sheets(run_sheet_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS delivery_run_sheet_outcomes (
    outcome_id TEXT PRIMARY KEY,
    run_sheet_id TEXT NOT NULL,
    run_sheet_row_id TEXT NOT NULL UNIQUE,
    order_id TEXT NOT NULL,
    outcome TEXT NOT NULL,
    reason_code TEXT,
    note TEXT,
    next_delivery_date TEXT,
    recorded_at TEXT NOT NULL,
    recorded_by_account_id INTEGER NOT NULL,
    recorded_by_account_name TEXT NOT NULL,
    CHECK(outcome IN ('DELIVERED', 'RETURN_TO_POOL')),
    CHECK(
        (outcome = 'DELIVERED'
            AND reason_code IS NULL
            AND next_delivery_date IS NULL)
        OR
        (outcome = 'RETURN_TO_POOL'
            AND reason_code IS NOT NULL
            AND next_delivery_date IS NOT NULL)
    ),
    FOREIGN KEY(run_sheet_id) REFERENCES delivery_run_sheets(run_sheet_id)
        ON DELETE CASCADE,
    FOREIGN KEY(run_sheet_row_id) REFERENCES delivery_run_sheet_rows(row_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_delivery_run_sheet_outcomes_run_sheet
ON delivery_run_sheet_outcomes (run_sheet_id);

CREATE TABLE IF NOT EXISTS opshop_pickup_collections (
    collection_id TEXT PRIMARY KEY,
    dispatch_date TEXT NOT NULL,
    pickup_date TEXT NOT NULL,
    driver_id TEXT NOT NULL,
    driver_name_snapshot TEXT NOT NULL,
    status TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    saved_at TEXT,
    saved_by_account_name TEXT,
    saved_by_account_id INTEGER,
    legacy_summary_id TEXT,
    UNIQUE(dispatch_date, pickup_date, driver_id),
    CHECK(status IN ('GENERATED', 'SAVED')),
    FOREIGN KEY(saved_by_account_id) REFERENCES operator_accounts(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_opshop_pickup_collections_legacy_summary
ON opshop_pickup_collections (legacy_summary_id)
WHERE legacy_summary_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS opshop_pickup_collection_rows (
    row_id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL,
    row_no INTEGER NOT NULL,
    pickup_task_id_snapshot TEXT,
    opshop_name_snapshot TEXT,
    suburb_snapshot TEXT,
    street_address_snapshot TEXT,
    area_region_snapshot TEXT,
    pickup_date_snapshot TEXT,
    run_type_snapshot TEXT,
    pickup_category_snapshot TEXT,
    route_group_id_snapshot TEXT,
    route_group_name_snapshot TEXT,
    pickup_frequency_snapshot TEXT,
    time_window_snapshot TEXT,
    call_before_arrival_snapshot INTEGER NOT NULL DEFAULT 0,
    call_timing_snapshot TEXT,
    primary_contact_snapshot TEXT,
    primary_phone_snapshot TEXT,
    secondary_contact_snapshot TEXT,
    secondary_phone_snapshot TEXT,
    access_type_snapshot TEXT,
    key_required_snapshot INTEGER,
    trailer_restriction_snapshot TEXT,
    notes_snapshot TEXT,
    status_snapshot TEXT,
    clothing_kg_snapshot REAL,
    shoes_kg_snapshot REAL,
    time_in_snapshot TEXT,
    time_out_snapshot TEXT,
    trolleys_out_to_opshops_snapshot INTEGER,
    trolleys_in_to_mcc_snapshot INTEGER,
    hard_toys_snapshot INTEGER,
    soft_toys_snapshot INTEGER,
    black_bags_snapshot INTEGER,
    shoe_bags_snapshot INTEGER,
    UNIQUE(collection_id, row_no),
    FOREIGN KEY(collection_id) REFERENCES opshop_pickup_collections(collection_id)
        ON DELETE CASCADE
);

INSERT OR IGNORE INTO manual_orders (
    order_id,
    invoice_number,
    order_no,
    company_name,
    phone,
    delivery_address,
    suburb,
    postcode,
    delivery_date,
    zone,
    urgency,
    preferred_driver_id,
    pallet_quantity,
    loose_bags_quantity,
    start_time,
    end_time,
    note,
    status
) VALUES
    (
        'ORD-001',
        'INV-1001',
        NULL,
        'Demo Customer A',
        '0400 000 001',
        '1 Demo Street',
        'Dandenong',
        '3175',
        '2026-05-05',
        'South East',
        'Urgent',
        'D001',
        2,
        0,
        '08:00',
        '12:00',
        'Call before delivery',
        'ACTIVE'
    ),
    (
        'ORD-002',
        'INV-1002',
        NULL,
        'Demo Customer B',
        '0400 000 002',
        '2 Demo Street',
        'Clayton',
        '3168',
        '2026-05-05',
        'South East',
        'Normal',
        'D002',
        0,
        12,
        '10:00',
        '14:00',
        'Loose Bags only',
        'ACTIVE'
    ),
    (
        'ORD-003',
        'INV-1003',
        NULL,
        'Demo Customer C',
        '0400 000 003',
        '3 Demo Street',
        'Springvale',
        '3171',
        '2026-05-05',
        'South East',
        'Normal',
        NULL,
        3,
        0,
        '09:00',
        '15:00',
        NULL,
        'ACTIVE'
    );

INSERT OR IGNORE INTO manual_drivers (
    driver_id,
    name,
    license_no,
    email,
    phone_number,
    start_time,
    end_time,
    is_available,
    preferred_zone,
    pallet_only,
    is_deleted
) VALUES
    ('D001', 'John', 'LIC-D001', 'john@example.com', '0400 100 001', '08:00', '16:00', 1, 'South East', 0, 0),
    ('D002', 'Tony', 'LIC-D002', 'tony@example.com', '0400 100 002', '08:00', '16:00', 1, 'West', 1, 0),
    ('D003', 'David', 'LIC-D003', 'david@example.com', '0400 100 003', '09:00', '15:00', 1, 'North', 0, 0);

INSERT OR IGNORE INTO manual_vehicles (
    vehicle_id,
    rego,
    type,
    is_available,
    pallet_capacity,
    tub_capacity,
    trolley_capacity,
    stillage_capacity,
    is_deleted
) VALUES
    ('V001', 'ABC123', 'truck', 1, 10, 0, 0, 0, 0),
    ('V002', 'XYZ888', 'truck', 1, 4, 0, 0, 0, 0),
    ('V003', 'MCC001', 'truck', 1, 6, 0, 0, 0, 0);
