# bme680_driver.py
#
# Functional BME680 driver for klipper-env-sensor
# Implements the official Bosch compensation formulas.
#
# Based on the Bosch BME68x Sensor API:
# https://github.com/BoschSensortec/BME68x-Sensor-API
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of klipper-env-sensor.
# Copyright (C) 2026  maxduracell

import logging
from typing import Dict, Optional

from .sensor_drivers import BaseSensor


class BME680Sensor(BaseSensor):
    """
    Full functional driver for the Bosch BME680.
    Provides compensated temperature, humidity, pressure and gas resistance.
    """

    # Registers
    REG_CHIP_ID     = 0xD0
    REG_RESET       = 0xE0
    REG_CTRL_HUM    = 0x72
    REG_STATUS      = 0x73
    REG_CTRL_MEAS   = 0x74
    REG_CONFIG      = 0x75
    REG_CTRL_GAS_1  = 0x71
    REG_GAS_WAIT_0  = 0x64
    REG_RES_HEAT_0  = 0x5A

    CHIP_ID = 0x61

    def __init__(self, i2c_mcu: str, i2c_bus: str, i2c_address: Optional[int], config):
        self.printer = config.get_printer()
        self.i2c_mcu_name = i2c_mcu
        self.i2c_bus = i2c_bus
        self.i2c_addr = i2c_address if i2c_address is not None else 0x76

        self.i2c = None
        self.cal = {}
        self.t_fine = 0.0
        self._is_initialized = False

        logging.info(f"BME680Sensor created on {i2c_mcu}:{i2c_bus} @ 0x{self.i2c_addr:02X}")

    def initialize(self) -> None:
        try:
            i2c_obj = self.printer.lookup_object(f"i2c_{self.i2c_mcu_name}")
            self.i2c = i2c_obj.get_i2c(self.i2c_bus, self.i2c_addr)

            # Soft reset
            self._write_byte(self.REG_RESET, 0xB6)
            self._pause(0.01)

            # Verify chip ID
            chip_id = self._read_byte(self.REG_CHIP_ID)
            if chip_id != self.CHIP_ID:
                raise Exception(f"Invalid chip ID 0x{chip_id:02X}, expected 0x61")

            logging.info(f"BME680 detected (Chip ID: 0x{chip_id:02X})")

            self._load_calibration()
            self._configure()

            self._is_initialized = True
            logging.info("BME680 initialization successful")

        except Exception as e:
            logging.exception("BME680 init failed")
            raise self.printer.config_error(f"Unable to initialize BME680: {e}")

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
        """Load factory calibration coefficients from the sensor."""
        coeff = self._read_bytes(0x89, 25)
        coeff2 = self._read_bytes(0xE1, 16)

        self.cal = {
            # Temperature
            "par_t1": (coeff[34] << 8) | coeff[33],
            "par_t2": self._to_int16((coeff[2] << 8) | coeff[1]),
            "par_t3": self._to_int8(coeff[3]),

            # Pressure
            "par_p1": (coeff[6] << 8) | coeff[5],
            "par_p2": self._to_int16((coeff[8] << 8) | coeff[7]),
            "par_p3": self._to_int8(coeff[9]),
            "par_p4": self._to_int16((coeff[12] << 8) | coeff[11]),
            "par_p5": self._to_int16((coeff[14] << 8) | coeff[13]),
            "par_p6": self._to_int8(coeff[16]),
            "par_p7": self._to_int8(coeff[15]),
            "par_p8": self._to_int16((coeff[20] << 8) | coeff[19]),
            "par_p9": self._to_int16((coeff[22] << 8) | coeff[21]),
            "par_p10": coeff[23],

            # Humidity
            "par_h1": (coeff2[2] << 4) | (coeff2[1] & 0x0F),
            "par_h2": (coeff2[0] << 4) | (coeff2[1] >> 4),
            "par_h3": self._to_int8(coeff2[3]),
            "par_h4": self._to_int8(coeff2[4]),
            "par_h5": self._to_int8(coeff2[5]),
            "par_h6": coeff2[6],
            "par_h7": self._to_int8(coeff2[7]),

            # Gas
            "par_g1": self._to_int8(coeff2[12]),
            "par_g2": self._to_int16((coeff2[11] << 8) | coeff2[10]),
            "par_g3": self._to_int8(coeff2[13]),
            "res_heat_range": (self._read_byte(0x02) >> 4) & 0x03,
            "res_heat_val": self._to_int8(self._read_byte(0x00)),
            "range_sw_err": self._to_int8((self._read_byte(0x04) & 0xF0) >> 4),
        }

        logging.info("BME680 calibration data loaded")

    def _to_int8(self, val: int) -> int:
        return val - 256 if val > 127 else val

    def _to_int16(self, val: int) -> int:
        return val - 65536 if val > 32767 else val

    def _configure(self):
        """Configure oversampling, filter and gas heater."""
        # Humidity oversampling x2
        self._write_byte(self.REG_CTRL_HUM, 0x02)

        # Temperature x8 + Pressure x4 (sleep mode)
        self._write_byte(self.REG_CTRL_MEAS, 0x54)

        # IIR filter
        self._write_byte(self.REG_CONFIG, 0x0C)

        # Gas heater: ~320°C for 150ms
        self._write_byte(self.REG_GAS_WAIT_0, 0x59)
        self._write_byte(self.REG_RES_HEAT_0, 0x73)
        self._write_byte(self.REG_CTRL_GAS_1, 0x10)

        logging.info("BME680 configured")

    def read(self) -> Optional[Dict[str, float]]:
        if not self._is_initialized:
            return None

        try:
            # Trigger forced mode
            self._write_byte(self.REG_CTRL_MEAS, 0x55)
            self._pause(0.25)

            data = self._read_bytes(0x1F, 15)

            press_adc = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
            temp_adc  = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
            hum_adc   = (data[6] << 8) | data[7]
            gas_adc   = (data[13] << 2) | (data[14] >> 6)
            gas_range = data[14] & 0x0F

            temperature = self._compensate_temperature(temp_adc)
            pressure    = self._compensate_pressure(press_adc)
            humidity    = self._compensate_humidity(hum_adc)
            gas_res     = self._compensate_gas(gas_adc, gas_range)

            return {
                "temperature": round(temperature, 2),
                "humidity": round(humidity, 2),
                "pressure": round(pressure, 2),
                "gas_resistance": int(gas_res),
            }

        except Exception as e:
            logging.exception("BME680 read failed")
            return None

    # =====================================================================
    # Official Bosch compensation formulas
    # =====================================================================

    def _compensate_temperature(self, temp_adc: int) -> float:
        var1 = ((temp_adc / 16384.0) - (self.cal["par_t1"] / 1024.0)) * self.cal["par_t2"]
        var2 = ((((temp_adc / 131072.0) - (self.cal["par_t1"] / 8192.0)) ** 2) *
                (self.cal["par_t3"] * 16.0))
        self.t_fine = var1 + var2
        return self.t_fine / 5120.0

    def _compensate_pressure(self, press_adc: int) -> float:
        var1 = (self.t_fine / 2.0) - 64000.0
        var2 = var1 * var1 * self.cal["par_p6"] / 32768.0
        var2 = var2 + var1 * self.cal["par_p5"] * 2.0
        var2 = (var2 / 4.0) + (self.cal["par_p4"] * 65536.0)
        var1 = (self.cal["par_p3"] * var1 * var1 / 524288.0 +
                self.cal["par_p2"] * var1) / 524288.0
        var1 = (1.0 + var1 / 32768.0) * self.cal["par_p1"]
        if var1 == 0:
            return 0.0
        pressure = 1048576.0 - press_adc
        pressure = ((pressure - (var2 / 4096.0)) * 6250.0) / var1
        var1 = self.cal["par_p9"] * pressure * pressure / 2147483648.0
        var2 = pressure * self.cal["par_p8"] / 32768.0
        pressure = pressure + (var1 + var2 + self.cal["par_p7"]) / 16.0
        return pressure / 100.0

    def _compensate_humidity(self, hum_adc: int) -> float:
        temp = self.t_fine / 5120.0
        var1 = hum_adc - ((self.cal["par_h1"] * 16.0) +
                          ((self.cal["par_h3"] / 2.0) * temp))
        var2 = var1 * ((self.cal["par_h2"] / 262144.0) *
                       (1.0 + (self.cal["par_h4"] / 16384.0) * temp +
                        (self.cal["par_h5"] / 1048576.0) * temp * temp))
        var3 = self.cal["par_h6"] / 16384.0
        var4 = self.cal["par_h7"] / 2097152.0
        humidity = var2 + ((var3 + (var4 * temp)) * var2 * var2)
        return max(0.0, min(100.0, humidity))

    def _compensate_gas(self, gas_adc: int, gas_range: int) -> float:
        lookup = [1, 1, 1, 1, 1, 0.99, 1, 0.992,
                  1, 1, 0.998, 0.995, 1, 0.99, 1, 1]
        var1 = 1340.0 + (5.0 * self.cal["range_sw_err"])
        var2 = var1 * lookup[gas_range]
        return var2 * gas_adc
