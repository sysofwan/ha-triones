from typing import Tuple
from bleak import BleakClient, BleakScanner
import traceback
import asyncio

from .const import LOGGER

WRITE_CHARACTERISTIC_UUIDS = ["0000ffd5-0000-1000-8000-00805f9b34fb", "0000ffd9-0000-1000-8000-00805f9b34fb", "0000ffe5-0000-1000-8000-00805f9b34fb", "0000ffe9-0000-1000-8000-00805f9b34fb"]
READ_CHARACTERISTIC_UUIDS  = ["0000ffd0-0000-1000-8000-00805f9b34fb", "0000ffd4-0000-1000-8000-00805f9b34fb", "0000ffe0-0000-1000-8000-00805f9b34fb", "0000ffe4-0000-1000-8000-00805f9b34fb"]

async def discover():
    """Discover Bluetooth LE devices."""
    devices = await BleakScanner.discover()
    LOGGER.debug("Discovered devices: %s", [{"address": device.address, "name": device.name} for device in devices])
    return [device for device in devices if device.name is not None and (device.name.lower().startswith("triones") or device.name.lower().startswith("ledble"))]

def create_status_callback(future: asyncio.Future):
    def callback(sender: int, data: bytearray):
        if not future.done():
            future.set_result(data)
    return callback

class TrionesInstance:
    def __init__(self, mac: str) -> None:
        self._mac = mac
        self._device = BleakClient(self._mac)
        self._is_on = None
        self._rgb_color = None
        self._brightness = None
        self._write_uuid = None
        self._read_uuid = None

    async def _write(self, data: bytearray):
        LOGGER.debug(''.join(format(x, ' 03x') for x in data))
        await self._device.write_gatt_char(self._write_uuid, data)

    @property
    def mac(self):
        return self._mac

    @property
    def is_on(self):
        return self._is_on
    
    @property
    def rgb_color(self):
        return self._rgb_color

    @property
    def white_brightness(self):
        return self._brightness

    async def set_color(self, rgb: Tuple[int, int, int]):
        r, g, b = rgb
        await self._write([0x56, r, g, b, 0x00, 0xF0, 0xAA])
    
    async def set_white(self, intensity: int):
        await self._write([0x56, 0, 0, 0, intensity, 0x0F, 0xAA])

    async def turn_on(self):
        await self._write(bytearray([0xCC, 0x23, 0x33]))
        
    async def turn_off(self):
        await self._write(bytearray([0xCC, 0x24, 0x33]))
    
    async def update(self):
        try:
            if not self._device.is_connected:
                await self._device.connect(timeout=20)
                await asyncio.sleep(1)

                for char in self._device.services.characteristics.values():
                    if char.uuid in WRITE_CHARACTERISTIC_UUIDS:
                        self._write_uuid = char.uuid
                    if char.uuid in READ_CHARACTERISTIC_UUIDS:
                        self._read_uuid = char.uuid

                if not self._read_uuid or not self._write_uuid:
                    LOGGER.error("No supported read/write UUIDs found")
                    return

                LOGGER.info(f"Read UUID: {self._read_uuid}, Write UUID: {self._write_uuid}")

            await asyncio.sleep(2)

            future = asyncio.get_event_loop().create_future()
            await self._device.start_notify(self._read_uuid, create_status_callback(future))
            await self._write(bytearray([0xEF, 0x01, 0x77]))
            
            await asyncio.wait_for(future, 5.0)
            await self._device.stop_notify(self._read_uuid)
            
            res = future.result()
            self._is_on = True if res[2] == 0x23 else False if res[2] == 0x24 else None
            self._rgb_color = (res[6], res[7], res[8])
            self._brightness = res[9] if res[9] > 0 else None
            LOGGER.debug(''.join(format(x, ' 03x') for x in res))

        except (Exception) as error:
            self._is_on = None
            LOGGER.error("Error getting status: %s", error)
            track = traceback.format_exc()
            LOGGER.debug(track)

    async def disconnect(self):
        if self._device.is_connected:
            await self._device.disconnect()