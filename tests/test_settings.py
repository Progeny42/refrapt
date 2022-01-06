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

    def test_ParseAllSettings(self):
        """Pass a test file with all options set."""

        testFile = """
        set rootPath   = K:/Working/refrapt
        set mirrorPath = D:/Working/refrapt/mirror
        set skelPath   = D:/Working/refrapt/skel
        set varPath    = K:/Working/refrapt/var

        set architecture       = i386
        set contents           = True
        set threads            = 16
        set authNoChallenge    = False
        set noCheckCertificate = False
        set unlink             = False
        set useProxy           = False
        set httpProxy          = ""
        set httpsProxy         = ""
        set proxyUser          = ""
        set proxyPass          = ""
        set certificate        = ""
        set caCertificate      = ""
        set privateKey         = ""
        set limitRate          = 500m
        set language           = en_GB
        set forceUpdate        = False
        set logLevel           = DEBUG
        set test               = False
        set byHash             = False
        """
        testFileLines =  [y for y in (x.strip() for x in testFile.splitlines()) if y]

        Settings.Parse(testFileLines)

        self.assertEqual(Settings.GetRootPath(), "K:/Working/refrapt")
        self.assertEqual(Settings.MirrorPath(), "D:/Working/refrapt/mirror")
        self.assertEqual(Settings.SkelPath(), "D:/Working/refrapt/skel")
        self.assertEqual(Settings.VarPath(), "K:/Working/refrapt/var")

        self.assertEqual(Settings.Architecture(), "i386")
        self.assertTrue(Settings.Contents())
        self.assertTrue(Settings.Threads(), multiprocessing.cpu_count())
        self.assertFalse(Settings.AuthNoChallenge())
        self.assertFalse(Settings.NoCheckCertificate())
        self.assertFalse(Settings.Unlink())
        self.assertFalse(Settings.UseProxy())
        self.assertEqual(Settings.HttpProxy(), "")
        self.assertEqual(Settings.HttpsProxy(), "")
        self.assertEqual(Settings.ProxyUser(), "")
        self.assertEqual(Settings.ProxyPassword(), "")
        self.assertEqual(Settings.Certificate(), "")
        self.assertEqual(Settings.CaCertificate(), "")
        self.assertEqual(Settings.PrivateKey(), "")
        self.assertEqual(Settings.LimitRate(), "500m")
            # Match how the settings deals with the Locale
        lang = locale.getdefaultlocale()[0]
        if "_" in lang:
            lang = lang.split("_")[0]
        self.assertEqual(Settings.Language(), lang)
        self.assertFalse(Settings.ForceUpdate())
        self.assertEqual(Settings.LogLevel(), logging.DEBUG)
        self.assertFalse(Settings.Test())
        self.assertFalse(Settings.ByHash())

if __name__ == '__main__':
    unittest.main()
