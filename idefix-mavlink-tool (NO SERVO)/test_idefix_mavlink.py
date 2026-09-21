import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from types import SimpleNamespace
from unittest.mock import Mock, patch

from idefix_mavlink import (
    DEFAULT_LOCAL_PORT,
    MAV_CMD_OBELICS_LED_BLINK,
    MAV_CMD_OBELICS_LED_BOUNCE,
    MAV_CMD_OBELICS_LED_OFF,
    MAV_CMD_OBELICS_LED_SPIN,
    # MAV_CMD_OBELICS_SERVO_HELLO,
    # MAV_CMD_OBELICS_SERVO_OFF,
    # MAV_CMD_OBELICS_SERVO_SWEEP,
    # MAV_CMD_OBELICS_SERVO_WIGGLE,
    MODE_TYPES,
    LedMode,
    # ServoMode,
    build_parser,
    decode_command,
    interactive,
    open_sender,
    parse_mode,
    selected_commands,
)


class ProtocolTests(unittest.TestCase):
    @patch("idefix_mavlink.require_pymavlink")
    def test_sender_binds_fixed_local_ack_port(self, require_pymavlink):
        connection = SimpleNamespace(port=Mock(), close=Mock())
        util = SimpleNamespace(mavlink_connection=Mock(return_value=connection))
        require_pymavlink.return_value = util

        returned = open_sender(
            "192.168.10.2",
            14_550,
            "0.0.0.0",
            DEFAULT_LOCAL_PORT,
            42,
            191,
        )

        self.assertIs(returned, connection)
        connection.port.bind.assert_called_once_with(("0.0.0.0", 14_551))
        util.mavlink_connection.assert_called_once_with(
            "udpout:192.168.10.2:14550",
            source_system=42,
            source_component=191,
            dialect="common",
        )

    @patch("idefix_mavlink.require_pymavlink")
    def test_sender_closes_socket_when_local_bind_fails(self, require_pymavlink):
        port = Mock()
        port.bind.side_effect = OSError("address already in use")
        connection = SimpleNamespace(port=port, close=Mock())
        require_pymavlink.return_value = SimpleNamespace(
            mavlink_connection=Mock(return_value=connection)
        )

        with self.assertRaises(ConnectionError):
            open_sender("192.168.10.2", 14_550, "0.0.0.0", 14_551, 42, 191)

        connection.close.assert_called_once_with()

    def test_sender_cli_uses_fixed_local_ack_port_by_default(self):
        args = build_parser().parse_args(
            ["send", "--host", "192.168.10.2", "led", "bounce"]
        )
        self.assertEqual(args.bind, "0.0.0.0")
        self.assertEqual(args.local_port, 14_551)

    def test_all_four_commands_are_unique_uint16_values(self):
        command_ids = {
            mode.value
            for enum_type in MODE_TYPES.values()
            for mode in enum_type
        }
        self.assertEqual(len(command_ids), 4)
        self.assertTrue(all(0 <= command_id <= 65_535 for command_id in command_ids))

    # def test_servo_names(self):
    #     self.assertEqual(parse_mode("servo", "wiggle"), ServoMode.SERVO_WIGGLE)
    #     self.assertEqual(parse_mode("servo", "SERVO_HELLO"), ServoMode.SERVO_HELLO)
    #     self.assertEqual(parse_mode("servo", "none"), ServoMode.SERVO_OFF)

    def test_led_names(self):
        self.assertEqual(parse_mode("led", "bounce"), LedMode.LED_BOUNCE)
        self.assertEqual(parse_mode("led", "LED_SPIN"), LedMode.LED_SPIN)
        self.assertEqual(parse_mode("led", "MAV_CMD_OBELICS_LED_BLINK"), LedMode.LED_BLINK)
        self.assertEqual(parse_mode("led", "none"), LedMode.LED_OFF)

    def test_command_ids_match_obelics_xml(self):
        # self.assertEqual(ServoMode.SERVO_OFF.value, MAV_CMD_OBELICS_SERVO_OFF)
        # self.assertEqual(ServoMode.SERVO_WIGGLE.value, MAV_CMD_OBELICS_SERVO_WIGGLE)
        # self.assertEqual(ServoMode.SERVO_SWEEP.value, MAV_CMD_OBELICS_SERVO_SWEEP)
        # self.assertEqual(ServoMode.SERVO_HELLO.value, MAV_CMD_OBELICS_SERVO_HELLO)
        self.assertEqual(LedMode.LED_OFF.value, MAV_CMD_OBELICS_LED_OFF)
        self.assertEqual(LedMode.LED_BOUNCE.value, MAV_CMD_OBELICS_LED_BOUNCE)
        self.assertEqual(LedMode.LED_SPIN.value, MAV_CMD_OBELICS_LED_SPIN)
        self.assertEqual(LedMode.LED_BLINK.value, MAV_CMD_OBELICS_LED_BLINK)

    def test_decode(self):
        # self.assertEqual(
        #     decode_command(MAV_CMD_OBELICS_SERVO_SWEEP).mode,
        #     ServoMode.SERVO_SWEEP,
        # )
        self.assertEqual(
            decode_command(MAV_CMD_OBELICS_LED_BOUNCE).mode,
            LedMode.LED_BOUNCE,
        )

    def test_reject_unknown_command(self):
        with self.assertRaises(LookupError):
            decode_command(123)

    def test_reject_unknown_mode(self):
        with self.assertRaises(ValueError):
            parse_mode("led", "rainbow")

    def test_cli_rejects_servo_commands(self):
        for mode in ("off", "wiggle", "sweep", "hello"):
            with self.subTest(mode=mode), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    build_parser().parse_args(
                        ["send", "--host", "192.168.10.2", "servo", mode]
                    )
                self.assertEqual(caught.exception.code, 2)

    def test_decode_rejects_disabled_servo_ids(self):
        for command in (60_010, 60_011, 60_012, 60_013):
            with self.subTest(command=command), self.assertRaises(LookupError):
                decode_command(command)

    def test_test_all_selects_only_led_commands(self):
        args = build_parser().parse_args(["test-all", "--host", "192.168.10.2"])
        self.assertEqual(
            [(actuator, int(mode)) for actuator, mode in selected_commands(args)],
            [("led", 60_000), ("led", 60_001), ("led", 60_002), ("led", 60_003)],
        )

    @patch("idefix_mavlink.send_one")
    @patch("idefix_mavlink.open_sender")
    def test_interactive_rejects_servos_and_still_sends_leds(self, open_sender, send_one):
        args = build_parser().parse_args(["interactive", "--host", "192.168.10.2"])
        output = io.StringIO()
        with patch("builtins.input", side_effect=["servo wiggle", "servo off", "led blink", "quit"]):
            with redirect_stdout(output):
                self.assertEqual(interactive(args), 0)
        send_one.assert_called_once_with(
            open_sender.return_value, "led", LedMode.LED_BLINK,
            1, 1, 42, 191, 2.0, 2,
        )
        self.assertNotIn("servo", output.getvalue().lower())
        self.assertEqual(output.getvalue().count("Formato non valido"), 2)
        open_sender.return_value.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
