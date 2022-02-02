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

if __name__ == '__main__':
    unittest.main()
