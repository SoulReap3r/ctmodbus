"""
Control Things Modbus, aka ctmodbus.py
Upgraded unified read/write system with popup table formatting.
"""

import socket
from datetime import datetime

from ctui import Ctui
from ctui.dialogs import message_dialog
from ctui.types import GreedyBin, GreedyInt
from pkg_resources import get_distribution
from pymodbus.client.sync import (
    ModbusSerialClient,
    ModbusTcpClient,
    ModbusUdpClient
)
from pymodbus.mei_message import ReadDeviceInformationRequest

from ctmodbus import common


# =====================================================================
#  UI SETUP
# =====================================================================
ctmodbus = Ctui()
ctmodbus.name = "ctmodbus"
ctmodbus.version = get_distribution("ctmodbus").version
ctmodmod = "Modbus penetration-testing toolkit"
ctmodbus.prompt = "ctmodbus> "
ctmodbus.output_text = ""   # Fixes old CTModbus scroll noise

ctmodbus.session = None
unit_id = 1


# =====================================================================
#  HELPERS
# =====================================================================
def popup(title, content):
    message_dialog(title=title, text=content)
    return content


def format_register_popup(title, base_addr, values):
    """Pretty popup output for registers."""
    out = f"{title}\n\n"
    out += "Addr    Int      HEX      ASCII\n"
    out += "----------------------------------\n"

    for i, v in enumerate(values):
        addr = base_addr + i
        hexv = f"{v:04X}"
        asc = chr(v & 0xFF) if 32 <= (v & 0xFF) <= 126 else "."
        out += f"{addr:<7} {v:<8} {hexv:<8} {asc}\n"

    return out


def is_csr_format(text):
    return "," in text or "-" in text


# =====================================================================
# DEBUG
# =====================================================================
@ctmodbus.command
def do_debug(cmd: str):
    """Run a python expression."""
    try:
        result = eval(cmd)
    except Exception as e:
        result = e
    return popup("Debug", str(result))


# =====================================================================
# CONNECTION COMMANDS
# =====================================================================
@ctmodbus.command
def do_connect():
    """Show available serial devices + listening ports."""
    txt = "Connected Serial Devices\n"
    txt += common.list_serial_devices()
    txt += "\n\nListening on localhost:\n"
    txt += common.list_listening_ports()
    return popup("Suggestions", txt)


@ctmodbus.command
def do_connect_ascii(device: str):
    """Connect to Modbus ASCII serial."""
    assert ctmodbus.session is None, "Session already open."
    dev = common.validate_serial_device(device)
    s = ModbusSerialClient(method="ascii", port=dev, timeout=1)
    assert s.connect(), f"Could not connect to {dev}"
    ctmodbus.session = s
    return popup("ASCII Connected", f"ASCII session opened with {dev}")


@ctmodbus.command
def do_connect_rtu(device: str):
    """Connect to Modbus RTU serial."""
    assert ctmodbus.session is None, "Session already open."
    dev = common.validate_serial_device(device)
    s = ModbusSerialClient(method="rtu", port=dev, timeout=1)
    assert s.connect(), f"Could not connect to {dev}"
    ctmodbus.session = s
    return popup("RTU Connected", f"RTU session opened with {dev}")


@ctmodbus.command
def do_connect_tcp(target: str):
    """Connect to Modbus TCP: <host:port>"""
    assert ctmodbus.session is None, "Session already open."
    host, port = common.parse_ip_port(target)
    s = ModbusTcpClient(host, port, timeout=3)
    assert s.connect(), f"Could not connect to {host}:{port}"
    ctmodbus.session = s
    return popup("TCP Connected", f"TCP session opened with {host}:{port}")


@ctmodbus.command
def do_connect_udp(target: str):
    """Connect to Modbus UDP: <host:port>"""
    assert ctmodbus.session is None, "Session already open."
    host, port = common.parse_ip_port(target)
    s = ModbusUdpClient(host, port, timeout=3)
    assert s.connect(), f"Could not connect to {host}:{port}"
    ctmodbus.session = s
    return popup("UDP Connected", f"UDP session opened with {host}:{port}")


@ctmodbus.command
def do_close():
    """Close a Modbus session."""
    assert ctmodbus.session, "No session open."
    ctmodbus.session.close()
    ctmodbus.session = None
    return popup("Closed", "Modbus session closed.")


# =====================================================================
#  UNIFIED READ SYSTEM
# =====================================================================
@ctmodbus.command
def do_read(kind: str, a: str = None, b: str = None):
    """
    Unified read system.
    Supports:
      read holding 1 100
      read holdingRegisters 1 100
      read holding 1,10-20,50
    """

    assert ctmodbus.session, "No session open."

    kind = kind.lower()

    # Map aliases
    if kind in ["holding", "holdingregisters", "horeg"]:
        read_type = "holding"
    elif kind in ["input", "inputregisters", "inreg"]:
        read_type = "input"
    elif kind in ["coils", "coil"]:
        read_type = "coils"
    elif kind in ["discrete", "discreteinputs"]:
        read_type = "discrete"
    else:
        return popup("Error", f"Unknown read category: {kind}")

    # Determine CSR or addr/count
    if a is None:
        return popup("Error", "Missing address or range")

    if is_csr_format(a):
        csr = a
        return read_csr_dispatch(read_type, csr)
    else:
        # Normal addr + count
        if b is None:
            count = 1
        else:
            count = int(b)
        start = int(a)
        return read_simple_dispatch(read_type, start, count)


def read_simple_dispatch(kind, start, count):
    """Normal: read holding 1 100"""

    if kind == "holding":
        resp = ctmodbus.session.read_holding_registers(start, count, unit=unit_id)
        registers = resp.registers
        content = format_register_popup(f"Holding Registers {start}-{start+count-1}", start, registers)
        return popup("Read Holding", content)

    if kind == "input":
        resp = ctmodbus.session.read_input_registers(start, count, unit=unit_id)
        registers = resp.registers
        content = format_register_popup(f"Input Registers {start}-{start+count-1}", start, registers)
        return popup("Read Input", content)

    if kind == "coils":
        resp = ctmodbus.session.read_coils(start, count, unit=unit_id)
        vals = [int(x) for x in resp.bits]
        txt = "\n".join(f"{start+i}: {vals[i]}" for i in range(len(vals)))
        return popup("Read Coils", txt)

    if kind == "discrete":
        resp = ctmodbus.session.read_discrete_inputs(start, count, unit=unit_id)
        vals = [int(x) for x in resp.bits]
        txt = "\n".join(f"{start+i}: {vals[i]}" for i in range(len(vals)))
        return popup("Read Discrete", txt)


def read_csr_dispatch(kind, csr):
    """CSR parsing: 1,10-20,50"""
    txt = ""

    for start, stop, count in common.csr_to_ranges(csr, 125):
        if kind == "holding":
            resp = ctmodbus.session.read_holding_registers(start, count, unit=unit_id)
            registers = resp.registers
            txt += format_register_popup(f"Holding {start}-{stop-1}", start, registers)
        elif kind == "input":
            resp = ctmodbus.session.read_input_registers(start, count, unit=unit_id)
            registers = resp.registers
            txt += format_register_popup(f"Input {start}-{stop-1}", start, registers)
        elif kind == "coils":
            resp = ctmodbus.session.read_coils(start, count, unit=unit_id)
            vals = [int(x) for x in resp.bits]
            txt += f"Coils {start}-{stop-1}\n" + "\n".join(f"{start+i}: {vals[i]}" for i in range(len(vals))) + "\n\n"
        elif kind == "discrete":
            resp = ctmodbus.session.read_discrete_inputs(start, count, unit=unit_id)
            vals = [int(x) for x in resp.bits]
            txt += f"Discrete {start}-{stop-1}\n" + "\n".join(f"{start+i}: {vals[i]}" for i in range(len(vals))) + "\n\n"

    return popup("Read (CSR)", txt)


# =====================================================================
# WRITE COMMANDS
# =====================================================================
@ctmodbus.command
def do_write():
    """Namespace: write commands."""


@ctmodbus.command
def do_write_register(address: int, values: GreedyInt):
    """Write register(s): <addr> <value...>"""
    assert ctmodbus.session, "No session open."

    if len(values) == 1:
        ctmodbus.session.write_register(address, values[0], unit=unit_id)
    else:
        ctmodbus.session.write_registers(address, values, unit=unit_id)

    txt = f"Wrote registers starting at {address}: {values}"
    return popup("Write Register", txt)


@ctmodbus.command
def do_write_coil(address: int, values: GreedyBin):
    """Write coil(s): <addr> <0/1...>"""
    assert ctmodbus.session, "No session open."

    if len(values) == 1:
        ctmodbus.session.write_coil(address, values[0], unit=unit_id)
    else:
        ctmodbus.session.write_coils(address, values, unit=unit_id)

    txt = f"Wrote coils starting at {address}: {values}"
    return popup("Write Coil", txt)


# =====================================================================
# MAIN
# =====================================================================
def main():
    ctmodbus.run()


if __name__ == "__main__":
    main()
