PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS manual_orders (
    order_id TEXT PRIMARY KEY,
    company_name TEXT,
    delivery_address TEXT,
    suburb TEXT NOT NULL,
    postcode TEXT,
    delivery_date TEXT,
    zone TEXT,
    urgency TEXT,
    preferred_driver_id TEXT,
    pallet_quantity INTEGER NOT NULL DEFAULT 0,
    loose_bags_quantity INTEGER NOT NULL DEFAULT 0,
    start_time TEXT,
    end_time TEXT,
    note TEXT
);

CREATE TABLE IF NOT EXISTS manual_drivers (
    driver_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    is_available INTEGER NOT NULL DEFAULT 1,
    preferred_zone TEXT
);

CREATE TABLE IF NOT EXISTS manual_vehicles (
    vehicle_id TEXT PRIMARY KEY,
    rego TEXT NOT NULL,
    type TEXT,
    is_available INTEGER NOT NULL DEFAULT 1,
    pallet_capacity INTEGER NOT NULL DEFAULT 0,
    tub_capacity INTEGER NOT NULL DEFAULT 0,
    trolley_capacity INTEGER NOT NULL DEFAULT 0,
    stillage_capacity INTEGER NOT NULL DEFAULT 0
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
    driver_id TEXT NOT NULL,
    vehicle_id TEXT NOT NULL,
    created_at TEXT,
    updated_at TEXT,
    PRIMARY KEY(dispatch_date, driver_id),
    FOREIGN KEY(driver_id) REFERENCES manual_drivers(driver_id),
    FOREIGN KEY(vehicle_id) REFERENCES manual_vehicles(vehicle_id)
);

INSERT OR IGNORE INTO manual_orders (
    order_id,
    company_name,
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
    note
) VALUES
    (
        'ORD-001',
        'Demo Customer A',
        '1 Demo Street',
        'Dandenong',
        '3175',
        '2026-05-05',
        'South East',
        'normal',
        NULL,
        2,
        0,
        NULL,
        NULL,
        NULL
    ),
    (
        'ORD-002',
        'Demo Customer B',
        '2 Demo Street',
        'Clayton',
        '3168',
        '2026-05-05',
        'South East',
        'normal',
        NULL,
        0,
        12,
        NULL,
        NULL,
        'Loose Bags only'
    ),
    (
        'ORD-003',
        'Demo Customer C',
        '3 Demo Street',
        'Springvale',
        '3171',
        '2026-05-05',
        'South East',
        'normal',
        NULL,
        3,
        0,
        NULL,
        NULL,
        NULL
    );

INSERT OR IGNORE INTO manual_drivers (
    driver_id,
    name,
    start_time,
    end_time,
    is_available,
    preferred_zone
) VALUES
    ('D001', 'John', NULL, NULL, 1, NULL),
    ('D002', 'Tony', NULL, NULL, 1, NULL),
    ('D003', 'David', NULL, NULL, 1, NULL);

INSERT OR IGNORE INTO manual_vehicles (
    vehicle_id,
    rego,
    type,
    is_available,
    pallet_capacity,
    tub_capacity,
    trolley_capacity,
    stillage_capacity
) VALUES
    ('V001', 'ABC123', 'truck', 1, 0, 0, 0, 0),
    ('V002', 'XYZ888', 'truck', 1, 0, 0, 0, 0),
    ('V003', 'MCC001', 'truck', 1, 0, 0, 0, 0);
