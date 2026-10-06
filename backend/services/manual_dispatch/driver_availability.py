def list_visible_drivers(repository, referenced_driver_ids=()):
    referenced_driver_ids = set(referenced_driver_ids)
    return [
        driver
        for driver in repository.list_specification_drivers()
        if driver.is_available or driver.driver_id in referenced_driver_ids
    ]
