# bme280_driver.py
#
# Functional driver for the Bosch BME280 sensor.
# Provides compensated temperature, humidity and pressure.
#
# Based on the official Bosch BME280 compensation formulas.
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of klipper-env-sensor.
# Copyright (C) 2026  maxduracell

import logging
from typing import Dict, Optional

from .sensor_drivers import BaseSensor


class BME280Sensor(BaseSensor):
    """
    Full functional driver for the Bosch BME280.
    """

    REG_CHIP_ID   = 0xD0
    REG_RESET     = 0xE0
    REG_CTRL_HUM  = 0xF2
    REG_STATUS    = 0xF3
    REG_CTRL_MEAS = 0xF4
    REG_CONFIG    = 0xF5

    CHIP_ID = 0x60

    def __init__(self, i2c_mcu: str, i2c_bus: str, i2c_address: Optional[int], config):
        self.printer = config.get_printer()
        self.i2c_mcu_name = i2c_mcu
        self.i2c_bus = i2c_bus
        self.i2c_addr = i2c_address if i2c_address is not None else 0x76

        self.i2c = None
        self.cal = {}
        self.t_fine = 0.0
        self._is_initialized = False

        logging.info(f"BME280Sensor created on {i2c_mcu}:{i2c_bus} @ 0x{self.i2c_addr:02X}")

    def initialize(self) -> None:
        try:
            i2c_obj = self.printer.lookup_object(f"i2c_{self.i2c_mcu_name}")
            self.i2c = i2c_obj.get_i2c(self.i2c_bus, self.i2c_addr)

            # Soft reset
            self._write_byte(self.REG_RESET, 0xB6)
            self._pause(0.01)

            chip_id = self._read_byte(self.REG_CHIP_ID)
            if chip_id != self.CHIP_ID:
                raise Exception(f"Invalid chip ID 0x{chip_id:02X}, expected 0x60")

            logging.info(f"BME280 detected (Chip ID: 0x{chip_id:02X})")

            self._load_calibration()
            self._configure()

            self._is_initialized = True
            logging.info("BME280 initialization successful")

        except Exception as e:
            logging.exception("BME280 init failed")
            raise self.printer.config_error(f"Unable to initialize BME280: {e}")

    def _write_byte(self, reg: int, value: int):
        self.i2c.write([reg, value])

    def _read_byte(self, reg: int) -> int:
        return self.i2c.read(reg, 1)[0]

    def _read_bytes(self, reg: int, length: int) -> bytes:
        return bytes(self.i2c.read(reg, length))

    def _pause(self, seconds: float):
        reactor = self.printer.get_reactor()
        reactor.pause(reactor.monotonic() + seconds)

    def _load_calibration(self):
        """Load factory calibration data."""
        # Temperature and pressure calibration (0x88 - 0xA1)
        coeff = self._read_bytes(0x88, 26)
        # Humidity calibration (0xA1 + 0xE1 - 0xE7)
        coeff_h = self._read_bytes(0xE1, 7)

        self.cal = {
            "dig_T1": (coeff[1] << 8) | coeff[0],
            "dig_T2": self._to_int16((coeff[3] << 8) | coeff[2]),
            "dig_T3": self._to_int16((coeff[5] << 8) | coeff[4]),

            "dig_P1": (coeff[7] << 8) | coeff[6],
            "dig_P2": self._to_int16((coeff[9] << 8) | coeff[8]),
            "dig_P3": self._to_int16((coeff[11] << 8) | coeff[10]),
            "dig_P4": self._to_int16((coeff[13] << 8) | coeff[12]),
            "dig_P5": self._to_int16((coeff[15] << 8) | coeff[14]),
            "dig_P6": self._to_int16((coeff[17] << 8) | coeff[16]),
            "dig_P7": self._to_int16((coeff[19] << 8) | coeff[18]),
            "dig_P8": self._to_int16((coeff[21] << 8) | coeff[20]),
            "dig_P9": self._to_int16((coeff[23] << 8) | coeff[22]),

            "dig_H1": self._read_byte(0xA1),
            "dig_H2": self._to_int16((coeff_h[1] << 8) | coeff_h[0]),
            "dig_H3": coeff_h[2],
            "dig_H4": self._to_int16((coeff_h[3] << 4) | (coeff_h[4] & 0x0F)),
            "dig_H5": self._to_int16((coeff_h[5] << 4) | (coeff_h[4] >> 4)),
            "dig_H6": self._to_int8(coeff_h[6]),
        }

        logging.info("BME280 calibration data loaded")

    def _to_int8(self, val: int) -> int:
        return val - 256 if val > 127 else val

    def _to_int16(self, val: int) -> int:
        return val - 65536 if val > 32767 else val

    def _configure(self):
        """Configure oversampling and filter."""
        # Humidity oversampling x4
        self._write_byte(self.REG_CTRL_HUM, 0x03)
        # Temperature x4 + Pressure x4 + Normal mode
        self._write_byte(self.REG_CTRL_MEAS, 0x6F)
        # Filter coefficient 4
        self._write_byte(self.REG_CONFIG, 0x10)

        logging.info("BME280 configured")

    def read(self) -> Optional[Dict[str, float]]:
        if not self._is_initialized:
            return None

        try:
            data = self._read_bytes(0xF7, 8)

            press_adc = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
            temp_adc  = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
            hum_adc   = (data[6] << 8) | data[7]

            temperature = self._compensate_temperature(temp_adc)
            pressure    = self._compensate_pressure(press_adc)
            humidity    = self._compensate_humidity(hum_adc)

            return {
                "temperature": round(temperature, 2),
                "humidity": round(humidity, 2),
                "pressure": round(pressure, 2),
            }

        except Exception as e:
            logging.exception("BME280 read failed")
            return None

    def _compensate_temperature(self, adc_T: int) -> float:
        var1 = (adc_T / 16384.0 - self.cal["dig_T1"] / 1024.0) * self.cal["dig_T2"]
        var2 = ((adc_T / 131072.0 - self.cal["dig_T1"] / 8192.0) *
                (adc_T / 131072.0 - self.cal["dig_T1"] / 8192.0)) * self.cal["dig_T3"]
        self.t_fine = var1 + var2
        return self.t_fine / 5120.0

    def _compensate_pressure(self, adc_P: int) -> float:
        var1 = self.t_fine / 2.0 - 64000.0
        var2 = var1 * var1 * self.cal["dig_P6"] / 32768.0
        var2 = var2 + var1 * self.cal["dig_P5"] * 2.0
        var2 = var2 / 4.0 + self.cal["dig_P4"] * 65536.0
        var1 = (self.cal["dig_P3"] * var1 * var1 / 524288.0 + self.cal["dig_P2"] * var1) / 524288.0
        var1 = (1.0 + var1 / 32768.0) * self.cal["dig_P1"]
        if var1 == 0:
            return 0
        p = 1048576.0 - adc_P
        p = (p - var2 / 4096.0) * 6250.0 / var1
        var1 = self.cal["dig_P9"] * p * p / 2147483648.0
        var2 = p * self.cal["dig_P8"] / 32768.0
        p = p + (var1 + var2 + self.cal["dig_P7"]) / 16.0
        return p / 100.0

    def _compensate_humidity(self, adc_H: int) -> float:
        var_H = self.t_fine - 76800.0
        var_H = (adc_H - (self.cal["dig_H4"] * 64.0 + self.cal["dig_H5"] / 16384.0 * var_H)) * \
                (self.cal["dig_H2"] / 65536.0 * (1.0 + self.cal["dig_H6"] / 67108864.0 * var_H *
                (1.0 + self.cal["dig_H3"] / 67108864.0 * var_H)))
        var_H = var_H * (1.0 - self.cal["dig_H1"] * var_H / 524288.0)
        return max(0.0, min(100.0, var_H))
