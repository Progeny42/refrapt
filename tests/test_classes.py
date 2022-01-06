"""Unit Test Cases for the Classes module."""

import unittest
from urllib import parse
from pathlib import Path
import re
import os

from settings import Settings
from classes import (
    SourceType,
    Source
)

class TestSource_Init(unittest.TestCase):
    """Test case for the Source.Init method."""

    def test_InitNoData(self):
        """Check that a Source initialised with blank arguments raises an exception."""

        self.assertRaises(ValueError, Source, "", "")

    def test_InitNoLine(self):
        """Check that a Source initialised with a blank "line" argument raises an exception."""

        self.assertRaises(ValueError, Source, "", "An Architecture")

    def test_InitNoArchitecture(self):
        """Check that a Source initialised with a blank "architecture" raises an exception."""

        self.assertRaises(ValueError, Source, "Random data", "")

    def test_InitMalformedLineNoSource(self):
        """Check that a Source initialised with a missing source type fails."""

        line = "http://gb.archive.ubuntu.com/ubuntu"

        self.assertRaises(ValueError, Source, line, "amd64")

    def test_InitMalformedLineSourceOnly(self):
        """Check that a Source initialised with a missing uri fails."""

        line = "deb"

        self.assertRaises(ValueError, Source, line, "amd64")

    def test_InitMalformedLineArchitecture(self):
        """Check that a Source initialised with a bad Architecture fails."""

        line = "deb [arch anArchitecture]"

        self.assertRaises(ValueError, Source, line, "amd64")

    def test_InitMalformedLineArchitecture2(self):
        """Check that a Source initialised with a bad Architecture fails."""

        line = "deb [arch anArchitecture"

        self.assertRaises(ValueError, Source, line, "amd64")

    def test_InitMalformedLineIncorrectOrder(self):
        """Check that a Source initialised in an incorrect order fails."""

        line = "deb uri component1 component2 [arch=amd64]"

        self.assertRaises(ValueError, Source, line, "amd64")

    def test_InitMinimal(self):
        """Check that a minimal example of a source definition succeeds."""

        line = "deb http://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64"
        defaultArchitecture = "amd64"

        source = Source(line, defaultArchitecture)

        self.assertEqual(source.SourceType, SourceType.Bin)
        self.assertListEqual(source.Architectures, [defaultArchitecture])
        self.assertEqual(source.Uri, line.split(" ")[1])
        self.assertEqual(source.Distribution, "")
        self.assertEqual(source.Components, [])
        self.assertTrue(source.Clean)

    def test_InitSingleComponent(self):
        """Check that a valid Binary source with one Component succeeds."""

        line = "deb http://gb.archive.ubuntu.com/ubuntu focal main"
        defaultArchitecture = "amd64"

        source = Source(line, defaultArchitecture)

        self.assertEqual(source.SourceType, SourceType.Bin)
        self.assertListEqual(source.Architectures, [defaultArchitecture])
        self.assertEqual(source.Uri, line.split(" ")[1])
        self.assertEqual(source.Distribution, line.split(" ")[2])
        self.assertEqual(source.Components, line.split(" ")[3:])
        self.assertTrue(source.Clean)

    def test_InitMultiComponent(self):
        """Check that a valid Binary source with multiple Components succeeds."""

        line = "deb http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
        defaultArchitecture = "amd64"

        source = Source(line, defaultArchitecture)

        self.assertEqual(source.SourceType, SourceType.Bin)
        self.assertListEqual(source.Architectures, [defaultArchitecture])
        self.assertEqual(source.Uri, line.split(" ")[1])
        self.assertEqual(source.Distribution, line.split(" ")[2])
        self.assertEqual(source.Components, line.split(" ")[3:])
        self.assertTrue(source.Clean)

    def test_InitSourceSingleComponent(self):
        """Check that a valid Source source with one Component succeeds."""

        line = "deb-src http://gb.archive.ubuntu.com/ubuntu focal main"
        defaultArchitecture = "amd64"

        source = Source(line, defaultArchitecture)

        self.assertEqual(source.SourceType, SourceType.Src)
        self.assertListEqual(source.Architectures, [defaultArchitecture])
        self.assertEqual(source.Uri, line.split(" ")[1])
        self.assertEqual(source.Distribution, line.split(" ")[2])
        self.assertEqual(source.Components, line.split(" ")[3:])
        self.assertTrue(source.Clean)

    def test_InitSourceMultiComponent(self):
        """Check that a valid Source source with multiple Components succeeds."""

        line = "deb-src http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
        defaultArchitecture = "amd64"

        source = Source(line, defaultArchitecture)

        self.assertEqual(source.SourceType, SourceType.Src)
        self.assertListEqual(source.Architectures, [defaultArchitecture])
        self.assertEqual(source.Uri, line.split(" ")[1])
        self.assertEqual(source.Distribution, line.split(" ")[2])
        self.assertEqual(source.Components, line.split(" ")[3:])
        self.assertTrue(source.Clean)

    def test_InitSingleArchitecture(self):
        """Check that a valid Binary source with an explicit Architecture succeeds."""

        architectures = "amd64"
        line = f"deb [arch={architectures}] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
        defaultArchitecture = "default"

        source = Source(line, defaultArchitecture)

        self.assertEqual(source.SourceType, SourceType.Bin)
        self.assertListEqual(source.Architectures, [architectures])
        self.assertEqual(source.Uri, line.split(" ")[2])
        self.assertEqual(source.Distribution, line.split(" ")[3])
        self.assertEqual(source.Components, line.split(" ")[4:])
        self.assertTrue(source.Clean)

    def test_InitMultiArchitecture(self):
        """Check that a valid Binary source with an explicit Architecture succeeds."""

        architectures = "amd64,i386,armhf"
        line = f"deb [arch={architectures}] http://archive.raspberrypi.org/debian buster main"
        defaultArchitecture = "default"

        source = Source(line, defaultArchitecture)

        self.assertEqual(source.SourceType, SourceType.Bin)
        self.assertListEqual(source.Architectures, architectures.split(","))
        self.assertEqual(source.Uri, line.split(" ")[2])
        self.assertEqual(source.Distribution, line.split(" ")[3])
        self.assertEqual(source.Components, line.split(" ")[4:])
        self.assertTrue(source.Clean)

class TestSource_GetReleaseFiles(unittest.TestCase):
    """Test case for the Source.GetReleaseFiles method."""

    # Release files expected are:
    #   <download-url>/InRelease
    #   <download-url>/Release
    #   <download-url>/Release.gpg
    _expectedReleaseFiles = ["InRelease", "Release", "Release.gpg"]

    def test_GetReleaseFilesBinarySource(self):
        """
            Check the expected Release files are returned for a given Binary source.
            Tests both Flat and Non-Flat repositories.
        """

        # Non-Flat test
        line = "deb http://gb.archive.ubuntu.com/ubuntu focal main"
        defaultArchitecture = "amd64"

        source = Source(line, defaultArchitecture)

        self.assertEqual(source.SourceType, SourceType.Bin)

        self._CheckReleaseFiles(line, source.GetReleaseFiles())

        # Flat test
        line = "deb http://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64"
        defaultArchitecture = "amd64"

        source = Source(line, defaultArchitecture)

        self.assertEqual(source.SourceType, SourceType.Bin)

        self._CheckReleaseFilesFlat(line, source.GetReleaseFiles())

    def test_GetReleaseFilesSourceSource(self):
        """
            Check the expected Release files are returned for a given Source source.
            Tests both Flat and Non-Flat repositories.
        """

        # Non-Flat test
        line = "deb-src http://gb.archive.ubuntu.com/ubuntu focal main"
        defaultArchitecture = "amd64"

        source = Source(line, defaultArchitecture)

        self.assertEqual(source.SourceType, SourceType.Src)

        self._CheckReleaseFiles(line, source.GetReleaseFiles())

        # Flat test
        line = "deb-src http://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64"
        defaultArchitecture = "amd64"

        source = Source(line, defaultArchitecture)

        self.assertEqual(source.SourceType, SourceType.Src)

        self._CheckReleaseFilesFlat(line, source.GetReleaseFiles())

    def _CheckReleaseFiles(self, line : str, files : list):
        """Check Release files and Download URLs are as expected for a given non-flat source."""

        self.assertTrue(len(files) == len(self._expectedReleaseFiles))

        for file in files:
            uri = line.split(' ')[1]
            distribution = line.split(' ')[2]

            expectedUrl = f"{uri}/dists/{distribution}"

            splitUrl = parse.urlsplit(file)
            actualUrl = f"{splitUrl.scheme}://{splitUrl.netloc}{splitUrl.path}"
            actualUrl = "".join(actualUrl.rpartition("/")[:-2])

            self.assertEqual(expectedUrl, actualUrl)

            filename = "".join(splitUrl.path.rpartition("/")[2])
            self.assertIn(filename, self._expectedReleaseFiles)

    def _CheckReleaseFilesFlat(self, line : str, files : list):
        """Check Release files and Download URLs are as expected for a given flat source."""
        self.assertTrue(len(files) == len(self._expectedReleaseFiles))

        for file in files:
            uri = line.split(' ')[1]

            expectedUrl = uri

            splitUrl = parse.urlsplit(file)
            actualUrl = f"{splitUrl.scheme}://{splitUrl.netloc}{splitUrl.path}"
            actualUrl = "".join(actualUrl.rpartition("/")[:-2])

            self.assertEqual(expectedUrl, actualUrl)

            filename = "".join(splitUrl.path.rpartition("/")[2])
            self.assertIn(filename, self._expectedReleaseFiles)

class TestSource_ParseReleaseFiles(unittest.TestCase):
    """Test case for the Source.ParseReleaseFiles method."""

    _testDirectory = str(Path(__file__).parent.absolute())
    _fixturesDirectory = f"{_testDirectory}/fixtures"

    _checksumTypes = ["SHA256", "SHA1", "MD5Sum"]

    def test_ParseReleaseFiles_Structured(self):
        """
            Check that only files matching the expected regexes are returned for the given repository 
            and configuration settings.
        """

        # Need to setup the Settings specifically for this test
        Settings.Init()
        dummyConfig = [
        f"set skelPath = {self._fixturesDirectory}/ReleaseFiles/Structured",
        "set contents  = False",
        "set byHash    = False",
        "set language  = 'en_GB'",
        ]
        Settings.Parse(dummyConfig)

        # Setup a Structured repository to test against
        line = "deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
        source = Source(line, "amd64")

        baseUrl = source.Uri + "/dists/" + source.Distribution + "/"

        indexFiles = source.ParseReleaseFiles() # type: list[str]

        # Ensure we actually got some files
        self.assertTrue(len(indexFiles) > 0)

        # For the configuration settings in the tests, we can expect the following Regexes to apply:       
        #   rf"{component}/binary-{architecture}/Release"
        #   rf"{component}/binary-{architecture}/Packages"
        #   rf"{component}/binary-{architecture}/Packages[^./]*(\.gz|\.bz2|\.xz|$)$"
        #   rf"{component}/cnf/Commands-{architecture}"
        #   rf"{component}/i18n/cnf/Commands-{architecture}"
        #   rf"{component}/i18n/Index"
        #   rf"{component}/i18n/Translation-{Settings.Language()}"
        #   rf"{component}/dep11/(Components-{architecture}\.yml|icons-[^./]+\.tar)"
        #
        # If none of the Regexes apply, then something is wrong
        regexes = []
        for architecture in source.Architectures:
            for component in source.Components:
                regexes.append(rf"{component}/binary-{architecture}/Release")
                regexes.append(rf"{component}/binary-{architecture}/Packages")
                regexes.append(rf"{component}/binary-{architecture}/Packages[^./]*(\.gz|\.bz2|\.xz|$)$")
                regexes.append(rf"{component}/cnf/Commands-{architecture}")
                regexes.append(rf"{component}/i18n/cnf/Commands-{architecture}")
                regexes.append(rf"{component}/i18n/Index")
                regexes.append(rf"{component}/i18n/Translation-{Settings.Language()}")
                regexes.append(rf"{component}/dep11/(Components-{architecture}\.yml|icons-[^./]+\.tar)")

        # Check that all files downloaded match a Regex expression
        for file in indexFiles:
            found = False
            for regex in regexes:
                found = found or re.match(regex, file.replace(baseUrl, ""))

            self.assertTrue(found)

    def test_ParseReleaseFiles_StructuredWithContents(self):
        """
            Check that only files matching the expected regexes are returned for the given repository 
            and configuration settings.
        """

        # Need to setup the Settings specifically for this test
        Settings.Init()
        dummyConfig = [
        f"set skelPath = {self._fixturesDirectory}/ReleaseFiles/Structured",
        "set contents  = True",
        "set byHash    = False",
        "set language  = 'en_GB'",
        ]
        Settings.Parse(dummyConfig)

        # Setup a Structured repository to test against
        line = "deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
        source = Source(line, "amd64")

        baseUrl = source.Uri + "/dists/" + source.Distribution + "/"

        indexFiles = source.ParseReleaseFiles() # type: list[str]

        # Ensure we actually got some files
        self.assertTrue(len(indexFiles) > 0)

        # For the configuration settings in the tests, we can expect the following Regexes to apply: 
        #   rf"Contents-{architecture}"
        #   rf"{component}/Contents-{architecture}"
        #   rf"{component}/binary-{architecture}/Release"
        #   rf"{component}/binary-{architecture}/Packages"
        #   rf"{component}/binary-{architecture}/Packages[^./]*(\.gz|\.bz2|\.xz|$)$"
        #   rf"{component}/cnf/Commands-{architecture}"
        #   rf"{component}/i18n/cnf/Commands-{architecture}"
        #   rf"{component}/i18n/Index"
        #   rf"{component}/i18n/Translation-{Settings.Language()}"
        #   rf"{component}/dep11/(Components-{architecture}\.yml|icons-[^./]+\.tar)"
        #
        # If none of the Regexes apply, then something is wrong
        regexes = []
        for architecture in source.Architectures:
            regexes.append(rf"Contents-{architecture}")
            for component in source.Components:
                regexes.append(rf"{component}/Contents-{architecture}")
                regexes.append(rf"{component}/binary-{architecture}/Release")
                regexes.append(rf"{component}/binary-{architecture}/Packages")
                regexes.append(rf"{component}/binary-{architecture}/Packages[^./]*(\.gz|\.bz2|\.xz|$)$")
                regexes.append(rf"{component}/cnf/Commands-{architecture}")
                regexes.append(rf"{component}/i18n/cnf/Commands-{architecture}")
                regexes.append(rf"{component}/i18n/Index")
                regexes.append(rf"{component}/i18n/Translation-{Settings.Language()}")
                regexes.append(rf"{component}/dep11/(Components-{architecture}\.yml|icons-[^./]+\.tar)")

        # Check that all files downloaded match a Regex expression
        for file in indexFiles:
            found = False
            for regex in regexes:
                found = found or re.match(regex, file.replace(baseUrl, ""))

            self.assertTrue(found)

    def test_ParseReleaseFiles_StructuredByHash(self):
        """
            Check that only files matching the expected regexes are returned for the given repository 
            and configuration settings.
        """

        # Need to setup the Settings specifically for this test
        Settings.Init()
        dummyConfig = [
        f"set skelPath = {self._fixturesDirectory}/ReleaseFiles/Structured",
        "set contents  = False",
        "set byHash    = True",
        "set language  = 'en_GB'",
        ]
        Settings.Parse(dummyConfig)

        # Setup a Structured repository to test against
        line = "deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
        source = Source(line, "amd64")

        baseUrl = source.Uri + "/dists/" + source.Distribution + "/"

        indexFiles = source.ParseReleaseFiles() # type: list[str]

        # Ensure we actually got some files
        self.assertTrue(len(indexFiles) > 0)

        # For the configuration settings in the tests, we can expect the following Regexes to apply: 
        #   rf"{component}/binary-{architecture}/by-hash/{checksumType}"
        #   rf"{component}/i18n/by-hash/{checksumType}"
        #   rf"{component}/binary-{architecture}/Release"
        #   rf"{component}/binary-{architecture}/Packages"
        #   rf"{component}/binary-{architecture}/Packages[^./]*(\.gz|\.bz2|\.xz|$)$"
        #   rf"{component}/cnf/by-hash/{checksumType}"
        #   rf"{component}/cnf/Commands-{architecture}"
        #   rf"{component}/i18n/cnf/Commands-{architecture}"
        #   rf"{component}/i18n/Index"
        #   rf"{component}/i18n/Translation-{Settings.Language()}"
        #   rf"{component}/dep11/(Components-{architecture}\.yml|icons-[^./]+\.tar)"
        #   rf"{component}/dep11/by-hash/{checksumType}"
        #
        # If none of the Regexes apply, then something is wrong
        regexes = []
        for architecture in source.Architectures:
            for component in source.Components:
                for checksumType in self._checksumTypes:
                    regexes.append(rf"{component}/binary-{architecture}/by-hash/{checksumType}")
                    regexes.append(rf"{component}/i18n/by-hash/{checksumType}")
                    regexes.append(rf"{component}/cnf/by-hash/{checksumType}")
                    regexes.append(rf"{component}/dep11/by-hash/{checksumType}")
                regexes.append(rf"{component}/binary-{architecture}/Release")
                regexes.append(rf"{component}/binary-{architecture}/Packages")
                regexes.append(rf"{component}/binary-{architecture}/Packages[^./]*(\.gz|\.bz2|\.xz|$)$")
                regexes.append(rf"{component}/cnf/Commands-{architecture}")
                regexes.append(rf"{component}/i18n/cnf/Commands-{architecture}")
                regexes.append(rf"{component}/i18n/Index")
                regexes.append(rf"{component}/i18n/Translation-{Settings.Language()}")
                regexes.append(rf"{component}/dep11/(Components-{architecture}\.yml|icons-[^./]+\.tar)")

        # Check that all files downloaded match a Regex expression
        for file in indexFiles:
            found = False
            for regex in regexes:
                found = found or re.match(regex, file.replace(baseUrl, ""))

            self.assertTrue(found)

    def test_ParseReleaseFiles_Structured_Flat(self):
        """
            Check that only files matching the expected regexes are returned for the given repository 
            and configuration settings.
        """

        # Need to setup the Settings specifically for this test
        Settings.Init()
        dummyConfig = [
        f"set skelPath = {self._fixturesDirectory}/ReleaseFiles/Flat",
        "set contents  = False",
        "set byHash    = False",
        "set language  = 'en_GB'",
        ]
        Settings.Parse(dummyConfig)

        # Setup a Structured repository to test against
        line = "deb [arch=amd64] http://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64"
        source = Source(line, "amd64")

        baseUrl = source.Uri + "/"

        indexFiles = source.ParseReleaseFiles() # type: list[str]

        # Ensure we actually got some files
        self.assertTrue(len(indexFiles) > 0)

        # For Flat Repositories, the entire contents of the file is read.
        # Therefore, just ensure that the Packages file is added at the very least
        regexes = []
        regexes.append(rf"Packages")
        regexes.append(rf"Packages[^./]*(\.gz|\.bz2|\.xz|$)$")

        # Check that all files downloaded match a Regex expression
        for file in indexFiles:
            found = False
            for regex in regexes:
                found = found or re.match(regex, file.replace(baseUrl, ""))

            self.assertTrue(found)

    def test_ParseReleaseFiles_StructuredWithContents_Flat(self):
        """
            Check that only files matching the expected regexes are returned for the given repository 
            and configuration settings.
        """

        # Need to setup the Settings specifically for this test
        Settings.Init()
        dummyConfig = [
        f"set skelPath = {self._fixturesDirectory}/ReleaseFiles/Flat",
        "set contents  = True",
        "set byHash    = False",
        "set language  = 'en_GB'",
        ]
        Settings.Parse(dummyConfig)

        # Setup a Structured repository to test against
        line = "deb [arch=amd64] http://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64"
        source = Source(line, "amd64")

        baseUrl = source.Uri + "/"

        indexFiles = source.ParseReleaseFiles() # type: list[str]

        # Ensure we actually got some files
        self.assertTrue(len(indexFiles) > 0)

        # For Flat Repositories, the entire contents of the file is read.
        # Therefore, just ensure that the Packages file is added at the very least
        regexes = []
        regexes.append(rf"Packages")
        regexes.append(rf"Packages[^./]*(\.gz|\.bz2|\.xz|$)$")

        # Check that all files downloaded match a Regex expression
        for file in indexFiles:
            found = False
            for regex in regexes:
                found = found or re.match(regex, file.replace(baseUrl, ""))

            self.assertTrue(found)

    def test_ParseReleaseFiles_StructuredByHash_Flat(self):
        """
            Check that only files matching the expected regexes are returned for the given repository 
            and configuration settings.
        """

        # Need to setup the Settings specifically for this test
        Settings.Init()
        dummyConfig = [
        f"set skelPath = {self._fixturesDirectory}/ReleaseFiles/Flat",
        "set contents  = False",
        "set byHash    = True",
        "set language  = 'en_GB'",
        ]
        Settings.Parse(dummyConfig)

        # Setup a Structured repository to test against
        line = "deb [arch=amd64] http://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64"
        source = Source(line, "amd64")

        baseUrl = source.Uri + "/"

        indexFiles = source.ParseReleaseFiles() # type: list[str]

        # Ensure we actually got some files
        self.assertTrue(len(indexFiles) > 0)

        # For Flat Repositories, the entire contents of the file is read.
        # Therefore, just ensure that the Packages file is added at the very least
        regexes = []
        regexes.append(rf"Packages")
        regexes.append(rf"Packages[^./]*(\.gz|\.bz2|\.xz|$)$")

        # Check that all files downloaded match a Regex expression
        for file in indexFiles:
            found = False
            for regex in regexes:
                found = found or re.match(regex, file.replace(baseUrl, ""))

            self.assertTrue(found)

    def test_ParseReleaseFiles_Structured_Source(self):
        """
            Check that only files matching the expected regexes are returned for the given repository 
            and configuration settings.
        """

        # Need to setup the Settings specifically for this test
        Settings.Init()
        dummyConfig = [
        f"set skelPath = {self._fixturesDirectory}/ReleaseFiles/Structured",
        "set contents  = False",
        "set byHash    = False",
        "set language  = 'en_GB'",
        ]
        Settings.Parse(dummyConfig)

        # Setup a Structured repository to test against
        line = "deb-src [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
        source = Source(line, "amd64")

        baseUrl = source.Uri + "/dists/" + source.Distribution + "/"

        indexFiles = source.ParseReleaseFiles() # type: list[str]

        # Ensure we actually got some files
        self.assertTrue(len(indexFiles) > 0)

        # For the configuration settings in the tests, we can expect the following Regexes to apply:       
        #   rf"{component}/source/Release"
        #   rf"{component}/source/Sources"
        #
        # If none of the Regexes apply, then something is wrong
        regexes = []
        for component in source.Components:
            regexes.append(rf"{component}/source/Release")
            regexes.append(rf"{component}/source/Sources")

        # Check that all files downloaded match a Regex expression
        for file in indexFiles:
            found = False
            for regex in regexes:
                found = found or re.match(regex, file.replace(baseUrl, ""))

            self.assertTrue(found)

    def test_ParseReleaseFiles_StructuredWithContents_Source(self):
        """
            Check that only files matching the expected regexes are returned for the given repository 
            and configuration settings.
        """

        # Need to setup the Settings specifically for this test
        Settings.Init()
        dummyConfig = [
        f"set skelPath = {self._fixturesDirectory}/ReleaseFiles/Structured",
        "set contents  = True",
        "set byHash    = False",
        "set language  = 'en_GB'",
        ]
        Settings.Parse(dummyConfig)

        # Setup a Structured repository to test against
        line = "deb-src [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
        source = Source(line, "amd64")

        baseUrl = source.Uri + "/dists/" + source.Distribution + "/"

        indexFiles = source.ParseReleaseFiles() # type: list[str]

        # Ensure we actually got some files
        self.assertTrue(len(indexFiles) > 0)

        # For the configuration settings in the tests, we can expect the following Regexes to apply:       
        #   rf"{component}/source/Release"
        #   rf"{component}/source/Sources"
        #
        # If none of the Regexes apply, then something is wrong
        regexes = []
        for component in source.Components:
            regexes.append(rf"{component}/source/Release")
            regexes.append(rf"{component}/source/Sources")

        # Check that all files downloaded match a Regex expression
        for file in indexFiles:
            found = False
            for regex in regexes:
                found = found or re.match(regex, file.replace(baseUrl, ""))

            self.assertTrue(found)

    def test_ParseReleaseFiles_StructuredByHash_Source(self):
        """
            Check that only files matching the expected regexes are returned for the given repository 
            and configuration settings.
        """

        # Need to setup the Settings specifically for this test
        Settings.Init()
        dummyConfig = [
        f"set skelPath = {self._fixturesDirectory}/ReleaseFiles/Structured",
        "set contents  = False",
        "set byHash    = True",
        "set language  = 'en_GB'",
        ]
        Settings.Parse(dummyConfig)

        # Setup a Structured repository to test against
        line = "deb-src [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
        source = Source(line, "amd64")

        baseUrl = source.Uri + "/dists/" + source.Distribution + "/"

        indexFiles = source.ParseReleaseFiles() # type: list[str]

        # Ensure we actually got some files
        self.assertTrue(len(indexFiles) > 0)

        # For the configuration settings in the tests, we can expect the following Regexes to apply:       
        #   rf"{component}/source/Release"
        #   rf"{component}/source/Sources"
        #
        # If none of the Regexes apply, then something is wrong
        regexes = []
        for component in source.Components:
            regexes.append(rf"{component}/source/Release")
            regexes.append(rf"{component}/source/Sources")

        # Check that all files downloaded match a Regex expression
        for file in indexFiles:
            found = False
            for regex in regexes:
                found = found or re.match(regex, file.replace(baseUrl, ""))

            self.assertTrue(found)

    @unittest.skip("Flat Source repositories are not supported")
    def test_ParseReleaseFiles_Structured_Flat_Source(self):
        """
            Check that only files matching the expected regexes are returned for the given repository 
            and configuration settings.
        """

        # Need to setup the Settings specifically for this test
        Settings.Init()
        dummyConfig = [
        f"set skelPath = {self._fixturesDirectory}/ReleaseFiles/Flat",
        "set contents  = False",
        "set byHash    = False",
        "set language  = 'en_GB'",
        ]
        Settings.Parse(dummyConfig)

        # Setup a Structured repository to test against
        line = "deb-src [arch=amd64] http://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64"
        source = Source(line, "amd64")

        baseUrl = source.Uri + "/"

        indexFiles = source.ParseReleaseFiles() # type: list[str]

        # Ensure we actually got some files
        self.assertTrue(len(indexFiles) > 0)

        # For Flat Repositories, the entire contents of the file is read.
        # Therefore, just ensure that the Packages file is added at the very least
        regexes = []
        regexes.append(rf"Packages")
        regexes.append(rf"Packages[^./]*(\.gz|\.bz2|\.xz|$)$")

        # Check that all files downloaded match a Regex expression
        for file in indexFiles:
            found = False
            for regex in regexes:
                found = found or re.match(regex, file.replace(baseUrl, ""))

            self.assertTrue(found)

    @unittest.skip("Flat Source repositories are not supported")
    def test_ParseReleaseFiles_StructuredWithContents_Flat_Source(self):
        """
            Check that only files matching the expected regexes are returned for the given repository 
            and configuration settings.
        """

        # Need to setup the Settings specifically for this test
        Settings.Init()
        dummyConfig = [
        f"set skelPath = {self._fixturesDirectory}/ReleaseFiles/Flat",
        "set contents  = True",
        "set byHash    = False",
        "set language  = 'en_GB'",
        ]
        Settings.Parse(dummyConfig)

        # Setup a Structured repository to test against
        line = "deb-src [arch=amd64] http://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64"
        source = Source(line, "amd64")

        baseUrl = source.Uri + "/"

        indexFiles = source.ParseReleaseFiles() # type: list[str]

        # Ensure we actually got some files
        self.assertTrue(len(indexFiles) > 0)

        # For Flat Repositories, the entire contents of the file is read.
        # Therefore, just ensure that the Packages file is added at the very least
        regexes = []
        regexes.append(rf"Packages")
        regexes.append(rf"Packages[^./]*(\.gz|\.bz2|\.xz|$)$")

        # Check that all files downloaded match a Regex expression
        for file in indexFiles:
            found = False
            for regex in regexes:
                found = found or re.match(regex, file.replace(baseUrl, ""))

            self.assertTrue(found)

    @unittest.skip("Flat Source repositories are not supported")
    def test_ParseReleaseFiles_StructuredByHash_Flat_Source(self):
        """
            Check that only files matching the expected regexes are returned for the given repository 
            and configuration settings.
        """

        # Need to setup the Settings specifically for this test
        Settings.Init()
        dummyConfig = [
        f"set skelPath = {self._fixturesDirectory}/ReleaseFiles/Flat",
        "set contents  = False",
        "set byHash    = True",
        "set language  = 'en_GB'",
        ]
        Settings.Parse(dummyConfig)

        # Setup a Structured repository to test against
        line = "deb-src [arch=amd64] http://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64"
        source = Source(line, "amd64")

        baseUrl = source.Uri + "/"

        indexFiles = source.ParseReleaseFiles() # type: list[str]

        # Ensure we actually got some files
        self.assertTrue(len(indexFiles) > 0)

        # For Flat Repositories, the entire contents of the file is read.
        # Therefore, just ensure that the Packages file is added at the very least
        regexes = []
        regexes.append(rf"Packages")
        regexes.append(rf"Packages[^./]*(\.gz|\.bz2|\.xz|$)$")

        # Check that all files downloaded match a Regex expression
        for file in indexFiles:
            found = False
            for regex in regexes:
                found = found or re.match(regex, file.replace(baseUrl, ""))

            self.assertTrue(found)

if __name__ == '__main__':
    unittest.main()
