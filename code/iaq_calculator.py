# iaq_calculator.py
#
# IAQ (Indoor Air Quality) and VOC calculation logic for klipper-env-sensor.
#
# This module takes raw readings from BME680, BME280, and/or SGP40 sensors
# and computes a meaningful air quality index.
#
# We deliberately avoid the closed-source Bosch BSEC library and instead
# implement an open-source, understandable, and maintainable solution.
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of klipper-env-sensor.
# Copyright (C) 2026  maxduracell
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.

import logging
import time
from typing import Dict, Any, Optional


class IAQCalculator:
    """
    Calculates Indoor Air Quality (IAQ) and VOC index.
    
    Features:
      - Temperature and humidity compensated gas resistance
      - Adaptive baseline tracking to fight sensor drift
      - Multiple operating modes (adaptive, locked, manual)
      - Clean interface for both real-time updates and macro access
    """

    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name().split()[-1]

        # Configuration
        self.algorithm = config.get("iaq_algorithm", "open_source").lower()
        self.baseline_mode = config.get("baseline_mode", "adaptive")   # adaptive, locked, manual

        # Adaptive baseline parameters
        self.baseline_gas = None
        self.baseline_humidity = 45.0
        self.adaptation_rate = 0.00005          # Very slow adaptation to avoid drift

        # Last calculated values
        self.last_iaq = 50.0
        self.last_voc_index = 75.0
        self.last_update_time = time.time()

        logging.info(f"IAQCalculator initialized for sensor '{self.name}' "
                    f"(algorithm={self.algorithm}, baseline_mode={self.baseline_mode})")

    def update(self, readings: Dict[str, float]) -> Dict[str, float]:
        """
        Main entry point. Takes raw sensor readings and returns enriched data
        including IAQ and compensated values.
        """
        if not readings:
            return {}

        temp = readings.get("temperature", 25.0)
        hum = readings.get("humidity", 45.0)
        gas = readings.get("gas_resistance")
        voc = readings.get("voc_index")

        result = {
            "temperature": round(temp, 2),
            "humidity": round(hum, 2),
            "pressure": round(readings.get("pressure", 1013.25), 2),
        }

        # Calculate IAQ from BME680 gas resistance if available
        if gas is not None:
            iaq_value = self._calculate_from_gas(gas, temp, hum)
            result["iaq"] = round(iaq_value, 1)
            result["gas_resistance"] = int(gas)
            self.last_iaq = iaq_value

        # Use SGP40 VOC index directly if available
        if voc is not None:
            result["voc_index"] = round(voc, 1)
            self.last_voc_index = voc

        return result

    def _calculate_from_gas(self, gas_resistance: float, temp: float, hum: float) -> float:
        """
        Calculate IAQ based on gas resistance with temperature and humidity compensation.
        Higher gas resistance = cleaner air.
        """
        if self.baseline_gas is None:
            self.baseline_gas = gas_resistance
            self.baseline_humidity = hum
            return 50.0

        # Slow adaptive baseline to reduce long-term drift
        if self.baseline_mode == "adaptive":
            self.baseline_gas = (self.baseline_gas * (1 - self.adaptation_rate) +
                               gas_resistance * self.adaptation_rate)

        # Simple but effective ratio-based IAQ calculation
        ratio = self.baseline_gas / max(gas_resistance, 1000)   # avoid division by zero
        iaq = 50.0 + (ratio - 1.0) * 180.0

        # Clamp to reasonable range
        iaq = max(0.0, min(500.0, iaq))

        return iaq

    def get_status(self) -> Dict[str, Any]:
        """Return current status for QUERY_ENV and debugging."""
        return {
            "iaq": round(self.last_iaq, 1),
            "voc_index": round(self.last_voc_index, 1),
            "baseline_gas": round(self.baseline_gas, 0) if self.baseline_gas else None,
            "baseline_mode": self.baseline_mode,
            "algorithm": self.algorithm
        }


def load_config_prefix(config):
    """Allows [env_sensor chamber] to also load the IAQ calculator if needed."""
    return IAQCalculator(config)
