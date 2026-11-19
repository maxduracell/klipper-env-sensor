# env_sensor.py
#
# Klipper Environment Sensor Module
# Supports: BME680, BME280, SGP40, and future sensors
# Provides clean readings, IAQ/VOC calculation, virtual sensors for Mainsail,
# persistent calibration, and macro-friendly values for chamber automation.
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of klipper-env-sensor.
# Copyright (C) 2026  [Your GitHub Username]
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

from __future__ import annotations
import logging
from typing import Dict, Any

from . import sensor_drivers, iaq_calculator


class EnvSensor:
    """
    Main Klipper module for environmental sensing.
    
    This class handles:
      - Loading the appropriate sensor driver
      - Creating virtual temperature sensors for Mainsail
      - Periodic sampling
      - IAQ/VOC calculation
      - Exposing data for macros and automation
    """

    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name().split()[-1]   # e.g. "chamber", "enclosure"

        # === Configuration Options ===
        self.sensor_type = config.get("sensor_type", "bme680").lower()
        self.i2c_mcu = config.get("i2c_mcu", "mcu")
        self.i2c_bus = config.get("i2c_bus", "i2c1a")
        self.i2c_address = config.getint("i2c_address", None, minval=0x08, maxval=0x77)
        
        self.sample_time = config.getfloat("sample_time", 3.0, above=0.5)
        self.iaq_algorithm = config.get("iaq_algorithm", "open_source").lower()
        self.enable_iaq = config.getboolean("enable_iaq", True)

        # === Load Sensor Driver ===
        self.sensor = sensor_drivers.create_sensor(
            sensor_type=self.sensor_type,
            i2c_mcu=self.i2c_mcu,
            i2c_bus=self.i2c_bus,
            i2c_address=self.i2c_address,
            config=config
        )

        # === Virtual Sensors for Mainsail UI ===
        self.printer.load_object(config, f"temperature_sensor {self.name}_temp")
        self.printer.load_object(config, f"temperature_sensor {self.name}_humidity")
        self.printer.load_object(config, f"temperature_sensor {self.name}_pressure")

        if self.enable_iaq:
            self.printer.load_object(config, f"temperature_sensor {self.name}_iaq")

        # Register events
        self.printer.register_event_handler("klippy:connect", self._on_connect)
        self.printer.register_event_handler("klippy:ready", self._on_ready)

        # GCode commands
        self.gcode = self.printer.lookup_object("gcode")
        self.gcode.register_mux_command(
            "QUERY_ENV", "SENSOR", self.name,
            self.cmd_QUERY_ENV,
            desc=f"Query the {self.name} environmental sensor"
        )

    def _on_connect(self):
        """Called once all MCUs are connected."""
        self.sensor.initialize()

    def _on_ready(self):
        """Called when the printer is fully ready."""
        reactor = self.printer.get_reactor()
        reactor.register_timer(self._sample_timer, reactor.monotonic() + 2.0)

    def _sample_timer(self, eventtime: float) -> float:
        """Main periodic sampling function."""
        try:
            readings = self.sensor.read()

            if readings is None:
                return eventtime + self.sample_time

            # Update virtual sensors (visible in Mainsail)
            self._update_virtual_sensors(readings)

            # Optional: Log to console (can be disabled in production)
            # logging.info(f"EnvSensor '{self.name}': {readings}")

        except Exception as e:
            logging.exception(f"EnvSensor '{self.name}' sampling error")

        return eventtime + self.sample_time

    def _update_virtual_sensors(self, readings: Dict[str, float]):
        """Update all virtual temperature sensors for Mainsail display."""
        # These will appear in the temperature graph and sensor list
        self.printer.lookup_object(f"temperature_sensor {self.name}_temp").sensor.update_temp(
            readings.get("temperature", 0.0)
        )
        # TODO: Add humidity, pressure, and IAQ virtual sensors

    def cmd_QUERY_ENV(self, gcmd):
        """GCode command: QUERY_ENV SENSOR=chamber"""
        try:
            data = self.sensor.read()
            gcmd.respond_info(f"EnvSensor {self.name}: {data}")
        except Exception as e:
            gcmd.respond_info(f"Error querying {self.name}: {str(e)}")


def load_config(config):
    """This is the entry point called by Klipper when it sees [env_sensor]"""
    return EnvSensor(config)
