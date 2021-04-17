from enum import Enum
import logging
import os
import multiprocessing 
import sys
import math
import re
import itertools
from functools import partial
import tqdm

from helpers import (
    SanitiseUri,
    WaitForThreads
)

class Settings:
    def __init__(self):
        self._settings = {
            "architecture"      : "i386", 
            "rootPath"          : "/var/spool/refrapt",
            "mirrorPath"        : "/mirror",
            "skelPath"          : "/skel",
            "varPath"           : "/var",
            "contents"          : True,
            "threads"           : multiprocessing.cpu_count(),
            "authNoChallenge"   : False,
            "noCheckCertificate": False,
            "unlink"            : False,
            "useProxy"          : False,
            "httpProxy"         : None,
            "httpsProxy"        : None,
            "proxyUser"         : None,
            "proxyPass"         : None,
            "limitRate"         : "500m", # Wget syntax
            "language"          : "en",   # TODO : Default to locale
            "forceUpdate"       : False,  # Use this to flag every single file as requiring an update, regardless of if the size matches. Use this if you know a file has changed, but you still have the old version (sizes were equal)
            "forceDownload"     : False,  # Use this to force Wget to redownload the file, even if the timestamp of the file matches that on the server. Use this in the event of an interrupted download
            "logLevel"          : "INFO"
        }

    def Parse(self, config):
        for line in config:
            if line.startswith("set"):
                key = line.split("set ")[1].split("=")[0].strip()
                
                if key in self._settings:
                    self._settings[key] = line.split("=")[1].strip()
                    logging.debug(f"Parsed setting: {key} = {self._settings.get(key)}")
                else:
                    logging.warn(f"Unknown setting in configuration file '{line}'")

    @property
    def Architecture(self) -> str:
        return self._settings["architecture"]

    @property
    def MirrorPath(self) -> str:
        return self._settings["rootPath"] + "/" + self._settings["mirrorPath"]

    @property
    def SkelPath(self) -> str:
        return self._settings["rootPath"] + "/" + self._settings["skelPath"]

    @property
    def VarPath(self) -> str:
        return self._settings["rootPath"] + "/" + self._settings["varPath"]

    @property
    def Contents(self) -> bool:
        return self._settings["contents"]

    @property
    def Threads(self) -> int:
        return self._settings["threads"]
        
    @property
    def AuthNoChallege(self) -> bool:
        return self._settings["authNoChallenge"]

    @property
    def NoCheckCertificate(self) -> bool:
        return self._settings["noCheckCertificate"]
    
    @property
    def Unlink(self) -> bool:
        return self._settings["unlink"]

    @property
    def UseProxy(self) -> bool:
        return self._settings["useProxy"]

    @property
    def UseHttpProxy(self) -> bool:
        return len(self._settings["httpProxy"]) > 0

    @property
    def HttpProxy(self) -> str:
        return self._settings["httpProxy"]

    @property
    def UseHttpsProxy(self) -> bool:
        return len(self._settings["httpsProxy"]) > 0

    @property
    def HttpsProxy(self) -> str:
        return self._settings["httpsProxy"]

    @property
    def UseProxyUser(self) -> bool:
        return len(self._settings["proxyUser"]) > 0

    @property
    def ProxyUser(self) -> str:
        return self._settings["proxyUser"]

    @property
    def UseProxyPassword(self) -> bool:
        return len(self._settings["proxyPass"]) > 0

    @property
    def ProxyPassword(self) -> str:
        return self._settings["proxyPass"]

    @property
    def LimitRate(self) -> str:
        return self._settings["limitRate"]

    @property
    def Language(self) -> str:
        return self._settings["language"]

    @property
    def ForceUpdate(self) -> bool:
        return self._settings["forceUpdate"]

    @property
    def ForceDownload(self) -> bool:
        return self._settings["forceDownload"]

    @property
    def LogLevel(self) -> str:
        return logging._nameToLevel[self._settings["logLevel"]]


class SourceType(Enum):
    Bin = 0
    Src = 1

class UrlType(Enum):
    Index       = 0
    Translation = 1
    Dep11       = 2
    Archive     = 3

class IndexType(Enum):
    Index   = 0
    Release = 1
    Dep11   = 2

class Source:
    def __init__(self, line, defaultArch):
        self._sourceType = SourceType.Bin
        self._architectures = []
        self._uri = None
        self._distribution = None
        self._components = []
        self._clean = True

        # Break down the line into its parts
        elements = line.split(" ")
        elements = list(filter(None, elements))

        # Determine Source type
        if elements[0] == "deb":
            self._sourceType = SourceType.Bin
        elif 'deb-src' in elements[0]:
            self._sourceType = SourceType.Src

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
        self._distribution  = elements[elementIndex + 1]
        self._components    = elements[elementIndex + 2:]

        logging.debug("Source")
        logging.debug(f"\tKind:         {self._sourceType}")
        logging.debug(f"\tArch:         {self._architectures}")
        logging.debug(f"\tUri:          {self._uri}")
        logging.debug(f"\tDistribution: {self._distribution}")
        logging.debug(f"\tComponents:   {self._components}")

    def GetIndexes(self, settings) -> list:
        baseUrl = self._uri + "/dists/" + self._distribution + "/"

        indexes = []

        if self._components:
            indexes.append(baseUrl + "InRelease")
            indexes.append(baseUrl + "Release")
            indexes.append(baseUrl + "Release.gpg")
        else:
            indexes.append(self._uri + "/" + self._distribution + "/Release")
            indexes.append(self._uri + "/" + self._distribution + "/Release.gpg")
            indexes.append(self._uri + "/" + self._distribution + "/Sources.gz")
            indexes.append(self._uri + "/" + self._distribution + "/Sources.bz2")
            indexes.append(self._uri + "/" + self._distribution + "/Sources.xz") 

        if self._sourceType == SourceType.Bin:
            # Binary Files
            if self._components:
                if settings.Contents:
                    for architecture in self._architectures:
                        indexes.append(baseUrl + "Contents-" + architecture + ".gz")
                        indexes.append(baseUrl + "Contents-" + architecture + ".bz2")
                        indexes.append(baseUrl + "Contents-" + architecture + ".xz")

                for component in self._components:
                    for architecture in self._architectures:
                        if settings.Contents:
                            indexes.append(baseUrl + component + "/Contents-" + architecture + ".gz")
                            indexes.append(baseUrl + component + "/Contents-" + architecture + ".bz2")
                            indexes.append(baseUrl + component + "/Contents-" + architecture + ".xz")

                        indexes.append(baseUrl + component + "/binary-" + architecture + "/Release")
                        indexes.append(baseUrl + component + "/binary-" + architecture + "/Packages.gz")
                        indexes.append(baseUrl + component + "/binary-" + architecture + "/Packages.bz2")
                        indexes.append(baseUrl + component + "/binary-" + architecture + "/Packages.xz")
                        
                    indexes.append(baseUrl + component + "/i18n/Index")

        elif self._sourceType == SourceType.Src:
            # Source Files
            if self._components:
                for component in self._components:
                    indexes.append(baseUrl + component + "/source/Release")
                    indexes.append(baseUrl + component + "/source/Sources.gz")
                    indexes.append(baseUrl + component + "/source/Sources.bz2")
                    indexes.append(baseUrl + component + "/source/Sources.xz")

        return indexes


    def GetReleaseFiles(self) -> list:
        if self._sourceType == SourceType.Src:
            return self.__GetSourceIndexes()
        elif self._sourceType == SourceType.Bin:
            return self.__GetPackageIndexes()

    def __GetSourceIndexes(self) -> list:
        indexes = []

        if self._components:
            for component in self._components:
                indexes.append(f"{SanitiseUri(self._uri)}/dists/{self._distribution}/{component}/source/Sources")
        else:
            indexes.append(f"{SanitiseUri(self._uri)}/{self._distribution}/Sources")

        return indexes

    def __GetPackageIndexes(self) -> list:
        indexes = []

        if self._components:
            for arch in self._architectures:
                for component in self._components:
                    indexes.append(f"{SanitiseUri(self._uri)}/dists/{self._distribution}/{component}/binary-{arch}/Packages")
        else:
            indexes.append(f"{SanitiseUri(self._uri)}/{self._distribution}/Packages")

        return indexes

    def GetTranslationIndexes(self, settings) -> list:
        if self._sourceType != SourceType.Bin:
            return
        
        baseUrl = self._uri + "/dists/" + self._distribution + "/"

        translationIndexes = []

        for component in self._components:
            translationIndexes += self.__ProcessTranslationIndex(baseUrl, component, settings)

        return translationIndexes

    def GetDep11Files(self, settings) -> list:
        if self._sourceType != SourceType.Bin:
            return
        
        baseUrl = self._uri + "/dists/" + self._distribution + "/"
        releaseUri = baseUrl + "Release"
        releasePath = settings.SkelPath + "/" +  SanitiseUri(releaseUri)

        dep11Files = []

        for component in self._components:
            dep11Files += self.__ProcessLine(releasePath, IndexType.Dep11, baseUrl, "", component)

        return dep11Files

    def __ProcessTranslationIndex(self, url, component, settings) -> list:
        # Extract all translation files from the dists/$DIST/$COMPONENT/i18n/Index
        # file. Fall back to parsing dists/$DIST/Release if i18n/Index is not found.

        baseUri = url + component + "/i18n/"
        indexUri = baseUri + "Index"
        indexPath = settings.SkelPath + "/" + SanitiseUri(indexUri)

        if not os.path.isfile(indexPath):
            releaseUri = url + "Release"
            releasePath = settings.SkelPath + "/" + SanitiseUri(releaseUri)
            return self.__ProcessLine(releasePath, IndexType.Release, url, "", component)
        else:
            return self.__ProcessLine(indexPath, IndexType.Index, indexUri, baseUri, "")

    def __ProcessLine(self, file, indexType, indexUri, baseUri = "", component = "") -> list:
        checksums = False

        indexes = []

        with open (file) as f:
            for line in f:
                if checksums:
                    if re.search("^ +(.*)$", line):
                        parts = list(filter(None, line.split(" ")))

                        # parts[0] = sha1
                        # parts[1] = size
                        # parts[2] = filename

                        if not len(parts) == 3:
                            logging.warn(f"Malformed checksum line '{line}' in {indexUri}")
                            continue

                        filename = parts[2].rstrip()

                        if indexType == IndexType.Release:
                            #if re.match(f"^{component}/i18n/Translation-{settings.Language}*\.(gz|bz2|xz)$", filename):
                            if re.match(f"^{component}/i18n/Translation-[^./]*\.(gz|bz2|xz)$", filename):
                                indexes.append(indexUri + filename)
                        elif indexType == IndexType.Dep11:
                            for arch in self._architectures:
                                if re.match(f"^{component}/dep11/(Components-{arch}\.yml|icons-[^./]+\.tar)\.(gz|bz2|xz)$", filename):
                                    indexes.append(indexUri + filename)
                        else:
                            indexes.append(baseUri + filename)                           
                    else:
                        checksums = False
                else:
                    checksums = "SHA256:" in line or "SHA1:" in line or "MD5Sum:" in line   

        return indexes

    @property
    def SourceType(self) -> SourceType:
        return self._sourceType

    @property
    def Uri(self) -> str:
        return self._uri

    @property
    def Distribution(self) -> str:
        return self._distribution

    @property   
    def Components(self) -> list:
        return self._components

    @property   
    def Architectures(self) -> list:
        return self._architectures

    @property
    def Clean(self) -> bool:
        return self._clean

    @Clean.setter
    def Clean(self, value):
        self._clean = value

class Downloader:
    def Download(urls, kind, settings):
        if not urls:
            logging.info("No files to download")
            return

        arguments = Downloader.CustomArguments(settings)

        logging.info(f"Downloading {len(urls)} {kind.name} files...")

        with multiprocessing.Pool(settings.Threads) as pool:
            downloadFunc = partial(Downloader.DownloadUrlsProcess, kind=kind.name, args=arguments, settings=settings)
            for _ in tqdm.tqdm(pool.imap_unordered(downloadFunc, urls), total=len(urls), unit=" file"):
                pass

    def DownloadUrlsProcess(urls, kind, args, settings):
        p = multiprocessing.current_process()

        baseCommand   = "wget --no-cache"
        timestamp     = "-N" 
        rateLimit     = f"--limit-rate={settings.LimitRate}"
        retries       = "-t 5"
        recursiveOpts = "-r -l inf"
        logFile       = f"-a {settings.VarPath}/{kind}-log.{p._identity[0]}"

        # With Timestamps enabled (-N), if a file did not fully download, and you attempt to redownload again,
        # Wget will check the timestamps, and possibly determine that nothing has changed. This would leave you with
        # a partial file which won't get updated until the file on the server gets updated!
        # By default, timestampping will save Wget re-downloading a file that it does not need to, but
        # if the option is set by the user, timestamps should be ignored to allow Wget to redownload the
        # file from scratch

        if not settings.ForceDownload:
            baseCommand += f" {timestamp} "

        #logging.debug(f"{baseCommand} {rateLimit} {retries} {recursiveOpts} {logFile} {inputFile} {args}")
        #os.system(f"{baseCommand} {rateLimit} {retries} {recursiveOpts} {logFile} {inputFile} {args}")

        #print(f"{baseCommand} {rateLimit} {retries} {recursiveOpts} {logFile} {urls} {args}")
        os.system(f"{baseCommand} {rateLimit} {retries} {recursiveOpts} {logFile} {urls} {args}")

    def CustomArguments(settings) -> list:
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

        return arguments

class Index:
    def __init__(self, path):
        self._path = path

    def Read(self):
        contents = []
        self._lines = []

        with open (self._path, "rb") as f:
            contents = f.readlines()

        for line in contents:
            self._lines.append(line.decode().rstrip())

    def GetPackages(self) -> list:
        packages = []
        package = dict()

        keywords = ["Filename", "MD5sum", "SHA1", "SHA256", "Size", "Files", "Directory"]

        key = None

        for line in self._lines:
            if not line:
                packages.append(package)
                package = dict()  
            else:
                match = re.search("^([\w\-]+:)", line)
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
