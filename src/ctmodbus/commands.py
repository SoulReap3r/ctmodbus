"""
Control Things Modbus Toolkit (ctmodbus)
Clean, stable version – no custom completer.
Compatible with ctui 0.7.x and pymodbus 2.5.x.
"""

import threading
import time
from datetime import datetime

from pkg_resources import get_distribution
from ctui import Ctui
from ctui.dialogs import message_dialog

from pymodbus.client.sync import (
    ModbusSerialClient,
    ModbusTcpClient,
    ModbusUdpClient
)
from pymodbus.mei_message import ReadDeviceInformationRequest

from ctmodbus import common
from ctmodbus.tags import TagManager


# ============================================================
# CTUI SETUP
# ============================================================
ctmodbus = Ctui()
ctmodbus.name = "ctmodbus"
ctmodbus.version = get_distribution("ctmodbus").version
ctmodbus.description = "Modbus penetration-testing toolkit"
ctmodbus.prompt = "ctmodbus> "

ctmodbus.session = None
unit_id = 1
tag_manager = TagManager()


# ============================================================
# DEBUG COMMAND
# ============================================================
@ctmodbus.command
def do_debug(cmd: str):
    """Execute Python expression inside ctmodbus."""
    try:
        result = eval(cmd)
        message_dialog(title="Debug Output", text=str(result))
    except Exception as e:
        message_dialog(title="Debug Error", text=str(e))


# ============================================================
# CONNECTION COMMANDS
# ============================================================
@ctmodbus.command
def do_connect():
    """Show available serial devices and listening ports."""
    text = "Serial Devices:\n"
    text += common.list_serial_devices()
    text += "\n\nListening Ports:\n"
    text += common.list_listening_ports()
    message_dialog(title="System Info", text=text)


@ctmodbus.command
def do_connect_tcp(host_port: str):
    """Connect to a Modbus TCP device. Usage: connect_tcp 127.0.0.1:502"""
    assert ctmodbus.session is None, "Session already open."

    host, port = common.parse_ip_port(host_port)
    s = ModbusTcpClient(host, port, timeout=3)

    assert s.connect(), f"Could not connect to {host}:{port}"
    ctmodbus.session = s
    return f"TCP session OPENED with {host}:{port}"


@ctmodbus.command
def do_connect_udp(host_port: str):
    """Connect to a Modbus UDP device."""
    assert ctmodbus.session is None, "Session already open."

    host, port = common.parse_ip_port(host_port)
    s = ModbusUdpClient(host, port, timeout=3)

    assert s.connect(), f"Could not connect to {host}:{port}"
    ctmodbus.session = s
    return f"UDP session OPENED with {host}:{port}"


@ctmodbus.command
def do_close():
    """Close the active Modbus session."""
    assert ctmodbus.session, "No session open."
    ctmodbus.session.close()
    ctmodbus.session = None
    return "Session CLOSED."


# ============================================================
# READ COMMANDS
# ============================================================
@ctmodbus.command
def do_read_id():
    """Read Modbus Device Identification."""
    assert ctmodbus.session, "No session open."

    resp = ctmodbus.session.execute(ReadDeviceInformationRequest(unit=1))
    assert not resp.isError(), "Device does not support Read ID."

    keys = [
        "VendorName", "ProductCode", "MajorMinorRevision",
        "VendorUrl", "ProductName", "ModelName", "UserApplicationName"
    ]

    text = ""
    for i, val in enumerate(resp.information):
        label = keys[i] if i < len(keys) else f"ObjectID {i}"
        text += f"{label}: {val}\n"

    return text


# ============================================================
# WRITE COMMANDS
# ============================================================
@ctmodbus.command
def do_write_coils(address: int, *values):
    """Write one or more coil values."""
    assert ctmodbus.session, "No open session."

    parsed = common.parse_value_list(" ".join(values))
    if isinstance(parsed, int):
        parsed = [parsed]

    if len(parsed) == 1:
        ctmodbus.session.write_coil(address, parsed[0], unit=unit_id)
        desc = "Write Single Coil"
    else:
        ctmodbus.session.write_coils(address, parsed, unit=unit_id)
        desc = "Write Multiple Coils"

    results = {address + i: v for i, v in enumerate(parsed)}
    return common.log_and_output_bits(desc, address, address + len(parsed), results)


@ctmodbus.command
def do_write_holdingRegisters(address: int, *values):
    """Write holding registers (int, string, hex)."""
    assert ctmodbus.session, "No open session."

    parsed = common.parse_value_list(" ".join(values))
    if isinstance(parsed, bytes):
        parsed = list(parsed)
    if isinstance(parsed, int):
        parsed = [parsed]

    if len(parsed) == 1:
        ctmodbus.session.write_register(address, parsed[0], unit=unit_id)
        desc = "Write Single Register"
    else:
        ctmodbus.session.write_registers(address, parsed, unit=unit_id)
        desc = "Write Multiple Registers"

    results = {address + i: v for i, v in enumerate(parsed)}
    return common.log_and_output_words(desc, address, address + len(parsed), results)


# ============================================================
# POLLING ENGINE
# ============================================================
def polling_worker(session, mode, csr, interval):
    loops = common.Loops(csr, minimum=0, maximum=65535)

    while True:
        try:
            for loop in loops:
                start, stop, count = loop["start"], loop["stop"], loop["count"]

                if mode == "coils":
                    resp = session.read_coils(start, count)
                    results = {a: int(b) for a, b in zip(range(start, stop), resp.bits)}
                    print(common.log_and_output_bits("poll coils", start, stop, results))

                elif mode == "holding_register":
                    resp = session.read_holding_registers(start, count)
                    results = {a: v for a, v in zip(range(start, stop), resp.registers)}
                    print(common.log_and_output_words("poll hreg", start, stop, results))

            time.sleep(interval)

        except Exception as e:
            print(f"[POLL ERROR] {e}")
            time.sleep(interval)


@ctmodbus.command
def do_poll(mode: str, csr: str, interval: int):
    """Poll coils/registers repeatedly. Example: poll coils 1-20 1"""
    assert ctmodbus.session, "No session open."

    valid = ["coils", "holding_register"]
    if mode not in valid:
        raise ValueError(f"Invalid type. Must be one of {valid}")

    thread = threading.Thread(
        target=polling_worker,
        args=(ctmodbus.session, mode, csr, interval),
        daemon=True
    )
    thread.start()

    return f"Polling started: {mode} {csr} every {interval}s"


# ============================================================
# MAIN ENTRY POINT
# ============================================================
def main():
    """Required for ctmodbus.exe entry point."""
    ctmodbus.run()


if __name__ == "__main__":
    main()
