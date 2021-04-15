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

from classes import (
    Settings,
    Source,
    SourceType,
    UrlType
)

# Consider these as Constants
CONFIG_FILE = "refrapt.cfg"

settings = Settings()
configData = []
urlDownloads = []
sources = []

@click.command()
def main():
    # Entry point

    try:
        # Read the configuration file
        with open (CONFIG_FILE) as f:
            global configData
            configData = list(filter(None, f.read().splitlines()))
        
        logging.debug(f"Read {len(configData)} lines from config")
    except FileNotFoundError:
        click.echo("Config file not found!", color='red')
        sys.exit()

    settings.Parse(configData)

    # Create working directories
    Path(settings.MirrorPath).mkdir(parents=True, exist_ok=True)
    Path(settings.SkelPath).mkdir(parents=True, exist_ok=True)
    Path(settings.VarPath).mkdir(parents=True, exist_ok=True)

    firstSourceLineIndex = 0
    for line in configData:
        if len(line) > 0 and line.startswith('#') or line.startswith("set"):
            firstSourceLineIndex += 1
            continue
        else:
            break

    sourceList = [x for x in configData[firstSourceLineIndex:] if not x.startswith("#")]


    ProcessSources(sourceList)
    os.chdir(settings.SkelPath)
    # DownloadUrls(UrlType.Index)
    
    # ProcessTranslationIndexes()
    # DownloadUrls(UrlType.Translation)

    # ProcessDep11Files()
    # DownloadUrls(UrlType.Dep11)

    # Main Downloads
    # Path(settings.VarPath + "/ALL").mkdir(parents=True, exist_ok=True)
    # Path(settings.VarPath + "/NEW").mkdir(parents=True, exist_ok=True)
    # Path(settings.VarPath + "/MD5").mkdir(parents=True, exist_ok=True)
    # Path(settings.VarPath + "/SHA1").mkdir(parents=True, exist_ok=True)
    # Path(settings.VarPath + "/SHA256").mkdir(parents=True, exist_ok=True)

    ProcessIndexes()

#@click.command()
def ProcessSources(sourceList):
    global sources
    global urlDownloads

    for line in sourceList:
        sources.append(Source(line, settings.Architecture))

    for source in sources:
        if source.SourceType == SourceType.SRC:

            if len(source.Components) > 0:
                url = source.Uri + "/dists/" + source.Distribution + "/"

                urlDownloads.append(url + "InRelease")
                urlDownloads.append(url + "Release")
                urlDownloads.append(url + "Release.gpg")

                for component in source.Components:
                    urlDownloads.append(url + component + "/source/Release")
                    urlDownloads.append(url + component + "/source/Sources.gz")
                    urlDownloads.append(url + component + "/source/Sources.bz2")
                    urlDownloads.append(url + component + "/source/Sources.xz")
            else:
                urlDownloads.append(source.Uri + "/" + source.Distribution + "/Release")
                urlDownloads.append(source.Uri + "/" + source.Distribution + "/Release.gpg")
                urlDownloads.append(source.Uri + "/" + source.Distribution + "/Sources.gz")
                urlDownloads.append(source.Uri + "/" + source.Distribution + "/Sources.bz2")
                urlDownloads.append(source.Uri + "/" + source.Distribution + "/Sources.xz")
        elif source.SourceType == SourceType.BIN:

            if len(source.Components) > 0:
                url = source.Uri + "/dists/" + source.Distribution + "/"

                urlDownloads.append(url + "InRelease")
                urlDownloads.append(url + "Release")
                urlDownloads.append(url + "Release.gpg")

                if settings.Contents:
                    for architecture in source.Architectures:
                        urlDownloads.append(url + "Contents-" + architecture + ".gz")
                        urlDownloads.append(url + "Contents-" + architecture + ".bz2")
                        urlDownloads.append(url + "Contents-" + architecture + ".xz")

                for component in source.Components:
                    for architecture in source.Architectures:
                        if settings.Contents:
                            urlDownloads.append(url + component + "/Contents-" + architecture + ".gz")
                            urlDownloads.append(url + component + "/Contents-" + architecture + ".bz2")
                            urlDownloads.append(url + component + "/Contents-" + architecture + ".xz")

                        urlDownloads.append(url + component + "/binary-" + architecture + "/Release")
                        urlDownloads.append(url + component + "/binary-" + architecture + "/Packages.gz")
                        urlDownloads.append(url + component + "/binary-" + architecture + "/Packages.bz2")
                        urlDownloads.append(url + component + "/binary-" + architecture + "/Packages.xz")
                        
                    urlDownloads.append(url + component + "/i18n/Index")
            else:
                urlDownloads.append(source.Uri + "/" + source.Distribution + "/Release")
                urlDownloads.append(source.Uri + "/" + source.Distribution + "/Release.gpg")
                urlDownloads.append(source.Uri + "/" + source.Distribution + "/Sources.gz")
                urlDownloads.append(source.Uri + "/" + source.Distribution + "/Sources.bz2")
                urlDownloads.append(source.Uri + "/" + source.Distribution + "/Sources.xz") 

#@click.command()
#@click.argument("kind", type=UrlType)
def DownloadUrls(kind):
    if len(urlDownloads) == 0:
        logging.debug("No files to download")
        return

    threadCount = settings.Threads

    # for url in urlDownloads:
    #     print(url)   

    if len(urlDownloads) < threadCount:
        threadCount = len(urlDownloads)

    arguments = []

    if settings.AuthNoChallege:
        arguments.append("--auth-no-challenge")
    if settings.NoCheckCertificate:
        arguments.append("--no-check-certificate")
    if settings.Unlink:
        arguments.append("--unlink")

    if settings.UseProxy:
        arguments.append("-e use_proxy=yes")

        if settings.UseHttpProxy:
            arguments.append("-e http_proxy=" + settings.HttpProxy)
        if settings.UseHttpsProxy:
            arguments.append("-e https_proxy=" + settings.HttpsProxy)
        if settings.UseProxyUser:
            arguments.append("-e proxy_user=" + settings.ProxyUser)
        if settings.UseProxyPassword:
            arguments.append("-e proxy_password=" + settings.ProxyPassword)

    logging.info(f"Downloading {len(urlDownloads)} {kind.name} files using {threadCount} threads...\n")
    logging.debug(f"args: {arguments}")

    i = 0
    processes = []

    chunkSize = math.ceil(len(urlDownloads) / threadCount)

    while len(urlDownloads) > 0:
        threadUrls = urlDownloads[0:chunkSize]
        del urlDownloads[0:chunkSize]

        with open (settings.VarPath + f"/{kind.name}-urls.{i}", "w") as f:
            for url in threadUrls:
                f.write(url + "\n")

        p = multiprocessing.Process(target=DownloadUrlsProcess, args=(threadUrls, kind.name, i, arguments))
        p.daemon = True
        p.start()

        processes.append(p)

        i += 1

    logging.info(f"Begin time: " + time.strftime("%H:%M:%S", time.localtime()) + " \n[" + str(len(processes)) + "]...")
    for process in processes:
        process.join()
        logging.info(f"[" + str(len(processes) - i) + "]...")
        i -= 1
    logging.info(f"End time:" + time.strftime("%H:%M:%S", time.localtime()) + "\n\n")

def DownloadUrlsProcess(urls, kind, index, args):
    baseCommand   = "wget --no-cache -N"
    rateLimit     = f"--limit-rate={settings.LimitRate}"
    retries       = "-t 5"
    recursiveOpts = "-r -l inf"
    logFile       = f"-o {settings.VarPath}/{kind}-log.{index}"
    inputFile     = f"-i {settings.VarPath}/{kind}-urls.{index}"

    #print(f"{baseCommand} {rateLimit} {retries} {recursiveOpts} {logFile} {inputFile} {args}")
    #os.system(f"{baseCommand} {rateLimit} {retries} {recursiveOpts} {logFile} {inputFile} {args}")

def ProcessTranslationIndexes():
    logging.debug("Processing translation indexes: [")

    for source in sources:
        if source.SourceType != SourceType.BIN:
            continue
        #logging.debug("T")
        if len(source.Components) > 0:
            url = source.Uri + "/dists/" + source.Distribution + "/"

            for component in source.Components:
                ProcessTranslationIndex(url, component)

    logging.debug("]\n\n")


def ProcessTranslationIndex(url, component):
    # Extract all translation files from the dists/$DIST/$COMPONENT/i18n/Index
    # file. Fall back to parsing dists/$DIST/Release if i18n/Index is not found.

    #distUri = RemoveDoubleSlashes(url)
    baseUri = url + component + "/i18n/"
    indexUri = baseUri + "Index"
    indexPath = settings.SkelPath + "/" + SanitiseUri(indexUri)

    logging.debug(indexPath)

    checksums = False

    if os.path.isfile(indexPath):
        with open (indexPath) as f:
            for line in f:
                if checksums:
                    if re.search("^ +(.*)$", line):
                        parts = list(filter(None, line.split(" ")))

                        # parts[0] = sha1
                        # parts[1] = size
                        # parts[2] = filename

                        if len(parts) == 3:
                            #if  "-" + settings.Language in parts[2]:
                            urlDownloads.append(baseUri + parts[2])
                        else:
                            logging.warn(f"Malformed checksum line '{line}' in {indexUri}")
                    else:
                        checksums = False
                else:
                    checksums = "SHA256:" in line or "SHA1:" in line or "MD5Sum:" in line
    else:
        FindTranslationFilesInRelease(url, component)
        return

def FindTranslationFilesInRelease(uri, component):
    # Look in the dists/$DIST/Release file for the translation files that belong
    # to the given component.

    releaseUri = uri + "Release"
    releasePath = settings.SkelPath + "/" +  SanitiseUri(releaseUri)

    checksums = False

    with open (releasePath) as f:
        for line in f:
            if checksums:
                if re.search("^ +(.*)$", line):
                    parts = list(filter(None, line.split(" ")))

                    # parts[0] = sha1
                    # parts[1] = size
                    # parts[2] = filename

                    if len(parts) == 3:
                        #if re.match(f"^{component}/i18n/Translation-{settings.Language}*\.bz2$", parts[2]):
                        if re.match(f"^{component}/i18n/Translation-[^./]*\.bz2$", parts[2]):
                            urlDownloads.append(uri + parts[2].rstrip())
                    else:
                        logging.warn(f"Malformed checksum line '{line}' in {releaseUri}")
                else:
                    checksums = False
            else:
                checksums = "SHA256:" in line or "SHA1:" in line or "MD5Sum:" in line

def ProcessDep11Files():
    logging.debug("Processing DEP-11 indexes: [")

    for source in sources:
        if source.SourceType != SourceType.BIN:
            continue
        #logging.debug("D")
        if len(source.Components) > 0:
            url = source.Uri + "/dists/" + source.Distribution + "/"

            for component in source.Components:
                FindDep11FilesInRelease(url, component, source.Architectures)

    logging.debug("]\n\n")

def FindDep11FilesInRelease(uri, component, architectures):
    # Look in the dists/$DIST/Release file for the DEP-11 files that belong
    # to the given component and architecture.

    releaseUri = uri + "Release"
    releasePath = settings.SkelPath + "/" +  SanitiseUri(releaseUri)

    checksums = False

    with open (releasePath) as f:
        for line in f:
            if checksums:
                if re.search("^ +(.*)$", line):
                    parts = list(filter(None, line.split(" ")))

                    # parts[0] = sha1
                    # parts[1] = size
                    # parts[2] = filename

                    if len(parts) == 3:
                        for arch in architectures:
                            if re.match(f"^{component}/dep11/(Components-{arch}\.yml|icons-[^./]+\.tar)\.(gz|bz2|xz)$", parts[2]):
                                urlDownloads.append(uri + parts[2].rstrip())
                    else:
                        logging.warn(f"Malformed checksum line '{line}' in {releaseUri}")
                else:
                    checksums = False
            else:
                checksums = "SHA256:" in line or "SHA1:" in line or "MD5Sum:" in line

def ProcessIndexes():
    logging.debug("Processing indexes: [")

    for source in sources:
        
        if source.SourceType == SourceType.SRC:
            #logging.debug("S")
            if len(source.Components) > 0:
                for component in source.Components:
                    ProcessIndex(source.Uri, f"/dists/{source.Distribution}/{component}/source/Sources")
            else:
                ProcessIndex(source.Uri, f"/{source.Distribution}/Sources")
        elif source.SourceType == SourceType.BIN:
            #logging.debug("P")
            if len(source.Components) > 0:
                for arch in source.Architectures:
                    for component in source.Components:
                        ProcessIndex(source.Uri, f"/dists/{source.Distribution}/{component}/binary-{arch}/Packages")
            else:
                ProcessIndex(source.Uri, f"/{source.Distribution}/Packages")

    logging.debug("]\n\n")

def ProcessIndex(uri, index):
    path = SanitiseUri(uri)

    mirror = settings.MirrorPath + "/" + path

    if os.path.isfile(f"{path}/{index}.gz"):
        os.system(f"gunzip < {path}/{index}.gz > {path}/{index}")
    elif os.path.isfile(f"{path}/{index}.xz"):
        os.system(f"xz -d {path}/{index}.xz > {path}/{index}")
    elif os.path.isfile(f"{path}/{index}.bz2"):
        os.system(f"bzip2 -d {path}/{index}.bz2 > {path}/{index}")

    package = []
    lines = []

    with open (settings.VarPath + "/ALL", "a+") as allFile, \
         open (settings.VarPath + "/NEW", "a+") as newFile, \
         open (settings.VarPath + "/MD5", "a+") as md5File, \
         open (settings.VarPath + "/SHA1", "a+") as sha1File, \
         open (settings.VarPath + "/SHA256", "a+") as sha256File:
        with open (f"{path}/{index}", "rb") as f:
            package = f.readlines()
            #l = re.compile("^([\w\-]+:)").split(f.read().decode())

        for line in package:
            lines.append(line.decode().rstrip())

        package = lines

        if any("Filename:" in s for s in package):
            # Packages Index
            WriteAllLines("Filename:", package, allFile, path)
            # WriteAllLines("MD5sum:", package, md5File, path)
            # WriteAllLines("SHA1:", package, sha1File, path)
            # WriteAllLines("SHA256:", package, sha1File, path)


def WriteAllLines(identifier, package, file, path):
    results = [i for i in package if i.startswith(identifier)]

    for result in results:
        splitLine = re.sub("^([\w\-]+:)", "", result).strip()
        file.write(f"{path}/{splitLine}\n")

def RemoveDoubleSlashes(string) -> str:
    string = string.replace("\\\\", "\\")
    string = string.replace("//", "/")

    return string

def SanitiseUri(uri) -> str:
    uri = re.sub("^(\w+)://", "", uri)

    if '@' in uri:
        uri = re.sub("^([^@]+)?@?/", "", uri)

    uri = re.sub(":\d+", "", uri) # Port information
   
    return uri

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()