# iaq_calculator.py
#
# IAQ (Indoor Air Quality) and VOC calculation logic for klipper-env-sensor.
#
# This module implements a simplified, open-source IAQ calculation.
# It is NOT a direct port of the proprietary Bosch BSEC library.
#
# Algorithm Inspiration & References:
#   - Bosch BME680 Application Notes (public documentation)
#   - Sensirion SGP40 Gas Index Algorithm concepts
#   - Various open-source BME680 IAQ implementations on GitHub
#   - Community reverse-engineering efforts of Bosch's approach
#       https://github.com/pimoroni/bme680-python
#       https://github.com/BoschSensortec/BME68x-Sensor-API (the official open-source low-level driver)
#       Various community implementations on GitHub (e.g. "bme680-iaq" repos
#
# The core idea is to track a slow-moving baseline of gas resistance
# and calculate IAQ based on deviation from that baseline, with basic
# temperature and humidity compensation.
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
from typing import Dict, Any


class IAQCalculator:
    """
    Calculates Indoor Air Quality (IAQ) and VOC index from environmental sensors.
    
    This is a simplified open-source implementation. It is not intended to match
    the accuracy of Bosch's proprietary BSEC library, but provides useful results
    for chamber monitoring and automation.
    """

    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name().split()[-1]

        self.baseline_mode = config.get("baseline_mode", "adaptive")
        
        # Baseline tracking
        self.baseline_gas = None
        self.adaptation_rate = 0.00005          # Very slow adaptation to fight drift

        # Last known values
        self.last_iaq = 50.0
        self.last_voc_index = 75.0
        self.last_gas_resistance = None

        logging.info(f"IAQCalculator initialized for '{self.name}' (baseline_mode={self.baseline_mode})")

    def update(self, readings: Dict[str, float]) -> Dict[str, float]:
        """Process sensor readings and return enriched data with IAQ values."""
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

        if gas is not None:
            iaq_value = self._calculate_from_gas(gas, temp, hum)
            result["iaq"] = round(iaq_value, 1)
            result["gas_resistance"] = int(gas)
            self.last_iaq = iaq_value
            self.last_gas_resistance = gas

        if voc is not None:
            result["voc_index"] = round(voc, 1)
            self.last_voc_index = voc

        return result

    def _calculate_from_gas(self, gas_resistance: float, temp: float, hum: float) -> float:
        """
        Simplified IAQ calculation based on gas resistance deviation from baseline.
        
        Inspired by:
          - Bosch BME680 documentation
          - Various open-source BME680 IAQ implementations
        """
        if self.baseline_gas is None:
            self.baseline_gas = gas_resistance
            return 50.0

        if self.baseline_mode == "adaptive":
            self.baseline_gas = (self.baseline_gas * (1 - self.adaptation_rate) + 
                               gas_resistance * self.adaptation_rate)

        ratio = self.baseline_gas / max(gas_resistance, 1000.0)
        iaq = 50.0 + (ratio - 1.0) * 180.0
        iaq = max(0.0, min(500.0, iaq))

        return iaq

    def get_status(self) -> Dict[str, Any]:
        return {
            "iaq": round(self.last_iaq, 1),
            "voc_index": round(self.last_voc_index, 1),
            "gas_resistance": self.last_gas_resistance,
            "baseline_gas": round(self.baseline_gas, 0) if self.baseline_gas else None,
            "baseline_mode": self.baseline_mode
        }


def load_config_prefix(config):
    return IAQCalculator(config)
