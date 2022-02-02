"""Unit Test Cases for the Classes.Package class."""

import unittest

from refrapt.classes import Package

class TestPackage(unittest.TestCase):

    def test_InitInvalid(self):
        """Check that a Package created with invalid parameters raises AssertionErrors."""

        badFilename = None
        badSize = -1
        badLatest = None

        goodFilename = "Filename"
        goodSize = 512
        goodLatest = True

        self.assertRaises(AssertionError, Package, badFilename, goodSize, goodLatest)
        self.assertRaises(AssertionError, Package, goodFilename, badSize, goodLatest)
        self.assertRaises(AssertionError, Package, goodFilename, goodSize, badLatest)

    def test_Filename(self):
        """Check the Package.Filename property."""

        filename = "Filename"

        package = Package(filename, 512, True)

        self.assertEqual(package.Filename, filename)

    def test_Size(self):
        """Check the Package.Size property."""

        size = 512

        package = Package("Filename", size, True)

        self.assertEqual(package.Size, size)

    def test_Latest(self):
        """Check the Package.Latest property."""

        latest = True

        package = Package("Filename", 512, latest)

        self.assertEqual(package.Latest, latest)
        