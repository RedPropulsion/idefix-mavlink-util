#!/usr/bin/env python3
"""MAVLink command simulator for the ObeliCS <-> Idefix link.

The same program can run as the receiver on Idefix or as the simulator on the
PC.  It deliberately uses standard COMMAND_LONG / COMMAND_ACK messages so the
first Ethernet test does not require a custom MAVLink dialect.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Iterable

# Must be set before importing pymavlink. It enables MAVLink 2 extension fields,
# including the ACK destination system and component.
os.environ.setdefault("MAVLINK20", "1")

try:
    from pymavlink import mavutil
except ImportError:  # pragma: no cover - exercised only on an unprepared host
    mavutil = None


# Values from the MAVLink common dialect (MAV_CMD_USER_1 and MAV_CMD_USER_2).
# They are intentionally kept in one place so they can later be replaced by
# project-specific messages or commands.
SERVO_COMMAND = 31_010
LED_COMMAND = 31_011
DEFAULT_PORT = 14_550


class ServoMode(IntEnum):
    SERVO_NONE = 0
    SERVO_WIGGLE = 1
    SERVO_SWEEP = 2
    SERVO_HELLO = 3


class LedMode(IntEnum):
    # These numeric values match enum demo_neopixel_mode in the supplied menu.c.
    NONE = 0
    SPIN = 1
    BLINK = 2
    BOUNCE = 3


MODE_TYPES: dict[str, type[IntEnum]] = {
    "servo": ServoMode,
    "led": LedMode,
}

COMMANDS = {
    "servo": SERVO_COMMAND,
    "led": LED_COMMAND,
}


@dataclass(frozen=True)
class DecodedCommand:
    actuator: str
    mode: IntEnum


def require_pymavlink() -> Any:
    if mavutil is None:
        raise SystemExit(
            "Dipendenza mancante: installa pymavlink con "
            "'python3 -m pip install -r requirements.txt'."
        )
    return mavutil


def parse_mode(actuator: str, value: str) -> IntEnum:
    """Parse friendly names such as 'wiggle' or the full 'SERVO_WIGGLE'."""
    enum_type = MODE_TYPES[actuator]
    normalized = value.strip().upper().replace("-", "_")
    if actuator == "servo" and not normalized.startswith("SERVO_"):
        normalized = f"SERVO_{normalized}"
    try:
        return enum_type[normalized]
    except KeyError as exc:
        choices = ", ".join(mode.name.lower() for mode in enum_type)
        raise ValueError(f"modalita {actuator!r} non valida: {value!r}; usa {choices}") from exc


def decode_command(command: int, param1: float) -> DecodedCommand:
    if command == SERVO_COMMAND:
        actuator, enum_type = "servo", ServoMode
    elif command == LED_COMMAND:
        actuator, enum_type = "led", LedMode
    else:
        raise LookupError(f"comando MAVLink non supportato: {command}")

    rounded = round(param1)
    if abs(param1 - rounded) > 1e-6:
        raise ValueError(f"param1 deve essere intero, ricevuto {param1}")
    try:
        return DecodedCommand(actuator, enum_type(rounded))
    except ValueError as exc:
        raise ValueError(f"modalita {actuator} fuori intervallo: {rounded}") from exc


def result_name(result: int) -> str:
    util = require_pymavlink()
    entry = util.mavlink.enums.get("MAV_RESULT", {}).get(result)
    return entry.name if entry else f"MAV_RESULT_{result}"


def open_sender(host: str, port: int, system_id: int, component_id: int) -> Any:
    util = require_pymavlink()
    return util.mavlink_connection(
        f"udpout:{host}:{port}",
        source_system=system_id,
        source_component=component_id,
        dialect="common",
    )


def send_heartbeat(connection: Any) -> None:
    util = require_pymavlink()
    connection.mav.heartbeat_send(
        util.mavlink.MAV_TYPE_GCS,
        util.mavlink.MAV_AUTOPILOT_INVALID,
        0,
        0,
        util.mavlink.MAV_STATE_ACTIVE,
    )


def wait_for_ack(
    connection: Any,
    command: int,
    timeout: float,
    own_system_id: int,
    own_component_id: int,
) -> Any | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        ack = connection.recv_match(type="COMMAND_ACK", blocking=True, timeout=remaining)
        if ack is None:
            return None
        if ack.command != command:
            continue
        # Zero means broadcast or a MAVLink 1 peer without target extension fields.
        if getattr(ack, "target_system", 0) not in (0, own_system_id):
            continue
        if getattr(ack, "target_component", 0) not in (0, own_component_id):
            continue
        return ack
    return None


def send_one(
    connection: Any,
    actuator: str,
    mode: IntEnum,
    target_system: int,
    target_component: int,
    own_system_id: int,
    own_component_id: int,
    timeout: float,
    retries: int,
) -> bool:
    command = COMMANDS[actuator]
    for attempt in range(retries + 1):
        send_heartbeat(connection)
        connection.mav.command_long_send(
            target_system,
            target_component,
            command,
            attempt,
            float(mode.value),
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        )
        print(
            f"TX  {actuator.upper():5s} {mode.name:13s} "
            f"command={command} param1={mode.value} tentativo={attempt + 1}"
        )
        ack = wait_for_ack(
            connection, command, timeout, own_system_id, own_component_id
        )
        if ack is not None:
            name = result_name(ack.result)
            print(f"ACK {name} da system={ack.get_srcSystem()} component={ack.get_srcComponent()}")
            return ack.result == require_pymavlink().mavlink.MAV_RESULT_ACCEPTED
        print(f"--- nessun ACK entro {timeout:.1f} s")
    return False


def send_ack(connection: Any, message: Any, result: int) -> None:
    connection.mav.command_ack_send(
        message.command,
        result,
        progress=0,
        result_param2=0,
        target_system=message.get_srcSystem(),
        target_component=message.get_srcComponent(),
    )


def addressed_to_us(message: Any, system_id: int, component_id: int) -> bool:
    return message.target_system in (0, system_id) and message.target_component in (
        0,
        component_id,
    )


def listen(args: argparse.Namespace) -> int:
    util = require_pymavlink()
    connection = util.mavlink_connection(
        f"udpin:{args.bind}:{args.port}",
        source_system=args.system_id,
        source_component=args.component_id,
        dialect="common",
    )
    print(
        f"Idefix in ascolto su udp://{args.bind}:{args.port} "
        f"come system={args.system_id} component={args.component_id}"
    )
    print("Ctrl+C per terminare.")
    accepted = 0
    try:
        while args.count == 0 or accepted < args.count:
            message = connection.recv_match(type="COMMAND_LONG", blocking=True, timeout=1.0)
            if message is None:
                continue
            if not addressed_to_us(message, args.system_id, args.component_id):
                continue
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            try:
                decoded = decode_command(message.command, message.param1)
            except LookupError as exc:
                print(f"RX  {timestamp} RIFIUTATO: {exc}")
                send_ack(connection, message, util.mavlink.MAV_RESULT_UNSUPPORTED)
                continue
            except ValueError as exc:
                print(f"RX  {timestamp} RIFIUTATO: {exc}")
                send_ack(connection, message, util.mavlink.MAV_RESULT_DENIED)
                continue

            print(
                f"RX  {timestamp} {decoded.actuator.upper():5s} "
                f"{decoded.mode.name:13s} da system={message.get_srcSystem()} "
                f"component={message.get_srcComponent()} seq={message.get_seq()}"
            )
            send_ack(connection, message, util.mavlink.MAV_RESULT_ACCEPTED)
            accepted += 1
    except KeyboardInterrupt:
        print("\nRicevitore arrestato.")
    finally:
        connection.close()
    return 0


def selected_commands(args: argparse.Namespace) -> Iterable[tuple[str, IntEnum]]:
    if args.action == "test-all":
        for actuator, enum_type in MODE_TYPES.items():
            for mode in enum_type:
                yield actuator, mode
    else:
        yield args.actuator, parse_mode(args.actuator, args.mode)


def send(args: argparse.Namespace) -> int:
    connection = open_sender(
        args.host, args.port, args.system_id, args.component_id
    )
    success = True
    try:
        for actuator, mode in selected_commands(args):
            ok = send_one(
                connection,
                actuator,
                mode,
                args.target_system,
                args.target_component,
                args.system_id,
                args.component_id,
                args.timeout,
                args.retries,
            )
            success = ok and success
    except ValueError as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 2
    finally:
        connection.close()
    return 0 if success else 1


def interactive(args: argparse.Namespace) -> int:
    connection = open_sender(
        args.host, args.port, args.system_id, args.component_id
    )
    print("Comandi: servo <none|wiggle|sweep|hello>, led <none|spin|blink|bounce>, quit")
    try:
        while True:
            try:
                line = input("obeliCS> ").strip()
            except EOFError:
                break
            if not line:
                continue
            if line.lower() in {"quit", "exit", "q"}:
                break
            parts = line.split()
            if len(parts) != 2 or parts[0].lower() not in MODE_TYPES:
                print("Formato non valido. Esempio: servo wiggle")
                continue
            actuator = parts[0].lower()
            try:
                mode = parse_mode(actuator, parts[1])
            except ValueError as exc:
                print(f"Errore: {exc}")
                continue
            send_one(
                connection,
                actuator,
                mode,
                args.target_system,
                args.target_component,
                args.system_id,
                args.component_id,
                args.timeout,
                args.retries,
            )
    except KeyboardInterrupt:
        print()
    finally:
        connection.close()
    return 0


def add_sender_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", required=True, help="indirizzo IP Ethernet di Idefix")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--system-id", type=int, default=42, help="system ID del PC")
    parser.add_argument("--component-id", type=int, default=191, help="component ID del PC")
    parser.add_argument("--target-system", type=int, default=1)
    parser.add_argument("--target-component", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--retries", type=int, default=2)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Simulatore ObeliCS e verificatore MAVLink per Idefix"
    )
    subparsers = parser.add_subparsers(dest="action", required=True)

    receiver = subparsers.add_parser("listen", help="riceve e conferma i comandi su Idefix")
    receiver.add_argument("--bind", default="0.0.0.0")
    receiver.add_argument("--port", type=int, default=DEFAULT_PORT)
    receiver.add_argument("--system-id", type=int, default=1)
    receiver.add_argument("--component-id", type=int, default=1)
    receiver.add_argument(
        "--count", type=int, default=0, help="esce dopo N comandi accettati; 0 = sempre"
    )
    receiver.set_defaults(function=listen)

    sender = subparsers.add_parser("send", help="invia un singolo comando dal PC")
    add_sender_options(sender)
    sender.add_argument("actuator", choices=sorted(MODE_TYPES))
    sender.add_argument("mode")
    sender.set_defaults(function=send)

    test_all = subparsers.add_parser("test-all", help="prova in sequenza tutte le modalita")
    add_sender_options(test_all)
    test_all.set_defaults(function=send)

    shell = subparsers.add_parser("interactive", help="apre una console interattiva sul PC")
    add_sender_options(shell)
    shell.set_defaults(function=interactive)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if getattr(args, "retries", 0) < 0:
        raise SystemExit("--retries non puo essere negativo")
    if getattr(args, "timeout", 1.0) <= 0:
        raise SystemExit("--timeout deve essere positivo")
    if getattr(args, "count", 0) < 0:
        raise SystemExit("--count non puo essere negativo")
    return args.function(args)


if __name__ == "__main__":
    raise SystemExit(main())
