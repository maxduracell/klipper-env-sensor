# env_sensor.py
#
# Klipper Environment Sensor Module
# Supports BME680, BME280, SGP40, and future sensors.
#
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  maxduracell

from __future__ import annotations
import logging
from typing import Dict, Any, Optional

from . import sensor_drivers, iaq_calculator

class VirtualSensor:
    """
    Dynamically registers with Klipper's heaters module to display values
    cleanly in Mainsail and Fluidd without requiring config overrides.
    """
    def __init__(self, name: str, heaters):
        self.name = name
        self.temp = 0.0
        self.min_temp = 0.0
        self.max_temp = 100.0
        heaters.register_sensor(self)

    def get_name(self) -> str:
        return self.name

    def get_status(self, eventtime: float) -> Dict[str, Any]:
        return {
            "temperature": self.temp,
            "measured_min_temp": self.min_temp,
            "measured_max_temp": self.max_temp,
        }

    def get_temp(self) -> float:
        return self.temp


class EnvSensor:
    """
    Klipper Module for environmental data processing.
    Exposes metrics cleanly both to dashboards and GCode macros.
    """

    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name().split()[-1]   # e.g. "chamber"

        # Configuration Parameters
        self.sensor_type = config.get("sensor_type", "bme680").lower()
        self.i2c_mcu = config.get("i2c_mcu", "mcu")
        self.i2c_bus = config.get("i2c_bus", "i2c1a")
        self.i2c_address = config.getint("i2c_address", None, minval=0x08, maxval=0x77)

        self.sample_time = config.getfloat("sample_time", 3.0, above=0.5)
        self.enable_iaq = config.getboolean("enable_iaq", True)
        self.iaq_algorithm = config.get("iaq_algorithm", "open_source").lower()
        self.baseline_mode = config.get("baseline_mode", "adaptive")

        # Load hardware driver safely
        self.sensor = sensor_drivers.create_sensor(
            sensor_type=self.sensor_type,
            i2c_mcu=self.i2c_mcu,
            i2c_bus=self.i2c_bus,
            i2c_address=self.i2c_address,
            config=config
        )

        # Load IAQ module if requested
        self.iaq = iaq_calculator.IAQCalculator(config) if self.enable_iaq else None

        self.last_readings = {}
        self.virtual_sensors: Dict[str, VirtualSensor] = {}

        self.printer.register_event_handler("klippy:connect", self._on_connect)
        self.printer.register_event_handler("klippy:ready", self._on_ready)

        # Register standard QUERY_ENV macro command
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode.register_mux_command(
            "QUERY_ENV", "SENSOR", self.name,
            self.cmd_QUERY_ENV,
            desc=f"Query the {self.name} environmental sensor"
        )

        logging.info(f"EnvSensor '{self.name}' initialized")

    def _on_connect(self):
        try:
            self.sensor.initialize()
            self._register_virtual_sensors()
        except Exception as e:
            logging.exception(f"Failed to initialize hardware for '{self.name}'")
            raise

    def _register_virtual_sensors(self):
        """Dynamically register virtual sensors with Klipper's heaters module for dashboard display."""
        try:
            heaters = self.printer.lookup_object("heaters")
            self.virtual_sensors["temperature"] = VirtualSensor(f"{self.name}_temp", heaters)
            self.virtual_sensors["humidity"] = VirtualSensor(f"{self.name}_humidity", heaters)
            self.virtual_sensors["pressure"] = VirtualSensor(f"{self.name}_pressure", heaters)
            
            if self.enable_iaq:
                self.virtual_sensors["iaq"] = VirtualSensor(f"{self.name}_iaq", heaters)
        except Exception as e:
            logging.warning(f"Could not register virtual sensors for {self.name}: {e}")

    def _on_ready(self):
        reactor = self.printer.get_reactor()
        reactor.register_timer(self._sample_timer, reactor.monotonic() + 2.0)

    def _sample_timer(self, eventtime: float) -> float:
        """Non-blocking asynchronous polling loop."""
        try:
            raw_readings = self.sensor.read()
            if raw_readings is None:
                return eventtime + self.sample_time

            if self.iaq is not None:
                enriched = self.iaq.update(raw_readings)
            else:
                enriched = raw_readings.copy()

            self.last_readings = enriched
            self._update_virtual_sensors(enriched)
        except Exception as e:
            logging.exception(f"EnvSensor '{self.name}' execution error during sample")

        return eventtime + self.sample_time

    def _update_virtual_sensors(self, readings: Dict[str, float]):
        """Update the registered virtual sensors for dashboard display."""
        for key, value in readings.items():
            if key in self.virtual_sensors:
                self.virtual_sensors[key].temp = value

    def get_status(self, eventtime: float) -> Dict[str, Any]:
        """Exposes metrics cleanly to Jinja2 macros and standard Klipper APIs."""
        status = {
            "temperature": self.last_readings.get("temperature", 0.0),
            "humidity": self.last_readings.get("humidity", 0.0),
            "pressure": self.last_readings.get("pressure", 0.0),
        }
        if self.enable_iaq:
            status["iaq"] = self.last_readings.get("iaq", 50.0)
            status["gas_resistance"] = self.last_readings.get("gas_resistance", 0)
            status["voc_index"] = self.last_readings.get("voc_index", 0.0)
            # FIXED: Corrected baseline_gas lookup location safely
            status["baseline_gas"] = self.iaq.get_status().get("baseline_gas") if self.iaq else None
        return status

    def cmd_QUERY_ENV(self, gcmd):
        """Standard QUERY_ENV G-Code implementation."""
        try:
            if not self.last_readings:
                gcmd.respond_info(f"EnvSensor {self.name}: Collecting first sample...")
                return

            status = self.get_status(0.0)
            gcmd.respond_info(f"EnvSensor {self.name}: {status}")
        except Exception as e:
            gcmd.respond_info(f"Error querying {self.name}: {str(e)}")

    @property
    def temperature(self) -> float:
        return self.last_readings.get("temperature", 0.0)

    @property
    def humidity(self) -> float:
        return self.last_readings.get("humidity", 0.0)

    @property
    def pressure(self) -> float:
        return self.last_readings.get("pressure", 0.0)

    @property
    def iaq(self) -> float:
        return self.last_readings.get("iaq", 0.0)

    @property
    def gas_resistance(self) -> int:
        return self.last_readings.get("gas_resistance", 0)

    @property
    def voc_index(self) -> float:
        return self.last_readings.get("voc_index", 0.0)

    @property
    def baseline_gas(self) -> Optional[float]:
        if self.iaq:
            return self.iaq.get_status().get("baseline_gas")
        return None

def load_config(config):
    return EnvSensor(config)
