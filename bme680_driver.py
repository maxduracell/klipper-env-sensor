# bme680_driver.py
#
# Production-ready, non-blocking BME680 driver for klipper-env-sensor
# Implements the official Bosch compensation formulas and dynamic heater calculations.
#
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  maxduracell

import logging
from typing import Dict, Optional
from .sensor_drivers import BaseSensor

class BME680Sensor(BaseSensor):
    """
    Standard-compliant BME680 driver using Klipper's official I2C helpers.
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
        self.reactor = self.printer.get_reactor()
        
        # Standard Klipper core I2C configuration helper
        # Automatically manages custom, hardware, and software bitbang I2C buses
        import bus
        self.i2c = bus.setup_sensorsbus(config, "i2c", default_addr=i2c_address or 0x76)
        
        self.cal = {}
        self.t_fine = 0.0
        self._is_initialized = False
        self.last_temp = 25.0
        self.last_written_heater_temp = -100.0  # Prevents redundant bus writes

        logging.info(f"BME680Sensor instance registered successfully")

    def initialize(self) -> None:
        try:
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
            logging.info("BME680 driver initialized successfully")
        except Exception as e:
            logging.exception("BME680 initialization failed")
            raise self.printer.config_error(f"Hardware initialization failed: {e}")

    def _write_byte(self, reg: int, value: int):
        self.i2c.write([reg, value])

    def _read_byte(self, reg: int) -> int:
        return self.i2c.read(reg, 1)[0]

    def _read_bytes(self, reg: int, length: int) -> bytes:
        return bytes(self.i2c.read(reg, length))

    def _pause(self, seconds: float):
        self.reactor.pause(self.reactor.monotonic() + seconds)

    def _to_int8(self, val: int) -> int:
        return val - 256 if val > 127 else val

    def _to_int16(self, val: int) -> int:
        return val - 65536 if val > 32767 else val

    def _load_calibration(self):
        """Loads factory calibration coefficients with safe page-switching."""
        c1 = self._read_bytes(0x89, 25)   # Page 0 (T, P, Hum parts)
        c2 = self._read_bytes(0xE1, 16)   # Page 0 (Remaining Hum & Gas)

        # Non-destructive Read-Modify-Write page switch
        status_reg = self._read_byte(self.REG_STATUS)
        self._write_byte(self.REG_STATUS, status_reg | 0x10)  # Switch to Page 1
        
        res_heat_range_raw = self._read_byte(0x02)
        res_heat_val_raw = self._read_byte(0x00)
        range_sw_err_raw = self._read_byte(0x04)
        
        self._write_byte(self.REG_STATUS, status_reg & ~0x10) # Restore Page 0

        # Sign-extend range_sw_err
        range_sw_err = (range_sw_err_raw & 0xF0) >> 4
        if range_sw_err > 7:
            range_sw_err -= 16

        self.cal = {
            "par_t1": (c1[1] << 8) | c1[0],
            "par_t2": self._to_int16((c1[3] << 8) | c1[2]),
            "par_t3": self._to_int8(c1[4]),
            "par_p1": (c1[6] << 8) | c1[5],
            "par_p2": self._to_int16((c1[8] << 8) | c1[7]),
            "par_p3": self._to_int8(c1[9]),
            "par_p4": self._to_int16((c1[12] << 8) | c1[11]),
            "par_p5": self._to_int16((c1[14] << 8) | c1[13]),
            "par_p6": self._to_int8(c1[16]),
            "par_p7": self._to_int8(c1[15]),
            "par_p8": self._to_int16((c1[20] << 8) | c1[19]),
            "par_p9": self._to_int16((c1[22] << 8) | c1[21]),
            "par_p10": c1[23],
            "par_h1": (c2[2] << 4) | (c2[1] & 0x0F),
            "par_h2": (c2[0] << 4) | (c2[1] >> 4),
            "par_h3": self._to_int8(c2[3]),
            "par_h4": self._to_int8(c2[4]),
            "par_h5": self._to_int8(c2[5]),
            "par_h6": c2[6],
            "par_h7": self._to_int8(c2[7]),
            "par_g1": self._to_int8(c2[12]),
            "par_g2": self._to_int16((c2[11] << 8) | c2[10]),
            "par_g3": self._to_int8(c2[13]),
            "res_heat_range": (res_heat_range_raw >> 4) & 0x03,
            "res_heat_val": self._to_int8(res_heat_val_raw),
            "range_sw_err": range_sw_err,
        }
        logging.info("BME680 calibration data loaded successfully")

    def _configure(self):
        self._write_byte(self.REG_CTRL_HUM, 0x02)           # Humidity x2
        self._write_byte(self.REG_CTRL_MEAS, 0xB4)          # Temp/Press x16, Sleep Mode
        self._write_byte(self.REG_CONFIG, 0x0C)             # Filter coefficient 3
        
        # Calculate initial heater configuration for ~320°C using baseline 25.0°C
        self._write_heater_if_changed(320, self.last_temp)
        self._write_byte(self.REG_GAS_WAIT_0, 0x59)         # 150ms delay target
        self._write_byte(self.REG_CTRL_GAS_1, 0x10)         # Enable gas heater profile
        logging.info("BME680 configured successfully")

    def _write_heater_if_changed(self, target_temp: int, ambient_temp: float):
        """Only write the heater configuration over I2C if the ambient temperature shifted significantly."""
        if abs(ambient_temp - self.last_written_heater_temp) > 0.5:
            res_heat_val = self._calc_heater_resistance(target_temp, ambient_temp)
            self._write_byte(self.REG_RES_HEAT_0, res_heat_val)
            self.last_written_heater_temp = ambient_temp

    def _calc_heater_resistance(self, target_temp: int, ambient_temp: float) -> int:
        """Calculate heater resistance register value using official Bosch formula."""
        var1 = (self.cal.get("par_g1", 0) / 16.0) + 49.0
        var2 = ((self.cal.get("par_g2", 0) / 32768.0) * 0.0005) + 0.00235
        var3 = self.cal.get("par_g3", 0) / 1024.0
        var4 = var1 * (1.0 + (var2 * target_temp))
        var5 = var4 + (var3 * ambient_temp)
        res_heat = int(3.4 * ((var5 * (4.0 / (4.0 + self.cal.get("res_heat_range", 0)))) *
                       (1.0 / (1.0 + (self.cal.get("res_heat_val", 0) * 0.002))) - 25))
        return min(255, max(0, res_heat))

    def read(self) -> Optional[Dict[str, float]]:
        if not self._is_initialized:
            return None
        try:
            status = self._read_byte(self.REG_STATUS)
            if not (status & 0x08):
                self._write_heater_if_changed(320, self.last_temp)
                self._write_byte(self.REG_CTRL_MEAS, 0xB5)
                return None

            data = self._read_bytes(0x1F, 15)
            press_adc = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
            temp_adc  = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
            hum_adc   = (data[6] << 8) | data[7]
            gas_adc   = (data[13] << 2) | (data[14] >> 6)
            gas_range = data[14] & 0x0F

            temperature = self._compensate_temperature(temp_adc)
            self.last_temp = temperature
            
            pressure    = self._compensate_pressure(press_adc)
            humidity    = self._compensate_humidity(hum_adc)
            gas_res     = self._compensate_gas(gas_adc, gas_range)

            # Pre-heat prep and trigger next measurement asynchronously
            self._write_heater_if_changed(320, self.last_temp)
            self._write_byte(self.REG_CTRL_MEAS, 0xB5)

            return {
                "temperature": round(temperature, 2),
                "humidity": round(humidity, 2),
                "pressure": round(pressure, 2),
                "gas_resistance": int(gas_res),
            }
        except Exception as e:
            logging.exception("BME680 raw read failure")
            return None

    # =====================================================================
    # Official Bosch compensation formulas (BME68x API)
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
        var1 = (self.cal["par_p3"] * var1 * var1 / 524288.0 + self.cal["par_p2"] * var1) / 524288.0
        var1 = (1.0 + var1 / 32768.0) * self.cal["par_p1"]
        if var1 == 0.0:
            return 0.0
        pressure = 1048576.0 - press_adc
        pressure = ((pressure - (var2 / 4096.0)) * 6250.0) / var1
        var1 = self.cal["par_p9"] * pressure * pressure / 2147483648.0
        var2 = pressure * self.cal["par_p8"] / 32768.0
        pressure = pressure + (var1 + var2 + self.cal["par_p7"]) / 16.0
        return pressure / 100.0

    def _compensate_humidity(self, hum_adc: int) -> float:
        temp = self.t_fine / 5120.0
        var1 = hum_adc - ((self.cal["par_h1"] * 16.0) + ((self.cal["par_h3"] / 2.0) * temp))
        var2 = var1 * ((self.cal["par_h2"] / 262144.0) *
                       (1.0 + (self.cal["par_h4"] / 16384.0) * temp +
                        (self.cal["par_h5"] / 1048576.0) * temp * temp))
        var3 = self.cal["par_h6"] / 16384.0
        var4 = self.cal["par_h7"] / 2097152.0
        humidity = var2 + ((var3 + (var4 * temp)) * var2 * var2)
        return max(0.0, min(100.0, humidity))

    def _compensate_gas(self, gas_adc: int, gas_range: int) -> float:
        const_array1 = [1.0, 1.0, 1.0, 1.0, 1.0, 0.99, 1.0, 0.992,
                        1.0, 1.0, 0.998, 0.995, 1.0, 0.99, 1.0, 1.0]
        const_array2 = [
            8000000.0, 4000000.0, 2000000.0, 1000000.0, 499500.0,
            249000.0, 125000.0, 63000.0, 31250.0, 15625.0,
            7812.5, 3906.25, 1953.125, 976.5625, 488.28125, 244.140625
        ]
        if gas_adc == 0 or gas_adc == 1023:
            return 0.0
        var1 = 1340.0 + (5.0 * self.cal.get("range_sw_err", 0))
        var2 = var1 * const_array1[gas_range]
        gas_res = (var2 * const_array2[gas_range]) / (gas_adc - 512.0 + var2)
        return gas_res
