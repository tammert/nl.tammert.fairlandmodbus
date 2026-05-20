from homey.driver import Driver, PairSession
import ipaddress


class FairlandModbusDriver(Driver):

    async def on_init(self):
        await super().on_init()
        # Initialize storage variable on the driver instance level
        self.log("Fairland Modbus Driver Initialized")

    async def on_pair(self, session: PairSession) -> None:

        async def on_validate_ip_details(data):
            # Extract and parse types safely
            ip = str(data.get('ip'))
            port = int(data.get('port'))
            unit_id = int(data.get('unit_id'))

            try:
                ipaddress.ip_address(ip)
            except ValueError:
                raise Exception(f"'{ip}' is not a valid IP address syntax.")

            if not (1 <= port <= 65535) or not (0 <= unit_id <= 255):
                raise Exception("Port or Unit ID parameters out of range.")

            return {
                "name": f"Fairland Modbus",
                "data": {
                    "id": f"fairland-modbus-{ip}-{port}-{unit_id}"
                },
                "settings": {
                    "ip_address": str(ip),
                    "port": int(port),
                    "unit_id": int(unit_id)
                }
            }

        session.set_handler('validate_ip_details', on_validate_ip_details)


homey_export = FairlandModbusDriver
