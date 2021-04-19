"""Python Debian mirroring tool."""

import sys
import logging
from logging.handlers import RotatingFileHandler
import click
import os
import time
from pathlib import Path
import multiprocessing
import math
import shutil
import tqdm
import datetime
import pkg_resources
import gzip
import lzma
import bz2

from refrapt.classes import (
    Source,
    UrlType,
    Downloader,
    Index,
)

from refrapt.helpers import SanitiseUri
from refrapt.settings import Settings

logger = logging.getLogger(__name__)

sources = [] # type: list[Source]
cleanList = dict()
rmDirs = [] # type: list[str]
rmFiles = [] # type: list[str]
clearSize = 0

@click.command()
@click.version_option(pkg_resources.require("refrapt")[0].version)
@click.option("--conf", default="/etc/apt/refrapt.conf", help="Path to configuration file.", type=click.STRING)
@click.option("--test", is_flag=True, default=False, help="Do not perform the main download for any .deb or source files.", type=click.BOOL)
def refrapt(conf: str, test: bool):
    """A tool to mirror Debian repositories for use as a local mirror."""

    global sources
    global cleanList
    global rmDirs
    global rmFiles
    global clearSize

    startTime = time.perf_counter()

    clearSize = 0

    ConfigureLogger()

    logger.info("Starting Refrapt process")

    configData = GetConfig(conf)

    # Parse the configuration file
    Settings.Parse(configData)
    logging.getLogger().setLevel(Settings.LogLevel())

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

    # Change to the Skel directory for working repository structure
    os.chdir(Settings.SkelPath())

    # Check for any "-lock" files.
    for file in os.listdir(Settings.VarPath()):
        if "Download-lock" in file:
            # A download was in progress and interrupted. This means a
            # partial download will be sitting on the drive. Remove
            # it to guarantee that it will be fully downloaded.
            with open(f"{Settings.VarPath()}/{file}") as f:
                uri = f.readline()
                uri = SanitiseUri(uri)
                if os.path.isfile(f"{Settings.MirrorPath()}/{uri}"):
                    os.remove(f"{Settings.MirrorPath()}/{uri}")
                elif os.path.isfile(f"{Settings.VarPath()}/{uri}"):
                    os.remove(f"{Settings.VarPath()}/{uri}")
                logger.info(f"Removed incomplete download {uri}")

    # Delete existing log files
    logger.info("Removing previous log files...")
    for item in os.listdir(Settings.VarPath()):
        os.remove(f"{Settings.VarPath()}/{item}")

    logger.info(f"Processing {len(sources)} sources...")

    # 1. Get the Index files for each of the sources
    indexFiles = []
    for source in sources:
        indexFiles += source.GetIndexes()

    for index in indexFiles:
        cleanList[SanitiseUri(index)] = True

    print()
    logger.info(f"Compiled a list of {len(indexFiles)} Index files for download")
    Downloader.Download(indexFiles, UrlType.Index)

    # 2. Get the Translation files for each of the Sources
    translationFiles = []
    for source in sources:
        translationFiles += source.GetTranslationIndexes()

    for translationFile in translationFiles:
        cleanList[SanitiseUri(translationFile)] = True

    print()
    logger.info(f"Compiled a list of {len(translationFiles)} Translation files for download")
    Downloader.Download(translationFiles, UrlType.Translation)

    # 3. Get the Dep11 files for each of the Sources
    dep11Files = []
    for source in sources:
        dep11Files += source.GetDep11Files()

    for dep11File in dep11Files:
        cleanList[SanitiseUri(dep11File)] = True

    print()
    logger.info(f"Compiled a list of {len(dep11Files)} Dep11 files for download")
    Downloader.Download(dep11Files, UrlType.Dep11)

    # 4. Unzip each of the Packages / Sources indexes and obtain a list of all files to download
    DecompressReleaseFiles()

    print()
    logger.info("Building file list...")
    filesToDownload = list([tuple()]) # type: list[tuple[list,int]]
    filesToDownload.clear()
    for source in tqdm.tqdm(sources, position=0, unit=" source", desc="Sources "):
        releaseFiles = source.GetReleaseFiles()

        key = source.Uri
        for file in tqdm.tqdm(releaseFiles, position=1, unit=" index", desc="Indexes ", leave=False):
            value = file[len(SanitiseUri(key)):]
            filesToDownload += ProcessIndex(key, value)

    for download, _ in filesToDownload:
        cleanList[SanitiseUri(download[0])] = True

    # 5. Perform the main download of Binary and Source files
    downloadSize = CalculateDownloadSize([x[1] for x in filesToDownload])
    print()
    logger.info(f"Compiled a list of {len(filesToDownload)} Binary and Source files of size {downloadSize} for download")

    os.chdir(Settings.MirrorPath())
    if not Settings.Test():
        Downloader.Download([x[0] for x in filesToDownload], UrlType.Archive)

    # 6. Copy Skel to Main Archive
    if not Settings.Test():
        print()
        logger.info("Copying Skel to Mirror")
        for indexUrl in tqdm.tqdm(cleanList, unit=" files"):
            if os.path.isfile(f"{Settings.SkelPath()}/{SanitiseUri(indexUrl)}"):
                path = Path(f"{Settings.MirrorPath()}/{SanitiseUri(indexUrl)}")
                os.makedirs(path.parent.absolute(), exist_ok=True)
                shutil.copyfile(f"{Settings.SkelPath()}/{SanitiseUri(indexUrl)}", f"{Settings.MirrorPath()}/{SanitiseUri(indexUrl)}")

    # 7. Remove any unused files
    Clean()

    print()
    logger.info(f"Refrapt completed in {datetime.timedelta(seconds=round(time.perf_counter() - startTime))}")

def ConfigureLogger():
    """Configure the logger for the Application."""
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%Y-%m-%d %H:%M:%S")

    consoleHandler = logging.StreamHandler(sys.stdout)
    consoleHandler.setFormatter(formatter)

    fileHandler = RotatingFileHandler("refrapt.log", maxBytes=524288000, backupCount=3)
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

    source = pkg_resources.resource_string(__name__, "refrapt.conf").decode().split("\n")
    with open(conf, "w") as f:
        f.writelines(source)

    logger.info("Configuration file created for first use. Add some sources and run again. Application exiting.")


def Clean():
    """Clean any files or directories that are not used.

       Determination of whether a file or directory is used
       is based on whether each of the files and directories
       within the path of a given Source were added to the
       cleanList[] variable. If they were not, that means
       based on the current configuration file, the items
       are not required.
    """

    for source in [x for x in sources if x.Clean]:
        directory = SanitiseUri(source.Uri)
        if os.path.isdir(directory) and not os.path.islink(directory):
            ProcessDirectory(directory)

    if clearSize == 0:
        return

    if Settings.Test():
        logger.info(f"Found {ConvertSize(clearSize)} in {len(rmFiles)} files and {len(rmDirs)} directories that could be freed.")
        return

    logger.info(f"{ConvertSize(clearSize)} in {len(rmFiles)} files and {len(rmDirs)} directories will be freed...")

    for file in tqdm.tqdm(rmFiles, unit=" files", desc="Files"):
        os.remove(file)

    for dir in tqdm.tqdm(rmDirs, unit=" dirs", desc="Dirs "):
        os.rmdir(dir)

def ProcessDirectory(directory: str) -> bool:
    """Recursively check whether a directory and all of its contents and eligible for removal."""
    required = False

    if directory in cleanList:
        return cleanList[directory]

    for item in os.listdir(directory):
        child = directory + "/" + item

        if os.path.isdir(child) and not os.path.islink(child):
            required |= ProcessDirectory(child)
        elif os.path.isfile(child):
            required |= ProcessFile(child)
        elif os.path.islink(child):
            required = True # Symlinks are always needed

    if not required:
        rmDirs.append(directory)

    return required

def ProcessFile(file: str) -> bool:
    """Check whether a file is eligible for removal."""
    global clearSize

    if file in cleanList:
        return cleanList[file]

    rmFiles.append(file)
    clearSize += os.path.getsize(file)

    return False


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
        releaseFiles += source.GetReleaseFiles()

    print()
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
        logger.warn(f"File '{file}' has an unsupported compression format")

def ProcessIndex(uri: str, index: str) -> list[tuple[str, int]]:
    """Processes each package listed in the Index file.

       For each Package that is found in the Index file,
       it is checked to see whether the file exists in the
       local mirror, and if not, adds it to the collection
       for download.
    """
    packageDownloads = []

    path = SanitiseUri(uri)

    indexFile = Index(f"{Settings.SkelPath()}/{path}/{index}")
    indexFile.Read()

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
                cleanList[f"{path}/{filename}"] = True
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
                            fileName = sourceFile[2]

                            cleanList[f"{path}/{directory}/{fileName}"] = True

                            allFile.write(f"{path}/{directory}/{fileName}\n")
                            md5File.write(f"{md5} {path}/{directory}/{fileName}\n")

                            if NeedUpdate(f"{mirror}/{directory}/{fileName}", size):
                                newFile.write(f"{uri}/{directory}/{fileName}\n")
                                packageDownloads.append((f"{uri}/{directory}/{fileName}", size))

    return packageDownloads

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
    else:
        return True

def ConvertSize(bytes: int) -> str:
    """Convert a number of bytes into a number with a suitable unit."""
    if bytes == 0:
        return "0B"

    sizeName = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(bytes, 1024)))
    p = math.pow(1024, i)
    s = round(bytes / p, 2)
    return "%s %s" % (s, sizeName[i])

def GetSources(configData: list) -> list:
    """Determine the Sources listed in the Configuration file."""
    sources = []
    for line in [x for x in configData if x.startswith("deb")]:
        sources.append(Source(line, Settings.Architecture()))

    for line in [x for x in configData if x.startswith("clean")]:
        if "False" in line:
            uri = line.split(" ")[1]
            source = [x for x in sources if x.Uri == uri]
            source[0].Clean = False
            logger.debug(f"Not cleaning {uri}")

    return sources
