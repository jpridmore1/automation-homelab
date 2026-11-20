"""Tiny 'HMI': polls the simulated PLC over Modbus TCP and prints its state.

Usage: python read_plc.py <host> [port]
"""

import sys
import time

from pymodbus.client import ModbusTcpClient

host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
port = int(sys.argv[2]) if len(sys.argv) > 2 else 502

client = ModbusTcpClient(host, port=port)
if not client.connect():
    sys.exit(f"Could not connect to {host}:{port}")

print(f"Polling PLC at {host}:{port} - Ctrl+C to stop")
try:
    while True:
        coils = client.read_coils(0, count=2)
        regs = client.read_holding_registers(0, count=4)
        if coils.isError() or regs.isError():
            print("Read error:", coils, regs)
        else:
            pump, auto = coils.bits[:2]
            level, temp, high, low = regs.registers
            print(
                f"level={level:3d}%  pump={'ON ' if pump else 'OFF'}  "
                f"auto={auto}  temp={temp / 10:.1f}C  setpoints={low}-{high}%"
            )
        time.sleep(2)
except KeyboardInterrupt:
    pass
finally:
    client.close()
