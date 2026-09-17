import unittest

from idefix_mavlink import (
    MAV_CMD_OBELICS_LED_BLINK,
    MAV_CMD_OBELICS_LED_BOUNCE,
    MAV_CMD_OBELICS_LED_OFF,
    MAV_CMD_OBELICS_LED_SPIN,
    MAV_CMD_OBELICS_SERVO_HELLO,
    MAV_CMD_OBELICS_SERVO_OFF,
    MAV_CMD_OBELICS_SERVO_SWEEP,
    MAV_CMD_OBELICS_SERVO_WIGGLE,
    MODE_TYPES,
    LedMode,
    ServoMode,
    decode_command,
    parse_mode,
)


class ProtocolTests(unittest.TestCase):
    def test_all_eight_commands_are_unique_uint16_values(self):
        command_ids = {
            mode.value
            for enum_type in MODE_TYPES.values()
            for mode in enum_type
        }
        self.assertEqual(len(command_ids), 8)
        self.assertTrue(all(0 <= command_id <= 65_535 for command_id in command_ids))

    def test_servo_names(self):
        self.assertEqual(parse_mode("servo", "wiggle"), ServoMode.SERVO_WIGGLE)
        self.assertEqual(parse_mode("servo", "SERVO_HELLO"), ServoMode.SERVO_HELLO)
        self.assertEqual(parse_mode("servo", "none"), ServoMode.SERVO_OFF)

    def test_command_ids_match_obelics_xml(self):
        self.assertEqual(ServoMode.SERVO_OFF.value, MAV_CMD_OBELICS_SERVO_OFF)
        self.assertEqual(ServoMode.SERVO_WIGGLE.value, MAV_CMD_OBELICS_SERVO_WIGGLE)
        self.assertEqual(ServoMode.SERVO_SWEEP.value, MAV_CMD_OBELICS_SERVO_SWEEP)
        self.assertEqual(ServoMode.SERVO_HELLO.value, MAV_CMD_OBELICS_SERVO_HELLO)
        self.assertEqual(LedMode.LED_OFF.value, MAV_CMD_OBELICS_LED_OFF)
        self.assertEqual(LedMode.LED_BOUNCE.value, MAV_CMD_OBELICS_LED_BOUNCE)
        self.assertEqual(LedMode.LED_SPIN.value, MAV_CMD_OBELICS_LED_SPIN)
        self.assertEqual(LedMode.LED_BLINK.value, MAV_CMD_OBELICS_LED_BLINK)

    def test_decode(self):
        self.assertEqual(
            decode_command(MAV_CMD_OBELICS_SERVO_SWEEP).mode,
            ServoMode.SERVO_SWEEP,
        )
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


if __name__ == "__main__":
    unittest.main()
