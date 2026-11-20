# sgp40_driver.py
#
# Functional driver for the Sensirion SGP40 VOC sensor.
# Provides raw gas signal and a simplified VOC index.
#
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  maxduracell

import logging
from typing import Dict, Optional
from .sensor_drivers import BaseSensor

class SGP40Sensor(BaseSensor):
    """
    Functional driver for the Sensirion SGP40 VOC sensor.
    """

    # SGP40 Commands
    CMD_MEASURE_RAW = [0x26, 0x0F]
    CMD_GET_SERIAL  = [0x36, 0x82]
    CMD_HEATER_OFF  = [0x36, 0x15]

    DEFAULT_I2C_ADDRESS = 0x59

    def __init__(self, i2c_mcu: str, i2c_bus: str, i2c_address: Optional[int], config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        
        # Standard Klipper core I2C configuration helper
        # Automatically handles MCU lookup, dynamic pins, and custom bus layouts.
        import bus
        self.i2c = bus.setup_sensorsbus(config, "i2c", default_addr=i2c_address or self.DEFAULT_I2C_ADDRESS)

        self._is_initialized = False

        # Simple baseline for VOC index calculation
        self.baseline = None
        self.adaptation_rate = 0.0001

        logging.info("SGP40Sensor registered successfully")

    def initialize(self) -> None:
        try:
            # Test communication by requesting serial number
            self.i2c.write(self.CMD_GET_SERIAL)
            self._pause(0.01)
            data = self.i2c.read(0x00, 9)  # 3 words + CRCs

            logging.info(f"SGP40 detected on bus")

            self._is_initialized = True
            logging.info("SGP40 initialization successful")

        except Exception as e:
            logging.exception("SGP40 init failed")
            raise self.printer.config_error(f"Unable to initialize SGP40: {e}")

    def _pause(self, seconds: float):
        self.reactor.pause(self.reactor.monotonic() + seconds)

    def read(self) -> Optional[Dict[str, float]]:
        """
        Read the SGP40 and return VOC related values.
        """
        if not self._is_initialized or self.i2c is None:
            return None

        try:
            self.i2c.write(self.CMD_MEASURE_RAW)
            self._pause(0.03)  # Measurement takes ~30ms

            data = self.i2c.read(0x00, 3)  # 2 bytes data + CRC

            raw_signal = (data[0] << 8) | data[1]

            # Simple VOC index calculation (0-500 scale)
            voc_index = self._calculate_voc_index(raw_signal)

            return {
                "voc_index": round(voc_index, 1),
                "raw_gas": raw_signal,
            }

        except Exception as e:
            logging.exception("SGP40 read failed")
            return None

    def _calculate_voc_index(self, raw_signal: int) -> float:
        """
        Simple open-source style VOC index calculation.
        Higher raw signal generally means cleaner air on SGP40.
        """
        if self.baseline is None:
            self.baseline = float(raw_signal)
            return 75.0  # Neutral starting point

        # Slow adaptive baseline
        self.baseline = (self.baseline * (1.0 - self.adaptation_rate) +
                         raw_signal * self.adaptation_rate)

        # Convert to 0-500 scale
        ratio = self.baseline / max(raw_signal, 1)
        voc = 50.0 + (ratio - 1.0) * 200.0
        return max(0.0, min(500.0, voc))
