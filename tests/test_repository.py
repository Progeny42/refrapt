"""Unit Test Cases for the Classes.Repository module."""

import unittest
from urllib import parse
from pathlib import Path
import re
import os

from refrapt.settings import Settings
from refrapt.classes import (
    RepositoryType,
    Repository
)

_testDirectory = str(Path(__file__).parent.absolute())
_fixturesDirectory = f"{_testDirectory}/fixtures"
_repositoryRegex = r"^(deb(-src)*) ?(\[arch=\w+(, ?(\w+))*\])? (\S+)(\s*$| ([a-zA-Z0-9_\-\/]+) ((\w+)( [a-zA-Z0-9_\-]*)*)(\s?[#].*)?)$"


class TestRepository_Init(unittest.TestCase):
    """Test case for the Repository.Init method."""

    _missingParams = [
        ("", ""), 
        ("", "An Architecture"), 
        ("Random data", "")
    ]

    def test_InitMissingParams(self):

        for p1, p2 in self._missingParams:
            with self.subTest():
                self.assertRaises(AssertionError, Repository, p1, p2)


    _malformedRepos = [
        "http://gb.archive.ubuntu.com/ubuntu",
        "deb",
        "deb [arch anArchitecture]",
        "deb [arch anArchitecture",
        "deb uri component1 component2 [arch=amd64]",
        "# not a repo",
        "deb[arch=amd64]https://repos.influxdata.com/ubuntufocalstable"
    ]

    def test_InitMalformedRepository(self):

        for repo in self._malformedRepos:
            with self.subTest():
                self.assertRaises(ValueError, Repository, repo, "amd64")

    _validRepos = [
        "deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse",
        "deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal-security main restricted universe multiverse",
        "deb [arch=amd64,i386] http://ftp.debian.org/debian buster main contrib non-free",
        "deb [arch=amd64,i386] http://ftp.debian.org/debian buster-updates main contrib non-free",
        "deb [arch=amd64,i386] http://security.debian.org buster/updates main contrib non-free",
        "deb [arch=amd64,i386,armhf] http://archive.raspberrypi.org/debian buster main",
        "deb [arch=amd64,i386,armhf] https://repos.influxdata.com/debian buster stable",
        "deb [arch=amd64] https://repos.influxdata.com/ubuntu focal stable",
        "deb [arch=amd64] http://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64",
        "deb-src [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse",
        "deb-src [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal-security main restricted universe multiverse",
        "deb-src [arch=amd64,i386] http://ftp.debian.org/debian buster main contrib non-free",
        "deb-src [arch=amd64,i386] http://ftp.debian.org/debian buster-updates main contrib non-free",
        "deb-src [arch=amd64,i386] http://security.debian.org buster/updates main contrib non-free",
        "deb-src [arch=amd64,i386,armhf] http://archive.raspberrypi.org/debian buster main",
        "deb-src [arch=amd64,i386,armhf] https://repos.influxdata.com/debian buster stable",
        "deb-src [arch=amd64] https://repos.influxdata.com/ubuntu focal stable",
        "deb-src [arch=amd64] http://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64",
        "deb http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse",
        "deb-src  http://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64",
    ]

    def test_InitValidRepos(self):
        

        for repo in self._validRepos:
            with self.subTest():
                defaultArchitecture = "amd64"
                repository = Repository(repo, defaultArchitecture)

                elements = re.search(_repositoryRegex, repo)

                repositoryType = elements.group(1)
                if repositoryType == "deb":
                    repoType = RepositoryType.Bin
                elif repositoryType == "deb-src":
                    repoType = RepositoryType.Src

                architectures = elements.group(3)
                if architectures:
                    architectures = architectures.replace("[arch=", "").replace(']', "")

                    architectureList = [x.strip() for x in architectures.split(',')]
                else:
                    architectureList = [ defaultArchitecture ]

                components = elements.group(9)
                if components:
                    componentList = [x.strip() for x in components.split(" ")]
                else:
                    componentList = []

                self.assertEqual(repository.RepositoryType, repoType)
                self.assertListEqual(repository.Architectures, architectureList)
                self.assertEqual(repository.Uri, elements.group(6))
                self.assertEqual(repository.Distribution, elements.group(8))
                self.assertEqual(repository.Components, componentList)
                self.assertTrue(repository.Clean)

class TestRepository_GetReleaseFiles(unittest.TestCase):
    """Test case for the Repository.GetReleaseFiles method."""

    # Release files expected are:
    #   <download-url>/InRelease
    #   <download-url>/Release
    #   <download-url>/Release.gpg
    _expectedReleaseFiles = ["InRelease", "Release", "Release.gpg"]

    _repositories = [
        "deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse",
        "deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal-security main restricted universe multiverse",
        "deb [arch=amd64,i386] http://ftp.debian.org/debian buster main contrib non-free",
        "deb [arch=amd64,i386] http://ftp.debian.org/debian buster-updates main contrib non-free",
        "deb [arch=amd64,i386] http://security.debian.org buster/updates main contrib non-free",
        "deb [arch=amd64,i386,armhf] http://archive.raspberrypi.org/debian buster main",
        "deb [arch=amd64,i386,armhf] https://repos.influxdata.com/debian buster stable",
        "deb [arch=amd64] https://repos.influxdata.com/ubuntu focal stable",
        "deb [arch=amd64] http://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64",
        "deb-src [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse",
        "deb-src [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal-security main restricted universe multiverse",
        "deb-src [arch=amd64,i386] http://ftp.debian.org/debian buster main contrib non-free",
        "deb-src [arch=amd64,i386] http://ftp.debian.org/debian buster-updates main contrib non-free",
        "deb-src [arch=amd64,i386] http://security.debian.org buster/updates main contrib non-free",
        "deb-src [arch=amd64,i386,armhf] http://archive.raspberrypi.org/debian buster main",
        "deb-src [arch=amd64,i386,armhf] https://repos.influxdata.com/debian buster stable",
        "deb-src [arch=amd64] https://repos.influxdata.com/ubuntu focal stable",
        "deb-src [arch=amd64] http://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64",
    ]

    def test_GetReleaseFiles(self):

        for repo in self._repositories:
            with self.subTest():
                defaultArchitecture = "amd64"
                repository = Repository(repo, defaultArchitecture)

                elements = re.search(_repositoryRegex, repo)

                repositoryType = elements.group(1)
                if repositoryType == "deb":
                    repoType = RepositoryType.Bin
                elif repositoryType == "deb-src":
                    repoType = RepositoryType.Src

                self.assertEqual(repository.RepositoryType, repoType)

                releaseFiles = repository.GetReleaseFiles()

                self.assertTrue(len(releaseFiles) == len(self._expectedReleaseFiles))

                for file in releaseFiles:
                    uri = elements.group(6)
                    distribution = elements.group(8)

                    if repository.Components:
                        expectedUrl = f"{uri}/dists/{distribution}"
                    else:
                        expectedUrl = uri

                    splitUrl = parse.urlsplit(file)
                    actualUrl = f"{splitUrl.scheme}://{splitUrl.netloc}{splitUrl.path}"
                    actualUrl = "".join(actualUrl.rpartition("/")[:-2])

                    self.assertEqual(expectedUrl, actualUrl)

                    filename = "".join(splitUrl.path.rpartition("/")[2])
                    self.assertIn(filename, self._expectedReleaseFiles)

class TestRepository_ParseReleaseFilesFromLocalMirror(unittest.TestCase):

    _checksumTypes = ["SHA256", "SHA1", "MD5Sum"]

    def _ParseReleaseFilesChecks(self, repository: Repository, indexFiles: list[str]):

        if repository.Components:
            baseUrl = repository.Uri + "/dists/" + repository.Distribution + "/"
        else:
            baseUrl = repository.Uri + "/"

        # Ensure we actually got some files
        self.assertTrue(len(indexFiles) > 0)

        # For the configuration settings in the tests, we can expect the following Regexes to apply:       
        #   rf"{component}/binary-{architecture}/Release"
        #   rf"{component}/binary-{architecture}/Packages"
        #   rf"{component}/binary-{architecture}/Packages[^./]*(\.gz|\.bz2|\.xz|$)$"
        #   rf"{component}/cnf/Commands-{architecture}"
        #   rf"{component}/i18n/cnf/Commands-{architecture}"
        #   rf"{component}/i18n/Index"
        #   rf"{component}/i18n/Translation-{Settings.Language[1 .. X]}"
        #   rf"{component}/dep11/(Components-{architecture}\.yml|icons-[^./]+\.tar)"
        #
        # If none of the Regexes apply, then something is wrong
        regexes = []
        for architecture in repository.Architectures:
            if Settings.Contents() and repository.RepositoryType == RepositoryType.Bin:
                regexes.append(rf"Contents-{architecture}")
            for component in repository.Components:
                if Settings.Contents() and repository.RepositoryType == RepositoryType.Bin:
                    regexes.append(rf"{component}/Contents-{architecture}")
                regexes.append(rf"{component}/binary-{architecture}/Release")
                regexes.append(rf"{component}/binary-{architecture}/Packages")
                regexes.append(rf"{component}/binary-{architecture}/Packages[^./]*(\.gz|\.bz2|\.xz|$)$")
                regexes.append(rf"{component}/cnf/Commands-{architecture}")
                regexes.append(rf"{component}/i18n/cnf/Commands-{architecture}")
                regexes.append(rf"{component}/i18n/Index")

                for language in Settings.Language():
                    regexes.append(rf"{component}/i18n/Translation-{language}")

                regexes.append(rf"{component}/dep11/(Components-{architecture}\.yml|icons-[^./]+\.tar)")

                if Settings.ByHash() and repository.RepositoryType == RepositoryType.Bin:
                    for checksumType in self._checksumTypes:
                        # TODO : I don't know why, but this does not appear to work for the ByHash test
                        regexes.append(rf"{baseUrl}{component}/binary-{architecture}/by-hash/{checksumType}/\w+")
                        regexes.append(rf"{baseUrl}{component}/cnf/by-hash/{checksumType}/\w+")
                        regexes.append(rf"{baseUrl}{component}/i18n/by-hash/{checksumType}/\w+")
                        regexes.append(rf"{baseUrl}{component}/dep11/by-hash/{checksumType}/\w+")

        # Check that all files downloaded match a Regex expression
        for file in indexFiles:
            found = False
            for regex in regexes:
                match = re.match(regex, file.replace(baseUrl, ""))

                if match != None:
                    found = found or match

            if not found:
                for regex in regexes:
                    print(regex.replace(baseUrl, ""))
                f = file.replace(baseUrl, "")
                print(f"File: '{f}'")

            self.assertTrue(found)

    _structuredRepos = [
        "deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse",
        "deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal-security main restricted universe multiverse",
        "deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal-updates main restricted universe multiverse",
        "deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal-proposed main restricted universe multiverse",
        "deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal-backports main restricted universe multiverse",
        "deb [arch=amd64,i386] http://ftp.debian.org/debian buster main contrib non-free",
        "deb [arch=amd64,i386] http://ftp.debian.org/debian buster-updates main contrib non-free",
        "deb [arch=amd64,i386] http://security.debian.org buster/updates main contrib non-free",
        "deb [arch=amd64,i386,armhf] http://archive.raspberrypi.org/debian buster main",
    ]

    def test_ParseReleaseFilesFromLocalMirror_Structured(self):
        # Need to setup the Settings specifically for this test
        Settings.Init()
        dummyConfig = [
        f"set mirrorPath = {_fixturesDirectory}/Structured",
        "set contents  = False",
        "set byHash    = False",
        "set language  = 'en_GB, de_DE'",
        ]
        Settings.Parse(dummyConfig)

        for repo in self._structuredRepos:
            with self.subTest():
                repository = Repository(repo, "amd64")

                indexFiles = repository.ParseReleaseFilesFromLocalMirror() # type: list[str]

                self._ParseReleaseFilesChecks(repository, indexFiles)

    def test_ParseReleaseFilesFromLocalMirror_StructuredWithContents(self):
        # Need to setup the Settings specifically for this test
        Settings.Init()
        dummyConfig = [
        f"set mirrorPath = {_fixturesDirectory}/Structured",
        "set contents  = True",
        "set byHash    = False",
        "set language  = 'en_GB, de_DE'",
        ]
        Settings.Parse(dummyConfig)

        for repo in self._structuredRepos:
            with self.subTest():
                repository = Repository(repo, "amd64")

                indexFiles = repository.ParseReleaseFilesFromLocalMirror() # type: list[str]

                self._ParseReleaseFilesChecks(repository, indexFiles)


    def test_ParseReleaseFilesFromLocalMirror_StructuredByHash(self):
        # Need to setup the Settings specifically for this test
        Settings.Init()
        dummyConfig = [
        f"set mirrorPath = {_fixturesDirectory}/Structured",
        "set contents  = False",
        "set byHash    = True",
        "set language  = 'en_GB, de_DE'",
        ]
        Settings.Parse(dummyConfig)

        for repo in self._structuredRepos:
            with self.subTest():
                repository = Repository(repo, "amd64")

                indexFiles = repository.ParseReleaseFilesFromLocalMirror() # type: list[str]

                self._ParseReleaseFilesChecks(repository, indexFiles)

# class TestRepository_Timestamp(unittest.TestCase):
#     """Test case for the Repository.Timestamp method."""

#     def test_Timestamp(self):
#         """Ensure that calling this with not files does not cause a crash."""

#         line = "deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
#         repository = Repository(line, "amd64")

#         repository.Timestamp()

# # class TestRepository_GetIndexFiles(unittest.TestCase):
# #     """Test case for the Repository.GetIndexFiles method."""

# #     def test_GetIndexFiles_EmptyRepository(self):
# #         """Test that querying index files without parsing a Release file returns nothing in both cases."""

# #         line = "deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
# #         repository = Repository(line, "amd64")

# #         self.assertTrue(len(repository.GetIndexFiles(True)) == 0) # All modified files
# #         self.assertTrue(len(repository.GetIndexFiles(False)) == 0) # All unmodified files

#     # def test_GetIndexFiles(self):
#     #     """Check the Index files returned are expected when Timestamp has not been called."""

#     #     # Need to setup the Settings specifically for this test
#     #     Settings.Init()
#     #     dummyConfig = [
#     #     f"set skelPath = {_fixturesDirectory}/Structured",
#     #     "set contents  = False",
#     #     "set byHash    = False",
#     #     "set language  = 'en_GB'",
#     #     ]
#     #     Settings.Parse(dummyConfig)

#     #     # Setup a Structured repository to test against
#     #     line = "deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
#     #     repository = Repository(line, "amd64")

#     #     indexFiles = repository.ParseReleaseFiles() # type: list[str]

#     #     # Ensure we actually got some files
#     #     self.assertTrue(len(indexFiles) > 0)

#     #     # Current Timestamp will not match the Download Timestamp and Timestamp has not been called
#     #     self.assertTrue(len(repository.GetIndexFiles(True)) > 0)
#     #     # All unmodified files should be returned.
#     #     self.assertTrue(len(repository.GetIndexFiles(False)) > 0)

#     #     # Ensure files exist within original indexFiles that were requested
#     #     for file in repository.GetIndexFiles(True):
#     #         self.assertTrue(any(file in s for s in indexFiles))
#     #     for file in repository.GetIndexFiles(False):
#     #         self.assertTrue(any(file in s for s in indexFiles))

#     # def test_GetIndexFiles_Timestamped(self):
#     #     """Check the Index files returned are expected when Timestamp has been called."""

#     #     # Need to setup the Settings specifically for this test
#     #     Settings.Init()
#     #     dummyConfig = [
#     #     f"set skelPath = {_fixturesDirectory}/Structured",
#     #     "set contents  = False",
#     #     "set byHash    = False",
#     #     "set language  = 'en_GB'",
#     #     ]
#     #     Settings.Parse(dummyConfig)

#     #     # Setup a Structured repository to test against
#     #     line = "deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
#     #     repository = Repository(line, "amd64")

#     #     indexFiles = repository.ParseReleaseFiles() # type: list[str]

#     #     # Ensure we actually got some files
#     #     self.assertTrue(len(indexFiles) > 0)

#     #     # Timestamp the files
#     #     repository.Timestamp()

#     #     # Files have been timestamped. The files already existed on disk, so were timestamped during Parse.
#     #     # The files after "download" (not performed here, already on disk), are equal - therefore Modified
#     #     # files is False
#     #     self.assertTrue(len(repository.GetIndexFiles(True)) == 0)
#     #     # Therefore, all unmodified files should be returned.
#     #     self.assertTrue(len(repository.GetIndexFiles(False)) > 0)

#     #     # Ensure files exist within original indexFiles that were requested
#     #     for file in repository.GetIndexFiles(True):
#     #         self.assertTrue(any(file in s for s in indexFiles))
#     #     for file in repository.GetIndexFiles(False):
#     #         self.assertTrue(any(file in s for s in indexFiles))

# class TestRepository_Properties(unittest.TestCase):
#     """Test case for each of the Repository class Properties."""

#     def test_RepositoryType_Binary(self):
#         """Test that a Binary Repository is correctly identified."""

#         line = "deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
#         repository = Repository(line, "amd64")

#         self.assertEqual(repository.RepositoryType, RepositoryType.Bin)

#     def test_RepositoryType_Source(self):
#         """Test that a Source Repository is correctly identified."""

#         line = "deb-src [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main restricted universe multiverse"
#         repository = Repository(line, "amd64")

#         self.assertEqual(repository.RepositoryType, RepositoryType.Src)

#     def test_Uri(self):
#         """Test that a Uri is correctly identified."""

#         uris = [
#             "http://gb.archive.ubuntu.com/ubuntu",
#             "http://ftp.debian.org/debian",
#             "http://security.debian.org",
#             "http://archive.raspberrypi.org/debian",
#             "http://raspbian.raspberrypi.org/raspbian",
#             "https://repos.influxdata.com/debian",
#             "https://repos.influxdata.com/ubuntu",
#             "http://ppa.launchpad.net/ansible/ansible/ubuntu",
#             "http://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64"
#         ]

#         for uri in uris:
#             line = f"deb [arch=amd64] {uri} dist component1"
#             repository = Repository(line, "amd64")

#             self.assertEqual(repository.Uri, uri)

#     def test_Distribution(self):
#         """Test that a Distribution is correctly identified."""
        
#         distributions = [
#             "focal",
#             "focal-security",
#             "focal-updates",
#             "focal-proposed",
#             "focal-backports",
#             "buster",
#             "buster-updates",
#             "buster/updates",
#             ""
#         ]

#         for dist in distributions:
#             line = f"deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu {dist}"
#             if dist:
#                 line += " component1"

#             repository = Repository(line, "amd64")
#             self.assertEqual(repository.Distribution, dist)

#     def test_Components(self):
#         """Test that Components are correctly identified."""
        
#         componentList = [
#             ["main", "restricted", "universe", "multiverse"],
#             ["main", "contrib", "non-free"],
#             ["main"],
#             ["stable"],
#             []
#         ]

#         for components in componentList:
#             line = f"deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu dist {' '.join(components)}"

#             repository = Repository(line, "amd64")
#             self.assertListEqual(repository.Components, components)

#     def test_Architectures(self):
#         """Test that Architectures are correctly identified."""
        
#         architectures = [
#             "Alpa",
#             "Arm",
#             "Armel",
#             "armhf",
#             "arm64",
#             "hppa",
#             "i386",
#             "amd64",
#             "ia64",
#             "m68k",
#             "mips",
#             "mipsel",
#             "mipsel",
#             "mips64el",
#             "PowerPC",
#             "PPC64",
#             "ppc64el",
#             "riscv64",
#             "s390",
#             "s390x",
#             "SH4",
#             "sparc64",
#             "x32",
#             "amd64,i386,armhf",
#             "amd64 , i386 , armhf",
#         ]

#         for arch in architectures:
#             line = f"deb [arch={arch}] http://gb.archive.ubuntu.com/ubuntu dist"

#             repository = Repository(line, "default")

#             if "," in arch:
#                 self.assertListEqual(arch.split(","), repository.Architectures)
#             else:
#                 self.assertIn(arch, repository.Architectures)

#     def test_Clean(self):
#         """Test that Clean Property is correctly read."""

#         line = f"deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu dist"

#         repository = Repository(line, "default")

#         # Clean is defuault behaviour
#         self.assertTrue(repository.Clean)

#         repository.Clean = False
#         self.assertFalse(repository.Clean)

#     # def test_Modified(self):
#     #     """Test that Modified is correctly identified."""

#     #     # Need to setup the Settings specifically for this test
#     #     Settings.Init()
#     #     dummyConfig = [
#     #     f"set skelPath = {_fixturesDirectory}/Structured",
#     #     "set contents  = False",
#     #     "set byHash    = False",
#     #     "set language  = 'en_GB'",
#     #     ]
#     #     Settings.Parse(dummyConfig)

#     #     line = f"deb [arch=amd64] http://gb.archive.ubuntu.com/ubuntu focal main"

#     #     repository = Repository(line, "default")

#     #     # No files added to Collection, so Repository is unmodified
#     #     self.assertFalse(repository.Modified)

#     #     # Parse files to set Current Timestamps of existing files
#     #     repository.ParseReleaseFiles()
#     #     self.assertTrue(repository.Modified) # Current Timestamp != 0 (default Download timestamp)

#     #     repository.Timestamp()
#     #     self.assertFalse(repository.Modified) # Current Timestamp == Modified Timestamp

if __name__ == '__main__':
    unittest.main()
