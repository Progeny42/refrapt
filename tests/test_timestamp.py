"""Unit Test Cases for the Classes.Timestamp module."""

import unittest

from refrapt.classes import (
    Timestamp
)

class TestTimestamp(unittest.TestCase):

    def test_TimestampInit(self):

        ts = Timestamp()

        self.assertEqual(ts.Current, 0.0)
        self.assertEqual(ts.Download, 0.0)

    def test_TimestampCurrent(self):

        ts = Timestamp()

        self.assertEqual(ts.Current, 0.0)

        testValue = 15.2597
        ts.Current = testValue

        self.assertEqual(ts.Current, testValue)

    def test_TimestampDownload(self):

        ts = Timestamp()

        self.assertEqual(ts.Download, 0.0)

        testValue = 15.2597
        ts.Download = testValue

        self.assertEqual(ts.Download, testValue)

    def test_TimestampModified(self):

        ts = Timestamp()

        self.assertFalse(ts.Modified)

        ts.Current = 1
        ts.Download = 2

        self.assertTrue(ts.Modified)
