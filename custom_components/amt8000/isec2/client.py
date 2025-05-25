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
    "panic": [0x40, 0x1a]
}

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
    # Log the raw data for debugging
    LOGGER.debug("Raw data: %s", [hex(x) for x in data])
    
    # The first 8 bytes are the header
    # Bytes 4-5 contain the length
    length = merge_octets(data[4:6]) - 2
    payload = data[8 : 8 + length]
    
    # Log the payload for debugging
    LOGGER.debug("Payload: %s", [hex(x) for x in payload])

    model = "AMT-8000" if payload[0] == 1 else "Unknown"

    # Get individual zone status from payload
    zones = {}
    
    # Read all possible zones (AMT-8000 supports up to 64 zones)
    # Each zone status is represented by 1 byte
    # Zones status starts at byte 21
    max_zones = min(64, len(payload) - 21)  # Calculate how many zones we can read
    
    for i in range(max_zones):
        try:
            # Calculate the correct byte position for each zone
            zone_byte = payload[21 + i]  # Each zone has 1 byte of status
            
            # Log the raw zone byte for debugging
            LOGGER.debug("Zone %d raw byte: 0x%02x", i+1, zone_byte)
            
            zone_status = "normal"
            
            # Check for different types of zone problems
            # Bit 0: Zone open/closed (0 = closed, 1 = open)
            # Bit 1: Zone tamper (0 = normal, 1 = tamper)
            # Bit 2: Zone bypassed (0 = normal, 1 = bypassed)
            # Bit 3: Zone low battery (0 = normal, 1 = low battery)
            # Bit 4: Zone communication failure (0 = normal, 1 = failure)
            # Bit 5: Zone triggered (0 = normal, 1 = triggered)
            
            problems = []
            
            # Primeiro verifica se está disparado (mais crítico)
            if (zone_byte & 0x20) > 0:  # Bit 5: Zone triggered
                problems.append("triggered")
            # Depois verifica outros problemas
            elif (zone_byte & 0x01) > 0:  # Bit 0: Zone open
                problems.append("open")
            elif (zone_byte & 0x02) > 0:  # Bit 1: Zone tamper
                problems.append("tamper")
            elif (zone_byte & 0x04) > 0:  # Bit 2: Zone bypassed
                problems.append("bypassed")
            elif (zone_byte & 0x08) > 0:  # Bit 3: Zone low battery
                problems.append("low_battery")
            elif (zone_byte & 0x10) > 0:  # Bit 4: Zone communication failure
                problems.append("comm_failure")
                
            # If there are any problems, join them with a comma
            if problems:
                zone_status = ",".join(problems)
                zones[str(i + 1)] = zone_status  # Zone numbers start at 1
                LOGGER.debug("Zone %d status: %s", i+1, zone_status)
        except IndexError:
            LOGGER.warning("Failed to read zone %d: payload too short", i+1)
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

        status["batteryStatus"] = battery_status_for(payload)
        status["tamper"] = (payload[71] & (1 << 0x01)) > 0

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
            raise CommunicationError("Client not connected. Call Client.connect")

        self.client.close()
        self.client.detach()

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

