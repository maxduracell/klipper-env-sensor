# __init__.py
#
# Main entrypoint for the Klipper Environmental Sensor Extension.
# Maps config sections to Python classes for startup registration.
#
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  maxduracell

"""
klipper-env-sensor
A Klipper module for environmental sensors (BME680, BME280, SGP40, etc.).
"""

from .env_sensor import EnvSensor, load_config
from .sensor_drivers import create_sensor, BaseSensor
from .iaq_calculator import IAQCalculator

__version__ = "0.1.0"
__all__ = ["EnvSensor", "load_config", "create_sensor", "BaseSensor", "IAQCalculator"]
