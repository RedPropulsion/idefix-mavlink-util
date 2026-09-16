import unittest

from idefix_mavlink import (
    LED_COMMAND,
    SERVO_COMMAND,
    LedMode,
    ServoMode,
    decode_command,
    parse_mode,
)


class ProtocolTests(unittest.TestCase):
    def test_servo_names(self):
        self.assertEqual(parse_mode("servo", "wiggle"), ServoMode.SERVO_WIGGLE)
        self.assertEqual(parse_mode("servo", "SERVO_HELLO"), ServoMode.SERVO_HELLO)

    def test_led_values_match_menu_c(self):
        self.assertEqual(parse_mode("led", "spin"), LedMode.SPIN)
        self.assertEqual(LedMode.SPIN.value, 1)
        self.assertEqual(LedMode.BLINK.value, 2)
        self.assertEqual(LedMode.BOUNCE.value, 3)

    def test_decode(self):
        self.assertEqual(decode_command(SERVO_COMMAND, 2.0).mode, ServoMode.SERVO_SWEEP)
        self.assertEqual(decode_command(LED_COMMAND, 3.0).mode, LedMode.BOUNCE)

    def test_reject_unknown_command(self):
        with self.assertRaises(LookupError):
            decode_command(123, 0.0)

    def test_reject_non_integer_or_unknown_mode(self):
        with self.assertRaises(ValueError):
            decode_command(SERVO_COMMAND, 1.5)
        with self.assertRaises(ValueError):
            decode_command(LED_COMMAND, 99.0)


if __name__ == "__main__":
    unittest.main()
