import asyncio

from homey.device import Device
from pymodbus.client import ModbusTcpClient
from typing import Any

THERMOSTAT_MODE_TO_MODBUS = {
    "auto": 0,
    "heat": 1,
    "cool": 2,
}

THERMOSTAT_MODE_FROM_MODBUS = {
    modbus_value: thermostat_mode
    for thermostat_mode, modbus_value in THERMOSTAT_MODE_TO_MODBUS.items()
}

THERMOSTAT_MODE_TARGET_TEMPERATURE_REGISTER = {
    "auto": 2,
    "heat": 3,
    "cool": 4,
}

HEATER_OPERATION_MODE_TO_MODBUS = {
    "silent": 0,
    "smart": 1,
    "super_silent": 2,
    "turbo": 3,
}

HEATER_OPERATION_MODE_FROM_MODBUS = {
    modbus_value: heater_operation_mode
    for heater_operation_mode, modbus_value in HEATER_OPERATION_MODE_TO_MODBUS.items()
}


def convert_temperature_to_celsius(temperature: int) -> float:
    return (temperature - 60) / 2


def convert_temperature_from_celsius(temperature: float) -> int:
    return int(temperature * 2 + 60)


class FairlandModbusDevice(Device):
    async def on_init(self):
        await super().on_init()

        settings = self.get_settings()
        self.ip_address = str(settings.get("ip_address"))
        self.port = int(settings.get("port"))
        self.unit_id = int(settings.get("unit_id"))

        self.modbus_client = ModbusTcpClient(self.ip_address, port=self.port)
        self.log(self.modbus_client.connect())

        # capability listeners
        self.register_capability_listener("onoff", self.on_capability_onoff)
        self.register_capability_listener("thermostat_mode", self.on_capability_thermostat_mode)
        self.register_capability_listener("heater_operation_mode", self.on_capability_heater_operation_mode)
        self.register_capability_listener("target_temperature", self.on_capability_target_temperature)

        # background polling for current measurements
        self.poll_task = asyncio.create_task(self.poll_measurements())

        self.log(f"initialized Fairland Modbus device at {self.ip_address}:{self.port}, unit {self.unit_id}")

    async def on_uninit(self):
        if hasattr(self, "poll_task"):
            self.poll_task.cancel()

            try:
                await self.poll_task
            except asyncio.CancelledError:
                pass

        if hasattr(self, "modbus_client"):
            self.modbus_client.close()

    def reconnect_modbus_client(self) -> None:
        if hasattr(self, "modbus_client"):
            self.modbus_client.close()

        self.modbus_client = ModbusTcpClient(self.ip_address, port=self.port)

        if not self.modbus_client.connect():
            raise ConnectionError("unable to reconnect to Modbus device")


    # turn the pool heat pump on/off (true=on, false=off)
    async def on_capability_onoff(self, value: bool, **kwargs: Any) -> None:
        self.log(f"setting heat pump power to {value}")
        self.log(self.modbus_client.write_coil(0, value, device_id=self.unit_id))

    # set the heating mode (0=auto, 1=heat, 2=cool)
    async def on_capability_thermostat_mode(self, value: str, **kwargs: Any) -> None:
        self.log(f"setting heat pump mode to {value}")
        internal_value = THERMOSTAT_MODE_TO_MODBUS.get(value)
        self.log(self.modbus_client.write_register(0, internal_value, device_id=self.unit_id))

    # set the mode (0=smart, 1=silent, 2=super_silent, 3=turbo)
    async def on_capability_heater_operation_mode(self, value: str, **kwargs: Any) -> None:
        self.log(f"setting heater operation mode to {value}")
        internal_value = HEATER_OPERATION_MODE_TO_MODBUS.get(value)
        self.log(self.modbus_client.write_register(1, internal_value, device_id=self.unit_id))

    async def on_capability_target_temperature(self, value: float, **kwargs: Any) -> None:
        self.log(f"setting target temperature to {value}")

        thermostat_mode = self.get_capability_value("thermostat_mode")
        target_temperature_register = THERMOSTAT_MODE_TARGET_TEMPERATURE_REGISTER.get(thermostat_mode)

        if target_temperature_register is None:
            self.log(f"unable to set target temperature for invalid mode '{thermostat_mode}'")
            return

        self.log(
            self.modbus_client.write_register(
                target_temperature_register,
                convert_temperature_from_celsius(value),
                device_id=self.unit_id,
            )
        )

    async def poll_measurements(self) -> None:
        while True:
            try:
                self.reconnect_modbus_client()
                await self.update_measurements()
                await self.set_available()
            except asyncio.CancelledError:
                raise
            except Exception as err:
                self.error(f"failed to poll Modbus measurements: {err}")
                await self.set_unavailable("unable to read Modbus measurements")

            await asyncio.sleep(self.get_settings().get("poll_interval", 60))

    async def update_measurements(self) -> None:
        onoff = self.modbus_client.read_coils(0, device_id=self.unit_id).bits[0]
        self.log(f"powered on: {onoff}")

        mode = self.modbus_client.read_holding_registers(0, device_id=self.unit_id).registers[0]
        thermostat_mode = THERMOSTAT_MODE_FROM_MODBUS.get(mode)
        self.log(f"mode: {mode}")

        set_temperature = 0
        target_temperature_register = THERMOSTAT_MODE_TARGET_TEMPERATURE_REGISTER.get(thermostat_mode)
        if target_temperature_register is not None:
            set_temperature = convert_temperature_to_celsius(
                self.modbus_client.read_holding_registers(
                    target_temperature_register,
                    device_id=self.unit_id,
                ).registers[0]
            )
        self.log(f"target temperature: {set_temperature}")

        heater_operation_mode_value = self.modbus_client.read_holding_registers(1, device_id=self.unit_id).registers[0]
        heater_operation_mode = HEATER_OPERATION_MODE_FROM_MODBUS.get(heater_operation_mode_value)
        self.log(f"heater operation mode: {heater_operation_mode}")

        current = self.modbus_client.read_input_registers(2, device_id=self.unit_id).registers[0] / 10  # 0.1A per int
        self.log(f"current: {current}")
        voltage = self.modbus_client.read_input_registers(11, device_id=self.unit_id).registers[0]
        self.log(f"voltage: {voltage}")
        water_inlet_temperature = convert_temperature_to_celsius(
            self.modbus_client.read_input_registers(3, device_id=self.unit_id).registers[0])
        self.log(f"water inlet temperature: {water_inlet_temperature}")
        water_outlet_temperature = convert_temperature_to_celsius(
            self.modbus_client.read_input_registers(4, device_id=self.unit_id).registers[0])
        self.log(f"water outlet temperature: {water_outlet_temperature}")
        ambient_temperature = convert_temperature_to_celsius(
            self.modbus_client.read_input_registers(5, device_id=self.unit_id).registers[0])
        self.log(f"ambient temperature: {ambient_temperature}")

        await self.set_capability_value("onoff", onoff)
        await self.set_capability_value("thermostat_mode", thermostat_mode)
        await self.set_capability_value("heater_operation_mode", heater_operation_mode)
        await self.set_capability_value("measure_current", current)
        await self.set_capability_value("measure_voltage", voltage)
        await self.set_capability_value("target_temperature", set_temperature)
        await self.set_capability_value("measure_temperature", water_inlet_temperature)
        await self.set_capability_value("measure_temperature.water_outlet", water_outlet_temperature)
        await self.set_capability_value("measure_temperature.ambient", ambient_temperature)


homey_export = FairlandModbusDevice
