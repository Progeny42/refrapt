"""Python Debian mirroring tool."""

import sys
import logging
from logging.handlers import RotatingFileHandler
import os
import time
from pathlib import Path
import multiprocessing
import math
import shutil
import datetime
import gzip
import lzma
import bz2
import site
import pkg_resources

import click
import tqdm
from filelock import FileLock

from refrapt.classes import (
    Source,
    UrlType,
    Downloader,
    Index,
    LogFilter
)

from refrapt.helpers import SanitiseUri
from refrapt.settings import Settings

logger = logging.getLogger(__name__)

sources = [] # type: list[Source]
filesToKeep = list() # type : dict[str]

@click.command()
@click.version_option(pkg_resources.require("refrapt")[0].version)
@click.option("--conf", default=f"{Settings.GetRootPath()}/refrapt.conf", help="Path to configuration file.", type=click.STRING)
@click.option("--test", is_flag=True, default=False, help="Do not perform the main download for any .deb or source files.", type=click.BOOL)
def main(conf: str, test: bool):
    """A tool to mirror Debian repositories for use as a local mirror."""

    global sources
    global filesToKeep

    startTime = time.perf_counter()

    ConfigureLogger()

    logger.info("Starting Refrapt process")

    configData = GetConfig(conf)

    # Parse the configuration file
    Settings.Parse(configData)
    logging.getLogger().setLevel(Settings.LogLevel())

    appLockFile = "refrapt-lock"

    # Ensure that command line argument for Test overrides if it is set in the configuration file
    if test:
        Settings.EnableTest()

    if Settings.Test():
        logger.info("## Running in Test mode. Main download will not occur! ##\n")

    sources = GetSources(configData)

    if not sources:
        logger.info("No sources found in configuration file. Application exiting.")
        sys.exit()

    # Create working directories
    Path(Settings.MirrorPath()).mkdir(parents=True, exist_ok=True)
    Path(Settings.SkelPath()).mkdir(parents=True, exist_ok=True)
    Path(Settings.VarPath()).mkdir(parents=True, exist_ok=True)

    Downloader.Init()

    # Change to the Skel directory for working repository structure
    os.chdir(Settings.SkelPath())

    # Check for any "-lock" files.
    for file in os.listdir(Settings.VarPath()):
        if "Download-lock" in file:
            # A download was in progress and interrupted. This means a
            # partial download will be sitting on the drive. Remove
            # it to guarantee that it will be fully downloaded.
            uri = None
            with open(f"{Settings.VarPath()}/{file}") as f:
                uri = f.readline()

            uri = SanitiseUri(uri)
            if os.path.isfile(f"{Settings.MirrorPath()}/{uri}"):
                os.remove(f"{Settings.MirrorPath()}/{uri}")
            elif os.path.isfile(f"{Settings.VarPath()}/{uri}"):
                os.remove(f"{Settings.VarPath()}/{uri}")
            logger.info(f"Removed incomplete download {uri}")
        if appLockFile in file:
            # Refrapt was interrupted during processing.
            # To ensure that files which now may not
            # be marked as Modified due to recently being
            # downloaded, force processing of all files
            logger.info("The previous Refrapt run was interrupted. Full processing will be performed to ensure completeness")
            Settings.SetForce()

    # Delete existing /var files
    logger.info("Removing previous /var files...")
    for item in os.listdir(Settings.VarPath()):
        os.remove(f"{Settings.VarPath()}/{item}")

    filesToDownload = list([tuple()]) # type: list[tuple[str, int]]
    filesToDownload.clear()

    # Create a lock file for the Application
    with FileLock(f"{Settings.VarPath()}/{appLockFile}.lock"):
        with open(f"{Settings.VarPath()}/{appLockFile}", "w+") as f:
            pass
        logger.info(f"Processing {len(sources)} sources...")

        # 1. Get the Release files for each of the sources
        releaseFiles = []
        for source in sources:
            releaseFiles += source.GetReleaseFiles()

        logger.debug("Adding Release Files to filesToKeep:")
        for releaseFile in releaseFiles:
            logger.debug(f"\t{SanitiseUri(releaseFile)}")
            filesToKeep.append(os.path.normpath(SanitiseUri(releaseFile)))

        print()
        logger.info(f"Compiled a list of {len(releaseFiles)} Release files for download")
        Downloader.Download(releaseFiles, UrlType.Release)

        # 2. Parse the Release files for the list of Index files to download
        indexFiles = []
        for source in sources:
            indexFiles += source.ParseReleaseFiles()

        logger.debug("Adding Index Files to filesToKeep:")
        for indexFile in indexFiles:
            logger.debug(f"\t{SanitiseUri(indexFile)}")
            filesToKeep.append(os.path.normpath(SanitiseUri(indexFile)))

        print()
        logger.info(f"Compiled a list of {len(indexFiles)} Index files for download")
        Downloader.Download(indexFiles, UrlType.Index)

        for source in sources:
            source.Timestamp()

        # 3. Unzip each of the Packages / Sources indices and obtain a list of all files to download
        DecompressReleaseFiles()

        print()
        logger.info("Building file list...")
        for source in tqdm.tqdm([x for x in sources if x.Modified], position=0, unit=" source", desc="Sources "):
            releaseFiles = source.GetIndexFiles(True) # Only get modified files

            key = source.Uri
            for file in tqdm.tqdm(releaseFiles, position=1, unit=" index", desc="Indices ", leave=False):
                value = file[len(SanitiseUri(key)):]
                filesToDownload += ProcessIndex(key, value)

        # Packages potentially add duplicate downloads, slowing down the rest
        # of the process. To counteract, remove duplicates now
        filesToDownload = list(set(filesToDownload))
        filesToKeep = list(set(filesToKeep))

        logger.debug(f"Files to keep: {len(filesToKeep)}")
        for file in filesToKeep:
            logger.debug(f"\t{file}")

        # 4. Perform the main download of Binary and Source files
        downloadSize = CalculateDownloadSize([x[1] for x in filesToDownload])
        print()
        logger.info(f"Compiled a list of {len(filesToDownload)} Binary and Source files of size {downloadSize} for download")

        os.chdir(Settings.MirrorPath())
        if not Settings.Test():
            Downloader.Download([x[0] for x in filesToDownload], UrlType.Archive)

        # 5. Copy Skel to Main Archive
        if not Settings.Test():
            print()
            logger.info("Copying Skel to Mirror")
            for indexUrl in tqdm.tqdm(filesToKeep, unit=" files"):
                skelFile   = f"{Settings.SkelPath()}/{SanitiseUri(indexUrl)}"
                if os.path.isfile(skelFile):
                    mirrorFile = f"{Settings.MirrorPath()}/{SanitiseUri(indexUrl)}"
                    copy = True
                    if os.path.isfile(mirrorFile):
                        # Compare files using Timestamp to save moving files that don't need to be
                        skelTimestamp   = os.path.getmtime(Path(skelFile))
                        mirrorTimestamp = os.path.getmtime(Path(mirrorFile))
                        copy = skelTimestamp > mirrorTimestamp

                    if copy:
                        os.makedirs(Path(mirrorFile).parent.absolute(), exist_ok=True)
                        shutil.copyfile(skelFile, mirrorFile)

        # 6. Remove any unused files
        print()
        Clean()

    # Lock file no longer required
    os.remove(f"{Settings.VarPath()}/{appLockFile}")
    if os.path.isfile(f"{Settings.VarPath()}/{appLockFile}.lock"):
        # Requires manual deletion on Unix
        os.remove(f"{Settings.VarPath()}/{appLockFile}.lock")

    print()
    logger.info(f"Refrapt completed in {datetime.timedelta(seconds=round(time.perf_counter() - startTime))}")

def ConfigureLogger():
    """Configure the logger for the Application."""
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%Y-%m-%d %H:%M:%S")

    # Console minimum level is INFO regardless of settings, to
    # prevent overloading the screen
    consoleHandler = logging.StreamHandler(sys.stdout)
    consoleHandler.setFormatter(formatter)
    consoleHandler.addFilter(LogFilter(logging.INFO))

    path = Path(Settings.GetRootPath())
    os.makedirs(path, exist_ok=True)
    fileHandler = RotatingFileHandler(f"{Settings.GetRootPath()}/refrapt.log", maxBytes=524288000, backupCount=3)
    fileHandler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(Settings.LogLevel())
    root.addHandler(consoleHandler)
    root.addHandler(fileHandler)

def GetConfig(conf: str) -> list:
    """Attempt to read the configuration file using the path provided.

       If the configuration file is not found, a default configuration
       will be written using the path provided, and the application
       will exit.
    """
    if not os.path.isfile(conf):
        logger.info("Configuration file not found. Creating default...")
        CreateConfig(conf)
        sys.exit()
    else:
        # Read the configuration file
        with open(conf) as f:
            configData = list(filter(None, f.read().splitlines()))

        logger.debug(f"Read {len(configData)} lines from config")
        return configData

def CreateConfig(conf: str):
    """Create a new configuration file using the default provided.

       If the destination directory for the file does not exist,
       the application will exit.
    """

    path = Path(conf)
    if not os.path.isdir(path.parent.absolute()):
        logger.error("Path for configuration file not valid. Application exiting.")
        sys.exit()

    defaultConfigPath = f"{site.USER_BASE}/refrapt/refrapt.conf.example"
    with open(defaultConfigPath, "r") as fIn:
        with open(conf, "w") as f:
            f.writelines(fIn.readlines())

    logger.info(f"Configuration file created for first use at '{conf}'. Add some sources and run again. Application exiting.")

def Clean():
    """Clean any files or directories that are not used.

       Determination of whether a file or directory is used
       is based on whether each of the files and directories
       within the path of a given Source were added to the
       filesToKeep[] variable. If they were not, that means
       based on the current configuration file, the items
       are not required.
    """

    # All sources marked as Clean and having been Modified
    cleanSources = [x for x in sources if x.Clean and x.Modified]

    if not cleanSources:
        logger.info("Nothing to clean")
        return

    logger.info("Beginning Clean process...")
    logger.debug("Clean Sources (Modified)")
    for src in cleanSources:
        logger.debug(f"{src.Uri} [{src.Distribution}] {src.Components}")
    # Remaining sources with the same URI
    allUriSources = []
    for cleanSource in cleanSources:
        allUriSources += [x for x in sources if x.Uri in cleanSource.Uri]
    # Remove duplicates
    allUriSources = list(set(allUriSources))

    logger.debug("All sources with same URI")
    for src in allUriSources:
        logger.debug(f"{src.Uri} [{src.Distribution}] {src.Components}")

    # In order to not end up removing files that are listed in Indices
    # that were not processed in previous steps, we do need to read the
    # remainder of the Packages and Sources files in for the source in order
    # to build a full list of maintained files.
    for source in tqdm.tqdm(allUriSources, position=0, unit=" source", desc="Sources "):
        releaseFiles = source.GetIndexFiles(False) # Gets unmodified release files

        key = source.Uri
        for file in tqdm.tqdm(releaseFiles, position=1, unit=" index", desc="Indices ", leave=False):
            value = file[len(SanitiseUri(key)):]
            ProcessUnmodifiedIndex(key, value)

    # Packages potentially add duplicate downloads, slowing down the rest
    # of the process. To counteract, remove duplicates now
    requiredFiles = [] # type: list[str]
    requiredFiles = list(set(filesToKeep))

    print()
    items = [] # type: list[str]
    logger.info("Compiling list of files to clean...")
    uris = {source.Uri for source in cleanSources}
    for uri in tqdm.tqdm(uris, position=0, unit=" mirror", desc="Mirrors"):
        walked = [] # type: list[str]
        for root, _, files in tqdm.tqdm(os.walk(SanitiseUri(uri)), position=1, unit=" fso", desc="FSO    ", leave=False, delay=0.5):
            for file in tqdm.tqdm(files, position=2, unit=" file", desc="Files  ", leave=False, delay=0.5):
                walked.append(os.path.join(root, file))

        logger.debug(f"{SanitiseUri(uri)}: Walked {len(walked)} items")
        items += [x for x in walked if os.path.normpath(x) not in requiredFiles and not os.path.islink(x)]

    logger.debug(f"Found {len(items)} which can be freed")
    for item in items:
        logger.debug(item)

    # Calculate size of items to clean
    if items:
        logger.info("Calculating space savings...")
        clearSize = 0
        for file in tqdm.tqdm(items, unit=" files"):
            clearSize += os.path.getsize(file)
    else:
        logger.info("No files eligible to clean")
        return

    if Settings.Test():
        print()
        logger.info(f"Found {ConvertSize(clearSize)} in {len(items)} files and directories that could be freed.")
        return

    print()
    logger.info(f"{ConvertSize(clearSize)} in {len(items)} files and directories will be freed...")

    for item in items:
        os.remove(item)

def CalculateDownloadSize(files: list) -> str:
    """Calculates the total size of a given listing of files."""
    size = 0
    for file in files:
        size += file

    return ConvertSize(size)

def DecompressReleaseFiles():
    """Decompresses the Release and Source files."""
    releaseFiles = []
    for source in sources:
        releaseFiles += source.GetIndexFiles(True) # Modified files only

    print()

    if not releaseFiles:
        logger.info("No files to decompress")
        return

    logger.info(f"Decompressing {len(releaseFiles)} Release / Source files...")

    with multiprocessing.Pool(Settings.Threads()) as pool:
        for _ in tqdm.tqdm(pool.imap_unordered(UnzipFile, releaseFiles), total=len(releaseFiles), unit=" file"):
            pass

def UnzipFile(file: str):
    """Determines the file format and unzips the given file."""

    if os.path.isfile(f"{file}.gz"):
        with gzip.open(f"{file}.gz", "rb") as f:
            with open(file, "wb") as out:
                shutil.copyfileobj(f, out)
    elif os.path.isfile(f"{file}.xz"):
        with lzma.open(f"{file}.xz", "rb") as f:
            with open(file, "wb") as out:
                shutil.copyfileobj(f, out)
    elif os.path.isfile(f"{file}.bz2"):
        with bz2.open(f"{file}.bz2", "rb") as f:
            with open(file, "wb") as out:
                shutil.copyfileobj(f, out)
    else:
        logger.warning(f"File '{file}' has an unsupported compression format")

def ProcessIndex(uri: str, index: str) -> list[tuple[str, int]]:
    """Processes each package listed in the Index file.

       For each Package that is found in the Index file,
       it is checked to see whether the file exists in the
       local mirror, and if not, adds it to the collection
       for download.
    """
    packageDownloads = [] # type: list[tuple[str, int]]

    path = SanitiseUri(uri)

    indexFile = Index(f"{Settings.SkelPath()}/{path}/{index}")
    indexFile.Read()
    logging.debug(f"Processing Index file: {Settings.SkelPath()}/{path}/{index}")

    packages = indexFile.GetPackages()

    mirror = Settings.MirrorPath() + "/" + path

    with open(Settings.VarPath() + "/ALL", "a+") as allFile, \
         open(Settings.VarPath() + "/NEW", "a+") as newFile, \
         open(Settings.VarPath() + "/MD5", "a+") as md5File, \
         open(Settings.VarPath() + "/SHA1", "a+") as sha1File, \
         open(Settings.VarPath() + "/SHA256", "a+") as sha256File:

        for package in tqdm.tqdm(packages, position=2, unit=" pkgs", desc="Packages", leave=False, delay=0.5):
            if "Filename" in package:
                # Packages Index
                filename = package["Filename"]

                if filename.startswith("./"):
                    filename = filename[2:]

                filesToKeep.append(os.path.normpath(f"{path}/{filename}"))
                allFile.write(f"{path}/{filename}\n")
                if "MD5sum" in package:
                    checksum = package["MD5sum"]
                    md5File.write(f"{checksum} {path}/{filename}\n")
                if "SHA1" in package:
                    checksum = package["SHA1"]
                    sha1File.write(f"{checksum} {path}/{filename}\n")
                if "SHA256" in package:
                    checksum = package["SHA256"]
                    sha256File.write(f"{checksum} {path}/{filename}\n")

                if NeedUpdate(f"{mirror}/{filename}", int(package["Size"])):
                    newFile.write(f"{uri}/{filename}\n")
                    packageDownloads.append((f"{uri}/{filename}", int(package["Size"])))
            else:
                # Sources Index
                for key, value in package.items():
                    if "Files" in key:
                        files = list(filter(None, value.splitlines())) # type: list[str]
                        for file in files:
                            directory = package["Directory"]
                            sourceFile = file.split(" ")

                            md5 = sourceFile[0]
                            size = int(sourceFile[1])
                            filename = sourceFile[2]

                            if filename.startswith("./"):
                                filename = filename[2:]

                            filesToKeep.append(os.path.normpath(f"{path}/{directory}/{filename}"))

                            allFile.write(f"{path}/{directory}/{filename}\n")
                            md5File.write(f"{md5} {path}/{directory}/{filename}\n")

                            if NeedUpdate(f"{mirror}/{directory}/{filename}", size):
                                newFile.write(f"{uri}/{directory}/{filename}\n")
                                packageDownloads.append((f"{uri}/{directory}/{filename}", size))

    logger.debug("Packages to download:")
    for pkg, _ in packageDownloads:
        logger.debug(f"\t{pkg}")

    return packageDownloads

def ProcessUnmodifiedIndex(uri: str, index: str):
    """Processes each package listed in the Index file.

       For each Package that is found in the Index file,
       it is checked to see whether the file exists in the
       local mirror, and if not, adds it to the collection
       for download.
    """
    path = SanitiseUri(uri)

    indexFile = Index(f"{Settings.SkelPath()}/{path}/{index}")
    indexFile.Read()
    logging.debug(f"Processing Index file: {Settings.SkelPath()}/{path}/{index}")

    packages = indexFile.GetPackages()

    for package in tqdm.tqdm(packages, position=2, unit=" pkgs", desc="Packages", leave=False, delay=0.5):
        if "Filename" in package:
            # Packages Index
            filename = package["Filename"]
            filesToKeep.append(os.path.normpath(f"{path}/{filename}"))
        else:
            # Sources Index
            for key, value in package.items():
                if "Files" in key:
                    files = list(filter(None, value.splitlines())) # type: list[str]
                    for file in files:
                        directory = package["Directory"]
                        sourceFile = file.split(" ")

                        fileName = sourceFile[2]

                        filesToKeep.append(os.path.normpath(f"{path}/{directory}/{fileName}"))

def NeedUpdate(path: str, size: int) -> bool:
    """Determine whether a file needs updating.

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
    # Allow the user to force an update via Settings

    if Settings.ForceUpdate():
        return True

    if os.path.isfile(path):
        return os.path.getsize(path) != size

    return True

def ConvertSize(size: int) -> str:
    """Convert a number of bytes into a number with a suitable unit."""
    if size == 0:
        return "0B"

    sizeName = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size, 1024)))
    p = math.pow(1024, i)
    s = round(size / p, 2)
    return "%s %s" % (s, sizeName[i])

def GetSources(configData: list) -> list:
    """Determine the Sources listed in the Configuration file."""
    for line in [x for x in configData if x.startswith("deb")]:
        sources.append(Source(line, Settings.Architecture()))

    for line in [x for x in configData if x.startswith("clean")]:
        if "False" in line:
            uri = line.split(" ")[1]
            source = [x for x in sources if x.Uri == uri]
            source[0].Clean = False
            logger.debug(f"Not cleaning {uri}")

    return sources
