"""
ctmodbus – Complete patched command module
Fully compatible with ctui 0.7.x and pymodbus 2.5.x
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
from ctmodbus.completer import CommandCompleter


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

# enable safer completer
ctmodbus.completer = CommandCompleter(ctmodbus.commands)


# ============================================================
# DEBUG
# ============================================================
@ctmodbus.command
def do_debug(cmd: str):
    """Execute Python expression inside ctmodbus"""
    try:
        result = eval(cmd)
        message_dialog(title="Debug Output", text=str(result))
    except Exception as e:
        message_dialog(title="Debug Error", text=str(e))


# ============================================================
# CONNECTION COMMANDS
# ============================================================
@ctmodbus.command
def do_connect_tcp(target: str):
    """Connect to a Modbus TCP device. Usage: connect tcp 127.0.0.1:502"""
    assert ctmodbus.session is None, "Session already open."

    host, port = common.parse_ip_port(target)
    s = ModbusTcpClient(host, port, timeout=3)

    assert s.connect(), f"Could not connect to {host}:{port}"
    ctmodbus.session = s
    return f"TCP session OPENED with {host}:{port}"


@ctmodbus.command
def do_connect_udp(target: str):
    """Connect to a Modbus UDP device."""
    assert ctmodbus.session is None, "Session already open."

    host, port = common.parse_ip_port(target)
    s = ModbusUdpClient(host, port, timeout=3)

    assert s.connect(), f"Could not connect to {host}:{port}"
    ctmodbus.session = s
    return f"UDP session OPENED with {host}:{port}"


@ctmodbus.command
def do_close():
    """Close active Modbus session."""
    assert ctmodbus.session, "No session open."
    ctmodbus.session.close()
    ctmodbus.session = None
    return "Session CLOSED."


# ============================================================
# READ COMMANDS
# ============================================================
def _format_result(title, base, values):
    text = f"{title}:\n"
    for i, v in enumerate(values):
        text += f"  {base + i}: {v}\n"
    return text


@ctmodbus.command
def do_read_id():
    """Read Modbus Device Identification."""
    assert ctmodbus.session, "No session open."

    resp = ctmodbus.session.execute(ReadDeviceInformationRequest(unit=unit_id))
    assert not resp.isError(), "Device does not support Read ID."

    text = "Device Identification:\n"
    for i, val in enumerate(resp.information):
        text += f"  {i}: {val}\n"

    return text


@ctmodbus.command
def do_read_coils(address: int, count: int = 1):
    """Read coils. Usage: read coils 0 10"""
    assert ctmodbus.session, "No session open."

    resp = ctmodbus.session.read_coils(address, count, unit=unit_id)
    if resp.isError():
        return "Read error."

    return _format_result("Coils", address, resp.bits[:count])


@ctmodbus.command
def do_read_discrete(address: int, count: int = 1):
    """Read discrete inputs. Usage: read discrete 0 10"""
    assert ctmodbus.session, "No session open."

    resp = ctmodbus.session.read_discrete_inputs(address, count, unit=unit_id)
    if resp.isError():
        return "Read error."

    return _format_result("Discrete Inputs", address, resp.bits[:count])


@ctmodbus.command
def do_read_holding(address: int, count: int = 1):
    """Read holding registers. Usage: read holding 0 10"""
    assert ctmodbus.session, "No session open."

    resp = ctmodbus.session.read_holding_registers(address, count, unit=unit_id)
    if resp.isError():
        return "Read error."

    return _format_result("Holding Registers", address, resp.registers)


@ctmodbus.command
def do_read_input(address: int, count: int = 1):
    """Read input registers. Usage: read input 0 10"""
    assert ctmodbus.session, "No session open."

    resp = ctmodbus.session.read_input_registers(address, count, unit=unit_id)
    if resp.isError():
        return "Read error."

    return _format_result("Input Registers", address, resp.registers)


# ============================================================
# WRITE COMMANDS
# ============================================================
@ctmodbus.command
def do_write_coils(address: int, *values):
    """Write coils. Usage: write coils 0 1 0 1"""
    assert ctmodbus.session, "No session open."

    parsed = common.parse_value_list(" ".join(values))
    if isinstance(parsed, int):
        parsed = [parsed]

    if len(parsed) == 1:
        ctmodbus.session.write_coil(address, parsed[0], unit=unit_id)
    else:
        ctmodbus.session.write_coils(address, parsed, unit=unit_id)

    return f"Wrote {parsed} starting at {address}"


@ctmodbus.command
def do_write_holdingRegisters(address: int, *values):
    """Write holding registers."""
    assert ctmodbus.session, "No session open."

    parsed = common.parse_value_list(" ".join(values))
    if isinstance(parsed, bytes):
        parsed = list(parsed)
    elif isinstance(parsed, int):
        parsed = [parsed]

    if len(parsed) == 1:
        ctmodbus.session.write_register(address, parsed[0], unit=unit_id)
    else:
        ctmodbus.session.write_registers(address, parsed, unit=unit_id)

    return f"Wrote {parsed} starting at {address}"


# ============================================================
# POLLING
# ============================================================
def polling_worker(session, mode, address, count, interval):
    while True:
        try:
            if mode == "coils":
                resp = session.read_coils(address, count, unit=unit_id)
                print(_format_result("Poll Coils", address, resp.bits[:count]))

            elif mode == "holding":
                resp = session.read_holding_registers(address, count, unit=unit_id)
                print(_format_result("Poll Holding", address, resp.registers))

        except Exception as e:
            print(f"[POLL ERROR] {e}")

        time.sleep(interval)


@ctmodbus.command
def do_poll(mode: str, address: int, count: int, interval: int):
    """Poll values. Example: poll coils 0 10 1"""
    assert ctmodbus.session, "No session open."

    valid = ["coils", "holding"]
    if mode not in valid:
        return f"Mode must be one of {valid}"

    thread = threading.Thread(
        target=polling_worker,
        args=(ctmodbus.session, mode, address, count, interval),
        daemon=True
    )
    thread.start()

    return f"Polling {mode} every {interval}s"


# ============================================================
# MAIN ENTRY
# ============================================================
def main():
    ctmodbus.run()


if __name__ == "__main__":
    main()
