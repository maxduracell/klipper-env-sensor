# klipper-env-sensor

***WARNING*** This is untested. Use at your own risk.

A Klipper extras module for environmental monitoring using BME680, BME280, SGP40, and similar sensors.

This module provides clean temperature, humidity, pressure, and air quality (IAQ/VOC) readings that appear in Mainsail/Fluidd, while also exposing the values for use in macros and chamber automation.

---

# Features

- Support for **BME680**, **BME280**, and **SGP40**
- Virtual sensors that appear cleanly in Mainsail and Fluidd
- Open-source IAQ / VOC calculation with adaptive baseline tracking to reduce sensor drift
- Easy-to-use values in macros for chamber automation
- Works with both stock Klipper and Kalico
- Supports sensors on the main MCU or a dedicated RP2040/Pico

---

# Supported Sensors

| Sensor   | Temperature | Humidity | Pressure | Gas / VOC | Notes                  |
|----------|-------------|----------|----------|-----------|------------------------|
| BME680   | ✓           | ✓        | ✓        | ✓        | Primary target sensor  |
| BME280   | ✓           | ✓        | ✓        | ✗        | Excellent basic sensor |
| SGP40    | ✗           | ✗        | ✗        | ✓        | Dedicated VOC sensor   |

---

# 💾 Installation

```bash
cd ~
git clone https://github.com/maxduracell/klipper-env-sensor.git

ln -s ~/klipper-env-sensor ~/klipper/klippy/extras/env_sensor

sudo systemctl restart klipper
```

   
## Configuration
Add a section like this to your printer.cfg:

```
[env_sensor chamber]
sensor_type: bme680
i2c_mcu: mcu
i2c_bus: i2c1a                    # Octopus v1.1 common I2C bus (PB8=SDA, PB9=SCL)
i2c_address: 118                  # Most BME680 modules are 0x76 = 118. Some are 0x77 = 119.
sample_time: 3.0
enable_iaq: True                  # Set to False to disable IAQ calculations
iaq_algorithm: open_source
baseline_mode: adaptive           # "adaptive" = slowly corrects sensor drift (recommended, "locked" = uses fixed baseline for more stability
baseline_file: ~/printer_data/config/.env_sensor_baselines.json
warmup_duration: 20        # in minutes - time to build a reliable initial baseline
save_interval: 30          # in minutes - how often to persist the baseline
```

Then add these macros and run your initial baseline.

```
[gcode_macro BUILD_IAQ_BASELINE]
description: Run sensor for the configured warm-up period to create a solid initial IAQ baseline
gcode:
    {% set sensor_name = params.SENSOR|default("chamber") %}
    {% set config_sec = 'env_sensor ' ~ sensor_name %}
    {% set warmup_min = printer.configfile.settings[config_sec].warmup_duration|default(20)|int %}
    {% set warmup_sec = warmup_min * 60 %}
    {% set warmup_complete = printer[config_sec].warmup_complete|default(false) %}

    RESPOND TYPE=echo MSG="=== Starting IAQ Baseline Build for {sensor_name} ==="
    RESPOND TYPE=echo MSG="Warm-up duration: {warmup_min} minutes ({warmup_sec} seconds)"

    {% if warmup_complete %}
        RESPOND TYPE=echo MSG="Note: Warm-up already completed (baseline restored from persistent file)."
    {% else %}
        RESPOND TYPE=echo MSG="Running warm-up now. Do not turn off the printer."
    {% endif %}

    # Schedule completion notification after the calculated seconds elapse
    UPDATE_DELAYED_GCODE DELAYED_GCODE=iaq_baseline_done DURATION={warmup_sec}

[delayed_gcode iaq_baseline_done]
gcode:
    RESPOND TYPE=echo MSG="=== IAQ Baseline Build Complete ==="
    RESPOND TYPE=echo MSG="Persistent baseline has been saved. Future restarts will skip the warm-up phase."
```

## Configuration Examples  
See config_example.cfg for example configurations:
  
## Available Values in Macros
You can access the following values in macros:

{printer["env_sensor chamber"].temperature}  
{printer["env_sensor chamber"].humidity}  
{printer["env_sensor chamber"].pressure}  
{printer["env_sensor chamber"].iaq}  
{printer["env_sensor chamber"].gas_resistance}  
{printer["env_sensor chamber"].voc_index}  (only if utilizing SGP40)  
{printer["env_sensor chamber"].baseline_gas}  

Example macro:

```
[gcode_macro ENV_QUERY]
description: Query any env_sensor (change "chamber" to match your sensor name)
gcode:
    QUERY_ENV SENSOR={params.SENSOR|default("chamber")}

[gcode_macro CHAMBER_STATUS]
description: Show current chamber environmental status (change "chamber" to match your sensor name)
gcode:
    {% set sensor_name = params.SENSOR|default("chamber") %}
    {% set sensor = printer["env_sensor " ~ sensor_name] %}
    {% set iaq = sensor.iaq|float %}
    {% set temp = sensor.temperature|float %}
    {% set hum = sensor.humidity|float %}
    RESPOND TYPE=command MSG="Chamber IAQ: {iaq:.1f} | Temp: {temp:.1f}°C | Humidity: {hum:.1f}%"
```

## Moonraker Update Manager
Add this to your moonraker.conf to enable easy updates from Mainsail:

```
[update_manager klipper-env-sensor]
type: git_repo
path: ~/klipper-env-sensor
origin: https://github.com/maxduracell/klipper-env-sensor.git
primary_branch: main
managed_services: klipper
```

# Development Notes & Transparency:  
This module was developed collaboratively.

Primary author / project lead: maxduracell  
Development assistance: Grok (xAI)

The architecture, feature set, sensor support decisions, and overall design were directed by the human author. Grok was used as a coding and design assistant to accelerate development, generate well-structured code, and help with documentation. All code has been reviewed and refined with the goal of creating a clean, maintainable, and useful Klipper module.
This transparency note is included because some members of the community prefer to know when AI tools were involved in a project’s creation.

License
This project is licensed under the GNU General Public License v3.0 or later.
See the LICENSE file for full details
