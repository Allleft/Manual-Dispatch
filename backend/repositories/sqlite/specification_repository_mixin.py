from backend.db.connection import connect

class SQLiteSpecificationRepositoryMixin:
    """Specification persistence responsibilities."""

    def list_drivers(self):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM manual_drivers
                WHERE is_available = 1 AND is_deleted = 0
                ORDER BY driver_id
                """
            ).fetchall()
        return [self._row_to_driver(row) for row in rows]

    def list_vehicles(self):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM manual_vehicles
                WHERE is_available = 1 AND is_deleted = 0
                ORDER BY vehicle_id
                """
            ).fetchall()
        return [self._row_to_vehicle(row) for row in rows]

    def list_specification_drivers(self):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM manual_drivers
                WHERE is_deleted = 0
                ORDER BY driver_id
                """
            ).fetchall()
        return [self._row_to_driver(row) for row in rows]

    def list_specification_vehicles(self):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM manual_vehicles
                WHERE is_deleted = 0
                ORDER BY vehicle_id
                """
            ).fetchall()
        return [self._row_to_vehicle(row) for row in rows]

    def list_driver_ids(self):
        with connect(self.db_path) as connection:
            rows = connection.execute("SELECT driver_id FROM manual_drivers").fetchall()
        return [row["driver_id"] for row in rows]

    def list_vehicle_ids(self):
        with connect(self.db_path) as connection:
            rows = connection.execute("SELECT vehicle_id FROM manual_vehicles").fetchall()
        return [row["vehicle_id"] for row in rows]

    def get_driver(self, driver_id):
        with connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT * FROM manual_drivers WHERE driver_id = ?",
                (driver_id,),
            ).fetchone()
        return self._row_to_driver(row) if row else None

    def get_vehicle(self, vehicle_id):
        with connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT * FROM manual_vehicles WHERE vehicle_id = ?",
                (vehicle_id,),
            ).fetchone()
        return self._row_to_vehicle(row) if row else None

    def create_driver(self, driver):
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO manual_drivers (
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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    driver.driver_id,
                    driver.name,
                    driver.license_no,
                    driver.email,
                    driver.phone_number,
                    driver.start_time,
                    driver.end_time,
                    int(driver.is_available),
                    driver.preferred_zone,
                    int(driver.pallet_only),
                    int(driver.is_deleted),
                ),
            )
            connection.commit()
        return self.get_driver(driver.driver_id)

    def update_driver(self, driver):
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                UPDATE manual_drivers
                SET
                    name = ?,
                    license_no = ?,
                    email = ?,
                    phone_number = ?,
                    start_time = ?,
                    end_time = ?,
                    is_available = ?,
                    preferred_zone = ?,
                    pallet_only = ?
                WHERE driver_id = ? AND is_deleted = 0
                """,
                (
                    driver.name,
                    driver.license_no,
                    driver.email,
                    driver.phone_number,
                    driver.start_time,
                    driver.end_time,
                    int(driver.is_available),
                    driver.preferred_zone,
                    int(driver.pallet_only),
                    driver.driver_id,
                ),
            )
            connection.commit()

        if cursor.rowcount == 0:
            raise ValueError(f"Driver does not exist: {driver.driver_id}")
        return self.get_driver(driver.driver_id)

    def delete_driver(self, driver_id):
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                UPDATE manual_drivers
                SET is_deleted = 1, is_available = 0
                WHERE driver_id = ? AND is_deleted = 0
                """,
                (driver_id,),
            )
            connection.commit()

        if cursor.rowcount == 0:
            raise ValueError(f"Driver does not exist: {driver_id}")
        return True

    def create_vehicle(self, vehicle):
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO manual_vehicles (
                    vehicle_id,
                    rego,
                    type,
                    is_available,
                    pallet_capacity,
                    tub_capacity,
                    trolley_capacity,
                    stillage_capacity,
                    is_deleted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    vehicle.vehicle_id,
                    vehicle.rego,
                    vehicle.type,
                    int(vehicle.is_available),
                    vehicle.pallet_capacity,
                    vehicle.tub_capacity,
                    vehicle.trolley_capacity,
                    vehicle.stillage_capacity,
                    int(vehicle.is_deleted),
                ),
            )
            connection.commit()
        return self.get_vehicle(vehicle.vehicle_id)

    def update_vehicle(self, vehicle):
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                UPDATE manual_vehicles
                SET
                    rego = ?,
                    type = ?,
                    is_available = ?,
                    pallet_capacity = ?,
                    tub_capacity = ?,
                    trolley_capacity = ?,
                    stillage_capacity = ?
                WHERE vehicle_id = ? AND is_deleted = 0
                """,
                (
                    vehicle.rego,
                    vehicle.type,
                    int(vehicle.is_available),
                    vehicle.pallet_capacity,
                    vehicle.tub_capacity,
                    vehicle.trolley_capacity,
                    vehicle.stillage_capacity,
                    vehicle.vehicle_id,
                ),
            )
            connection.commit()

        if cursor.rowcount == 0:
            raise ValueError(f"Vehicle does not exist: {vehicle.vehicle_id}")
        return self.get_vehicle(vehicle.vehicle_id)

    def delete_vehicle(self, vehicle_id):
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                UPDATE manual_vehicles
                SET is_deleted = 1, is_available = 0
                WHERE vehicle_id = ? AND is_deleted = 0
                """,
                (vehicle_id,),
            )
            connection.commit()

        if cursor.rowcount == 0:
            raise ValueError(f"Vehicle does not exist: {vehicle_id}")
        return True
