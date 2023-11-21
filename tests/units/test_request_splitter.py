import datetime
import os
import unittest

from eodag.api.product.request_splitter import RequestSplitter
from eodag.config import PluginConfig
from eodag.utils.exceptions import MisconfiguredError
from tests import TEST_RESOURCES_PATH


class TestRequestSplitter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestRequestSplitter, cls).setUpClass()
        cls.constraints_file_path = os.path.join(
            TEST_RESOURCES_PATH, "constraints.json"
        )

    def test_invalid_config(self):
        metadata = {"year": "year", "month": "month", "day": "day", "time": "time"}
        multiselect_values = ["year"]
        split_time_values = {"param": "year", "duration": 2}
        config = PluginConfig.from_mapping(
            {
                "metadata_mapping": metadata,
                "multi_select_values": multiselect_values,
                "constraints_file_path": self.constraints_file_path,
                "products_split_timedelta": split_time_values,
            }
        )
        with self.assertRaises(MisconfiguredError):
            RequestSplitter(config, metadata)

    def test_split_timespan_by_year(self):
        metadata = {"year": "year", "month": "month", "day": "day", "time": "time"}
        multiselect_values = ["year", "month", "day", "time"]
        split_time_values = {"param": "year", "duration": 2}
        config = PluginConfig.from_mapping(
            {
                "metadata_mapping": metadata,
                "multi_select_values": multiselect_values,
                "constraints_file_path": self.constraints_file_path,
                "products_split_timedelta": split_time_values,
            }
        )
        splitter = RequestSplitter(config, metadata)
        result, num_items = splitter.get_time_slices("2000-02-01", "2003-05-30")
        self.assertEqual(2, len(result))
        expected_result = [
            {
                "year": ["2002", "2003"],
                "month": ["01", "02", "03"],
                "day": ["01", "10", "20"],
                "time": ["01:00", "12:00", "18:00"],
            },
            {
                "year": ["2000", "2001"],
                "month": ["01", "02", "03", "04", "05"],
                "day": ["01", "10", "20", "25"],
                "time": ["01:00", "12:00", "18:00", "22:00"],
            },
        ]
        self.assertDictEqual(expected_result[0], result[0])
        self.assertDictEqual(expected_result[1], result[1])
        config = PluginConfig.from_mapping(
            {
                "metadata_mapping": metadata,
                "multi_select_values": ["month", "day", "time"],
                "constraints_file_path": self.constraints_file_path,
                "products_split_timedelta": split_time_values,
            }
        )
        splitter = RequestSplitter(config, metadata)
        result, num_items = splitter.get_time_slices("2000-02-01", "2003-05-30")
        self.assertEqual(4, len(result))
        expected_result = [
            {
                "year": "2003",
                "month": ["01", "02", "03"],
                "day": ["01", "10", "20"],
                "time": ["01:00", "12:00", "18:00"],
            },
            {
                "year": "2002",
                "month": ["01", "02", "03"],
                "day": ["01", "10", "20"],
                "time": ["01:00", "12:00", "18:00"],
            },
            {
                "year": "2001",
                "month": ["01", "02", "03", "04", "05"],
                "day": ["01", "10", "20", "25"],
                "time": ["01:00", "12:00", "18:00", "22:00"],
            },
            {
                "year": "2000",
                "month": ["01", "02", "03", "04", "05"],
                "day": ["01", "10", "20", "25"],
                "time": ["01:00", "12:00", "18:00", "22:00"],
            },
        ]
        self.assertDictEqual(expected_result[0], result[0])
        self.assertDictEqual(expected_result[1], result[1])
        self.assertDictEqual(expected_result[2], result[2])
        self.assertDictEqual(expected_result[3], result[3])
        result, num_items = splitter.get_time_slices(
            "2000-02-01", "2003-05-30", constraint_values={"time": "22:00"}
        )
        self.assertEqual(4, len(result))
        expected_result = [
            {
                "year": "2003",
                "month": ["12"],
                "day": ["01", "10", "20", "25"],
                "time": ["01:00", "12:00", "18:00", "22:00"],
            },
            {
                "year": "2002",
                "month": ["12"],
                "day": ["01", "10", "20", "25"],
                "time": ["01:00", "12:00", "18:00", "22:00"],
            },
            {
                "year": "2001",
                "month": ["01", "02", "03", "04", "05"],
                "day": ["01", "10", "20", "25"],
                "time": ["01:00", "12:00", "18:00", "22:00"],
            },
            {
                "year": "2000",
                "month": ["01", "02", "03", "04", "05"],
                "day": ["01", "10", "20", "25"],
                "time": ["01:00", "12:00", "18:00", "22:00"],
            },
        ]
        self.assertDictEqual(expected_result[0], result[0])
        self.assertDictEqual(expected_result[1], result[1])
        self.assertDictEqual(expected_result[2], result[2])
        self.assertDictEqual(expected_result[3], result[3])

    def test_split_timespan_by_year_without_input_dates(self):
        metadata = {"year": "year", "month": "month", "day": "day", "time": "time"}
        multiselect_values = ["year", "month", "day", "time"]
        split_time_values = {"param": "year", "duration": 1}
        product_type_config = {"missionStartDate": "1999-01-01"}
        config = PluginConfig.from_mapping(
            {
                "multi_select_values": multiselect_values,
                "constraints_file_path": self.constraints_file_path,
                "products_split_timedelta": split_time_values,
                "product_type_config": product_type_config,
            }
        )
        splitter = RequestSplitter(config, metadata)
        result, num_items = splitter.get_time_slices()
        self.assertEqual(6, len(result))
        self.assertEqual(6, num_items)
        years = [r["year"][0] for r in result]
        years.sort()
        self.assertEqual(
            str(["2000", "2001", "2002", "2003", "2004", "2005"]), str(years)
        )
        result, num_items = splitter.get_time_slices(num_products=5)
        self.assertEqual(5, len(result))
        result, num_items = splitter.get_time_slices("2002-01-01")
        self.assertEqual(4, len(result))
        years = [r["year"][0] for r in result]
        years.sort()
        self.assertEqual(str(["2002", "2003", "2004", "2005"]), str(years))
        result, num_items = splitter.get_time_slices(end_date="2004-07-01")
        self.assertEqual(5, len(result))
        years = [r["year"][0] for r in result]
        years.sort()
        self.assertEqual(str(["2000", "2001", "2002", "2003", "2004"]), str(years))
        result, num_items = splitter.get_time_slices(num_products=3, page=2)
        self.assertEqual(3, len(result))
        self.assertEqual(6, num_items)
        years = [r["year"][0] for r in result]
        years.sort()
        self.assertEqual(str(["2000", "2001", "2002"]), str(years))

    def test_split_timespan_by_month(self):
        metadata = {"year": "year", "month": "month", "day": "day", "time": "time"}
        multiselect_values = ["year", "month", "day", "time"]
        split_time_values = {"param": "month", "duration": 2}
        config = PluginConfig.from_mapping(
            {
                "metadata_mapping": metadata,
                "multi_select_values": multiselect_values,
                "constraints_file_path": self.constraints_file_path,
                "products_split_timedelta": split_time_values,
            }
        )
        splitter = RequestSplitter(config, metadata)
        result, num_items = splitter.get_time_slices("2000-01-01", "2001-06-30")
        self.assertEqual(5, len(result))
        expected_result_row_4 = {
            "year": ["2000"],
            "month": ["03", "04"],
            "day": ["01", "10", "20", "25"],
            "time": ["01:00", "12:00", "18:00", "22:00"],
        }
        expected_result_row_2 = {
            "year": ["2001"],
            "month": ["01", "02"],
            "day": ["01", "10", "20", "25"],
            "time": ["01:00", "12:00", "18:00", "22:00"],
        }
        self.assertDictEqual(expected_result_row_4, result[3])
        self.assertDictEqual(expected_result_row_2, result[1])
        config = PluginConfig.from_mapping(
            {
                "metadata_mapping": metadata,
                "multi_select_values": ["year", "day", "time"],
                "constraints_file_path": self.constraints_file_path,
                "products_split_timedelta": split_time_values,
            }
        )
        splitter = RequestSplitter(config, metadata)
        result, num_items = splitter.get_time_slices("2000-01-01", "2001-06-30")
        self.assertEqual(13, len(result))
        expected_result_row_13 = {
            "year": ["2000"],
            "month": "01",
            "day": ["01", "10", "20", "25"],
            "time": ["01:00", "12:00", "18:00", "22:00"],
        }
        expected_result_row_8 = {
            "year": ["2000"],
            "month": "06",
            "day": ["03", "05"],
            "time": ["01:00", "12:00", "18:00", "22:00"],
        }
        self.assertDictEqual(expected_result_row_13, result[12])
        self.assertDictEqual(expected_result_row_8, result[7])
        result, num_items = splitter.get_time_slices(
            "2002-01-01", "2002-12-30", constraint_values={"time": "22:00"}
        )
        self.assertEqual(1, len(result))
        expected_result = [
            {
                "year": ["2002"],
                "month": "12",
                "day": ["01", "10", "20", "25"],
                "time": ["01:00", "12:00", "18:00", "22:00"],
            }
        ]
        self.assertDictEqual(expected_result[0], result[0])

    def test_split_timespan_by_month_without_input_dates(self):
        metadata = {"year": "year", "month": "month", "day": "day", "time": "time"}
        multiselect_values = ["year", "month", "day", "time"]
        split_time_values = {"param": "month", "duration": 1}
        product_type_config = {"missionStartDate": "1999-01-01"}
        config = PluginConfig.from_mapping(
            {
                "multi_select_values": multiselect_values,
                "constraints_file_path": self.constraints_file_path,
                "products_split_timedelta": split_time_values,
                "product_type_config": product_type_config,
            }
        )
        splitter = RequestSplitter(config, metadata)
        result, num_items = splitter.get_time_slices()
        self.assertEqual(20, len(result))
        result, num_items = splitter.get_time_slices(end_date="2001-12-31")
        self.assertEqual(14, len(result))
        result, num_items = splitter.get_time_slices(
            end_date="2002-12-31", num_products=25
        )
        self.assertEqual(18, len(result))
        result, num_items = splitter.get_time_slices(
            end_date="2002-01-31", num_products=25
        )
        self.assertEqual(15, len(result))
        result, num_items = splitter.get_time_slices(num_products=12, page=2)
        self.assertEqual(12, len(result))
        self.assertEqual("2002", result[0]["year"][0])

    def test_split_timespan_by_year_with_dates(self):
        metadata = {
            "startTimeFromAscendingNode": [
                "date=startTimeFromAscendingNode/to/completionTimeFromAscendingNode",
                "$.date",
            ],
            "completionTimeFromAscendingNode": "$.date",
        }
        multiselect_values = []
        split_time_values = {"param": "year", "duration": 2}
        config = PluginConfig.from_mapping(
            {
                "metadata_mapping": metadata,
                "multi_select_values": multiselect_values,
                "constraints_file_path": os.path.join(
                    TEST_RESOURCES_PATH, "constraints_dates.json"
                ),
                "products_split_timedelta": split_time_values,
            }
        )
        splitter = RequestSplitter(config, metadata)
        result, num_items = splitter.get_time_slices("1999-02-01", "2004-05-30")
        self.assertEqual(3, len(result))
        expected_result = [
            {
                "start_date": datetime.datetime(2000, 2, 1),
                "end_date": datetime.datetime(2001, 12, 31),
            },
            {
                "start_date": datetime.datetime(2002, 1, 1),
                "end_date": datetime.datetime(2003, 12, 31),
            },
            {
                "start_date": datetime.datetime(2004, 1, 1),
                "end_date": datetime.datetime(2004, 12, 31),
            },
        ]
        self.assertDictEqual(expected_result[0], result[0])
        self.assertDictEqual(expected_result[1], result[1])
        self.assertDictEqual(expected_result[2], result[2])

    def test_split_timespan_by_month_with_dates(self):
        metadata = {
            "startTimeFromAscendingNode": [
                "date=startTimeFromAscendingNode/to/completionTimeFromAscendingNode",
                "$.date",
            ],
            "completionTimeFromAscendingNode": "$.date",
        }
        multiselect_values = []
        split_time_values = {"param": "month", "duration": 2}
        config = PluginConfig.from_mapping(
            {
                "metadata_mapping": metadata,
                "multi_select_values": multiselect_values,
                "constraints_file_path": os.path.join(
                    TEST_RESOURCES_PATH, "constraints_dates.json"
                ),
                "products_split_timedelta": split_time_values,
            }
        )

        splitter = RequestSplitter(config, metadata)
        result, num_items = splitter.get_time_slices("1999-02-01", "2001-06-30")
        self.assertEqual(9, len(result))
        expected_result_row_1 = {
            "start_date": datetime.datetime(2000, 2, 1),
            "end_date": datetime.datetime(2000, 3, 31),
        }
        expected_result_row_6 = {
            "start_date": datetime.datetime(2000, 12, 1),
            "end_date": datetime.datetime(2001, 1, 31),
        }
        expected_result_row_9 = {
            "start_date": datetime.datetime(2001, 6, 1),
            "end_date": datetime.datetime(2001, 6, 30),
        }
        self.assertDictEqual(expected_result_row_1, result[0])
        self.assertDictEqual(expected_result_row_6, result[5])
        self.assertDictEqual(expected_result_row_9, result[8])

    def test_dont_split_short_timespan(self):
        metadata = {"year": "year", "month": "month", "day": "day", "time": "time"}
        multiselect_values = ["year", "month", "day", "time"]
        split_time_values = {"param": "year", "duration": 2}
        config = PluginConfig.from_mapping(
            {
                "metadata_mapping": metadata,
                "multi_select_values": multiselect_values,
                "constraints_file_path": self.constraints_file_path,
                "products_split_timedelta": split_time_values,
            }
        )
        splitter = RequestSplitter(config, metadata)
        result, num_items = splitter.get_time_slices("2000-02-01", "2000-07-30")
        self.assertEqual(1, len(result))
        result[0]["month"].sort()
        result[0]["day"].sort()
        result[0]["time"].sort()
        expected_result_row = {
            "year": ["2000"],
            "month": ["02", "03", "04", "05"],
            "day": ["01", "10", "20", "25"],
            "time": ["01:00", "12:00", "18:00", "22:00"],
        }
        self.assertDictEqual(expected_result_row, result[0])
        result, num_items = splitter.get_time_slices("2000-02-01", "2000-02-12")
        self.assertEqual(1, len(result))
        result[0]["day"].sort()
        result[0]["time"].sort()
        expected_result_row = {
            "year": ["2000"],
            "month": ["02"],
            "day": ["01", "10"],
            "time": ["01:00", "12:00", "18:00", "22:00"],
        }
        self.assertDictEqual(expected_result_row, result[0])

    def test_get_variables_for_timespan_and_params(self):
        metadata = {
            "startTimeFromAscendingNode": [
                "date=startTimeFromAscendingNode/to/completionTimeFromAscendingNode",
                "$.date",
            ],
            "completionTimeFromAscendingNode": "$.date",
        }
        config = PluginConfig.from_mapping(
            {
                "metadata_mapping": metadata,
                "multi_select_values": [],
                "constraints_file_path": os.path.join(
                    TEST_RESOURCES_PATH, "constraints_dates.json"
                ),
                "products_split_timedelta": {"param": "month", "duration": 2},
                "assets_split_parameter": "param",
            }
        )
        splitter = RequestSplitter(config, metadata)
        start_date = datetime.datetime(2001, 6, 1)
        end_date = datetime.datetime(2001, 6, 30)
        params = {"step": ["102", "108"]}
        result = splitter._get_variables_for_timespan_and_params(
            start_date, end_date, params
        )
        result.sort()
        self.assertEqual(
            str(["121", "122", "134", "136", "146", "147", "151"]), str(result)
        )
        result = splitter._get_variables_for_timespan_and_params(
            start_date, end_date, params, ["121", "122"]
        )
        result.sort()
        self.assertEqual(str(["121", "122"]), str(sorted(result)))
        params = {"step": ["1"]}
        result = splitter._get_variables_for_timespan_and_params(
            start_date, end_date, params
        )
        self.assertEqual(str([]), str(result))
        start_date = datetime.datetime(2006, 1, 1)
        end_date = datetime.datetime(2007, 1, 1)
        params = {"step": ["102", "108"]}
        result = splitter._get_variables_for_timespan_and_params(
            start_date, end_date, params
        )
        result.sort()
        self.assertEqual(
            str(["121", "122", "134", "136", "146", "147", "151", "165", "166"]),
            str(result),
        )
        params = {"step": ["1"]}
        result = splitter._get_variables_for_timespan_and_params(
            start_date, end_date, params
        )
        result.sort()
        self.assertEqual(
            str(
                [
                    "228001",
                    "228002",
                    "228039",
                    "228139",
                    "228141",
                    "228144",
                    "228164",
                    "228228",
                ]
            ),
            str(result),
        )

    def test_get_variables_for_years_and_params(self):
        metadata = {"year": "year", "month": "month", "day": "day", "time": "time"}
        multiselect_values = ["year", "month", "day", "time"]
        split_time_values = {"param": "year", "duration": 2}
        config = PluginConfig.from_mapping(
            {
                "metadata_mapping": metadata,
                "multi_select_values": multiselect_values,
                "constraints_file_path": self.constraints_file_path,
                "products_split_timedelta": split_time_values,
                "assets_split_parameter": "variable",
            }
        )
        splitter = RequestSplitter(config, metadata)
        params = {"time": ["01:00"]}
        result = splitter.get_variables_for_product("200101_200212", params)
        result.sort()
        self.assertEqual(str(["a", "b"]), str(result))
        result = splitter.get_variables_for_product("200101_200212", params, ["b", "e"])
        self.assertEqual(str(["b"]), str(result))
        params = {"time": ["22:00"], "day": ["03"]}
        result = splitter.get_variables_for_product("200101_200112", params)
        result.sort()
        self.assertEqual(str(["e", "f"]), str(result))

    def test_apply_additional_splitting(self):
        metadata = {
            "year": "year",
            "month": "month",
            "day": "day",
            "leadtime_hour": "leadtime_hour",
            "type": "type",
        }
        multiselect_values = ["year", "month", "day", "leadtime_hour"]
        split_time_values = {"param": "month", "duration": 1}
        other_split_params = ["leadtime_hour"]
        config = PluginConfig.from_mapping(
            {
                "metadata_mapping": metadata,
                "multi_select_values": multiselect_values,
                "constraints_file_path": self.constraints_file_path,
                "products_split_timedelta": split_time_values,
                "assets_split_parameter": "variable",
                "other_product_split_params": other_split_params,
            }
        )
        splitter = RequestSplitter(config, metadata)
        request_params = {
            "year": ["2002"],
            "month": ["01"],
            "day": ["01", "10", "20"],
            "leadtime_hour": ["24", "48", "72"],
        }
        splitted_params = splitter.apply_additional_splitting(request_params)
        self.assertEqual(3, len(splitted_params))
        row_1 = {
            "year": ["2002"],
            "month": ["01"],
            "day": ["01", "10", "20"],
            "leadtime_hour": ["24"],
        }
        row_2 = {
            "year": ["2002"],
            "month": ["01"],
            "day": ["01", "10", "20"],
            "leadtime_hour": ["48"],
        }
        row_3 = {
            "year": ["2002"],
            "month": ["01"],
            "day": ["01", "10", "20"],
            "leadtime_hour": ["72"],
        }
        self.assertDictEqual(row_1, splitted_params[0])
        self.assertDictEqual(row_2, splitted_params[1])
        self.assertDictEqual(row_3, splitted_params[2])
        request_params = {
            "year": ["2002"],
            "month": ["01"],
            "day": ["01", "10", "20"],
            "leadtime_hour": ["96"],
        }
        splitted_params = splitter.apply_additional_splitting(request_params)
        self.assertEqual(0, len(splitted_params))
        config = PluginConfig.from_mapping(
            {
                "metadata_mapping": metadata,
                "multi_select_values": [
                    "year",
                    "month",
                    "day",
                    "leadtime_hour",
                    "type",
                ],
                "constraints_file_path": self.constraints_file_path,
                "products_split_timedelta": split_time_values,
                "assets_split_parameter": "variable",
                "other_product_split_params": ["leadtime_hour", "type"],
            }
        )
        splitter = RequestSplitter(config, metadata)
        request_params = {
            "year": ["2002"],
            "month": ["01"],
            "day": ["01", "10", "20"],
            "leadtime_hour": ["24", "48", "72"],
            "type": ["A", "B"],
        }
        splitted_params = splitter.apply_additional_splitting(request_params)
        self.assertEqual(6, len(splitted_params))
        row_1 = {
            "year": ["2002"],
            "month": ["01"],
            "day": ["01", "10", "20"],
            "leadtime_hour": ["24"],
            "type": ["A"],
        }
        assert row_1 in splitted_params
        row_2 = {
            "year": ["2002"],
            "month": ["01"],
            "day": ["01", "10", "20"],
            "leadtime_hour": ["24"],
            "type": ["B"],
        }
        assert row_2 in splitted_params
        row_3 = {
            "year": ["2002"],
            "month": ["01"],
            "day": ["01", "10", "20"],
            "leadtime_hour": ["48"],
            "type": ["A"],
        }
        assert row_3 in splitted_params
