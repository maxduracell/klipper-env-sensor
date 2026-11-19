# klipper-env-sensor

A Klipper extras module for environmental monitoring using BME680, BME280, SGP40, and similar sensors.

This module provides clean temperature, humidity, pressure, and air quality (IAQ/VOC) readings that appear in Mainsail/Fluidd, while also exposing the values for use in macros and chamber automation.

**Repository:** https://github.com/maxduracell/klipper-env-sensor

---

## Features

- Support for **BME680**, **BME280**, and **SGP40**
- Virtual temperature sensors that appear cleanly in Mainsail/Fluidd
- Open-source IAQ / VOC calculation with adaptive baseline (helps reduce sensor drift)
- Values easily accessible from macros for chamber automation
- Works with both stock Klipper and Kalico
- Can run on the main MCU (e.g. Octopus) or a dedicated RP2040/Pico
- Moonraker update manager support

---

## Supported Sensors

| Sensor   | Temperature | Humidity | Pressure | Gas / VOC | Notes                  |
|----------|-------------|----------|----------|-----------|------------------------|
| BME680   | ✓           | ✓        | ✓        | ✓         | Primary target sensor  |
| BME280   | ✓           | ✓        | ✓        | ✗         | Excellent basic sensor |
| SGP40    | ✗           | ✗        | ✗        | ✓         | Dedicated VOC sensor   |

---

## Installation

1. Clone the repository:

```bash
cd ~
git clone https://github.com/maxduracell/klipper-env-sensor.git
```
2. Create a symbolic link into your Klipper extras directory:

```bash
ln -s ~/klipper-env-sensor/env_sensor.py ~/klipper/klippy/extras/env_sensor.py
```
3.Restart Klipper:

```bas
hsudo systemctl restart klipper
```
Configuration
Add a section like this to your printer.cfg:

[env_sensor chamber]
sensor_type: bme680
i2c_mcu: mcu
i2c_bus: i2c1a
i2c_address: 118
sample_time: 3.0
iaq_algorithm: open_source
baseline_mode: adaptive

See config_example.cfg for more examples (including RP2040 and BME280 + SGP40 combinations).
