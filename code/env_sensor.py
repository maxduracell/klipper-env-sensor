# klipper-env-sensor/env_sensor.py
#
# Klipper module for environmental sensors (BME680, BME280, SGP40, etc.)
# Provides clean sensor readings, IAQ/VOC calculation, virtual sensors for Mainsail,
# and exposes values for macro automation (chamber control, filter fans, etc.)
#
# Author: Grok (with user input)
# Compatible with: Stock Klipper and Kalico

from __future__ import annotations
import logging
from . import sensor_drivers, iaq

class EnvSensor:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name().split()[-1]  # e.g. "chamber"

        # === Configuration ===
        self.sensor_type = config.get("sensor_type", "bme680").lower()
        self.i2c_mcu = config.get("i2c_mcu", "mcu")
        self.i2c_bus = config.get("i2c_bus", "i2c1a")
        self.i2c_address = config.getint("i2c_address", None, minval=0, maxval=0x7f)
        
        self.sample_time = config.getfloat("sample_time", 3.0, minval=1.0)
        self.iaq_algorithm = config.get("iaq_algorithm", "open_source")

        # === Sensor Driver ===
        self.sensor = sensor_drivers.create_sensor(
            self.sensor_type, 
            self.i2c_mcu, 
            self.i2c_bus, 
            self.i2c_address,
            config
        )

        # === Register with Klipper ===
        self.printer.register_event_handler("klippy:connect", self._handle_connect)
        self.printer.register_event_handler("klippy:ready", self._handle_ready)

        # Create virtual temperature sensors so they show up nicely in Mainsail
        self.temp_sensor = self.printer.load_object(config, "temperature_sensor " + self.name)
        # We will update this sensor with our readings

        # Register GCode commands
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode.register_mux_command(
            "QUERY_ENV", "SENSOR", self.name, self.cmd_QUERY_ENV,
            desc="Query environmental sensor readings")

    def _handle_connect(self):
        """Called when Klipper connects to all MCUs"""
        self.sensor.setup()

    def _handle_ready(self):
        """Called when printer is ready"""
        reactor = self.printer.get_reactor()
        reactor.register_timer(self._sample_timer, reactor.monotonic() + 1.0)

    def _sample_timer(self, eventtime):
        """Main sampling loop"""
        try:
            data = self.sensor.read()
            
            if data is None:
                return eventtime + self.sample_time

            # Update virtual temperature sensor (shows in Mainsail)
            self.temp_sensor.sensor.update_temp(data.get("temperature", 0.0))

            # TODO: Update other virtual sensors (humidity, pressure, iaq, etc.)
            # TODO: Run IAQ calculation from iaq.py

            logging.info(f"EnvSensor {self.name}: {data}")

        except Exception as e:
            logging.exception(f"Error reading {self.name} sensor: {e}")

        return eventtime + self.sample_time

    def cmd_QUERY_ENV(self, gcmd):
        """GCode command: QUERY_ENV SENSOR=chamber"""
        try:
            data = self.sensor.read()
            gcmd.respond_info(f"EnvSensor {self.name}: {data}")
        except Exception as e:
            gcmd.respond_info(f"Error reading sensor: {e}")


def load_config(config):
    """Klipper entry point"""
    return EnvSensor(config)
