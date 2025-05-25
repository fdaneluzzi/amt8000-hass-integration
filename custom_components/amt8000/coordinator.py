from datetime import timedelta, datetime
from typing import Any

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant

from .isec2.client import Client as ISecClient, CommunicationError

import logging

LOGGER = logging.getLogger(__name__)

class AmtCoordinator(DataUpdateCoordinator):
    """Coordinate the amt status update."""

    def __init__(self, hass: HomeAssistant, client: ISecClient, password) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="AMT-8000 Data Polling",
            update_interval=timedelta(seconds=5),
        )
        self.client = client
        self.password = password
        self.data = {}
        self.paired_zones = {}  # Store paired zones information
        self.next_update = datetime.now()
        self.stored_status = None
        self.attempt = 0
        self.last_log_time = datetime.now()

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from AMT-8000."""
        self.attempt += 1

        if(datetime.now() < self.next_update):
           return self.stored_status

        try:
            # Only log every 5 seconds to reduce log spam
            if (datetime.now() - self.last_log_time).total_seconds() >= 5:
                LOGGER.info("retrieving amt-8000 updated status...")
                self.last_log_time = datetime.now()

            self.client.connect()
            self.client.auth(self.password)
            status = self.client.status()
            
            # Get paired sensors list if we don't have it yet
            if not self.paired_zones:
                self.paired_zones = self.client.get_paired_sensors()
                if self.paired_zones:
                    LOGGER.info("Found paired zones: %s", list(self.paired_zones.keys()))

            if status is None:
                return None

            # Process the data
            processed_data = {
                "status": {
                    "siren": status.get("siren", False),
                    "status": status.get("status", "unknown"),
                    "zonesFiring": status.get("zonesFiring", False),
                    "zonesClosed": status.get("zonesClosed", False),
                    "batteryStatus": status.get("batteryStatus", "unknown"),
                    "tamper": status.get("tamper", False),
                },
                "zones": {},
            }

            # Only process zones that are paired
            for zone_id in self.paired_zones:
                zone_status = status.get("zones", {}).get(zone_id, "normal")
                processed_data["zones"][zone_id] = zone_status

            self.stored_status = processed_data
            self.attempt = 0
            self.next_update = datetime.now()

            return processed_data

        except Exception as err:
            LOGGER.error("Error fetching AMT-8000 data: %s", err)
            seconds = 2 ** self.attempt
            time_difference = timedelta(seconds=seconds)
            self.next_update = datetime.now() + time_difference
            LOGGER.info("Next retry after %s", self.next_update)
            return self.stored_status

        finally:
            try:
                if hasattr(self.client, 'client') and self.client.client is not None:
                    self.client.close()
            except CommunicationError:
                pass
            except Exception as e:
                LOGGER.debug("Error closing client connection: %s", str(e))