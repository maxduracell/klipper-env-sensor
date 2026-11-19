# __init__.py
#
# This file makes the env_sensor directory a proper Python package.
# It allows the imports in env_sensor.py to work:
#     from . import sensor_drivers, iaq_calculator
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of klipper-env-sensor.
# Copyright (C) 2026  maxduracell

"""
klipper-env-sensor

A Klipper module for environmental sensors (BME680, BME280, SGP40, etc.).
"""

from .env_sensor import EnvSensor
from .sensor_drivers import create_sensor, BaseSensor
from .iaq_calculator import IAQCalculator

__version__ = "0.1.0"
__all__ = ["EnvSensor", "create_sensor", "BaseSensor", "IAQCalculator"]

# This allows `from . import env_sensor` to work cleanly
