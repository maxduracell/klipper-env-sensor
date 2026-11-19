# sensor_drivers.py
#
# Low-level hardware drivers for environmental sensors.
# This module acts as a factory and provides a consistent interface
# for all supported sensors (BME680, BME280, SGP40, etc.).
#
# Each sensor driver must implement:
#   - initialize() : Configure and start the sensor
#   - read()       : Return a dictionary of sensor readings
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of klipper-env-sensor.
# Copyright (C) 2026  maxduracell

import logging
from typing import Dict, Any, Optional

# Import individual sensor drivers
from . import bme680_driver
from . import bme280_driver
from . import sgp40_driver


def create_sensor(sensor_type: str, i2c_mcu: str, i2c_bus: str,
                 i2c_address: Optional[int], config) -> "BaseSensor":
    """
    Factory function that returns the correct sensor driver instance.
    
    This allows the main env_sensor module to remain clean while supporting
    multiple sensor types through a common interface.
    
    Args:
        sensor_type (str): Type of sensor ("bme680", "bme280", "sgp40")
        i2c_mcu (str): Name of the MCU the sensor is connected to
        i2c_bus (str): I2C bus name (e.g. "i2c1a")
        i2c_address (int): I2C address (optional - will use default if None)
        config: Klipper config object for error reporting
    
    Returns:
        BaseSensor instance
    """
    st = sensor_type.lower().strip()

    if st in ("bme680", "bme68x"):
        logging.info(f"Loading BME680 driver for {i2c_mcu}:{i2c_bus}")
        return bme680_driver.BME680Sensor(i2c_mcu, i2c_bus, i2c_address, config)

    elif st == "bme280":
        logging.info(f"Loading BME280 driver for {i2c_mcu}:{i2c_bus}")
        return bme280_driver.BME280Sensor(i2c_mcu, i2c_bus, i2c_address, config)

    elif st in ("sgp40", "sgp41"):
        logging.info(f"Loading SGP40 driver for {i2c_mcu}:{i2c_bus}")
        return sgp40_driver.SGP40Sensor(i2c_mcu, i2c_bus, i2c_address, config)

    else:
        raise config.error(
            f"Unsupported sensor_type '{sensor_type}'. "
            "Supported types: bme680, bme280, sgp40"
        )


# ===========================================================================
# Abstract Base Class - All sensor drivers must follow this interface
# ===========================================================================
class BaseSensor:
    """
    Abstract base class defining the interface that all sensor drivers must implement.
    
    This ensures the main env_sensor.py module can work with any sensor without
    knowing the low-level details.
    """

    def initialize(self) -> None:
        """
        Initialize the sensor hardware.
        Called once during 'klippy:connect' event.
        Should configure I2C, set oversampling, heater settings, etc.
        """
        raise NotImplementedError("Sensor driver must implement initialize()")

    def read(self) -> Optional[Dict[str, float]]:
        """
        Read current values from the sensor.
        
        Returns:
            Dictionary containing sensor readings, or None on failure.
            Expected keys:
                - 'temperature' (float, °C)
                - 'humidity' (float, %)
                - 'pressure' (float, hPa)
                - 'gas_resistance' (float, Ohms)      [BME680 only]
                - 'voc_index' (float)                 [SGP40 only]
        """
        raise NotImplementedError("Sensor driver must implement read()")
