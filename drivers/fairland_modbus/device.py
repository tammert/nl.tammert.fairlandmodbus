from homey.device import Device
from pymodbus.client import ModbusTcpClient


class FairlandModbusDevice(Device):
    async def on_init(self):
        await super().on_init()

        settings = self.get_settings()
        self.ip_address = str(settings.get("ip_address"))
        self.port = int(settings.get("port"))
        self.unit_id = int(settings.get("unit_id"))

        self.modbus_client = ModbusTcpClient(self.ip_address, port=self.port)
        self.log(self.modbus_client.connect())

        # turn the heat pump on
        self.log(self.modbus_client.write_coil(0, True, device_id=self.unit_id))

        # set the heating mode (0=auto, 1=heat, 2=cool)
        self.log(self.modbus_client.write_register(0, 1, device_id=self.unit_id))

        # set the mode (0=smart, 1=silent, 2=super_silent, 3=turbo)
        self.log(self.modbus_client.write_register(1, 2, device_id=self.unit_id))

        # read the compressor running %
        self.log(self.modbus_client.read_input_registers(0))

        self.log(f"Initialized Fairland Modbus device at {self.ip_address}:{self.port}, unit {self.unit_id}")


homey_export = FairlandModbusDevice
