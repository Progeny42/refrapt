from enum import Enum
import logging
import os
import multiprocessing 

class Settings:
    def __init__(self):
        self._architecture = "i386"

        # TODO : Development only. Remove in production
        if os.name == "nt":
            self._mirrorPath = "K:/Working/refrapt/mirror"
            self._skelPath = "K:/Working/refrapt/skel"
            self._varPath = "K:/Working/refrapt/var"
        else:
            self._mirrorPath = "./mirror"
            self._skelPath = "./skel"
            self._varPath = "./var" 

        self._contents = True
        self._threads = multiprocessing.cpu_count()
        self._authNoChallenge = False
        self._noCheckCertficate = False
        self._unlink = False
        self._useProxy = False
        self._httpProxy = None
        self._httpsProxy = None
        self._proxyUser = None
        self._proxyPass = None
        self._limitRate = "100m"
        self._language = "en"

    def Parse(self, config):
        for line in config:
            if line.startswith('#'):
                continue
            elif line.startswith("set"):
                self.__ParseSetting(line)

    def __ParseSetting(self, setting):
        settingName = setting.split("set")[1].strip()
        settingValue = setting.split("=")[1].strip()

        if "architecture" in setting:
            self._architecture = settingValue
        else:
            logging.warn(f"Setting not supported! {settingName}")

    @property
    def Architecture(self) -> str:
        return self._architecture

    @property
    def MirrorPath(self) -> str:
        return self._mirrorPath

    @property
    def SkelPath(self) -> str:
        return self._skelPath

    @property
    def VarPath(self) -> str:
        return self._varPath

    @property
    def Contents(self) -> bool:
        return self._contents

    @property
    def Threads(self) -> int:
        return self._threads
        
    @property
    def AuthNoChallege(self) -> bool:
        return self._authNoChallenge

    @property
    def NoCheckCertificate(self) -> bool:
        return self._noCheckCertficate
    
    @property
    def Unlink(self) -> bool:
        return self._unlink

    @property
    def UseProxy(self) -> bool:
        return self._useProxy

    @property
    def UseHttpProxy(self) -> bool:
        return len(self._httpProxy) > 0

    @property
    def HttpProxy(self) -> str:
        return self._httpProxy

    @property
    def UseHttpsProxy(self) -> bool:
        return len(self._httpsProxy) > 0

    @property
    def HttpsProxy(self) -> str:
        return self._httpsProxy

    @property
    def UseProxyUser(self) -> bool:
        return len(self._proxyUser) > 0

    @property
    def ProxyUser(self) -> str:
        return self._proxyUser

    @property
    def UseProxyPassword(self) -> bool:
        return len(self._proxyPass) > 0

    @property
    def ProxyPassword(self) -> str:
        return self._proxyPass

    @property
    def LimitRate(self) -> str:
        return self._limitRate

    @property
    def Language(self) -> str:
        return self._language


class SourceType(Enum):
    BIN = 0
    SRC = 1

class UrlType(Enum):
    Index       = 0
    Translation = 1
    Dep11       = 2
    Archive     = 3

class Source:
    def __init__(self, line, defaultArch):
        self._sourceType = SourceType.BIN
        self._architectures = []
        self._uri = None
        self._distribution = None
        self._components = []

        # Break down the line into its parts
        elements = line.split(" ")
        elements = list(filter(None, elements))

        # Determine Source type
        if elements[0] == "deb":
            self._sourceType = SourceType.BIN
        elif 'deb-src' in elements[0]:
            self._sourceType = SourceType.SRC

        elementIndex = 1

        # If Architecture(s) is specified, store it, else set the default
        if "[" in line and "]" in line:
            # Architecture is defined
            archList = line.split("[")[1].split("]")[0].split("=")[1]
            self._architectures = archList.split(",")
            elementIndex += 1
        else:
            self._architectures.append(defaultArch)

        self._uri           = elements[elementIndex]
        self._distribution  = elements[elementIndex + 1]
        self._components    = elements[elementIndex + 2:]

        # logging.debug("Source")
        # logging.debug(f"\tKind:         {self._sourceType}")
        # logging.debug(f"\tArch:         {self._architectures}")
        # logging.debug(f"\tUri:          {self._uri}")
        # logging.debug(f"\tDistribution: {self._distribution}")
        # logging.debug(f"\tComponents:   {self._components}")

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

