from datetime import timedelta, datetime

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
)

from .isec2.client import Client as ISecClient

import logging

LOGGER = logging.getLogger(__name__)

class AmtCoordinator(DataUpdateCoordinator):
    """Coordinate the amt status update."""

    def __init__(self, hass, isec_client: ISecClient, password):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="AMT-8000 Data Polling",
            update_interval=timedelta(seconds=10),
        )
        self.isec_client = isec_client
        self.password = password
        self.next_update = datetime.now()
        self.stored_status = None
        self.attemt = 0

    async def _async_update_data(self):
        """Retrieve the current status."""
        self.attemt += 1

        if(datetime.now() < self.next_update):
           LOGGER.debug("Using stored status: %s", self.stored_status)
           return self.stored_status

        try:
          LOGGER.info("retrieving amt-8000 updated status...")
          self.isec_client.connect()
          self.isec_client.auth(self.password)
          status = self.isec_client.status()
          LOGGER.debug("Raw status from ISec client: %s", status)
          self.isec_client.close()

          # Create a data structure that includes zones
          data = {
              "status": {
                  "siren": status.get("siren", False),
                  "status": status.get("status", "unknown"),
                  "zonesFiring": status.get("zonesFiring", False),
                  "zonesClosed": status.get("zonesClosed", False),
                  "batteryStatus": status.get("batteryStatus", "unknown"),
                  "tamper": status.get("tamper", False)
              },
              "zones": status.get("zones", {})
          }

          LOGGER.debug("Processed data structure: %s", data)
          self.stored_status = data
          self.attemt = 0
          self.next_update = datetime.now()

          return data
        except Exception as e:
          LOGGER.error("Coordinator update error: %s", str(e))
          seconds = 2 ** self.attemt
          time_difference = timedelta(seconds=seconds)
          self.next_update = datetime.now() + time_difference
          LOGGER.info("Next retry after %s", self.next_update)
          return self.stored_status

        finally:
           self.isec_client.close()