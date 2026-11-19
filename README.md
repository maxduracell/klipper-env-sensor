# klipper-env-sensor

***WARNING*** This is untested. Use at your own risk.

A Klipper extras module for environmental monitoring using BME680, BME280, SGP40, and similar sensors.

This module provides clean temperature, humidity, pressure, and air quality (IAQ/VOC) readings that appear in Mainsail/Fluidd, while also exposing the values for use in macros and chamber automation.

**Repository:** https://github.com/maxduracell/klipper-env-sensor

---

# Features

- Support for **BME680**, **BME280**, and **SGP40**
- Virtual sensors that appear cleanly in Mainsail and Fluidd
- Open-source IAQ / VOC calculation with adaptive baseline tracking to reduce sensor drift
- Easy-to-use values in macros for chamber automation
- Works with both stock Klipper and Kalico
- Supports sensors on the main MCU or a dedicated RP2040/Pico

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
ln -s ~/klipper-env-sensor ~/klipper/klippy/extras/env_sensor
```
3. Restart Klipper:

```bash
sudo systemctl restart klipper
```
4. Add the [env_sensor ...] section to your printer.cfg (see config_example.cfg for examples).
   
Configuration
Add a section like this to your printer.cfg:

```
[env_sensor chamber]
sensor_type: bme680
i2c_mcu: mcu
i2c_bus: i2c1a
i2c_address: 118
sample_time: 3.0
iaq_algorithm: open_source
baseline_mode: adaptive
```
Configuration Examples
See config_example.cfg for recommended configurations, including:

BME680 on Octopus I2C
BME680 on RP2040/Pico (recommended for flexible sensor placement)
BME280 + SGP40 combination

Available Values in Macros
You can access the following values in macros:

```
{printer["env_sensor chamber"].temperature}
{printer["env_sensor chamber"].humidity}
{printer["env_sensor chamber"].pressure}
{printer["env_sensor chamber"].iaq}
{printer["env_sensor chamber"].gas_resistance}
{printer["env_sensor chamber"].voc_index}
{printer["env_sensor chamber"].baseline_gas}
```

Example macro:

```
[gcode_macro REPORT_AIR_QUALITY]
gcode:
    {% set iaq = printer["env_sensor chamber"].iaq|float %}
    {% set temp = printer["env_sensor chamber"].temperature|float %}
    {% set hum = printer["env_sensor chamber"].humidity|float %}
    RESPOND TYPE=command MSG="Chamber IAQ: {iaq:.1f} | Temp: {temp:.1f}°C | Humidity: {hum:.1f}%"
```

Moonraker Update Manager
Add this to your moonraker.conf to enable easy updates from Mainsail:

```
[update_manager klipper-env-sensor]
type: git_repo
path: ~/klipper-env-sensor
origin: https://github.com/maxduracell/klipper-env-sensor.git
primary_branch: main
managed_services: klipper
```

Development Notes & Transparency:  
This module was developed collaboratively.

Primary author / project lead: maxduracell  
Development assistance: Grok (xAI)

The architecture, feature set, sensor support decisions, and overall design were directed by the human author. Grok was used as a coding and design assistant to accelerate development, generate well-structured code, and help with documentation. All code has been reviewed and refined with the goal of creating a clean, maintainable, and useful Klipper module.
This transparency note is included because some members of the community prefer to know when AI tools were involved in a project’s creation.

License
This project is licensed under the GNU General Public License v3.0 or later.
See the LICENSE file for full details
