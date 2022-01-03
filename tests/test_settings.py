"""Unit Test Cases for the Settings class."""

import logging
import multiprocessing
import unittest
import platform
from pathlib import Path
import locale

from settings import Settings

class TestSettings(unittest.TestCase):
    """Test case for the Settings class."""
    def setUp(self) -> None:
        Settings.Init()
        return super().setUp()

    def test_Init(self):
        """Check that settings are reverted to Default when calling Init."""

        # Initialise and check defaults
        Settings.Init()
        self.test_DefaultSettings()

        # Modify some random settings
        testFile = ["set rootPath = This is a test"]
        Settings.Parse(testFile)

        # Initialise and check defaults
        Settings.Init()
        self.test_DefaultSettings()

    def test_DefaultSettings(self):
        """Tests the default settings."""

        self.assertEqual(Settings.Architecture(), platform.machine())
        self.assertEqual(Settings.GetRootPath(), f"{str(Path.home())}/refrapt")
        self.assertEqual(Settings.MirrorPath(), f"{str(Path.home())}/refrapt/mirror")
        self.assertEqual(Settings.SkelPath(), f"{str(Path.home())}/refrapt/skel")
        self.assertEqual(Settings.VarPath(), f"{str(Path.home())}/refrapt/var")
        self.assertTrue(Settings.Contents())
        self.assertEqual(Settings.Threads(), multiprocessing.cpu_count())
        self.assertFalse(Settings.AuthNoChallenge())
        self.assertFalse(Settings.NoCheckCertificate())
        self.assertFalse(Settings.Unlink())
        self.assertFalse(Settings.UseProxy())
        self.assertIsNone(Settings.HttpProxy())
        self.assertIsNone(Settings.HttpsProxy())
        self.assertIsNone(Settings.ProxyUser())
        self.assertIsNone(Settings.ProxyPassword())
        self.assertIsNone(Settings.Certificate())
        self.assertIsNone(Settings.CaCertificate())
        self.assertIsNone(Settings.PrivateKey())
        self.assertEqual(Settings.LimitRate(), "500m")

        # Match how the settings deals with the Locale
        lang = locale.getdefaultlocale()[0]
        if "_" in lang:
            lang = lang.split("_")[0]
        self.assertEqual(Settings.Language(), lang)
        self.assertFalse(Settings.ForceUpdate())
        self.assertEqual(Settings.LogLevel(), logging.INFO)
        self.assertFalse(Settings.Test())
        self.assertFalse(Settings.ByHash())

    def test_EnableTestMode(self):
        """Tests that enabling Test mode correctly sets the option in Settings."""

        self.assertFalse(Settings.Test())
        Settings.EnableTest()
        self.assertTrue(Settings.Test())

    def test_EnableForceMode(self):
        """Tests that enabling Force mode correctly sets the option in Settings."""

        self.assertFalse(Settings.Force())
        Settings.SetForce()
        self.assertTrue(Settings.Force())

    def test_ParseEmptyFile(self):
        """Pass an empty list representing an empty configuration file."""

        Settings.Parse([])
        self.test_DefaultSettings()

    def test_ParseCommentFile(self):
        """Pass a dummy file with differing comments."""

        testFile = [
            "# This is a comment.",
            "## Double comment.",
            " # Space at start of comment",
            "\t # Tab at start of comment."
        ]

        Settings.Parse(testFile)
        self.test_DefaultSettings()

    def test_ParseInvalidSyntax(self):
        """Pass a dummy file with different syntax errors."""

        testFile = [
            "// This is the wrong comment!",
            "rootPath = this is a test",
            "set contents = 'this is not a boolean'",
            "set threads = zero",
            "set anoptionthatdoesnotexist = foo",
            "set logLevel = abcs",
            "set loglevel # This is the wrong casing.",
            "set",
            " set ",
            "set    ",
            "setlogLevel=thisshouldntwork",
            "set threads = 0.1",
            "set threads = #FF"
        ]

        Settings.Parse(testFile)
        self.test_DefaultSettings()

if __name__ == '__main__':
    unittest.main()
