from typing import Tuple
from bleak import BleakClient, BleakScanner
import traceback
import asyncio

from .const import LOGGER

W_CHARACTERISTIC_UUID = "0000ffd9-0000-1000-8000-00805f9b34fb"
R_CHARACTERISTIC_UUID = "0000ffd4-0000-1000-8000-00805f9b34fb"

async def discover():
    """Discover Bluetooth LE devices."""
    devices = await BleakScanner.discover()
    return [device for device in devices if device.name.startswith("Triones-")]

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

    async def _write(self, data: bytearray):
        LOGGER.debug(''.join(format(x, ' 03x') for x in data))
        await self._device.write_gatt_char(W_CHARACTERISTIC_UUID, data)

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

            await asyncio.sleep(2)

            future = asyncio.get_event_loop().create_future()
            await self._device.start_notify(R_CHARACTERISTIC_UUID, create_status_callback(future))
            await self._write(bytearray([0xEF, 0x01, 0x77]))
            
            await asyncio.wait_for(future, 5.0)
            await self._device.stop_notify(R_CHARACTERISTIC_UUID)
            
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