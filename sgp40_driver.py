# sgp40_driver.py
#
# Robust, non-blocking driver for the Sensirion SGP40 VOC sensor.
# Implements precise temperature and humidity compensation and asynchronous read timing.
#
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  maxduracell

import logging
from typing import Dict, Optional, Tuple
from .sensor_drivers import BaseSensor

class SGP40Sensor(BaseSensor):
    """
    Asynchronous, non-blocking driver for the Sensirion SGP40 VOC sensor.
    Supports dynamic relative humidity & temperature compensation.
    """
    CMD_MEASURE_RAW = [0x26, 0x0F]
    CMD_GET_SERIAL  = [0x36, 0x82]
    CMD_HEATER_OFF  = [0x36, 0x15]

    DEFAULT_I2C_ADDRESS = 0x59

    def __init__(self, i2c_mcu: str, i2c_bus: str, i2c_address: Optional[int], config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        
        # Standard Klipper core I2C configuration helper
        import bus
        self.i2c = bus.setup_sensorsbus(config, "i2c", default_addr=i2c_address or self.DEFAULT_I2C_ADDRESS)

        self._is_initialized = False
        self.baseline = None
        self.adaptation_rate = 0.0001
        
        # Non-blocking measurement state
        self.measurement_start_time: Optional[float] = None

        logging.info("SGP40Sensor registered successfully")

    def initialize(self) -> None:
        try:
            self.i2c.write(self.CMD_GET_SERIAL)
            self._pause(0.01)
            data = self.i2c.read(0x00, 9)  # 3 words + CRCs

            self._is_initialized = True
            logging.info("SGP40 initialization successful")
        except Exception as e:
            logging.exception("SGP40 init failed")
            raise self.printer.config_error(f"Unable to initialize SGP40: {e}")

    def _pause(self, seconds: float):
        self.reactor.pause(self.reactor.monotonic() + seconds)

    def _generate_crc(self, data: list) -> int:
        """Sensirion standard CRC8 calculation."""
        crc = 0xFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = (crc << 1) ^ 0x31
                else:
                    crc <<= 1
                crc &= 0xFF
        return crc

    def _get_compensation_readings(self) -> Tuple[float, float]:
        """
        Dynamically lookup sibling sensors to feed live compensation data.
        Defaults to 25.0°C and 50.0% RH.
        """
        temp, hum = 25.0, 50.0
        try:
            for name, obj in self.printer.lookup_objects():
                if name.startswith("env_sensor ") and obj != self:
                    status = obj.get_status(0.0)
                    if "temperature" in status and "humidity" in status:
                        temp = status["temperature"]
                        hum = status["humidity"]
                        break
        except Exception:
            pass
        return temp, hum

    def read(self) -> Optional[Dict[str, float]]:
        """
        Read SGP40 raw signal and VOC index asynchronously without blocking.
        """
        if not self._is_initialized or self.i2c is None:
            return None

        try:
            now = self.reactor.monotonic()

            # State 0: Trigger Measurement with dynamic compensation
            if self.measurement_start_time is None:
                temp, hum = self._get_compensation_readings()

                # Convert values to Sensirion tick ranges
                hum_ticks = int(round(hum * 65535.0 / 100.0))
                temp_ticks = int(round((temp + 45.0) * 65535.0 / 175.0))

                # Split ticks into bytes
                hum_bytes = [hum_ticks >> 8, hum_ticks & 0xFF]
                temp_bytes = [temp_ticks >> 8, temp_ticks & 0xFF]

                # Calculate checksums
                hum_crc = self._generate_crc(hum_bytes)
                temp_crc = self._generate_crc(temp_bytes)

                # Command packet: [CMD_0, CMD_1, RH_MSB, RH_LSB, RH_CRC, T_MSB, T_LSB, T_CRC]
                payload = self.CMD_MEASURE_RAW + hum_bytes + [hum_crc] + temp_bytes + [temp_crc]
                
                self.i2c.write(payload)
                self.measurement_start_time = now
                return None

            # State 1: Await measurement completion (30ms required, allowing 35ms safety window)
            elapsed = now - self.measurement_start_time
            if elapsed < 0.035:
                return None  # Yield back to the Klipper reactor loop

            # State 2: Retrieve raw measurement data
            data = self.i2c.read(0x00, 3)  # 2 bytes data + 1 byte CRC
            self.measurement_start_time = None  # Reset state

            raw_signal = (data[0] << 8) | data[1]
            voc_index = self._calculate_voc_index(raw_signal)

            return {
                "voc_index": round(voc_index, 1),
                "raw_gas": raw_signal,
            }
        except Exception as e:
            logging.exception("SGP40 read failed")
            self.measurement_start_time = None  # Reset state on error
            return None

    def _calculate_voc_index(self, raw_signal: int) -> float:
        """Simple adaptive baseline VOC index calculation."""
        if self.baseline is None:
            self.baseline = float(raw_signal)
            return 75.0

        self.baseline = (self.baseline * (1.0 - self.adaptation_rate) +
                         raw_signal * self.adaptation_rate)

        ratio = self.baseline / max(raw_signal, 1)
        voc = 50.0 + (ratio - 1.0) * 200.0
        return max(0.0, min(500.0, voc))
