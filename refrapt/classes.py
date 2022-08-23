"""Classes for abstraction and use with Refrapt."""

from enum import Enum
import logging
import os
import multiprocessing
import re
from functools import partial
from dataclasses import dataclass
import collections
from pathlib import Path
from abc import ABC, abstractmethod

import multiprocessing

from refrapt.helpers import SanitiseUri, UnzipFile
from refrapt.settings import Settings
import tqdm
import filelock

import sys
import urllib.parse

logger = logging.getLogger(__name__)

class RepositoryType(Enum):
    """Distinguish between Binary and Source mirrors."""
    Bin = 0
    Src = 1

class UrlType(Enum):
    """Type of downloadable files."""
    Index       = 0
    Archive     = 1
    Release     = 2

class Package:
    def __init__(self, filename: str, size: int, latest: bool):
        self._Filename = filename
        self._Size = size
        self._Latest = latest

    @property
    def Filename(self) -> str:
        return self._Filename

    @property
    def Size(self) -> int:
        return self._Size

    @property
    def Latest(self) -> bool:
        return self._Latest

class Repository:
    """Represents a Repository as defined the Configuration file."""
    def __init__(self, line, defaultArch):
        """Initialises a Repository with a line from the Configuration file and the default Architecture."""
        self._repositoryType = RepositoryType.Bin
        self._architectures = [] # type: list[str]
        self._uri = None
        self._distribution = None
        self._components = [] # type: list[str]
        self._clean = True

        # Remove any inline comments
        if "#" in line:
            line = line[0:line.index("#")]

        # Break down the line into its parts
        elements = line.split(" ")
        elements = list(filter(None, elements))

        # Determine Repository type
        if elements[0] == "deb":
            self._repositoryType = RepositoryType.Bin
        elif 'deb-src' in elements[0]:
            self._repositoryType = RepositoryType.Src

        elementIndex = 1

        # If Architecture(s) is specified, store it, else set the default
        if "[" in line and "]" in line:
            # Architecture is defined
            archList = line.split("[")[1].split("]")[0].replace("arch=", "")
            self._architectures = archList.split(",")
            elementIndex += 1
        else:
            self._architectures.append(defaultArch)

        self._uri           = elements[elementIndex]

        # Handle flat repositories
        if len(elements) > elementIndex + 1 and not elements[elementIndex + 1] == "/":
            self._distribution = elements[elementIndex + 1]
            self._components   = elements[elementIndex + 2:]
        else:
            self._distribution = ""
            self._components = []

        self._packageCollection = PackageCollection(self._components, self._architectures)
        self._sourceCollection  = SourceCollection(self._components)

        logger.debug("Repository")
        logger.debug(f"\tKind:         {self._repositoryType}")
        logger.debug(f"\tArch:         {self._architectures}")
        logger.debug(f"\tUri:          {self._uri}")
        logger.debug(f"\tDistribution: {self._distribution}")
        logger.debug(f"\tComponents:   {self._components}")
        logger.debug(f"\tPackage Coll: {self._packageCollection}")
        logger.debug(f"\tSource Coll:  {self._sourceCollection}")
        logger.debug(f"\tFlat:         {not self._components}")

    def GetReleaseFiles(self) -> list:
        """
            Get the Release files for the Repository.

            Section 1.1 of the DebianRepository Format document states:
            - "To download packages from a repository, apt would download a InRelease or Release file from the 
            $ARCHIVE_ROOT/dists/$DISTRIBUTION directory."
            - "InRelease files are signed in-line while Release files should have an accompanying Release.gpg file."
            - https://wiki.debian.org/DebianRepository/Format#Overview

            Section 1.2 defines these files as "Release" files.
            - https://wiki.debian.org/DebianRepository/Format#A.22Release.22_files
            
        """

        baseUrl = self._uri + "/"
        if self._components:
            baseUrl += "dists/" + self._distribution + "/"

        releaseFiles = []

        releaseFiles.append(baseUrl + "InRelease")
        releaseFiles.append(baseUrl + "Release")
        releaseFiles.append(baseUrl + "Release.gpg")

        for file in releaseFiles:
            file = os.path.normpath(file)

        return releaseFiles

    def _ParseReleaseFiles(self, rootPath: str) -> list:
        """
            Get a list of all Index files from the Release file.

            Section 1.2 of the DebianRepository Format document states:
            - "Servers shall provide the InRelease file, and might provide a Release files and its signed counterparts"
            - https://wiki.debian.org/DebianRepository/Format#A.22Release.22_files

            Therefore default to parsing the InRelease file.

            For the purposes of identifying which package indexes are required for download,
            the MD5Sum, SHA1 and SHA256 fields are parsed.

            Section 1.2.10 states:
            - "Those fields shall be multi-line fields containing multiple lines of whitespace separated data. 
               Each line shall contain;
                - The checksum of the file in the format corresponding to the field
                - The size of the file (integer >= 0)
                - The filename relative to the directory of the Release file

              Each datum must be separated by one or more whitespace characters."
            - https://wiki.debian.org/DebianRepository/Format#MD5Sum.2C_SHA1.2C_SHA256
        """

        baseUrl = self._uri + "/"
        if self._components:
            baseUrl += "dists/" + self._distribution + "/"

        inReleaseFilePath = rootPath + "/" + SanitiseUri(baseUrl) + "/InRelease"
        releaseFilePath   = rootPath + "/" + SanitiseUri(baseUrl) + "/Release"

        # Default to InRelease
        releaseFileToRead = inReleaseFilePath

        if not os.path.isfile(inReleaseFilePath):
            # Fall back to Release
            releaseFileToRead = releaseFilePath

        checksums = False

        indexFiles = []

        with open(releaseFileToRead) as f:
            for line in f:
                if ("SHA256:" in line or "SHA1:" in line or "MD5Sum:" in line) and "Hash:" not in line:
                    checksumType = line
                    checksumType = checksumType.replace(":", "").strip()
                    checksums = False

                if checksums:
                    if re.search("^ +(.*)$", line):
                        parts = list(filter(None, line.split(" ")))

                        # parts[0] = checksum
                        # parts[1] = size
                        # parts[2] = filename

                        if not len(parts) == 3:
                            logger.warning(f"Malformed checksum line '{line}' in {releaseFileToRead}")
                            continue

                        checksum = parts[0].strip()
                        filename = parts[2].rstrip()

                        if self._repositoryType == RepositoryType.Bin:
                            for architecture in self._architectures:
                                if Settings.Contents():
                                    if re.match(rf"Contents-{architecture}", filename):
                                        indexFiles.append(f"{baseUrl}{filename}")

                                if self._components:
                                    for component in self._components:
                                        if Settings.Contents():
                                            if re.search(rf"{component}/Contents-{architecture}", filename):
                                                indexFiles.append(f"{baseUrl}{filename}")

                                        binaryByHash = rf"{baseUrl}{component}/binary-{architecture}/by-hash/{checksumType}/{checksum}"

                                        if re.match(rf"{component}/binary-{architecture}/Release", filename):
                                            indexFiles.append(f"{baseUrl}{filename}")
                                            if Settings.ByHash():
                                                indexFiles.append(binaryByHash)

                                        if re.match(rf"{component}/binary-{architecture}/Packages", filename):
                                            indexFiles.append(f"{baseUrl}{filename}")

                                            if re.match(rf"{component}/binary-{architecture}/Packages[^./]*(\.gz|\.bz2|\.xz|$)$", filename):
                                                self._packageCollection.Add(component, architecture, f"{baseUrl}{filename}")
                                            if Settings.ByHash():
                                                indexFiles.append(binaryByHash)

                                        if re.match(rf"{component}/cnf/Commands-{architecture}", filename):
                                            indexFiles.append(f"{baseUrl}{filename}")
                                            if Settings.ByHash():
                                                indexFiles.append(rf"{baseUrl}{component}/cnf/by-hash/{checksumType}/{checksum}")

                                        i18nByHash = rf"{baseUrl}{component}/i18n/by-hash/{checksumType}/{checksum}"

                                        if re.match(rf"{component}/i18n/cnf/Commands-{architecture}", filename):
                                            indexFiles.append(f"{baseUrl}{filename}")
                                            if Settings.ByHash():
                                                indexFiles.append(i18nByHash)

                                        if re.match(rf"{component}/i18n/Index", filename):
                                            indexFiles.append(f"{baseUrl}{filename}")
                                            if Settings.ByHash():
                                                indexFiles.append(i18nByHash)

                                        for language in Settings.Language():
                                            if re.match(rf"{component}/i18n/Translation-{language}", filename):
                                                indexFiles.append(f"{baseUrl}{filename}")
                                                if Settings.ByHash():
                                                    indexFiles.append(i18nByHash)

                                        if re.match(rf"{component}/dep11/(Components-{architecture}\.yml|icons-[^./]+\.tar)", filename):
                                            indexFiles.append(f"{baseUrl}{filename}")
                                            if Settings.ByHash():
                                                indexFiles.append(f"{baseUrl}{component}/dep11/by-hash/{checksumType}/{checksum}")
                                else:
                                    indexFiles.append(f"{baseUrl}{filename}")
                                    self._packageCollection.Add("Flat", architecture, f"{baseUrl}{filename}")

                        elif self._repositoryType == RepositoryType.Src:
                            for component in self._components:
                                if re.match(rf"{component}/source/Release", filename):
                                    indexFiles.append(f"{baseUrl}{filename}")

                                if re.match(rf"{component}/source/Sources[^./]*(\.gz|\.bz2|\.xz|$)$", filename):
                                    indexFiles.append(f"{baseUrl}{filename}")
                                    self._sourceCollection.Add(component, f"{baseUrl}{filename}")
                    else:
                        checksums = False
                else:
                    checksums = "SHA256:" in line or "SHA1:" in line or "MD5Sum:" in line

        if self._repositoryType == RepositoryType.Bin:
            self._packageCollection.DetermineCurrentTimestamps()
        elif self._repositoryType == RepositoryType.Src:
            self._sourceCollection.DetermineCurrentTimestamps()

        for file in indexFiles:
            file = os.path.normpath(file)

        return list(set(indexFiles)) # Remove duplicates caused by reading multiple listings for each checksum type

    def ParseReleaseFilesFromLocalMirror(self) -> list:
        """
            Get a list of all Index files from the Release file 
            using the files that exist in the /mirror directory.
        """

        return self._ParseReleaseFiles(Settings.MirrorPath())

    def ParseReleaseFilesFromRemote(self) -> list:
        """
            Get a list of all Index files from the Release file 
            using the files that exist in the /skel directory.
        """

        return self._ParseReleaseFiles(Settings.SkelPath())

    def Timestamp(self):
        """Record the timestamps for all 'Packages' or 'Sources' Indices."""
        
        if self._repositoryType == RepositoryType.Bin:
            self._packageCollection.DetermineDownloadTimestamps()
        elif self._repositoryType == RepositoryType.Src:
            self._sourceCollection.DetermineDownloadTimestamps()

    def DecompressIndexFiles(self):
        """
            Decompress the Binary Package Indices (Binary Repository) or 
            Source Indices (Source Repository).
        """

        indexFiles = self._GetIndexFiles(True) # Modified files only

        if not indexFiles:
            return

        indexType = None
        if self._repositoryType == RepositoryType.Bin:
            indexType = "Packages     "
        elif self.RepositoryType == RepositoryType.Src:
            indexType = "Sources      "

        with multiprocessing.Pool(Settings.Threads()) as pool:
            for _ in tqdm.tqdm(pool.imap_unordered(UnzipFile, indexFiles), position=1, total=len(indexFiles), unit=" index", desc=indexType, leave=False):
                pass

    def ParseIndexFiles(self) -> list[Package]:
        """
            Read the Binary Package Indices (Binary Repository) or 
            Source Indices (Source Repository) for all Filenames.

            Section 1.4 of the DebianRepository Format document states:
            - "[The files] consist of multiple paragraphs ... and the additional 
              fields defined in this section, precisely:
                - Filename (mandatory)"
            - https://wiki.debian.org/DebianRepository/Format#A.22Packages.22_Indices

            Only the filename is of interest in order to download it.
        """       

        indices = self._GetIndexFiles(True) # Modified files only

        fileList = [] # type: list[Package]

        for file in tqdm.tqdm(indices, position=1, unit=" index", desc="Indices      ", leave=False):
            fileList += self._ProcessIndex(Settings.SkelPath(), file, False)

        return fileList

    def ParseIndexFilesFromLocalMirror(self) -> list[Package]:
        """Get all items listed in the Index files that exist within the /mirror directory."""

        # The Force setting needs to be enabled so that a Repository will return all Index Files, 
        # and not just modified ones. The dependency isn't great, but this feature is an add-on
        # and not part of the initial design
        Settings.SetForceUpdate()

        indices = self._GetIndexFiles(True) # All files due to Force being Enabled

        fileList = [] # type: list[str]

        for file in tqdm.tqdm(indices, position=1, unit=" index", desc="Indices      ", leave=False):
            fileList += self._ProcessIndex(Settings.MirrorPath(), file, True)
        
        return fileList

    def ParseUnmodifiedIndexFiles(self) -> list[str]:
        """
            Read the Binary Package Indices (Binary Repository) or 
            Source Indices (Source Repository) for all Filenames.

            Section 1.4 of the DebianRepository Format document states:
            - "[The files] consist of multiple paragraphs ... and the additional 
              fields defined in this section, precisely:
                - Filename (mandatory)"
            - https://wiki.debian.org/DebianRepository/Format#A.22Packages.22_Indices

            Only the filename is of interest in order to download it.
        """       

        indices = self._GetIndexFiles(False) # Unmodified files only

        fileList = [] # type: list[Package]

        for file in tqdm.tqdm(indices, position=1, unit=" index", desc="Indices      ", leave=False):
            fileList += self._ProcessIndex(Settings.SkelPath(), file, True)

        return [x for x in fileList if x.Latest]

    def Exists(self) -> bool:
        """
            Check whether the a directory for this Repository was created on disk
            after Download. If it does not, this Repository could not be found online.
        """

        repositoryDirectory = Settings.SkelPath() + "/" + SanitiseUri(self._uri)

        logger.debug(f"Checking repo exists: {repositoryDirectory}")

        path = Path(repositoryDirectory)
        return os.path.isdir(path.parent.absolute())

    def _ProcessIndex(self, indexRoot: str, index: str, skipUpdateCheck: bool) -> list[Package]:
        """
            Processes each package listed in the Index file.

            For each Package that is found in the Index file,
            it is checked to see whether the file exists in the
            local mirror, and if not, adds it to the collection
            for download.

            If the file does exist, checks based on the filesize
            to determine if the file has been updated.
        """

        packageList = [] # type: list[Package]

        path = SanitiseUri(self.Uri)

        indexFile = Index(f"{indexRoot}/{index}")
        indexFile.Read()
        logging.debug(f"Processing Index file: {indexRoot}/{index}")

        packages = indexFile.GetPackages() # type: list[dict[str,str]]

        mirror = Settings.MirrorPath() + "/" + path
        
        for package in tqdm.tqdm(packages, position=2, unit=" pkgs", desc="Packages     ", leave=False, delay=0.5):
            if "Filename" in package:
                # Packages Index
                filename = package["Filename"]

                if filename.startswith("./"):
                    filename = filename[2:]
                
                packageList.append(Package(os.path.normpath(f"{path}/{filename}"), int(package["Size"]), skipUpdateCheck or not self._NeedUpdate(os.path.normpath(f"{mirror}/{filename}"), int(package["Size"]))))
            else:
                # Sources Index
                for key, value in package.items():
                    if "Files" in key:
                        files = list(filter(None, value.splitlines())) # type: list[str]
                        for file in files:
                            directory = package["Directory"]
                            sourceFile = file.split(" ")

                            size = int(sourceFile[1])
                            filename = sourceFile[2]

                            if filename.startswith("./"):
                                filename = filename[2:]

                            packageList.append(Package(os.path.normpath(f"{path}/{directory}/{filename}"), size, skipUpdateCheck or not self._NeedUpdate(os.path.normpath(f"{mirror}/{directory}/{filename}"), size)))

        if [x for x in packageList if not x.Latest]:
            logger.debug(f"Packages to update ({len([x for x in packageList if not x.Latest])}):")
            for pkg in [x.Filename for x in packageList if not x.Latest]:
                logger.debug(f"\t{pkg}")

        return packageList

    def _NeedUpdate(self, path: str, size: int) -> bool:
        """
            Determine whether a file needs updating.

            If the file exists on disk, its size is compared
            to that listed in the Package. The result of the
            comparison determines whether the file should be
            downloaded.

            If the file does not exist, it must be downloaded.

            Function can be forced to always return True
            in the event that the correct setting is applied
            in the Configuration file.
        """

        # Realistically, this is a bad check, as the size
        # could remain the same, but source may have changed.
        # Allow the user to force an update via Settings.

        # Ideally, a comparison of the checksum listed in the Package
        # and the actual file would be good, but potentially slow

        if Settings.ForceUpdate():
            return True

        if os.path.isfile(path):
            return os.path.getsize(path) != size

        return True

    def _GetIndexFiles(self, modified: bool) -> list:
        """
            Get all Binary Package Indices (Binary Repository) or 
            Source Indices (Source Repository) for the Repository.
        """

        indexCollection = None # type: IndexCollection

        if self._repositoryType == RepositoryType.Bin:
            indexCollection = self._packageCollection
        elif self.RepositoryType == RepositoryType.Src:
            indexCollection = self._sourceCollection

        if modified:
            return indexCollection.ModifiedFiles
        else:
            return indexCollection.UnmodifiedFiles

    @property
    def RepositoryType(self) -> RepositoryType:
        """Gets the type of Repository this object represents."""
        return self._repositoryType

    @property
    def Uri(self) -> str:
        """Gets the Uri of the Repository."""
        return self._uri

    @property
    def Distribution(self) -> str:
        """Gets the Distribution of the Repository."""
        return self._distribution

    @property
    def Components(self) -> list:
        """Gets the Components of the Repository."""
        return self._components

    @property
    def Architectures(self) -> list:
        """Gets the Architectures of the Repository."""
        return self._architectures

    @property
    def Clean(self) -> bool:
        """Gets whether the resulting directory should be cleaned."""
        return self._clean

    @Clean.setter
    def Clean(self, value: bool):
        """Sets whether the resulting directory should be cleaned."""
        self._clean = value

    @property
    def Modified(self) -> bool:
        """Get whether any of the files in this Repository have been modified."""

        if self._repositoryType == RepositoryType.Bin:
            return len(self._packageCollection.ModifiedFiles) > 0
        elif self._repositoryType == RepositoryType.Src:
            return len(self._sourceCollection.ModifiedFiles) > 0

class Timestamp:
    """Simple Timestamp class for measuring before and after of a file."""
    
    def __init__(self):
        """Initialise timestamps to 0.0."""
        self._currentTimestamp = 0.0
        self._downloadedTimestamp = 0.0

    @property
    def Current(self) -> float:
        """Get the Timestamp of the file before download. Will be 0.0 if the file does not exist."""
        return self._currentTimestamp

    @Current.setter
    def Current(self, timestamp: float):
        """Set the Timestamp of the file before download."""
        self._currentTimestamp = timestamp

    @property
    def Download(self) -> float:
        """Get the Timestamp of the file after download."""
        return self._downloadedTimestamp

    @Download.setter
    def Download(self, timestamp: float):
        """Set the Timestamp of the file after download."""
        self._downloadedTimestamp = timestamp

    @property
    def Modified(self) -> bool:
        """Get whether the file has been modified."""
        return self._currentTimestamp != self._downloadedTimestamp

class IndexCollection(ABC):
    """A collection of Indices for a Repository."""

    @abstractmethod
    def _GetFiles(self, modified: bool) -> list:
        """Get a list of all files based on whether they have been modified or not."""
        pass

    @abstractmethod
    def DetermineCurrentTimestamps(self):
        """Record the current Timestamp of a file."""
        pass

    @abstractmethod
    def DetermineDownloadTimestamps(self):
        """Record the current Timestamp of a file after download."""
        pass

    @property
    def ModifiedFiles(self) -> list:
        """Get a list of all modified files in this collection or all if Force is enabled."""
        return self._GetFiles(True)

    @property
    def UnmodifiedFiles(self) -> list:
        """Get a list of all unmodified files in this collection or all if Force is enabled."""
        return self._GetFiles(False)

class PackageCollection(IndexCollection):
    """
        A collection of all possible 'Packages' Indices for a Repository.

        Section 1.4 of the DebianRepository Format document indicates that:
        - 'Packages' Indices are distinguished by both Component and Architecture.
        - https://wiki.debian.org/DebianRepository/Format#A.22Packages.22_Indices
    """

    def __init__(self, components: list, architectures: list):
        """Initialises a PackageCollection with a dictionary of each Component and Architecture."""
        self._packageCollection = collections.defaultdict(lambda : collections.defaultdict(dict)) # type: dict[str, dict[str, dict[str, Timestamp]]] # For each component, each architecture, for each file, timestamp

        # Initialise the collection
        for component in components:
            for architecture in architectures:
                self._packageCollection[component][architecture] = dict()

    def Add(self, component: str, architecture: str, file: str):
        """Add a file to the collection for a given Component and Architecture."""
        self._packageCollection[component][architecture][SanitiseUri(file)] = Timestamp()

    def DetermineCurrentTimestamps(self):
        """For each file stored in this collection, determine the current timestamp of the file, and record it."""

        logger.debug("Getting timestamps of current files in Skel (if available)")
        # Gather timestamps for all files (that exist)
        for component in self._packageCollection:
            for architecture in self._packageCollection[component]:
                for file in self._packageCollection[component][architecture]:
                    if os.path.isfile(f"{Settings.SkelPath()}/{file}"):
                        self._packageCollection[component][architecture][file].Current = os.path.getmtime(Path(f"{Settings.SkelPath()}/{SanitiseUri(file)}"))
                        logger.debug(f"\tCurrent: [{component}] [{architecture}] [{file}]: {self._packageCollection[component][architecture][file].Current}")

    def DetermineDownloadTimestamps(self):
        """For each file stored in this collection, determine the current timestamp of the file, and record it.

           If a file does not exist on disk after the download, then it will be removed from this collection.
        """

        logger.debug("Getting timestamps of downloaded files in Skel")
        removables = collections.defaultdict(dict) # type: dict[str, dict[str, list[str]]]
        for component in self._packageCollection:
            for architecture in self._packageCollection[component]:
                removables[component][architecture] = list()

        for component in self._packageCollection:
            for architecture in self._packageCollection[component]:
                for file in self._packageCollection[component][architecture]:
                    if os.path.isfile(f"{Settings.SkelPath()}/{file}"):
                        self._packageCollection[component][architecture][file].Download = os.path.getmtime(Path(f"{Settings.SkelPath()}/{SanitiseUri(file)}"))
                        logger.debug(f"\tDownload: [{component}] [{architecture}] [{file}]: {self._packageCollection[component][architecture][file].Download}")
                    else:
                        # File does not exist after download, therefore it does not exist in the repository, and can be marked for removal
                        removables[component][architecture].append(file)
                        logger.debug(f"\tMarked for removal (does not exist): [{component}] [{architecture}] [{file}]")

        # Remove marked files
        for component in removables:
            for architecture in removables[component]:
                for file in removables[component][architecture]:
                    del self._packageCollection[component][architecture][file]

    def _GetFiles(self, modified: bool) -> list:
        """Get a list of all files based on whether they have been modified or not."""

        files = [] # type: list[str]

        for component in self._packageCollection:
            for architecture in self._packageCollection[component]:
                for file in self._packageCollection[component][architecture]:

                    addFile = False

                    if modified:
                        addFile = self._packageCollection[component][architecture][file].Modified or Settings.PreviousRunInterrupted() or Settings.ForceUpdate()
                    else:
                        addFile = not self._packageCollection[component][architecture][file].Modified or Settings.PreviousRunInterrupted() or Settings.ForceUpdate()

                    if addFile:
                        filename, _ = os.path.splitext(file)
                        files.append(filename)

        return list(set(files)) # Ensure uniqueness due to stripped extension

class SourceCollection(IndexCollection):
    """
        A collection of all possible 'Packages' Indices for a Repository.

        Section 1.5 of the DebianRepository Format document indicates that:
        - 'Sources' Indices are distinguished by both Component only.
        - https://wiki.debian.org/DebianRepository/Format#A.22Sources.22_Indices
    """

    def __init__(self, components: list):
        """Initialises a SourceCollection with a dictionary of each Component."""
        self._sourceCollection = collections.defaultdict(dict) # type: dict[str, dict[str, Timestamp]] # For each component, for each file, timestamp

        # Initialise the collection
        for component in components:
            self._sourceCollection[component] = dict()

    def Add(self, component: str, file: str):
        """Add a file to the collection for a given Component."""
        self._sourceCollection[component][SanitiseUri(file)] = Timestamp()

    def DetermineCurrentTimestamps(self):
        """For each file stored in this collection, determine the current timestamp of the file, and record it."""

        logger.debug("Getting timestamps of current files in Skel (if available)")
        # Gather timestamps for all files (that exist)
        for component in self._sourceCollection:
            for file in self._sourceCollection[component]:
                if os.path.isfile(f"{Settings.SkelPath()}/{file}"):
                    self._sourceCollection[component][file].Current = os.path.getmtime(Path(f"{Settings.SkelPath()}/{SanitiseUri(file)}"))
                    logger.debug(f"\tCurrent: [{component}] [{file}]: {self._sourceCollection[component][file].Current}")

    def DetermineDownloadTimestamps(self):
        """For each file stored in this collection, determine the current timestamp of the file, and record it.

           If a file does not exist on disk after the download, then it will be removed from this collection.
        """

        logger.debug("Getting timestamps of downloaded files in Skel")
        removables = collections.defaultdict(dict) # type: dict[str, list[str]]
        for component in self._sourceCollection:
            removables[component] = list()

        for component in self._sourceCollection:
            for file in self._sourceCollection[component]:
                if os.path.isfile(f"{Settings.SkelPath()}/{file}"):
                    self._sourceCollection[component][file].Download = os.path.getmtime(Path(f"{Settings.SkelPath()}/{SanitiseUri(file)}"))
                    logger.debug(f"\tDownload: [{component}] [{file}]: {self._sourceCollection[component][file].Download}")
                else:
                    # File does not exist after download, therefore it does not exist in the repository, and can be marked for removal
                    removables[component].append(file)
                    logger.debug(f"\tMarked for removal (does not exist): [{component}] [{file}]")

        # Remove marked files
        for component in removables:
            for file in removables[component]:
                del self._sourceCollection[component][file]

    def _GetFiles(self, modified: bool) -> list:
        """Get a list of all files based on whether they have been modified or not."""

        files = [] # type: list[str]

        for component in self._sourceCollection:
            for file in self._sourceCollection[component]:

                addFile = False

                if modified:
                    addFile = self._sourceCollection[component][file].Modified or Settings.PreviousRunInterrupted() or Settings.ForceUpdate()
                else:
                    addFile = not self._sourceCollection[component][file].Modified or Settings.PreviousRunInterrupted() or Settings.ForceUpdate()

                if addFile:
                    filename, _ = os.path.splitext(file)
                    files.append(filename)

        return list(set(files)) # Ensure uniqueness due to stripped extension

@dataclass
class Downloader:
    """Downloads a list of files."""
    @staticmethod
    def Init():
        """Setup filelock for quieter logging and handling of lock files (unix)."""

        # Quieten filelock's logger
        filelock.logger().setLevel(logging.CRITICAL)

        # filelock does not delete releasd lock files on Unix due
        # to potential race conditions in the event of multiple
        # programs trying to lock the file.
        # Refrapt only uses them to track whether a file was fully
        # downloaded or not in the event of interruption, so we
        # can cleanup the files now.
        for file in os.listdir(Settings.VarPath()):
            if ".lock" in file:
                os.remove(f"{Settings.VarPath()}/{file}")

    @staticmethod
    def Download(urls: list, kind: UrlType):
        """Download a list of files of a specific type"""
        if not urls:
            logger.info("No files to download")
            return

        arguments = Downloader.CustomArguments()

        logger.info(f"Downloading {len(urls)} {kind.name} files...")

        with multiprocessing.Pool(Settings.Threads()) as pool:
            downloadFunc = partial(Downloader.DownloadUrlsProcess, kind=kind.name, args=arguments, logPath=Settings.VarPath(), rateLimit=Settings.LimitRate())
            for _ in tqdm.tqdm(pool.imap_unordered(downloadFunc, urls), total=len(urls), unit=" file"):
                pass

    @staticmethod
    def DownloadUrlsProcess(url: str, kind: str, args: list, logPath: str, rateLimit: str):
        """Worker method for downloading a particular Url, used in multiprocessing."""
        process = multiprocessing.current_process()

        baseCommand   = "wget --no-cache -N --no-verbose"
        rateLimit     = f"--limit-rate={rateLimit}"
        retries       = "--tries=20 --waitretry=60 --retry-on-http-error=503,429"
        recursiveOpts = "--recursive --level=inf"
        logFile       = f"-a {logPath}/{kind}-log.{process._identity[0]}"

        filename = f"{logPath}/Download-lock.{process._identity[0]}"

        # Ensure forward slashes are used for URLs
        normalisedUrl = url.replace(os.sep, '/')
        
        command = f"{baseCommand} {rateLimit} {retries} {recursiveOpts} {logFile} {normalisedUrl}"

        if args:
            command += f" {args}"

        with filelock.FileLock(f"{filename}.lock"):
            with open(filename, "w") as f:
                f.write(normalisedUrl)

            os.system(command)

            os.remove(filename)

    @staticmethod
    def CustomArguments() -> list:
        """Creates custom Wget arguments based on the Settings provided."""
        arguments = []

        if Settings.AuthNoChallege():
            arguments.append("--auth-no-challenge")
        if Settings.NoCheckCertificate():
            arguments.append("--no-check-certificate")
        if Settings.Unlink():
            arguments.append("--unlink")

        if Settings.Certificate():
            arguments.append(f"--certificate={Settings.Certificate()}")
        if Settings.CaCertificate():
            arguments.append(f"--ca-certificate={Settings.CaCertificate()}")
        if Settings.PrivateKey():
            arguments.append(f"--privateKey={Settings.PrivateKey()}")

        if Settings.UseProxy():
            arguments.append("-e use_proxy=yes")

            if Settings.HttpProxy():
                arguments.append("-e http_proxy=" + Settings.HttpProxy())
            if Settings.HttpsProxy():
                arguments.append("-e https_proxy=" + Settings.HttpsProxy())
            if Settings.ProxyUser():
                arguments.append("-e proxy_user=" + Settings.ProxyUser())
            if Settings.ProxyPassword():
                arguments.append("-e proxy_password=" + Settings.ProxyPassword())

        return arguments

class Index:
    """Represents an Index file."""

    def __init__(self, path: str):
        """Initialise an Index file with a path."""

        self._path = path
        self._lines = [] # type: list[str]

    def Read(self):
        """Read and decode the contents of the file."""

        contents = []

        with open(self._path, "rb") as f:
            contents = f.readlines()

        for line in contents:
            self._lines.append(line.decode().rstrip())

    def GetPackages(self) -> list:
        """
            Get a list of all Packages listed in the file.

            Although DebianRepository Format document states that "Packages" Indices 
            and "Sources" Indices are formatted based on different formats, both
            contain some common fields, so can be processed identically here.

            Policy 5.3 (Binary package control files -- DEBIAN/control)
            (https://www.debian.org/doc/debian-policy/ch-controlfields.html#debian-source-control-files-dsc)

            Policy 5.5 (5.4 Debian source control files -- .dsc)
            (https://www.debian.org/doc/debian-policy/ch-controlfields.html#debian-changes-files-changes)
        """

        packages = []    # type: list[dict[str,str]]
        package = dict() # type: dict[str,str]

        keywords = ["Filename", "MD5sum", "SHA1", "SHA256", "Size", "Files", "Directory"]

        key = None

        for line in self._lines:
            if not line:
                packages.append(package)
                package = dict()
            else:
                match = re.search(r"^([\w\-]+:)", line)
                if not match and key:
                    # Value continues on next line, append data
                    package[key] += f"\n{line.strip()}"
                else:
                    key = line.split(":")[0]
                    if key in keywords:
                        value = line.split(":")[1].strip()
                        package[key] = value
                    else:
                        # Ignore, we don't need it
                        key = None

        return packages



class LogFilter(object):
    """Class to provide filtering for logging.

       The Level passed to this class will define the minimum
       log level that is allowed by logger.
    """
    def __init__(self, level):
        """Initialise the filter level."""
        self.__level = level

    def filter(self, logRecord):
        """Return whether the Record is covered by a filter or not."""
        return logRecord.levelno >= self.__level
