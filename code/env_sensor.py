# env_sensor.py
#
# Klipper Environment Sensor Module
# Supports BME680, BME280, SGP40, and future sensors.
#
# Features:
#   - Virtual sensors visible in Mainsail/Fluidd
#   - IAQ / VOC calculation with drift compensation
#   - Clean macro interface for chamber automation
#   - Support for multiple MCUs (Octopus I2C, RP2040, etc.)
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

from __future__ import annotations
import logging
from typing import Dict, Any

from . import sensor_drivers, iaq_calculator


class EnvSensor:
    """
    Main Klipper module for environmental sensors.
    
    Values available in macros:
        printer["env_sensor chamber"].temperature
        printer["env_sensor chamber"].humidity
        printer["env_sensor chamber"].pressure
        printer["env_sensor chamber"].iaq
        printer["env_sensor chamber"].gas_resistance
        printer["env_sensor chamber"].voc_index
        printer["env_sensor chamber"].baseline_gas
    """

    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name().split()[-1]   # e.g. "chamber"

        # ==================== Configuration ====================
        self.sensor_type = config.get("sensor_type", "bme680").lower()
        self.i2c_mcu = config.get("i2c_mcu", "mcu")
        self.i2c_bus = config.get("i2c_bus", "i2c1a")
        self.i2c_address = config.getint("i2c_address", None, minval=0x08, maxval=0x77)

        self.sample_time = config.getfloat("sample_time", 3.0, above=0.5)
        self.enable_iaq = config.getboolean("enable_iaq", True)
        self.iaq_algorithm = config.get("iaq_algorithm", "open_source").lower()
        self.baseline_mode = config.get("baseline_mode", "adaptive")

        # Load hardware driver
        self.sensor = sensor_drivers.create_sensor(
            sensor_type=self.sensor_type,
            i2c_mcu=self.i2c_mcu,
            i2c_bus=self.i2c_bus,
            i2c_address=self.i2c_address,
            config=config
        )

        # Load IAQ calculator if enabled
        self.iaq = iaq_calculator.IAQCalculator(config) if self.enable_iaq else None

        # Store latest readings for macro access
        self.last_readings = {}

        # Register virtual sensors for Mainsail/Fluidd
        self._register_virtual_sensors(config)

        self.printer.register_event_handler("klippy:connect", self._on_connect)
        self.printer.register_event_handler("klippy:ready", self._on_ready)

        self.gcode = self.printer.lookup_object('gcode')
        self.gcode.register_mux_command(
            "QUERY_ENV", "SENSOR", self.name,
            self.cmd_QUERY_ENV,
            desc=f"Query the {self.name} environmental sensor"
        )

        logging.info(f"EnvSensor '{self.name}' initialized (type: {self.sensor_type})")

    def _register_virtual_sensors(self, config):
        """Create virtual sensors so they appear in Mainsail."""
        self.printer.load_object(config, f"temperature_sensor {self.name}_temp")
        self.printer.load_object(config, f"temperature_sensor {self.name}_humidity")
        self.printer.load_object(config, f"temperature_sensor {self.name}_pressure")

        if self.enable_iaq:
            self.printer.load_object(config, f"temperature_sensor {self.name}_iaq")

    def _on_connect(self):
        self.sensor.initialize()

    def _on_ready(self):
        reactor = self.printer.get_reactor()
        reactor.register_timer(self._sample_timer, reactor.monotonic() + 2.0)

    def _sample_timer(self, eventtime: float) -> float:
        """Main sampling loop."""
        try:
            raw_readings = self.sensor.read()
            if raw_readings is None:
                return eventtime + self.sample_time

            # Enrich readings with IAQ calculation if enabled
            if self.iaq is not None:
                enriched = self.iaq.update(raw_readings)
            else:
                enriched = raw_readings.copy()

            self.last_readings = enriched
            self._update_virtual_sensors(enriched)

        except Exception as e:
            logging.exception(f"EnvSensor '{self.name}' sampling error")

        return eventtime + self.sample_time

    def _update_virtual_sensors(self, readings: Dict[str, float]):
        """Update virtual sensors for Mainsail display."""
        try:
            self.printer.lookup_object(f"temperature_sensor {self.name}_temp").sensor.update_temp(
                readings.get("temperature", 0.0)
            )
            self.printer.lookup_object(f"temperature_sensor {self.name}_humidity").sensor.update_temp(
                readings.get("humidity", 0.0)
            )
            self.printer.lookup_object(f"temperature_sensor {self.name}_pressure").sensor.update_temp(
                readings.get("pressure", 0.0)
            )

            if self.enable_iaq and "iaq" in readings:
                self.printer.lookup_object(f"temperature_sensor {self.name}_iaq").sensor.update_temp(
                    readings.get("iaq", 0.0)
                )
        except Exception as e:
            logging.exception(f"Failed to update virtual sensors for {self.name}")

    def cmd_QUERY_ENV(self, gcmd):
        """GCode command: QUERY_ENV SENSOR=chamber"""
        try:
            if not self.last_readings:
                gcmd.respond_info(f"EnvSensor {self.name}: No data available yet")
                return

            status = self.iaq.get_status() if self.iaq else {}
            combined = {**self.last_readings, **status}
            gcmd.respond_info(f"EnvSensor {self.name}: {combined}")
        except Exception as e:
            gcmd.respond_info(f"Error querying {self.name}: {str(e)}")

    # ==========================================================
    # Properties for easy macro access
    # ==========================================================
    @property
    def temperature(self):
        return self.last_readings.get("temperature", 0.0)

    @property
    def humidity(self):
        return self.last_readings.get("humidity", 0.0)

    @property
    def pressure(self):
        return self.last_readings.get("pressure", 0.0)

    @property
    def iaq(self):
        return self.last_readings.get("iaq", 0.0)

    @property
    def gas_resistance(self):
        return self.last_readings.get("gas_resistance", 0)

    @property
    def voc_index(self):
        return self.last_readings.get("voc_index", 0.0)

    @property
    def baseline_gas(self):
        if self.iaq:
            return self.iaq.get_status().get("baseline_gas")
        return None


def load_config(config):
    """Klipper entry point - required"""
    return EnvSensor(config)
