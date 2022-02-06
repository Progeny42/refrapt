"""Unit Test Cases for the Helpers module."""

import unittest
import re

from refrapt import helpers

class TestHelpers(unittest.TestCase):
    """Test case for the Helpers module."""

    def test_SanitiseUri(self):
        """Check that Uris are correctly formatted for use with the filesystem."""

        uriList = [
            "http://gb.archive.ubuntu.com/ubuntu",
            "http://ftp.debian.org/debian",
            "http://security.debian.org",
            "http://archive.raspberrypi.org/debian",
            "http://raspbian.raspberrypi.org/raspbian",
            "https://repos.influxdata.com/debian",
            "https://repos.influxdata.com/ubuntu",
            "http://ppa.launchpad.net/ansible/ansible/ubuntu",
            "http://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64"
            "https://NotARealSite:8000",
            "ftp://OldServer:3000"
        ]

        # As explained by regex101.com, the expected conditions are as follows:
        #   From the start of the string;
        #       Matches any word character (equivalent to [a-zA-Z0-9_])
        #       Matches the previous token between one and unlimited times
        #       Matches the characters :// literally
        #   From anywhere in the string;
        #       Matches the character : literally
        #       Matches a digit (equivalent to [0-9])
        #       Matches the previous token between one and unlimited times
        #
        #   The overall effect is that the leading "[protocol]://" should be removed,
        #   and any usage of port numbers ":[port]" are stripped from a Uri.

        # Use the same regex as verification that the function still performs as expected.

        for uri in uriList:
            sanitisedUri = helpers.SanitiseUri(uri)

            self.assertFalse(re.search(r"^(\w+)://", sanitisedUri))
            self.assertFalse(re.search(r":\d+", sanitisedUri))

    def test_ConvertSize(self):

        # ConvertSize uses base 2 (1024)
        values = [ "1.0", "2.0", "4.0", "8.0", "16.0", "32.0", "64.0", "128.0", "256.0", "512.0" ]
        sizeName = [ "B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB" ]

        index = 1
        sizeIndex = 0
        for i in range(0, 8*11):
            result = helpers.ConvertSize(2*pow(2,i))

            self.assertEqual(result, values[index] + " " + sizeName[sizeIndex])

            if index == 9:
                index = 0
                sizeIndex += 1
            else:
                index += 1

    def test_ConvertSize_MassiveValue(self):

        # Values greater than 1023 YB shall be expressed in terms of YB
        self.assertEqual(helpers.ConvertSize(2*pow(2,(8*11) + 1)), "1024.0 YB")
        self.assertEqual(helpers.ConvertSize(2*pow(2,(8*11) + 2)), "2048.0 YB")
        self.assertEqual(helpers.ConvertSize(2*pow(2,(8*11) + 3)), "4096.0 YB")
        
    def test_ConvertSize_NegativeValue(self):

        self.assertEqual(helpers.ConvertSize(-1), "0 B")