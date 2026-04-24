from __future__ import annotations

import unittest

from scripts import flight_parser


class FlightParserTests(unittest.TestCase):
    def test_parse_route_with_terminals(self) -> None:
        result = flight_parser.parse_flight_title("乘坐 CA1210 西安咸阳T2-北京首都T3")
        self.assertTrue(result["ok"])
        self.assertTrue(result["data"]["is_flight_event"])
        self.assertEqual(result["data"]["flight_no"], "CA1210")
        self.assertEqual(result["data"]["departure_airport_raw"], "西安咸阳")
        self.assertEqual(result["data"]["departure_terminal"], "T2")
        self.assertEqual(result["data"]["arrival_airport_raw"], "北京首都")
        self.assertEqual(result["data"]["arrival_terminal"], "T3")

    def test_parse_terminal_word_format(self) -> None:
        result = flight_parser.parse_flight_title("MU5579 上海虹桥2号航站楼-深圳宝安T3")
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["flight_no"], "MU5579")
        self.assertEqual(result["data"]["departure_airport_raw"], "上海虹桥")
        self.assertEqual(result["data"]["departure_terminal"], "T2")

    def test_parse_travelsky_title_from_beijing(self) -> None:
        result = flight_parser.parse_flight_title("乘坐CA1349 北京首都T3-长沙黄花T1 当地时间19:55-22:30 【航旅纵横】")
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["flight_no"], "CA1349")
        self.assertEqual(result["data"]["departure_airport_raw"], "北京首都")
        self.assertEqual(result["data"]["departure_terminal"], "T3")

    def test_parse_travelsky_title_from_changsha(self) -> None:
        result = flight_parser.parse_flight_title("乘坐CA1928 长沙黄花T1-北京首都T3 当地时间22:55-01:20 【航旅纵横】")
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["flight_no"], "CA1928")
        self.assertEqual(result["data"]["departure_airport_raw"], "长沙黄花")
        self.assertEqual(result["data"]["departure_terminal"], "T1")

    def test_parse_route_without_flight_number(self) -> None:
        result = flight_parser.parse_flight_title("深圳到北京的航班")
        self.assertTrue(result["ok"])
        self.assertTrue(result["data"]["is_flight_event"])
        self.assertIsNone(result["data"]["flight_no"])
        self.assertEqual(result["data"]["departure_airport_raw"], "深圳")
        self.assertEqual(result["data"]["arrival_airport_raw"], "北京")

    def test_unparseable_title_is_not_flight(self) -> None:
        result = flight_parser.parse_flight_title("周会")
        self.assertTrue(result["ok"])
        self.assertFalse(result["data"]["is_flight_event"])
        self.assertIsNone(result["data"]["departure_airport_raw"])

    def test_empty_title_is_error(self) -> None:
        result = flight_parser.parse_flight_title("")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "title must be a non-empty string.")


if __name__ == "__main__":
    unittest.main()
