"""
Control Things Modbus – CTModbus (Fixed & Improved)
Original CTModbus command behaviour restored.
Bug-fixes applied: popup formatting, read functions, and register/coil handling.
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
    ModbusUdpClient,
)

from pymodbus.mei_message import ReadDeviceInformationRequest
from ctmodbus import common


# =====================================================================
# UI SETUP
# =====================================================================
ctmodbus = Ctui()
ctmodbus.name = "ctmodbus"
ctmodbus.version = get_distribution("ctmodbus").version
ctmodbus.prompt = "ctmodbus> "
ctmodbus.output_text = ""     # fixes repeated scroll output

ctmodbus.session = None
unit_id = 1


# =====================================================================
# HELPERS
# =====================================================================
def popup(title, text):
    """Display a popup window."""
    message_dialog(title=title, text=text)
    return text


def format_reg_table(title, base, values):
    """Pretty formatted popup table for registers."""
    out = f"{title}\n\n"
    out += "Addr    Int      HEX      ASCII\n"
    out += "----------------------------------\n"

    for i, v in enumerate(values):
        addr = base + i
        hexv = f"{v:04X}"
        asc = chr(v & 0xFF) if 32 <= (v & 0xFF) <= 126 else "."
        out += f"{addr:<7}{v:<9}{hexv:<9}{asc}\n"

    return out


# =====================================================================
# DEBUG
# =====================================================================
@ctmodbus.command
def do_debug(cmd: str):
    """Run Python code inside CTModbus."""
    try:
        result = eval(cmd)
    except Exception as e:
        result = e
    return popup("Debug Output", str(result))


# =====================================================================
# CONNECTION COMMANDS
# =====================================================================
@ctmodbus.command
def do_connect():
    """List available serial devices & open ports."""
    txt = "Connected Serial Devices:\n"
    txt += common.list_serial_devices()
    txt += "\nListening ports on localhost:\n"
    txt += common.list_listening_ports()
    return popup("Connection Menu", txt)


@ctmodbus.command
def do_connect_ascii(device: str):
    """Connect to Modbus ASCII."""
    assert ctmodbus.session is None, "Session already open."
    dev = common.validate_serial_device(device)
    cli = ModbusSerialClient(method="ascii", port=dev, timeout=1)
    assert cli.connect(), f"Could not connect to {dev}"
    ctmodbus.session = cli
    return popup("ASCII Connected", f"Session open with {dev}")


@ctmodbus.command
def do_connect_rtu(device: str):
    """Connect to Modbus RTU."""
    assert ctmodbus.session is None, "Session already open."
    dev = common.validate_serial_device(device)
    cli = ModbusSerialClient(method="rtu", port=dev, timeout=1)
    assert cli.connect(), f"Could not connect to {dev}"
    ctmodbus.session = cli
    return popup("RTU Connected", f"Session open with {dev}")


@ctmodbus.command
def do_connect_tcp(target: str):
    """Connect to Modbus TCP."""
    assert ctmodbus.session is None, "Session already open."
    host, port = common.parse_ip_port(target)
    cli = ModbusTcpClient(host, port, timeout=3)
    assert cli.connect(), f"Could not connect to {host}:{port}"
    ctmodbus.session = cli
    return popup("TCP Connected", f"Session open with {host}:{port}")


@ctmodbus.command
def do_connect_udp(target: str):
    """Connect to Modbus UDP."""
    assert ctmodbus.session is None, "Session already open."
    host, port = common.parse_ip_port(target)
    cli = ModbusUdpClient(host, port, timeout=3)
    assert cli.connect(), f"Could not connect to {host}:{port}"
    ctmodbus.session = cli
    return popup("UDP Connected", f"Session open with {host}:{port}")


@ctmodbus.command
def do_close():
    """Close current Modbus session."""
    assert ctmodbus.session, "No session open."
    ctmodbus.session.close()
    ctmodbus.session = None
    return popup("Closed", "Session closed.")


# =====================================================================
# READ – ORIGINAL CTMODBUS BEHAVIOUR
# =====================================================================

@ctmodbus.command
def do_read_id():
    """Read device identification."""
    assert ctmodbus.session, "No session open."

    resp = ctmodbus.session.execute(ReadDeviceInformationRequest(unit=unit_id))
    assert not resp.isError(), "Device does not support ID read."

    txt = "Device Identification:\n\n"
    for i, v in enumerate(resp.information):
        txt += f"{i}: {v}\n"

    return popup("Read ID", txt)


@ctmodbus.command
def do_read_coils(start: int, count: int = 1):
    """Read coils: read_coils <start> <count>"""
    assert ctmodbus.session, "No session open."

    resp = ctmodbus.session.read_coils(start, count, unit=unit_id)
    vals = [int(x) for x in resp.bits[:count]]

    txt = "\n".join(f"{start+i}: {vals[i]}" for i in range(len(vals)))

    return popup(f"Read Coils {start}-{start+count-1}", txt)


@ctmodbus.command
def do_read_discreteInputs(start: int, count: int = 1):
    """Read discrete inputs."""
    assert ctmodbus.session, "No session open."

    resp = ctmodbus.session.read_discrete_inputs(start, count, unit=unit_id)
    vals = [int(x) for x in resp.bits[:count]]

    txt = "\n".join(f"{start+i}: {vals[i]}" for i in range(len(vals)))

    return popup(f"Read Discrete Inputs {start}-{start+count-1}", txt)


@ctmodbus.command
def do_read_inputRegisters(start: int, count: int = 1):
    """Read input registers."""
    assert ctmodbus.session, "No session open."

    resp = ctmodbus.session.read_input_registers(start, count, unit=unit_id)
    regs = resp.registers

    return popup(
        "Read Input Registers",
        format_reg_table(f"Input Registers {start}-{start+count-1}", start, regs),
    )


@ctmodbus.command
def do_read_holdingRegisters(start: int, count: int = 1):
    """Read holding registers."""
    assert ctmodbus.session, "No session open."

    resp = ctmodbus.session.read_holding_registers(start, count, unit=unit_id)
    regs = resp.registers

    return popup(
        "Read Holding Registers",
        format_reg_table(f"Holding Registers {start}-{start+count-1}", start, regs),
    )


# =====================================================================
# WRITE COMMANDS
# =====================================================================
@ctmodbus.command
def do_write_register(address: int, values: GreedyInt):
    """Write register(s)."""
    assert ctmodbus.session, "No session open."

    if len(values) == 1:
        ctmodbus.session.write_register(address, values[0], unit=unit_id)
    else:
        ctmodbus.session.write_registers(address, values, unit=unit_id)

    return popup("Write Register", f"Wrote registers starting at {address}: {values}")


@ctmodbus.command
def do_write_coil(address: int, values: GreedyBin):
    """Write coil(s)."""
    assert ctmodbus.session, "No session open."

    if len(values) == 1:
        ctmodbus.session.write_coil(address, values[0], unit=unit_id)
    else:
        ctmodbus.session.write_coils(address, values, unit=unit_id)

    return popup("Write Coil", f"Wrote coils starting at {address}: {values}")


# =====================================================================
# MAIN
# =====================================================================
def main():
    ctmodbus.run()


if __name__ == "__main__":
    main()
