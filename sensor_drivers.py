# sensor_drivers.py
#
# Factory and common interface for environmental sensor drivers.
#
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  maxduracell

import logging
from typing import Dict, Optional

def create_sensor(sensor_type: str, i2c_mcu: str, i2c_bus: str,
                 i2c_address: Optional[int], config):
    """
    Factory function that returns the appropriate sensor driver.
    Uses dynamic imports to prevent startup crashes if some drivers are missing.
    """
    st = sensor_type.lower().strip()

    if st in ("bme680", "bme68x"):
        logging.info(f"Loading BME680 driver ({i2c_mcu}:{i2c_bus})")
        from . import bme680_driver
        return bme680_driver.BME680Sensor(i2c_mcu, i2c_bus, i2c_address, config)

    elif st == "bme280":
        logging.info(f"Loading BME280 driver ({i2c_mcu}:{i2c_bus})")
        from . import bme280_driver
        return bme280_driver.BME280Sensor(i2c_mcu, i2c_bus, i2c_address, config)

    elif st in ("sgp40", "sgp41"):
        logging.info(f"Loading SGP40 driver ({i2c_mcu}:{i2c_bus})")
        from . import sgp40_driver
        return sgp40_driver.SGP40Sensor(i2c_mcu, i2c_bus, i2c_address, config)

    else:
        raise config.error(
            f"Unsupported sensor_type '{sensor_type}'. "
            "Supported types: bme680, bme280, sgp40"
        )


class BaseSensor:
    """
    Abstract base class that all sensor drivers must implement.
    """

    def initialize(self) -> None:
        """Called once during klippy:connect."""
        raise NotImplementedError("Sensor driver must implement initialize()")

    def read(self) -> Optional[Dict[str, float]]:
        """
        Read current sensor values.
        
        Must return a dictionary with at least some of these keys:
            temperature, humidity, pressure, gas_resistance, voc_index
        or None on failure.
        """
        raise NotImplementedError("Sensor driver must implement read()")
