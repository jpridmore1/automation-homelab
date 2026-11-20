"""Simulated PLC: a water tank with a pump, exposed over Modbus TCP.

Register map (all addresses start at 0):
  Coil 0             pump running (1 = on)
  Coil 1             auto mode (1 = PLC controls the pump)
  Holding reg 0      tank level, 0-100 %
  Holding reg 1      water temperature, tenths of a degree C (215 = 21.5 C)
  Holding reg 2      high setpoint: pump stops at this level (auto mode)
  Holding reg 3      low setpoint: pump starts at this level (auto mode)
"""

import asyncio
import logging
import random

from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusServerContext,
    ModbusSlaveContext,
)
from pymodbus.server import StartAsyncTcpServer

COILS = 1  # Modbus function code for coils
HOLDING = 3  # Modbus function code for holding registers

PUMP_COIL = 0
LEVEL_REG = 0

log = logging.getLogger("plc")


async def scan_cycle(device):
    """Like a real PLC's scan: read inputs, run logic, write outputs, repeat."""
    while True:
        pump, auto = device.getValues(COILS, PUMP_COIL, 2)
        level, _temp, high, low = device.getValues(HOLDING, LEVEL_REG, 4)

        # Control logic (what ladder logic would do on a real PLC)
        if auto:
            if level >= high:
                pump = False
            elif level <= low:
                pump = True

        # "Physics": the pump fills the tank, otherwise it drains
        level = min(100, level + 2) if pump else max(0, level - 1)
        temp = 215 + random.randint(-3, 3)

        device.setValues(COILS, PUMP_COIL, [pump])
        device.setValues(HOLDING, LEVEL_REG, [level, temp])
        log.info("level=%3d%%  pump=%-3s  auto=%s", level, "ON" if pump else "OFF", bool(auto))
        await asyncio.sleep(1)


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    device = ModbusSlaveContext(
        di=ModbusSequentialDataBlock(0, [0] * 10),
        co=ModbusSequentialDataBlock(0, [False] * 10),
        hr=ModbusSequentialDataBlock(0, [0] * 10),
        ir=ModbusSequentialDataBlock(0, [0] * 10),
    )
    # Starting state: pump off, auto mode on, tank half full, setpoints 80/20
    device.setValues(COILS, PUMP_COIL, [False, True])
    device.setValues(HOLDING, LEVEL_REG, [50, 215, 80, 20])

    context = ModbusServerContext(slaves=device, single=True)
    asyncio.create_task(scan_cycle(device))

    log.info("Simulated PLC listening on Modbus TCP port 502")
    await StartAsyncTcpServer(context=context, address=("0.0.0.0", 502))


if __name__ == "__main__":
    asyncio.run(main())
