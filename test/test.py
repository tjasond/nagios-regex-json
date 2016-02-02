# import the package
import sys
import check_json
import unittest
import json
import argparse

from check_json import NagiosHelper
from check_json import JsonRuleProcessor

class TestJsonRuleProcessor(unittest.TestCase):

    def setUp(self):
        testfile = open("test/test_nagios.json", 'r').read()
        dictionary = json.loads(testfile)
        parsedProperties = dict()
        check_json.flattenJson(dictionary, "", -1, parsedProperties)

        self.rp = JsonRuleProcessor(parsedProperties, TestArgs())

    def test_exists(self) :
        matches = self.rp.checkExists(["nonexistent.*"])
        self.assertTrue(len(matches) == 1)

        matches = self.rp.checkExists(["critical.*"])
        self.assertTrue(len(matches) == 0)

    def test_literal_value(self) :
        matches = self.rp.checkKeyValue(["critical.*\.status,OK,1"], self.rp.literalValueChecker)
        self.assertEquals(1, len(matches))

        matches = self.rp.checkKeyValue(["critical.*\.status,OK:ALARM,1"], self.rp.literalValueChecker)
        self.assertEquals(0, len(matches))

    def test_range_value(self) :
        matches = self.rp.checkKeyValue(["non_critical.*\.MetricOne,16,1"], self.rp.valueRangeChecker)
        self.assertEquals(0, len(matches))

        matches = self.rp.checkKeyValue(["non_critical.*\.MetricOne,10,1"], self.rp.valueRangeChecker)
        self.assertEquals(1, len(matches))

        matches = self.rp.checkKeyValue(["non_critical.*\.MetricOne,16:,1"], self.rp.valueRangeChecker)
        self.assertEquals(1, len(matches))

        matches = self.rp.checkKeyValue(["non_critical.*\.MetricOne,@10:20,1"], self.rp.valueRangeChecker)
        self.assertEquals(1, len(matches))

        matches = self.rp.checkKeyValue(["non_critical.*\.MetricOne,16:20,1"], self.rp.valueRangeChecker)
        self.assertEquals(1, len(matches))

        matches = self.rp.checkKeyValue(["non_critical.*\.MetricOne,~:10,1"], self.rp.valueRangeChecker)
        self.assertEquals(1, len(matches))

        matches = self.rp.checkKeyValue(["non_critical.*\.MetricOne,~:16,1"], self.rp.valueRangeChecker)
        self.assertEquals(0, len(matches))

class TestArgs :
    debug = False

if __name__ == '__main__':
    unittest.main()
