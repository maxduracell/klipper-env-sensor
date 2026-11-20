# iaq_calculator.py
#
# IAQ (Indoor Air Quality) and VOC calculation logic for klipper-env-sensor.
#
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  maxduracell

import logging
from typing import Dict, Any

class IAQCalculator:
    """
    Calculates Indoor Air Quality (IAQ) and VOC index from environmental sensors.
    """

    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name().split()[-1]

        self.baseline_mode = config.get("baseline_mode", "adaptive")
        
        # Baseline tracking (helps fight long-term sensor drift)
        self.baseline_gas = None
        self.adaptation_rate = 0.00005          # Very slow adaptation to fight drift

        # Last known values (for macros and status queries)
        self.last_iaq = 50.0
        self.last_voc_index = 75.0
        self.last_gas_resistance = None

        logging.info(f"IAQCalculator initialized for '{self.name}' "
                    f"(baseline_mode={self.baseline_mode})")

    def update(self, readings: Dict[str, float]) -> Dict[str, float]:
        """Takes raw sensor readings and returns enriched data with IAQ and VOC values."""
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
        Bosch-style IAQ calculation with 25% humidity and 75% gas resistance weightings.
        This resolves the dead temperature/humidity parameter issues.
        """
        if self.baseline_gas is None:
            self.baseline_gas = gas_resistance
            return 50.0

        if self.baseline_mode == "adaptive":
            self.baseline_gas = (self.baseline_gas * (1 - self.adaptation_rate) +
                                 gas_resistance * self.adaptation_rate)

        # 1. Humidity score (25% weight, ideal target is 40.0% RH)
        hum_weight = 0.25
        hum_reference = 40.0
        if hum > hum_reference:
            hum_score = ((100.0 - hum) / (100.0 - hum_reference)) * hum_weight
        else:
            hum_score = (hum / hum_reference) * hum_weight
        hum_score = max(0.0, min(hum_weight, hum_score))

        # 2. Gas score (75% weight)
        gas_weight = 0.75
        gas_score = (gas_resistance / self.baseline_gas) * gas_weight
        gas_score = max(0.0, min(gas_weight, gas_score))

        # 3. Total score (where 1.0 is pristine, 0.0 is completely contaminated)
        total_score = hum_score + gas_score

        # 4. Scale to standard IAQ index (0 to 500)
        iaq = (1.0 - total_score) * 500.0
        return max(0.0, min(500.0, iaq))

    def get_status(self) -> Dict[str, Any]:
        """Return current status for QUERY_ENV and debugging."""
        return {
            "iaq": round(self.last_iaq, 1),
            "voc_index": round(self.last_voc_index, 1),
            "gas_resistance": self.last_gas_resistance,
            "baseline_gas": round(self.baseline_gas, 0) if self.baseline_gas else None,
            "baseline_mode": self.baseline_mode
        }


def load_config_prefix(config):
    return IAQCalculator(config)
