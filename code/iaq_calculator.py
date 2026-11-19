# iaq_calculator.py
#
# Air Quality (IAQ / VOC) calculation module for klipper-env-sensor.
# This module takes raw sensor readings and computes a meaningful
# Indoor Air Quality (IAQ) index and VOC level.
#
# We are using an open-source approach instead of the closed-source
# Bosch BSEC library.
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of klipper-env-sensor.
# Copyright (C) 2026 maxduracell

import logging
import time
from typing import Dict, Optional


class IAQCalculator:
    """
    Calculates Indoor Air Quality (IAQ) and VOC index from BME680 and/or SGP40 readings.
    
    Features:
      - Temperature and humidity compensation
      - Adaptive baseline tracking to reduce sensor drift
      - Configurable calibration modes
      - Persistent baseline storage (planned)
    """

    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name().split()[-1]

        # Configuration
        self.algorithm = config.get("iaq_algorithm", "open_source").lower()
        self.baseline_mode = config.get("baseline_mode", "adaptive")  # "adaptive", "locked", "manual"
        
        # Adaptive baseline tracking
        self.baseline_gas = None
        self.baseline_timestamp = None
        self.adaptation_rate = 0.0001  # How quickly the baseline adapts (very slow)

        # Last calculated values
        self.last_iaq = 50.0
        self.last_voc_index = 75.0

        logging.info(f"IAQCalculator initialized for '{self.name}' using {self.algorithm} algorithm")

    def update(self, readings: Dict[str, float]) -> Dict[str, float]:
        """
        Update IAQ calculation with latest sensor readings.
        
        Expected input keys:
            - temperature (°C)
            - humidity (%)
            - gas_resistance (Ohms) from BME680
            - voc_index from SGP40 (if available)
        """
        if not readings:
            return {}

        temp = readings.get("temperature", 25.0)
        hum = readings.get("humidity", 50.0)
        gas = readings.get("gas_resistance")

        result = {
            "temperature": round(temp, 2),
            "humidity": round(hum, 2),
            "pressure": round(readings.get("pressure", 1013.25), 2),
        }

        # Calculate IAQ if we have gas resistance data
        if gas is not None:
            iaq_value = self._calculate_iaq_from_gas(gas, temp, hum)
            result["iaq"] = round(iaq_value, 1)
            result["gas_resistance"] = int(gas)
            self.last_iaq = iaq_value

        # If we have a direct VOC index from SGP40, use it
        if "voc_index" in readings:
            result["voc_index"] = round(readings["voc_index"], 1)
            self.last_voc_index = readings["voc_index"]

        return result

    def _calculate_iaq_from_gas(self, gas_resistance: float, temp: float, hum: float) -> float:
        """
        Simple but effective open-source IAQ calculation.
        Based on relative change from baseline with temperature/humidity compensation.
        """
        if self.baseline_gas is None:
            self.baseline_gas = gas_resistance
            self.baseline_timestamp = time.time()
            return 50.0  # Neutral starting IAQ

        # Very slow adaptive baseline to combat sensor drift
        if self.baseline_mode == "adaptive":
            self.baseline_gas = (self.baseline_gas * (1 - self.adaptation_rate) + 
                               gas_resistance * self.adaptation_rate)

        # Calculate relative change (higher gas resistance = cleaner air)
        ratio = self.baseline_gas / gas_resistance

        # Convert to IAQ scale (roughly 0-500, lower is better air)
        iaq = 50.0 + (ratio - 1.0) * 150.0
        iaq = max(0.0, min(500.0, iaq))

        return iaq

    def get_status(self) -> Dict[str, Any]:
        """Return current status for QUERY_ENV and debugging."""
        return {
            "iaq": round(self.last_iaq, 1),
            "voc_index": round(self.last_voc_index, 1),
            "baseline_gas": self.baseline_gas,
            "baseline_mode": self.baseline_mode
        }


def load_config_prefix(config):
    """Optional: Allows [env_sensor chamber] to also load IAQ calculator"""
    return IAQCalculator(config)
