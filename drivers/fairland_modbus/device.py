from homey.device import Device, CapabilityListener, Value
from pymodbus.client import ModbusTcpClient
from typing import Any


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

        # read the compressor running %
        # self.log(self.modbus_client.read_input_registers(0))

        self.log(f"initialized Fairland Modbus device at {self.ip_address}:{self.port}, unit {self.unit_id}")


    # turn the pool heat pump on/off (true=on, false=off)
    async def on_capability_onoff(self, value: bool, **kwargs: Any) -> None:
        self.log(f"setting heat pump power to {value}")
        self.log(self.modbus_client.write_coil(0, value, device_id=self.unit_id))

    # set the heating mode (0=auto, 1=heat, 2=cool)
    async def on_capability_thermostat_mode(self, value: str, **kwargs: Any) -> None:
        self.log(f"setting heat pump mode to {value}")
        internal_value = 0
        match value:
            case "auto":
                internal_value = 0
            case "heat":
                internal_value = 1
            case "cool":
                internal_value = 2
            case _:
                self.log(f"invalid mode '${value}'")
        self.log(self.modbus_client.write_register(0, internal_value, device_id=self.unit_id))

    # set the mode (0=smart, 1=silent, 2=super_silent, 3=turbo)
    async def on_capability_heater_operation_mode(self, value: str, **kwargs: Any) -> None:
        #TODO: smart/silence seem to be switched? find correct values when pump is running
        self.log(f"setting heater operation mode to {value}")
        internal_value = 0
        match value:
            case "smart":
                internal_value = 0
            case "silent":
                internal_value = 1
            case "super_silent":
                internal_value = 2
            case "turbo":
                internal_value = 3
            case _:
                self.log(f"invalid mode '${value}'")
        self.log(self.modbus_client.write_register(1, internal_value, device_id=self.unit_id))


homey_export = FairlandModbusDevice
