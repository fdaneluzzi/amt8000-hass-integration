"""Module for amt-8000 communication."""

import socket
import logging

LOGGER = logging.getLogger(__name__)

timeout = 2  # Set the timeout to 2 seconds

dst_id = [0x00, 0x00]
our_id = [0x8F, 0xFF]
commands = {
    "auth": [0xF0, 0xF0],
    "status": [0x0B, 0x4A],
    "arm_disarm": [0x40, 0x1e],
    "panic": [0x40, 0x1a],
    "paired_sensors": [0x0B, 0x01]  # New command to get paired sensors list
}

ZONE_START = 64      # primeiro byte de zona dentro do payload
MAX_ZONES   = 64

def split_into_octets(n):
   if 0 <= n <= 0xFFFF:
       high_byte = (n >> 8) & 0xFF
       low_byte = n & 0xFF
       return [high_byte, low_byte]
   else:
       raise ValueError("Número fora do intervalo (0 a 65535)")

def calculate_checksum(buffer):
    """Calculate a checksum for a given array of bytes."""
    checksum = 0
    for value in buffer:
        checksum ^= value
    checksum ^= 0xFF
    checksum &= 0xFF
    return checksum


def build_status(data):
    """Build the amt-8000 status from a given array of bytes."""
    # The first 8 bytes are the header
    # Bytes 4-5 contain the length
    length = merge_octets(data[4:6]) - 2
    payload = data[8 : 8 + length]
    
    # Verifica se o payload tem o tamanho mínimo necessário
    if len(payload) < 22:
        LOGGER.error("Payload too short: %d bytes", len(payload))
        return None

    # O modelo é AMT-8000 se o byte 0 for 0x8b
    model = "AMT-8000" if payload[0] == 0x8b else "Unknown"

    # Get individual zone status from payload
    zones = {}
    
    # Read all possible zones (AMT-8000 supports up to 64 zones)
    # Each zone status is represented by 1 byte
    # Zones status starts at byte 86 (22 header + 64 reserved block)
    max_zones = min(64, len(payload) - 84)  # Calculate how many zones we can read
    
    # Skip header (22 bytes) and reserved block (64 bytes)
    for i in range(max_zones):
        try:
            # Calculate the correct byte position for each zone
            zone_byte = payload[84 + i]  # Each zone has 1 byte of status
            
            zone_status = "normal"
            problems = []
            
            # Check for different types of zone problems
            if (zone_byte & 0x01) > 0:  # Bit 0: Zone open
                problems.append("open_triggered")
            if (zone_byte & 0x02) > 0:  # Bit 1: Communication failure
                problems.append("comm_failure")
            if (zone_byte & 0x04) > 0:  # Bit 2: Zone bypassed
                problems.append("bypassed")
            if (zone_byte & 0x08) > 0:  # Bit 3: Zone low battery
                problems.append("low_battery")
            if (zone_byte & 0x10) > 0:  # Bit 4: Zone tamper
                problems.append("tamper")
            if (zone_byte & 0x20) > 0:  # Bit 5: Zone triggered
                problems.append("memory_triggered")
                
            # If there are any problems, join them with a comma
            if problems:
                zone_status = ",".join(problems)
                zones[str(i + 1)] = zone_status
        except IndexError:
            break
        except Exception as e:
            LOGGER.error("Error processing zone %d: %s", i+1, str(e))
            continue

    try:
        status = {
            "model": model,
            "version": f"{payload[1]}.{payload[2]}.{payload[3]}",
            "status": get_status(payload),
            "zonesFiring": (payload[20] & 0x8) > 0,
            "zonesClosed": (payload[20] & 0x4) > 0,
            "siren": (payload[20] & 0x2) > 0,
            "zones": zones
        }

        # Verifica se o payload tem o tamanho necessário para ler o status da bateria e tamper
        if len(payload) >= 135:
            status["batteryStatus"] = battery_status_for(payload)
        else:
            status["batteryStatus"] = "unknown"
            
        if len(payload) >= 72:
            status["tamper"] = (payload[71] & (1 << 0x01)) > 0
        else:
            status["tamper"] = False

        return status
    except Exception as e:
        LOGGER.error("Error building status: %s", str(e))
        return None


def battery_status_for(resp):
    """Retrieve the battery status."""
    batt = resp[134]
    if batt == 0x01:
        return "dead"
    if batt == 0x02:
        return "low"
    if batt == 0x03:
        return "middle"
    if batt == 0x04:
        return "full"

    return "unknown"


def merge_octets(buf):
    """Merge octets."""
    return buf[0] * 256 + buf[1]


def get_status(payload):
    """Retrieve the current status from a given array of bytes."""
    status = (payload[20] >> 5) & 0x03
    if status == 0x00:
        return "disarmed"
    if status == 0x01:
        return "partial_armed"
    if status == 0x03:
        return "armed_away"
    return "unknown"


class CommunicationError(Exception):
    """Exception raised for communication error."""

    def __init__(self, message="Communication error"):
        """Initialize the error."""
        self.message = message
        super().__init__(self.message)


class AuthError(Exception):
    """Exception raised for authentication error."""

    def __init__(self, message="Authentication Error"):
        """Initialize the error."""
        self.message = message
        super().__init__(self.message)


class Client:
    """Client to communicate with amt-8000."""

    def __init__(self, host, port, device_type=1, software_version=0x10):
        """Initialize the client."""
        self.host = host
        self.port = port
        self.device_type = device_type
        self.software_version = software_version
        self.client = None

    def close(self):
        """Close a connection."""
        if self.client is None:
            LOGGER.debug("Client not connected, nothing to close")
            return

        try:
            self.client.close()
            self.client.detach()
        except Exception as e:
            LOGGER.debug("Error closing client connection: %s", str(e))
        finally:
            self.client = None

    def connect(self):
        """Create a new connection."""
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.settimeout(timeout)
        self.client.connect((self.host, self.port))

    def auth(self, password):
        """Create a authentication for the current connection."""
        if self.client is None:
            raise CommunicationError("Client not connected. Call Client.connect")

        pass_array = []
        for char in password:
            if len(password) != 6 or not char.isdigit():
                raise CommunicationError(
                    "Cannot parse password, only 6 integers long are accepted"
                )

            pass_array.append(int(char))

        length = [0x00, 0x0a]
        data = (
            dst_id
            + our_id
            + length
            + commands["auth"]
            + [self.device_type]
            + pass_array
            + [self.software_version]
        )

        cs = calculate_checksum(data)
        payload = bytes(data + [cs])

        self.client.send(payload)

        return_data = bytearray()

        data = self.client.recv(1024)

        return_data.extend(data)

        result = return_data[8:9][0]

        if result == 0:
            return True
        if result == 1:
            raise AuthError("Invalid password")
        if result == 2:
            raise AuthError("Incorrect software version")
        if result == 3:
            raise AuthError("Alarm panel will call back")
        if result == 4:
            raise AuthError("Waiting for user permission")
        raise CommunicationError("Unknown payload response for authentication")

    def status(self):
        """Return the current status."""
        if self.client is None:
            raise CommunicationError("Client not connected. Call Client.connect")

        length = [0x00, 0x02]
        status_data = dst_id + our_id + length + commands["status"]
        cs = calculate_checksum(status_data)
        payload = bytes(status_data + [cs])

        return_data = bytearray()
        self.client.send(payload)

        data = self.client.recv(1024)
        return_data.extend(data)

        status = build_status(return_data)
        return status

    def arm_system(self, partition):
        """Return the current status."""
        if self.client is None:
              raise CommunicationError("Client not connected. Call Client.connect")

        if partition == 0:
          partition = 0xFF

        length = [0x00, 0x04]
        arm_data = dst_id + our_id + length + commands["arm_disarm"] + [ partition, 0x01 ]
        cs = calculate_checksum(arm_data)
        payload = bytes(arm_data + [cs])

        return_data = bytearray()
        self.client.send(payload)

        data = self.client.recv(1024)
        return_data.extend(data)

        if return_data[8] == 0x91:
            return 'armed'

        return 'not_armed'

    def disarm_system(self, partition):
        """Return the current status."""
        if self.client is None:
              raise CommunicationError("Client not connected. Call Client.connect")

        if partition == 0:
          partition = 0xFF

        length = [0x00, 0x04]
        arm_data = dst_id + our_id + length + commands["arm_disarm"] + [ partition, 0x00 ]
        cs = calculate_checksum(arm_data)
        payload = bytes(arm_data + [cs])

        return_data = bytearray()
        self.client.send(payload)

        data = self.client.recv(1024)
        return_data.extend(data)

        if return_data[8] == 0x91:
            return 'disarmed'

        return 'not_disarmed'

    def panic(self, type):
        """Return the current status."""
        if self.client is None:
              raise CommunicationError("Client not connected. Call Client.connect")

        length = [0x00, 0x03]
        arm_data = dst_id + our_id + length + commands["panic"] +[ type ]
        cs = calculate_checksum(arm_data)
        payload = bytes(arm_data + [cs])

        return_data = bytearray()
        self.client.send(payload)

        data = self.client.recv(1024)
        return_data.extend(data)

        if return_data[7] == 0xfe:
            return 'triggered'

        return 'not_triggered'

    def get_paired_sensors(self):
        """Get the list of paired sensors from the alarm panel."""
        if self.client is None:
            raise CommunicationError("Client not connected. Call Client.connect")

        length = [0x00, 0x02]
        sensors_data = dst_id + our_id + length + commands["paired_sensors"]
        cs = calculate_checksum(sensors_data)
        payload = bytes(sensors_data + [cs])

        return_data = bytearray()
        self.client.send(payload)

        data = self.client.recv(1024)
        return_data.extend(data)

        # The response starts at byte 8 (after header)
        # Each byte represents 8 zones (1 bit per zone)
        paired_zones = {}
        try:
            # Skip header (8 bytes) and read zone status
            for byte_index in range(8):  # 8 bytes = 64 zones
                if len(return_data) > 8 + byte_index:
                    byte_value = return_data[8 + byte_index]
                    # Check each bit in the byte
                    for bit in range(8):
                        zone_number = (byte_index * 8) + bit + 1
                        if (byte_value & (1 << bit)) > 0:  # If bit is set, zone is paired
                            paired_zones[str(zone_number)] = True
        except Exception as e:
            LOGGER.error("Error reading paired sensors: %s", str(e))
            return None

        return paired_zones

