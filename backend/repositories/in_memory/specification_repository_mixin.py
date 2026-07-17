class InMemorySpecificationRepositoryMixin:
    """Specification in-memory responsibilities."""

    def list_drivers(self):
        return [
            driver
            for driver in self.drivers
            if driver.is_available and not driver.is_deleted
        ]

    def list_vehicles(self):
        return [
            vehicle
            for vehicle in self.vehicles
            if vehicle.is_available and not vehicle.is_deleted
        ]

    def list_specification_drivers(self):
        return [driver for driver in self.drivers if not driver.is_deleted]

    def list_specification_vehicles(self):
        return [vehicle for vehicle in self.vehicles if not vehicle.is_deleted]

    def list_driver_ids(self):
        return [driver.driver_id for driver in self.drivers]

    def list_vehicle_ids(self):
        return [vehicle.vehicle_id for vehicle in self.vehicles]

    def get_driver(self, driver_id):
        return next(
            (driver for driver in self.drivers if driver.driver_id == driver_id),
            None,
        )

    def get_vehicle(self, vehicle_id):
        return next(
            (vehicle for vehicle in self.vehicles if vehicle.vehicle_id == vehicle_id),
            None,
        )

    def create_driver(self, driver):
        if self.get_driver(driver.driver_id):
            raise ValueError(f"Driver already exists: {driver.driver_id}")
        self.drivers.append(driver)
        return driver

    def update_driver(self, driver):
        for index, existing in enumerate(self.drivers):
            if existing.driver_id == driver.driver_id and not existing.is_deleted:
                self.drivers[index] = driver
                return driver
        raise ValueError(f"Driver does not exist: {driver.driver_id}")

    def delete_driver(self, driver_id):
        driver = self.get_driver(driver_id)
        if not driver or driver.is_deleted:
            raise ValueError(f"Driver does not exist: {driver_id}")
        driver.is_deleted = True
        driver.is_available = False
        return True

    def create_vehicle(self, vehicle):
        if self.get_vehicle(vehicle.vehicle_id):
            raise ValueError(f"Vehicle already exists: {vehicle.vehicle_id}")
        self.vehicles.append(vehicle)
        return vehicle

    def update_vehicle(self, vehicle):
        for index, existing in enumerate(self.vehicles):
            if existing.vehicle_id == vehicle.vehicle_id and not existing.is_deleted:
                self.vehicles[index] = vehicle
                return vehicle
        raise ValueError(f"Vehicle does not exist: {vehicle.vehicle_id}")

    def delete_vehicle(self, vehicle_id):
        vehicle = self.get_vehicle(vehicle_id)
        if not vehicle or vehicle.is_deleted:
            raise ValueError(f"Vehicle does not exist: {vehicle_id}")
        vehicle.is_deleted = True
        vehicle.is_available = False
        return True
