"""Unit Test Cases for the Classes module."""

import unittest
from urllib import parse
from pathlib import Path
import re
import os

from settings import Settings
from classes import (
    RepositoryType,
    Repository
)

_testDirectory = str(Path(__file__).parent.absolute())
_fixturesDirectory = f"{_testDirectory}/fixtures"

class TestRepository_Init(unittest.TestCase):
    """Test case for the Repository.Init method."""

    def test_InitNoData(self):
        """Check that a Repository initialised with blank arguments raises an exception."""

        self.assertRaises(ValueError, Repository, "", "")

    def test_InitNoLine(self):
        """Check that a Repository initialised with a blank "line" argument raises an exception."""

        self.assertRaises(ValueError, Repository, "", "An Architecture")

    def test_InitNoArchitecture(self):
        """Check that a Repository initialised with a blank "architecture" raises an exception."""

        self.assertRaises(ValueError, Repository, "Random data", "")

    def test_InitMalformedLineNoRepository(self):
        """Check that a Repository initialised with a missing RepositoryType fails."""

        line = "http://gb.archive.ubuntu.com/ubuntu"

        self.assertRaises(ValueError, Repository, line, "amd64")

    def test_InitMalformedLineRepositoryOnly(self):
        """Check that a Repository initialised with a missing uri fails."""

        line = "deb"

        self.assertRaises(ValueError, Repository, line, "amd64")

    def test_InitMalformedLineArchitecture(self):
        """Check that a Repository initialised with a bad Architecture fails."""

        line = "deb [arch anArchitecture]"

        self.assertRaises(ValueError, Repository, line, "amd64")

    def test_InitMalformedLineArchitecture2(self):
        """Check that a Repository initialised with a bad Architecture fails."""

        line = "deb [arch anArchitecture"

        self.assertRaises(ValueError, Repository, line, "amd64")

    def test_InitMalformedLineIncorrectOrder(self):
        """Check that a Repository initialised in an incorrect order fails."""

        line = "deb uri component1 component2 [arch=amd64]"

        self.assertRaises(ValueError, Repository, line, "amd64")

    def test_InitMinimal(self):
        """Check that a minimal example of a Repository definition succeeds."""

        line = "deb http://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64"
        defaultArchitecture = "amd64"

        repository = Repository(line, defaultArchitecture)

        self.assertEqual(repository.RepositoryType, RepositoryType.Bin)
        self.assertListEqual(repository.Architectures, [defaultArchitecture])
        self.assertEqual(repository.Uri, line.split(" ")[1])
        self.assertEqual(repository.Distribution, "")
        self.assertEqual(repository.Components, [])
        self.assertTrue(repository.Clean)

    def test_InitSingleComponent(self):
        """Check that a valid Binary Repository with one Component succeeds."""

        line = "deb http://gb.archive.ubuntu.com/ubuntu focal main"
        defaultArchitecture = "amd64"

        repository = Repository(line, defaultArchitecture)

        self.assertEqual(repository.RepositoryType, RepositoryType.Bin)
        self.assertListEqual(repository.Architectures, [defaultArchitecture])
        self.assertEqual(repository.Uri, line.split(" ")[1])
        self.assertEqual(repository.Distribution, line.split(" ")[2])
        self.assertEqual(repository.Components, line.split(" ")[3:])
        self.assertTrue(repository.Clean)

    def test_InitMultiComponent(self):
        """Check that a valid Binary Repository with multiple Components succeeds."""

        line = "deb http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
        defaultArchitecture = "amd64"

        repository = Repository(line, defaultArchitecture)

        self.assertEqual(repository.RepositoryType, RepositoryType.Bin)
        self.assertListEqual(repository.Architectures, [defaultArchitecture])
        self.assertEqual(repository.Uri, line.split(" ")[1])
        self.assertEqual(repository.Distribution, line.split(" ")[2])
        self.assertEqual(repository.Components, line.split(" ")[3:])
        self.assertTrue(repository.Clean)

    def test_InitRepositorySingleComponent(self):
        """Check that a valid Source Repository with one Component succeeds."""

        line = "deb-src http://gb.archive.ubuntu.com/ubuntu focal main"
        defaultArchitecture = "amd64"

        repository = Repository(line, defaultArchitecture)

        self.assertEqual(repository.RepositoryType, RepositoryType.Src)
        self.assertListEqual(repository.Architectures, [defaultArchitecture])
        self.assertEqual(repository.Uri, line.split(" ")[1])
        self.assertEqual(repository.Distribution, line.split(" ")[2])
        self.assertEqual(repository.Components, line.split(" ")[3:])
        self.assertTrue(repository.Clean)

    def test_InitRepositoryMultiComponent(self):
        """Check that a valid Source Repository with multiple Components succeeds."""

        line = "deb-src http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
        defaultArchitecture = "amd64"

        repository = Repository(line, defaultArchitecture)

        self.assertEqual(repository.RepositoryType, RepositoryType.Src)
        self.assertListEqual(repository.Architectures, [defaultArchitecture])
        self.assertEqual(repository.Uri, line.split(" ")[1])
        self.assertEqual(repository.Distribution, line.split(" ")[2])
        self.assertEqual(repository.Components, line.split(" ")[3:])
        self.assertTrue(repository.Clean)

    def test_InitSingleArchitecture(self):
        """Check that a valid Binary Repository with an explicit Architecture succeeds."""

        architectures = "amd64"
        line = f"deb [arch={architectures}] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
        defaultArchitecture = "default"

        repository = Repository(line, defaultArchitecture)

        self.assertEqual(repository.RepositoryType, RepositoryType.Bin)
        self.assertListEqual(repository.Architectures, [architectures])
        self.assertEqual(repository.Uri, line.split(" ")[2])
        self.assertEqual(repository.Distribution, line.split(" ")[3])
        self.assertEqual(repository.Components, line.split(" ")[4:])
        self.assertTrue(repository.Clean)

    def test_InitMultiArchitecture(self):
        """Check that a valid Binary Repository with an explicit Architecture succeeds."""

        architectures = "amd64,i386,armhf"
        line = f"deb [arch={architectures}] http://archive.raspberrypi.org/debian buster main"
        defaultArchitecture = "default"

        repository = Repository(line, defaultArchitecture)

        self.assertEqual(repository.RepositoryType, RepositoryType.Bin)
        self.assertListEqual(repository.Architectures, architectures.split(","))
        self.assertEqual(repository.Uri, line.split(" ")[2])
        self.assertEqual(repository.Distribution, line.split(" ")[3])
        self.assertEqual(repository.Components, line.split(" ")[4:])
        self.assertTrue(repository.Clean)

class TestRepository_GetReleaseFiles(unittest.TestCase):
    """Test case for the Repository.GetReleaseFiles method."""

    # Release files expected are:
    #   <download-url>/InRelease
    #   <download-url>/Release
    #   <download-url>/Release.gpg
    _expectedReleaseFiles = ["InRelease", "Release", "Release.gpg"]

    def test_GetReleaseFilesBinaryRepository(self):
        """
            Check the expected Release files are returned for a given Binary repository.
            Tests both Flat and Non-Flat repositories.
        """

        # Non-Flat test
        line = "deb http://gb.archive.ubuntu.com/ubuntu focal main"
        defaultArchitecture = "amd64"

        repository = Repository(line, defaultArchitecture)

        self.assertEqual(repository.RepositoryType, RepositoryType.Bin)

        self._CheckReleaseFiles(line, repository.GetReleaseFiles())

        # Flat test
        line = "deb http://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64"
        defaultArchitecture = "amd64"

        repository = Repository(line, defaultArchitecture)

        self.assertEqual(repository.RepositoryType, RepositoryType.Bin)

        self._CheckReleaseFilesFlat(line, repository.GetReleaseFiles())

    def test_GetReleaseFilesSourceRepository(self):
        """
            Check the expected Release files are returned for a given Source repository.
            Tests both Flat and Non-Flat repositories.
        """

        # Non-Flat test
        line = "deb-src http://gb.archive.ubuntu.com/ubuntu focal main"
        defaultArchitecture = "amd64"

        repository = Repository(line, defaultArchitecture)

        self.assertEqual(repository.RepositoryType, RepositoryType.Src)

        self._CheckReleaseFiles(line, repository.GetReleaseFiles())

        # Flat test
        line = "deb-src http://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64"
        defaultArchitecture = "amd64"

        repository = Repository(line, defaultArchitecture)

        self.assertEqual(repository.RepositoryType, RepositoryType.Src)

        self._CheckReleaseFilesFlat(line, repository.GetReleaseFiles())

    def _CheckReleaseFiles(self, line : str, files : list):
        """Check Release files and Download URLs are as expected for a given non-flat repository."""

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
        """Check Release files and Download URLs are as expected for a given flat repository."""
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

# class TestRepository_ParseReleaseFiles(unittest.TestCase):
#     """Test case for the Repository.ParseReleaseFiles method."""

#     _checksumTypes = ["SHA256", "SHA1", "MD5Sum"]

#     def test_ParseReleaseFiles_Structured(self):
#         """
#             Check that only files matching the expected regexes are returned for the given repository 
#             and configuration settings.
#         """

#         # Need to setup the Settings specifically for this test
#         Settings.Init()
#         dummyConfig = [
#         f"set skelPath = {_fixturesDirectory}/Structured",
#         "set contents  = False",
#         "set byHash    = False",
#         "set language  = 'en_GB, de_DE'",
#         ]
#         Settings.Parse(dummyConfig)

#         # Setup a Structured repository to test against
#         line = "deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
#         repository = Repository(line, "amd64")

#         baseUrl = repository.Uri + "/dists/" + repository.Distribution + "/"

#         indexFiles = repository.ParseReleaseFiles() # type: list[str]

#         # Ensure we actually got some files
#         self.assertTrue(len(indexFiles) > 0)

#         # For the configuration settings in the tests, we can expect the following Regexes to apply:       
#         #   rf"{component}/binary-{architecture}/Release"
#         #   rf"{component}/binary-{architecture}/Packages"
#         #   rf"{component}/binary-{architecture}/Packages[^./]*(\.gz|\.bz2|\.xz|$)$"
#         #   rf"{component}/cnf/Commands-{architecture}"
#         #   rf"{component}/i18n/cnf/Commands-{architecture}"
#         #   rf"{component}/i18n/Index"
#         #   rf"{component}/i18n/Translation-{Settings.Language[1 .. X]}"
#         #   rf"{component}/dep11/(Components-{architecture}\.yml|icons-[^./]+\.tar)"
#         #
#         # If none of the Regexes apply, then something is wrong
#         regexes = []
#         for architecture in repository.Architectures:
#             for component in repository.Components:
#                 regexes.append(rf"{component}/binary-{architecture}/Release")
#                 regexes.append(rf"{component}/binary-{architecture}/Packages")
#                 regexes.append(rf"{component}/binary-{architecture}/Packages[^./]*(\.gz|\.bz2|\.xz|$)$")
#                 regexes.append(rf"{component}/cnf/Commands-{architecture}")
#                 regexes.append(rf"{component}/i18n/cnf/Commands-{architecture}")
#                 regexes.append(rf"{component}/i18n/Index")

#                 for language in Settings.Language():
#                     regexes.append(rf"{component}/i18n/Translation-{language}")

#                 regexes.append(rf"{component}/dep11/(Components-{architecture}\.yml|icons-[^./]+\.tar)")

#         # Check that all files downloaded match a Regex expression
#         for file in indexFiles:
#             found = False
#             for regex in regexes:
#                 found = found or re.match(regex, file.replace(baseUrl, ""))

#             self.assertTrue(found)

#     def test_ParseReleaseFiles_StructuredWithContents(self):
#         """
#             Check that only files matching the expected regexes are returned for the given repository 
#             and configuration settings.
#         """

#         # Need to setup the Settings specifically for this test
#         Settings.Init()
#         dummyConfig = [
#         f"set skelPath = {_fixturesDirectory}/Structured",
#         "set contents  = True",
#         "set byHash    = False",
#         "set language  = 'en_GB'",
#         ]
#         Settings.Parse(dummyConfig)

#         # Setup a Structured repository to test against
#         line = "deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
#         repository = Repository(line, "amd64")

#         baseUrl = repository.Uri + "/dists/" + repository.Distribution + "/"

#         indexFiles = repository.ParseReleaseFiles() # type: list[str]

#         # Ensure we actually got some files
#         self.assertTrue(len(indexFiles) > 0)

#         # For the configuration settings in the tests, we can expect the following Regexes to apply: 
#         #   rf"Contents-{architecture}"
#         #   rf"{component}/Contents-{architecture}"
#         #   rf"{component}/binary-{architecture}/Release"
#         #   rf"{component}/binary-{architecture}/Packages"
#         #   rf"{component}/binary-{architecture}/Packages[^./]*(\.gz|\.bz2|\.xz|$)$"
#         #   rf"{component}/cnf/Commands-{architecture}"
#         #   rf"{component}/i18n/cnf/Commands-{architecture}"
#         #   rf"{component}/i18n/Index"
#         #   rf"{component}/i18n/Translation-{Settings.Language()}"
#         #   rf"{component}/dep11/(Components-{architecture}\.yml|icons-[^./]+\.tar)"
#         #
#         # If none of the Regexes apply, then something is wrong
#         regexes = []
#         for architecture in repository.Architectures:
#             regexes.append(rf"Contents-{architecture}")
#             for component in repository.Components:
#                 regexes.append(rf"{component}/Contents-{architecture}")
#                 regexes.append(rf"{component}/binary-{architecture}/Release")
#                 regexes.append(rf"{component}/binary-{architecture}/Packages")
#                 regexes.append(rf"{component}/binary-{architecture}/Packages[^./]*(\.gz|\.bz2|\.xz|$)$")
#                 regexes.append(rf"{component}/cnf/Commands-{architecture}")
#                 regexes.append(rf"{component}/i18n/cnf/Commands-{architecture}")
#                 regexes.append(rf"{component}/i18n/Index")
#                 regexes.append(rf"{component}/i18n/Translation-{Settings.Language()}")
#                 regexes.append(rf"{component}/dep11/(Components-{architecture}\.yml|icons-[^./]+\.tar)")

#         # Check that all files downloaded match a Regex expression
#         for file in indexFiles:
#             found = False
#             for regex in regexes:
#                 found = found or re.match(regex, file.replace(baseUrl, ""))

#             self.assertTrue(found)

#     def test_ParseReleaseFiles_StructuredByHash(self):
#         """
#             Check that only files matching the expected regexes are returned for the given repository 
#             and configuration settings.
#         """

#         # Need to setup the Settings specifically for this test
#         Settings.Init()
#         dummyConfig = [
#         f"set skelPath = {_fixturesDirectory}/Structured",
#         "set contents  = False",
#         "set byHash    = True",
#         "set language  = 'en_GB'",
#         ]
#         Settings.Parse(dummyConfig)

#         # Setup a Structured repository to test against
#         line = "deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
#         repository = Repository(line, "amd64")

#         baseUrl = repository.Uri + "/dists/" + repository.Distribution + "/"

#         indexFiles = repository.ParseReleaseFiles() # type: list[str]

#         # Ensure we actually got some files
#         self.assertTrue(len(indexFiles) > 0)

#         # For the configuration settings in the tests, we can expect the following Regexes to apply: 
#         #   rf"{component}/binary-{architecture}/by-hash/{checksumType}"
#         #   rf"{component}/i18n/by-hash/{checksumType}"
#         #   rf"{component}/binary-{architecture}/Release"
#         #   rf"{component}/binary-{architecture}/Packages"
#         #   rf"{component}/binary-{architecture}/Packages[^./]*(\.gz|\.bz2|\.xz|$)$"
#         #   rf"{component}/cnf/by-hash/{checksumType}"
#         #   rf"{component}/cnf/Commands-{architecture}"
#         #   rf"{component}/i18n/cnf/Commands-{architecture}"
#         #   rf"{component}/i18n/Index"
#         #   rf"{component}/i18n/Translation-{Settings.Language()}"
#         #   rf"{component}/dep11/(Components-{architecture}\.yml|icons-[^./]+\.tar)"
#         #   rf"{component}/dep11/by-hash/{checksumType}"
#         #
#         # If none of the Regexes apply, then something is wrong
#         regexes = []
#         for architecture in repository.Architectures:
#             for component in repository.Components:
#                 for checksumType in self._checksumTypes:
#                     regexes.append(rf"{component}/binary-{architecture}/by-hash/{checksumType}")
#                     regexes.append(rf"{component}/i18n/by-hash/{checksumType}")
#                     regexes.append(rf"{component}/cnf/by-hash/{checksumType}")
#                     regexes.append(rf"{component}/dep11/by-hash/{checksumType}")
#                 regexes.append(rf"{component}/binary-{architecture}/Release")
#                 regexes.append(rf"{component}/binary-{architecture}/Packages")
#                 regexes.append(rf"{component}/binary-{architecture}/Packages[^./]*(\.gz|\.bz2|\.xz|$)$")
#                 regexes.append(rf"{component}/cnf/Commands-{architecture}")
#                 regexes.append(rf"{component}/i18n/cnf/Commands-{architecture}")
#                 regexes.append(rf"{component}/i18n/Index")
#                 regexes.append(rf"{component}/i18n/Translation-{Settings.Language()}")
#                 regexes.append(rf"{component}/dep11/(Components-{architecture}\.yml|icons-[^./]+\.tar)")

#         # Check that all files downloaded match a Regex expression
#         for file in indexFiles:
#             found = False
#             for regex in regexes:
#                 found = found or re.match(regex, file.replace(baseUrl, ""))

#             self.assertTrue(found)

#     def test_ParseReleaseFiles_Structured_Flat(self):
#         """
#             Check that only files matching the expected regexes are returned for the given repository 
#             and configuration settings.
#         """

#         # Need to setup the Settings specifically for this test
#         Settings.Init()
#         dummyConfig = [
#         f"set skelPath = {_fixturesDirectory}/Flat",
#         "set contents  = False",
#         "set byHash    = False",
#         "set language  = 'en_GB'",
#         ]
#         Settings.Parse(dummyConfig)

#         # Setup a Structured repository to test against
#         line = "deb [arch=amd64] http://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64"
#         repository = Repository(line, "amd64")

#         baseUrl = repository.Uri + "/"

#         indexFiles = repository.ParseReleaseFiles() # type: list[str]

#         # Ensure we actually got some files
#         self.assertTrue(len(indexFiles) > 0)

#         # For Flat Repositories, the entire contents of the file is read.
#         # Therefore, just ensure that the Packages file is added at the very least
#         regexes = []
#         regexes.append(rf"Packages")
#         regexes.append(rf"Packages[^./]*(\.gz|\.bz2|\.xz|$)$")

#         # Check that all files downloaded match a Regex expression
#         for file in indexFiles:
#             found = False
#             for regex in regexes:
#                 found = found or re.match(regex, file.replace(baseUrl, ""))

#             self.assertTrue(found)

#     def test_ParseReleaseFiles_StructuredWithContents_Flat(self):
#         """
#             Check that only files matching the expected regexes are returned for the given repository 
#             and configuration settings.
#         """

#         # Need to setup the Settings specifically for this test
#         Settings.Init()
#         dummyConfig = [
#         f"set skelPath = {_fixturesDirectory}/Flat",
#         "set contents  = True",
#         "set byHash    = False",
#         "set language  = 'en_GB'",
#         ]
#         Settings.Parse(dummyConfig)

#         # Setup a Structured repository to test against
#         line = "deb [arch=amd64] http://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64"
#         repository = Repository(line, "amd64")

#         baseUrl = repository.Uri + "/"

#         indexFiles = repository.ParseReleaseFiles() # type: list[str]

#         # Ensure we actually got some files
#         self.assertTrue(len(indexFiles) > 0)

#         # For Flat Repositories, the entire contents of the file is read.
#         # Therefore, just ensure that the Packages file is added at the very least
#         regexes = []
#         regexes.append(rf"Packages")
#         regexes.append(rf"Packages[^./]*(\.gz|\.bz2|\.xz|$)$")

#         # Check that all files downloaded match a Regex expression
#         for file in indexFiles:
#             found = False
#             for regex in regexes:
#                 found = found or re.match(regex, file.replace(baseUrl, ""))

#             self.assertTrue(found)

#     def test_ParseReleaseFiles_StructuredByHash_Flat(self):
#         """
#             Check that only files matching the expected regexes are returned for the given repository 
#             and configuration settings.
#         """

#         # Need to setup the Settings specifically for this test
#         Settings.Init()
#         dummyConfig = [
#         f"set skelPath = {_fixturesDirectory}/Flat",
#         "set contents  = False",
#         "set byHash    = True",
#         "set language  = 'en_GB'",
#         ]
#         Settings.Parse(dummyConfig)

#         # Setup a Structured repository to test against
#         line = "deb [arch=amd64] http://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64"
#         repository = Repository(line, "amd64")

#         baseUrl = repository.Uri + "/"

#         indexFiles = repository.ParseReleaseFiles() # type: list[str]

#         # Ensure we actually got some files
#         self.assertTrue(len(indexFiles) > 0)

#         # For Flat Repositories, the entire contents of the file is read.
#         # Therefore, just ensure that the Packages file is added at the very least
#         regexes = []
#         regexes.append(rf"Packages")
#         regexes.append(rf"Packages[^./]*(\.gz|\.bz2|\.xz|$)$")

#         # Check that all files downloaded match a Regex expression
#         for file in indexFiles:
#             found = False
#             for regex in regexes:
#                 found = found or re.match(regex, file.replace(baseUrl, ""))

#             self.assertTrue(found)

#     def test_ParseReleaseFiles_Structured_Repository(self):
#         """
#             Check that only files matching the expected regexes are returned for the given repository 
#             and configuration settings.
#         """

#         # Need to setup the Settings specifically for this test
#         Settings.Init()
#         dummyConfig = [
#         f"set skelPath = {_fixturesDirectory}/Structured",
#         "set contents  = False",
#         "set byHash    = False",
#         "set language  = 'en_GB'",
#         ]
#         Settings.Parse(dummyConfig)

#         # Setup a Structured repository to test against
#         line = "deb-src http://deb.debian.org/debian/ bullseye-updates main contrib non-free"
#         repository = Repository(line, "amd64")

#         baseUrl = repository.Uri + "/dists/" + repository.Distribution + "/"

#         indexFiles = repository.ParseReleaseFiles() # type: list[str]

#         # Ensure we actually got some files
#         self.assertTrue(len(indexFiles) > 0)

#         # For the configuration settings in the tests, we can expect the following Regexes to apply:       
#         #   rf"{component}/source/Release"
#         #   rf"{component}/source/Sources[^./]*(\.gz|\.bz2|\.xz|$)$"
#         #
#         # If none of the Regexes apply, then something is wrong
#         regexes = []
#         for component in repository.Components:
#             regexes.append(rf"{component}/source/Release")
#             regexes.append(rf"{component}/source/Sources[^./]*(\.gz|\.bz2|\.xz|$)$")

#         # Check that all files downloaded match a Regex expression
#         for file in indexFiles:
#             found = False
#             for regex in regexes:
#                 found = found or re.match(regex, file.replace(baseUrl, ""))

#             self.assertTrue(found)

#     def test_ParseReleaseFiles_StructuredWithContents_Repository(self):
#         """
#             Check that only files matching the expected regexes are returned for the given repository 
#             and configuration settings.
#         """

#         # Need to setup the Settings specifically for this test
#         Settings.Init()
#         dummyConfig = [
#         f"set skelPath = {_fixturesDirectory}/Structured",
#         "set contents  = True",
#         "set byHash    = False",
#         "set language  = 'en_GB'",
#         ]
#         Settings.Parse(dummyConfig)

#         # Setup a Structured repository to test against
#         line = "deb-src [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
#         repository = Repository(line, "amd64")

#         baseUrl = repository.Uri + "/dists/" + repository.Distribution + "/"

#         indexFiles = repository.ParseReleaseFiles() # type: list[str]

#         # Ensure we actually got some files
#         self.assertTrue(len(indexFiles) > 0)

#         # For the configuration settings in the tests, we can expect the following Regexes to apply:       
#         #   rf"{component}/source/Release"
#         #   rf"{component}/source/Sources"
#         #
#         # If none of the Regexes apply, then something is wrong
#         regexes = []
#         for component in repository.Components:
#             regexes.append(rf"{component}/source/Release")
#             regexes.append(rf"{component}/source/Sources")

#         # Check that all files downloaded match a Regex expression
#         for file in indexFiles:
#             found = False
#             for regex in regexes:
#                 found = found or re.match(regex, file.replace(baseUrl, ""))

#             self.assertTrue(found)

#     def test_ParseReleaseFiles_StructuredByHash_Repository(self):
#         """
#             Check that only files matching the expected regexes are returned for the given repository 
#             and configuration settings.
#         """

#         # Need to setup the Settings specifically for this test
#         Settings.Init()
#         dummyConfig = [
#         f"set skelPath = {_fixturesDirectory}/Structured",
#         "set contents  = False",
#         "set byHash    = True",
#         "set language  = 'en_GB'",
#         ]
#         Settings.Parse(dummyConfig)

#         # Setup a Structured repository to test against
#         line = "deb-src [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
#         repository = Repository(line, "amd64")

#         baseUrl = repository.Uri + "/dists/" + repository.Distribution + "/"

#         indexFiles = repository.ParseReleaseFiles() # type: list[str]

#         # Ensure we actually got some files
#         self.assertTrue(len(indexFiles) > 0)

#         # For the configuration settings in the tests, we can expect the following Regexes to apply:       
#         #   rf"{component}/source/Release"
#         #   rf"{component}/source/Sources"
#         #
#         # If none of the Regexes apply, then something is wrong
#         regexes = []
#         for component in repository.Components:
#             regexes.append(rf"{component}/source/Release")
#             regexes.append(rf"{component}/source/Sources")

#         # Check that all files downloaded match a Regex expression
#         for file in indexFiles:
#             found = False
#             for regex in regexes:
#                 found = found or re.match(regex, file.replace(baseUrl, ""))

#             self.assertTrue(found)

#     @unittest.skip("Flat Source repositories are not supported")
#     def test_ParseReleaseFiles_Structured_Flat_Repository(self):
#         """
#             Check that only files matching the expected regexes are returned for the given repository 
#             and configuration settings.
#         """

#         # Need to setup the Settings specifically for this test
#         Settings.Init()
#         dummyConfig = [
#         f"set skelPath = {_fixturesDirectory}/Flat",
#         "set contents  = False",
#         "set byHash    = False",
#         "set language  = 'en_GB'",
#         ]
#         Settings.Parse(dummyConfig)

#         # Setup a Structured repository to test against
#         line = "deb-src [arch=amd64] http://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64"
#         repository = Repository(line, "amd64")

#         baseUrl = repository.Uri + "/"

#         indexFiles = repository.ParseReleaseFiles() # type: list[str]

#         # Ensure we actually got some files
#         self.assertTrue(len(indexFiles) > 0)

#         # For Flat Repositories, the entire contents of the file is read.
#         # Therefore, just ensure that the Packages file is added at the very least
#         regexes = []
#         regexes.append(rf"Packages")
#         regexes.append(rf"Packages[^./]*(\.gz|\.bz2|\.xz|$)$")

#         # Check that all files downloaded match a Regex expression
#         for file in indexFiles:
#             found = False
#             for regex in regexes:
#                 found = found or re.match(regex, file.replace(baseUrl, ""))

#             self.assertTrue(found)

#     @unittest.skip("Flat Source repositories are not supported")
#     def test_ParseReleaseFiles_StructuredWithContents_Flat_Repository(self):
#         """
#             Check that only files matching the expected regexes are returned for the given repository 
#             and configuration settings.
#         """

#         # Need to setup the Settings specifically for this test
#         Settings.Init()
#         dummyConfig = [
#         f"set skelPath = {_fixturesDirectory}/Flat",
#         "set contents  = True",
#         "set byHash    = False",
#         "set language  = 'en_GB'",
#         ]
#         Settings.Parse(dummyConfig)

#         # Setup a Structured repository to test against
#         line = "deb-src [arch=amd64] http://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64"
#         repository = Repository(line, "amd64")

#         baseUrl = repository.Uri + "/"

#         indexFiles = repository.ParseReleaseFiles() # type: list[str]

#         # Ensure we actually got some files
#         self.assertTrue(len(indexFiles) > 0)

#         # For Flat Repositories, the entire contents of the file is read.
#         # Therefore, just ensure that the Packages file is added at the very least
#         regexes = []
#         regexes.append(rf"Packages")
#         regexes.append(rf"Packages[^./]*(\.gz|\.bz2|\.xz|$)$")

#         # Check that all files downloaded match a Regex expression
#         for file in indexFiles:
#             found = False
#             for regex in regexes:
#                 found = found or re.match(regex, file.replace(baseUrl, ""))

#             self.assertTrue(found)

#     @unittest.skip("Flat Source repositories are not supported")
#     def test_ParseReleaseFiles_StructuredByHash_Flat_Repository(self):
#         """
#             Check that only files matching the expected regexes are returned for the given repository 
#             and configuration settings.
#         """

#         # Need to setup the Settings specifically for this test
#         Settings.Init()
#         dummyConfig = [
#         f"set skelPath = {_fixturesDirectory}/Flat",
#         "set contents  = False",
#         "set byHash    = True",
#         "set language  = 'en_GB'",
#         ]
#         Settings.Parse(dummyConfig)

#         # Setup a Structured repository to test against
#         line = "deb-src [arch=amd64] http://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64"
#         repository = Repository(line, "amd64")

#         baseUrl = repository.Uri + "/"

#         indexFiles = repository.ParseReleaseFiles() # type: list[str]

#         # Ensure we actually got some files
#         self.assertTrue(len(indexFiles) > 0)

#         # For Flat Repositories, the entire contents of the file is read.
#         # Therefore, just ensure that the Packages file is added at the very least
#         regexes = []
#         regexes.append(rf"Packages")
#         regexes.append(rf"Packages[^./]*(\.gz|\.bz2|\.xz|$)$")

#         # Check that all files downloaded match a Regex expression
#         for file in indexFiles:
#             found = False
#             for regex in regexes:
#                 found = found or re.match(regex, file.replace(baseUrl, ""))

#             self.assertTrue(found)

class TestRepository_Timestamp(unittest.TestCase):
    """Test case for the Repository.Timestamp method."""

    def test_Timestamp(self):
        """Ensure that calling this with not files does not cause a crash."""

        line = "deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
        repository = Repository(line, "amd64")

        repository.Timestamp()

# class TestRepository_GetIndexFiles(unittest.TestCase):
#     """Test case for the Repository.GetIndexFiles method."""

#     def test_GetIndexFiles_EmptyRepository(self):
#         """Test that querying index files without parsing a Release file returns nothing in both cases."""

#         line = "deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
#         repository = Repository(line, "amd64")

#         self.assertTrue(len(repository.GetIndexFiles(True)) == 0) # All modified files
#         self.assertTrue(len(repository.GetIndexFiles(False)) == 0) # All unmodified files

    # def test_GetIndexFiles(self):
    #     """Check the Index files returned are expected when Timestamp has not been called."""

    #     # Need to setup the Settings specifically for this test
    #     Settings.Init()
    #     dummyConfig = [
    #     f"set skelPath = {_fixturesDirectory}/Structured",
    #     "set contents  = False",
    #     "set byHash    = False",
    #     "set language  = 'en_GB'",
    #     ]
    #     Settings.Parse(dummyConfig)

    #     # Setup a Structured repository to test against
    #     line = "deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
    #     repository = Repository(line, "amd64")

    #     indexFiles = repository.ParseReleaseFiles() # type: list[str]

    #     # Ensure we actually got some files
    #     self.assertTrue(len(indexFiles) > 0)

    #     # Current Timestamp will not match the Download Timestamp and Timestamp has not been called
    #     self.assertTrue(len(repository.GetIndexFiles(True)) > 0)
    #     # All unmodified files should be returned.
    #     self.assertTrue(len(repository.GetIndexFiles(False)) > 0)

    #     # Ensure files exist within original indexFiles that were requested
    #     for file in repository.GetIndexFiles(True):
    #         self.assertTrue(any(file in s for s in indexFiles))
    #     for file in repository.GetIndexFiles(False):
    #         self.assertTrue(any(file in s for s in indexFiles))

    # def test_GetIndexFiles_Timestamped(self):
    #     """Check the Index files returned are expected when Timestamp has been called."""

    #     # Need to setup the Settings specifically for this test
    #     Settings.Init()
    #     dummyConfig = [
    #     f"set skelPath = {_fixturesDirectory}/Structured",
    #     "set contents  = False",
    #     "set byHash    = False",
    #     "set language  = 'en_GB'",
    #     ]
    #     Settings.Parse(dummyConfig)

    #     # Setup a Structured repository to test against
    #     line = "deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
    #     repository = Repository(line, "amd64")

    #     indexFiles = repository.ParseReleaseFiles() # type: list[str]

    #     # Ensure we actually got some files
    #     self.assertTrue(len(indexFiles) > 0)

    #     # Timestamp the files
    #     repository.Timestamp()

    #     # Files have been timestamped. The files already existed on disk, so were timestamped during Parse.
    #     # The files after "download" (not performed here, already on disk), are equal - therefore Modified
    #     # files is False
    #     self.assertTrue(len(repository.GetIndexFiles(True)) == 0)
    #     # Therefore, all unmodified files should be returned.
    #     self.assertTrue(len(repository.GetIndexFiles(False)) > 0)

    #     # Ensure files exist within original indexFiles that were requested
    #     for file in repository.GetIndexFiles(True):
    #         self.assertTrue(any(file in s for s in indexFiles))
    #     for file in repository.GetIndexFiles(False):
    #         self.assertTrue(any(file in s for s in indexFiles))

class TestRepository_Properties(unittest.TestCase):
    """Test case for each of the Repository class Properties."""

    def test_RepositoryType_Binary(self):
        """Test that a Binary Repository is correctly identified."""

        line = "deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
        repository = Repository(line, "amd64")

        self.assertEqual(repository.RepositoryType, RepositoryType.Bin)

    def test_RepositoryType_Source(self):
        """Test that a Source Repository is correctly identified."""

        line = "deb-src [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
        repository = Repository(line, "amd64")

        self.assertEqual(repository.RepositoryType, RepositoryType.Src)

    def test_Uri(self):
        """Test that a Uri is correctly identified."""

        uris = [
            "http://gb.archive.ubuntu.com/ubuntu",
            "http://ftp.debian.org/debian",
            "http://security.debian.org",
            "http://archive.raspberrypi.org/debian",
            "http://raspbian.raspberrypi.org/raspbian",
            "https://repos.influxdata.com/debian",
            "https://repos.influxdata.com/ubuntu",
            "http://ppa.launchpad.net/ansible/ansible/ubuntu",
            "http://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64"
        ]

        for uri in uris:
            line = f"deb [arch=amd64] {uri} dist component1"
            repository = Repository(line, "amd64")

            self.assertEqual(repository.Uri, uri)

    def test_Distribution(self):
        """Test that a Distribution is correctly identified."""
        
        distributions = [
            "focal",
            "focal-security",
            "focal-updates",
            "focal-proposed",
            "focal-backports",
            "buster",
            "buster-updates",
            "buster/updates",
            ""
        ]

        for dist in distributions:
            line = f"deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu {dist}"
            if dist:
                line += " component1"

            repository = Repository(line, "amd64")
            self.assertEqual(repository.Distribution, dist)

    def test_Components(self):
        """Test that Components are correctly identified."""
        
        componentList = [
            ["main", "restricted", "universe", "multiverse"],
            ["main", "contrib", "non-free"],
            ["main"],
            ["stable"],
            []
        ]

        for components in componentList:
            line = f"deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu dist {' '.join(components)}"

            repository = Repository(line, "amd64")
            self.assertListEqual(repository.Components, components)

    def test_Architectures(self):
        """Test that Architectures are correctly identified."""
        
        architectures = [
            "Alpa",
            "Arm",
            "Armel",
            "armhf",
            "arm64",
            "hppa",
            "i386",
            "amd64",
            "ia64",
            "m68k",
            "mips",
            "mipsel",
            "mipsel",
            "mips64el",
            "PowerPC",
            "PPC64",
            "ppc64el",
            "riscv64",
            "s390",
            "s390x",
            "SH4",
            "sparc64",
            "x32",
            "amd64,i386,armhf",
            "amd64 , i386 , armhf",
        ]

        for arch in architectures:
            line = f"deb [arch={arch}] http://gb.archive.ubuntu.com/ubuntu dist"

            repository = Repository(line, "default")

            if "," in arch:
                self.assertListEqual(arch.split(","), repository.Architectures)
            else:
                self.assertIn(arch, repository.Architectures)

    def test_Clean(self):
        """Test that Clean Property is correctly read."""

        line = f"deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu dist"

        repository = Repository(line, "default")

        # Clean is defuault behaviour
        self.assertTrue(repository.Clean)

        repository.Clean = False
        self.assertFalse(repository.Clean)

    # def test_Modified(self):
    #     """Test that Modified is correctly identified."""

    #     # Need to setup the Settings specifically for this test
    #     Settings.Init()
    #     dummyConfig = [
    #     f"set skelPath = {_fixturesDirectory}/Structured",
    #     "set contents  = False",
    #     "set byHash    = False",
    #     "set language  = 'en_GB'",
    #     ]
    #     Settings.Parse(dummyConfig)

    #     line = f"deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main"

    #     repository = Repository(line, "default")

    #     # No files added to Collection, so Repository is unmodified
    #     self.assertFalse(repository.Modified)

    #     # Parse files to set Current Timestamps of existing files
    #     repository.ParseReleaseFiles()
    #     self.assertTrue(repository.Modified) # Current Timestamp != 0 (default Download timestamp)

    #     repository.Timestamp()
    #     self.assertFalse(repository.Modified) # Current Timestamp == Modified Timestamp

if __name__ == '__main__':
    unittest.main()
