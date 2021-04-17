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

@click.command()
def main():
    global sources

    configData = []
    indexUrls = []

    try:
        # Read the configuration file
        with open (CONFIG_FILE) as f:
            configData = list(filter(None, f.read().splitlines()))
        
        logging.debug(f"Read {len(configData)} lines from config")
    except FileNotFoundError:
        click.echo("Config file not found!", color='red')
        sys.exit()

    # Create working directories
    Path(settings.MirrorPath).mkdir(parents=True, exist_ok=True)
    Path(settings.SkelPath).mkdir(parents=True, exist_ok=True)
    Path(settings.VarPath).mkdir(parents=True, exist_ok=True)

    # Change to the Skel directory for working repository structure
    os.chdir(settings.SkelPath)

    # Parse the configuration file
    settings.Parse(configData)
    sources = GetSources(configData)

    logging.debug(f"Processing {len(sources)} sources...")

    # 1. Get the Index files for each of the sources
    indexFiles = []
    for source in sources:
        indexFiles += source.GetIndexes(settings)
    
    logging.debug(f"Compiled a list of {len(indexFiles)} Index files for download")
    Downloader.Download(indexFiles, UrlType.Index, settings)

    sys.exit()

    # 2. Get the Translation files for each of the Sources
    translationFiles = []
    for source in sources:
        translationFiles += source.GetTranslationIndexes(settings)

    logging.debug(f"Compiled a list of {len(translationFiles)} Translation files for download")
    Downloader.Download(translationFiles, UrlType.Translation, settings)

    # 3. Get the Dep11 files for each of the Sources
    dep11Files = []
    for source in sources:
        dep11Files += source.GetDep11Files(settings)

    logging.debug(f"Compiled a list of {len(dep11Files)} Dep11 files for download")
    Downloader.Download(dep11Files, UrlType.Dep11, settings)

    # 4. Unzip each of the Packages / Sources indexes and obtain a list of all files to download
    DecompressReleaseFiles()

    filesToDownload = list([tuple()])
    filesToDownload.clear()
    for source in sources:
        releaseFiles = source.GetReleaseFiles()

        key = source.Uri
        logging.debug(f"Processing Index: {SanitiseUri(key)} {source.Distribution}...")
        for file in releaseFiles:
            value = file[len(SanitiseUri(key)):]
            filesToDownload += ProcessIndex(key, value)

    # 5. Perform the main download of Binary and Source files
    downloadSize = CalculateDownloadSize([x[1] for x in filesToDownload])
    logging.debug(f"Compiled a list of {len(filesToDownload)} Binary and Source files of size {downloadSize} for download")

    os.chdir(settings.MirrorPath)
    #Downloader.Download([x[0] for x in filesToDownload], UrlType.Archive, settings)

    # Copy Skel to Main Archive
    # for indexUrl in indexUrls:
    #     if os.path.isfile(f"{settings.SkelPath}/{SanitiseUri(indexUrl)}"):
    #         path = Path(f"{settings.MirrorPath}/{SanitiseUri(indexUrl)}")
    #         os.makedirs(path.parent.absolute(), exist_ok=True)
    #         copyfile(f"{settings.SkelPath}/{SanitiseUri(indexUrl)}", f"{settings.MirrorPath}/{SanitiseUri(indexUrl)}")

def CalculateDownloadSize(files) -> str:
    size = 0
    for file in files:
        size += file

    return ConvertSize(size)

def DecompressReleaseFiles():
    releaseFiles = []
    for source in sources:
        releaseFiles += source.GetReleaseFiles()

    threadCount = settings.Threads

    if len(releaseFiles) < threadCount:
        threadCount = len(releaseFiles)

    logging.info(f"Decompressing {len(releaseFiles)} Release / Source files using {threadCount} threads...\n")

    i = 0
    processes = []
    files = []

    t = time.perf_counter()

    # threadJobs = [[] for i in range(threadCount)]

    # while releaseFiles:
    #     for x in range(threadCount):
    #         if not releaseFiles:
    #             break
    #         else:
    #             threadJobs[x].append(releaseFiles[0])
    #             del releaseFiles[0] 

    # for job in threadJobs:

    #     p = multiprocessing.Process(target=UnzipFile, args=(job,))
    #     p.daemon = True
    #     p.start()

    #     processes.append(p)

    #     i += 1

    # WaitForThreads(processes)

    # with multiprocessing.Pool(processes=threadCount) as p:
    #     p.map(UnzipFile, releaseFiles)

    pool = multiprocessing.Pool(threadCount)
    for _ in tqdm.tqdm(pool.imap_unordered(UnzipFile, releaseFiles), total=len(releaseFiles)):
        pass

    print(f"{time.perf_counter() - t:0.4f} seconds")

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

        for package in packages:
            if "Filename" in package:
                # Packages Index
                filename = package["Filename"]
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
    if os.path.isfile(path):
        return os.path.getsize(path) != size or settings.ForceUpdate
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

    return sources

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()