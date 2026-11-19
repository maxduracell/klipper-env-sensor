# bme280_driver.py
#
# Low-level driver for the Bosch BME280 sensor.
# Simpler than the BME680 (no gas sensor or heater).
# Used for temperature, humidity, and pressure only.
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of klipper-env-sensor.
# Copyright (C) 2026 maxduracell

import logging
from typing import Dict, Optional
from . import BaseSensor


class BME280Sensor(BaseSensor):
    """
    Driver for the BME280 environmental sensor.
    
    The BME280 is a very popular and stable sensor for basic
    temperature, humidity, and barometric pressure readings.
    It does NOT have a gas sensor.
    """

    DEFAULT_I2C_ADDRESS = 0x76
    ALTERNATE_I2C_ADDRESS = 0x77

    def __init__(self, i2c_mcu: str, i2c_bus: str, i2c_address: Optional[int], config):
        self.printer = config.get_printer()
        self.i2c_mcu_name = i2c_mcu
        self.i2c_bus = i2c_bus
        self.i2c = None

        self.i2c_addr = i2c_address if i2c_address is not None else self.DEFAULT_I2C_ADDRESS

        self._is_initialized = False

        logging.info(f"BME280Sensor initialized on {i2c_mcu}:{i2c_bus} @ 0x{self.i2c_addr:02X}")

    def initialize(self) -> None:
        """Initialize the BME280 sensor."""
        try:
            self.i2c = self.printer.lookup_object(f"i2c_{self.i2c_mcu_name}").get_i2c(self.i2c_bus)
            
            # Read chip ID to verify sensor is present
            chip_id = self.i2c.read(self.i2c_addr, 0xD0, 1)[0]
            if chip_id != 0x60:
                raise Exception(f"Invalid BME280 chip ID: 0x{chip_id:02X} (expected 0x60)")

            logging.info(f"BME280 detected successfully (Chip ID: 0x{chip_id:02X})")
            
            # TODO: Full initialization sequence (soft reset, configure oversampling, IIR filter, etc.)
            self._is_initialized = True

        except Exception as e:
            logging.exception("Failed to initialize BME280")
            raise self.printer.config_error(f"Unable to initialize BME280: {e}")

    def read(self) -> Optional[Dict[str, float]]:
        """Read temperature, humidity, and pressure from the BME280."""
        if not self._is_initialized or self.i2c is None:
            return None

        try:
            # TODO: Implement actual register reads and compensation calculations
            # For now we return placeholder values so the module can be tested.

            readings = {
                "temperature": 22.3,
                "humidity": 48.5,
                "pressure": 1012.8,
                "status": "placeholder_bme280"
            }

            return readings

        except Exception as e:
            logging.exception("BME280 read failed")
            return None
