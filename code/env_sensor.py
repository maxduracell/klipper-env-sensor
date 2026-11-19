# env_sensor.py
#
# Klipper Environment Sensor Module
# Supports BME680, BME280, SGP40, and future sensors.
#
# Provides:
#   - Virtual sensors visible in Mainsail/Fluidd
#   - IAQ / VOC calculation with drift compensation
#   - Values easily accessible in macros
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
        printer["env_sensor <name>"].temperature
        printer["env_sensor <name>"].humidity
        printer["env_sensor <name>"].pressure
        printer["env_sensor <name>"].iaq
        printer["env_sensor <name>"].gas_resistance
        printer["env_sensor <name>"].voc_index
    """

    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name().split()[-1]   # e.g. "chamber"

        # Configuration
        self.sensor_type = config.get("sensor_type", "bme680").lower()
        self.i2c_mcu = config.get("i2c_mcu", "mcu")
        self.i2c_bus = config.get("i2c_bus", "i2c1a")
        self.i2c_address = config.getint("i2c_address", None, minval=0x08, maxval=0x77)

        self.sample_time = config.getfloat("sample_time", 3.0, above=0.5)
        self.enable_iaq = config.getboolean("enable_iaq", True)
        self.iaq_algorithm = config.get("iaq_algorithm", "open_source").lower()
        self.baseline_mode = config.get("baseline_mode", "adaptive")

        # Load the sensor driver
        self.sensor = sensor_drivers.create_sensor(
            sensor_type=self.sensor_type,
            i2c_mcu=self.i2c_mcu,
            i2c_bus=self.i2c_bus,
            i2c_address=self.i2c_address,
            config=config
        )

        # Load IAQ calculator if enabled
        self.iaq = iaq_calculator.IAQCalculator(config) if self.enable_iaq else None

        # Register virtual sensors for Mainsail
        self._register_virtual_sensors(config)

        self.printer.register_event_handler("klippy:connect", self._on_connect)
        self.printer.register_event_handler("klippy:ready", self._on_ready)

        self.gcode = self.printer.lookup_object('gcode')
        self.gcode.register_mux_command(
            "QUERY_ENV", "SENSOR", self.name,
            self.cmd_QUERY_ENV,
            desc=f"Query the {self.name} environmental sensor"
        )

    def _register_virtual_sensors(self, config):
        """Create virtual sensors visible in Mainsail."""
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
        try:
            readings = self.sensor.read()
            if readings is None:
                return eventtime + self.sample_time

            enriched = self.iaq.update(readings) if self.iaq else readings

            # Update virtual sensors
            self.printer.lookup_object(f"temperature_sensor {self.name}_temp").sensor.update_temp(
                enriched.get("temperature", 0.0)
            )

        except Exception as e:
            logging.exception(f"EnvSensor '{self.name}' error")

        return eventtime + self.sample_time

    def cmd_QUERY_ENV(self, gcmd):
        """QUERY_ENV SENSOR=chamber"""
        try:
            data = self.sensor.read()
            enriched = self.iaq.update(data) if self.iaq else data
            gcmd.respond_info(f"EnvSensor {self.name}: {enriched}")
        except Exception as e:
            gcmd.respond_info(f"Error: {e}")


def load_config(config):
    return EnvSensor(config)
