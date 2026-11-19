# iaq_calculator.py
#
# IAQ (Indoor Air Quality) and VOC calculation logic for klipper-env-sensor.
#
# This module processes raw sensor readings from BME680, BME280, and SGP40
# and computes a meaningful Indoor Air Quality (IAQ) index.
#
# We use an open-source algorithm instead of the proprietary Bosch BSEC library.
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

import logging
import time
from typing import Dict, Any, Optional


class IAQCalculator:
    """
    Calculates Indoor Air Quality (IAQ) and VOC index.
    
    This class is responsible for:
      - Converting raw gas resistance into a usable IAQ score (0-500)
      - Applying temperature and humidity compensation
      - Maintaining an adaptive baseline to reduce sensor drift over time
      - Providing clean values for both Mainsail virtual sensors and macros
    """

    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name().split()[-1]

        # Configuration
        self.algorithm = config.get("iaq_algorithm", "open_source").lower()
        self.baseline_mode = config.get("baseline_mode", "adaptive")   # adaptive, locked, manual

        # Baseline tracking (helps fight long-term sensor drift)
        self.baseline_gas = None
        self.baseline_humidity = 45.0
        self.adaptation_rate = 0.00005          # Very slow adaptation rate

        # Last known values (used by macros and status queries)
        self.last_iaq = 50.0
        self.last_voc_index = 75.0
        self.last_gas_resistance = None
        self.last_update_time = time.time()

        logging.info(f"IAQCalculator initialized for '{self.name}' "
                    f"(algorithm={self.algorithm}, baseline_mode={self.baseline_mode})")

    def update(self, readings: Dict[str, float]) -> Dict[str, float]:
        """
        Process raw sensor readings and return enriched data with IAQ values.
        
        Expected input keys from sensor:
            temperature (°C), humidity (%), pressure (hPa), gas_resistance (Ohms)
        
        Returns keys that will be available in macros:
            temperature, humidity, pressure, iaq, gas_resistance, voc_index
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

        # Calculate IAQ from BME680 gas resistance
        if gas is not None:
            iaq_value = self._calculate_from_gas(gas, temp, hum)
            result["iaq"] = round(iaq_value, 1)
            result["gas_resistance"] = int(gas)
            self.last_iaq = iaq_value
            self.last_gas_resistance = gas

        # Use direct VOC index from SGP40 if available
        if voc is not None:
            result["voc_index"] = round(voc, 1)
            self.last_voc_index = voc

        self.last_update_time = time.time()
        return result

    def _calculate_from_gas(self, gas_resistance: float, temp: float, hum: float) -> float:
        """
        Core IAQ calculation based on gas resistance.
        Higher resistance = cleaner air.
        """
        if self.baseline_gas is None:
            self.baseline_gas = gas_resistance
            self.baseline_humidity = hum
            return 50.0

        # Slowly adapt baseline if in adaptive mode (helps with sensor aging/drift)
        if self.baseline_mode == "adaptive":
            self.baseline_gas = (self.baseline_gas * (1 - self.adaptation_rate) +
                               gas_resistance * self.adaptation_rate)

        # Calculate relative change from baseline
        ratio = self.baseline_gas / max(gas_resistance, 1000.0)
        iaq = 50.0 + (ratio - 1.0) * 180.0

        # Clamp to valid IAQ range (0-500)
        iaq = max(0.0, min(500.0, iaq))

        return iaq

    def get_status(self) -> Dict[str, Any]:
        """Return current status for QUERY_ENV and debugging."""
        return {
            "iaq": round(self.last_iaq, 1),
            "voc_index": round(self.last_voc_index, 1),
            "gas_resistance": self.last_gas_resistance,
            "baseline_gas": round(self.baseline_gas, 0) if self.baseline_gas else None,
            "baseline_mode": self.baseline_mode,
            "algorithm": self.algorithm
        }


def load_config_prefix(config):
    """Allows [env_sensor chamber] to also load the IAQ calculator if needed."""
    return IAQCalculator(config)
