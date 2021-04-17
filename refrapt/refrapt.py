import sys
import logging
import click
import os
import time
from pathlib import Path
import multiprocessing 
import re
import math
import codecs
from shutil import copyfile
from itertools import product
import tqdm
import datetime

from classes import (
    Settings,
    Source,
    SourceType,
    UrlType,
    Downloader,
    Index,
)

from helpers import (
    SanitiseUri,
    WaitForThreads
)

CONFIG_FILE = "refrapt.cfg"

settings = Settings()

sources = []
cleanList = dict()
rmDirs = []
rmFiles = []
clearSize = 0

@click.command()
def main():
    global sources
    global cleanList
    global rmDirs
    global rmFiles
    global clearSize

    clearSize = 0

    configData = []
    indexUrls = []

    startTime = time.perf_counter()

    try:
        # Read the configuration file
        with open (CONFIG_FILE) as f:
            configData = list(filter(None, f.read().splitlines()))
        
        logging.debug(f"Read {len(configData)} lines from config")
    except FileNotFoundError:
        logging.critical("Config file not found!")
        sys.exit()

    # Parse the configuration file
    settings.Parse(configData)
    logging.basicConfig(level=settings.LogLevel, force=True)

    sources = GetSources(configData)

    # Create working directories
    Path(settings.MirrorPath).mkdir(parents=True, exist_ok=True)
    Path(settings.SkelPath).mkdir(parents=True, exist_ok=True)
    Path(settings.VarPath).mkdir(parents=True, exist_ok=True)

    # Change to the Skel directory for working repository structure
    os.chdir(settings.SkelPath)

    # Delete existing log files
    logging.info(f"Removing previous log files...")
    for item in os.listdir(settings.VarPath):
        os.remove(f"{settings.VarPath}/{item}")

    sys.exit()

    logging.info(f"Processing {len(sources)} sources...")

    # 1. Get the Index files for each of the sources
    indexFiles = []
    for source in sources:
        indexFiles += source.GetIndexes(settings)
    
    for index in indexFiles:
        cleanList[SanitiseUri(index)] = True
    
    print()
    logging.info(f"Compiled a list of {len(indexFiles)} Index files for download")
    Downloader.Download(indexFiles, UrlType.Index, settings)

    # 2. Get the Translation files for each of the Sources
    translationFiles = []
    for source in sources:
        translationFiles += source.GetTranslationIndexes(settings)

    for translationFile in translationFiles:
        cleanList[SanitiseUri(translationFile)] = True

    print()
    logging.info(f"Compiled a list of {len(translationFiles)} Translation files for download")
    Downloader.Download(translationFiles, UrlType.Translation, settings)

    # 3. Get the Dep11 files for each of the Sources
    dep11Files = []
    for source in sources:
        dep11Files += source.GetDep11Files(settings)

    for dep11File in dep11Files:
        cleanList[SanitiseUri(dep11File)] = True

    print()
    logging.info(f"Compiled a list of {len(dep11Files)} Dep11 files for download")
    Downloader.Download(dep11Files, UrlType.Dep11, settings)

    # 4. Unzip each of the Packages / Sources indexes and obtain a list of all files to download
    DecompressReleaseFiles()

    print()
    logging.info(f"Building file list...")
    filesToDownload = list([tuple()])
    filesToDownload.clear()
    for source in tqdm.tqdm(sources, position=0, unit=" source", desc="Sources "):
        releaseFiles = source.GetReleaseFiles()

        key = source.Uri
        for file in tqdm.tqdm(releaseFiles, position=1, unit=" index", desc="Indexes ", leave=False):
            value = file[len(SanitiseUri(key)):]
            filesToDownload += ProcessIndex(key, value)

    for download in filesToDownload:
        cleanList[SanitiseUri(download[0])] = True

    # 5. Perform the main download of Binary and Source files
    downloadSize = CalculateDownloadSize([x[1] for x in filesToDownload])
    print()
    logging.info(f"Compiled a list of {len(filesToDownload)} Binary and Source files of size {downloadSize} for download")

    os.chdir(settings.MirrorPath)
    Downloader.Download([x[0] for x in filesToDownload], UrlType.Archive, settings)

    # 6. Copy Skel to Main Archive
    print()
    logging.info(f"Copying Skel to Mirror")
    for indexUrl in tqdm.tqdm(cleanList, unit=" files"):
        if os.path.isfile(f"{settings.SkelPath}/{SanitiseUri(indexUrl)}"):
            path = Path(f"{settings.MirrorPath}/{SanitiseUri(indexUrl)}")
            os.makedirs(path.parent.absolute(), exist_ok=True)
            copyfile(f"{settings.SkelPath}/{SanitiseUri(indexUrl)}", f"{settings.MirrorPath}/{SanitiseUri(indexUrl)}")

    # 7. Remove any unused files
    Clean()

    print()
    logging.info(f"Refrapt completed in {datetime.timedelta(seconds=round(time.perf_counter() - startTime))}")

def Clean():
    for source in [x for x in sources if x.Clean]:
        directory = SanitiseUri(source.Uri)
        if os.path.isdir(directory) and not os.path.islink(directory):
            ProcessDirectory(directory)

    if clearSize == 0:
        return

    logging.info(f"{ConvertSize(clearSize)} in {len(rmFiles)} files and {len(rmDirs)} directories will be freed...")

    for file in tqdm.tqdm(rmFiles, unit=" files", desc="Files"):
        os.remove(file)

    for dir in tqdm.tqdm(rmDirs, unit=" dirs", desc="Dirs "):
        os.rmdir(dir)

def ProcessDirectory(directory) -> bool:
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

def ProcessFile(file) -> bool:
    global clearSize

    if file in cleanList:
        return cleanList[file]

    rmFiles.append(file)
    clearSize += os.path.getsize(file)

    return False


def CalculateDownloadSize(files) -> str:
    size = 0
    for file in files:
        size += file

    return ConvertSize(size)

def DecompressReleaseFiles():
    releaseFiles = []
    for source in sources:
        releaseFiles += source.GetReleaseFiles()

    print()
    logging.info(f"Decompressing {len(releaseFiles)} Release / Source files...")

    with multiprocessing.Pool(settings.Threads) as pool:
        for _ in tqdm.tqdm(pool.imap_unordered(UnzipFile, releaseFiles), total=len(releaseFiles), unit=" file"):
            pass

def UnzipFile(file):

    # for file in files:
        if os.path.isfile(f"{file}.gz"):
            os.system(f"gunzip < {file}.gz > {file}")
        elif os.path.isfile(f"{file}.xz"):
            os.system(f"xz -d {file}.xz > {file}")
        elif os.path.isfile(f"{file}.bz2"):
            os.system(f"bzip2 -d {file}.bz2 > {file}")

def ProcessIndex(uri, index) -> tuple[list, int]:
    packageDownloads = []

    path = SanitiseUri(uri)

    index = Index(f"{settings.SkelPath}/{path}/{index}")
    index.Read()

    packages = index.GetPackages()

    mirror = settings.MirrorPath + "/" + path

    with open (settings.VarPath + "/ALL", "a+") as allFile, \
         open (settings.VarPath + "/NEW", "a+") as newFile, \
         open (settings.VarPath + "/MD5", "a+") as md5File, \
         open (settings.VarPath + "/SHA1", "a+") as sha1File, \
         open (settings.VarPath + "/SHA256", "a+") as sha256File:

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
                        files = list(filter(None, value.splitlines())) 
                        for file in files:
                            directory = package["Directory"]
                            sourceFile = file.split(" ")

                            md5 = sourceFile[0]
                            size = int(sourceFile[1])
                            fileName = sourceFile[2]

                            cleanList[f"{path}/{directory}/{filename}"] = True

                            allFile.write(f"{path}/{directory}/{fileName}\n")
                            md5File.write(f"{md5} {path}/{directory}/{fileName}\n")

                            if NeedUpdate(f"{mirror}/{directory}/{fileName}", size):
                                newFile.write(f"{uri}/{directory}/{fileName}\n")
                                packageDownloads.append((f"{uri}/{directory}/{fileName}", size))

    return packageDownloads

def NeedUpdate(path, size: int) -> bool:
    # Realistically, this is a bad check, as the size
    # could remain the same, but source may have changed.
    # Allow the user to force an update via Settings

    if settings.ForceUpdate:
        return True

    if os.path.isfile(path):
        return os.path.getsize(path) != size
    else:
        return True

def ConvertSize(bytes) -> str:
    if bytes == 0:
        return "0B"

    sizeName = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(bytes, 1024)))
    p = math.pow(1024, i)
    s = round(bytes / p, 2)
    return "%s %s" % (s, sizeName[i])

def GetSources(configData) -> list:
    sourceList = [x for x in configData if x.startswith("deb")]

    sources = []
    for line in sourceList:
        sources.append(Source(line, settings.Architecture))

    for line in [x for x in configData if x.startswith("clean")]:
        if "False" in line:
            uri = line.split(" ")[1]
            source = [x for x in sources if x.Uri == uri]
            source[0].Clean = False
            logging.debug(f"Not cleaning {uri}")

    return sources

if __name__ == "__main__":
    logging.basicConfig(level=settings.LogLevel)
    main()