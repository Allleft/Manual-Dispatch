PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS manual_orders (
    order_id TEXT PRIMARY KEY,
    invoice_number TEXT,
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
    start_time TEXT,
    end_time TEXT,
    note TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS manual_drivers (
    driver_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    is_available INTEGER NOT NULL DEFAULT 1,
    preferred_zone TEXT,
    pallet_only INTEGER NOT NULL DEFAULT 0
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
    invoice_number,
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
    start_time,
    end_time,
    is_available,
    preferred_zone,
    pallet_only
) VALUES
    ('D001', 'John', '08:00', '16:00', 1, 'South East', 0),
    ('D002', 'Tony', '08:00', '16:00', 1, 'West', 1),
    ('D003', 'David', '09:00', '15:00', 1, 'North', 0);

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
    ('V001', 'ABC123', 'truck', 1, 10, 0, 0, 0),
    ('V002', 'XYZ888', 'truck', 1, 4, 0, 0, 0),
    ('V003', 'MCC001', 'truck', 1, 6, 0, 0, 0);
