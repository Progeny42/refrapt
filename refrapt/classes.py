from enum import Enum
import logging

class Settings:
    def __init__(self):
        self._architecture = "i386"
        self._mirrorPath = "./mirror"
        self._skelPath = "./skel"
        self._varPath = "./var"

    def Parse(self, config):
        for line in config:
            if line.startswith('#'):
                continue
            if line.startswith("set"):
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


class SourceType(Enum):
    BIN  = 0
    SRC  = 1
    ARCH = 2

class Source:
    def __init__(self, line):
        self._sourceType = SourceType.BIN
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
        else:
            self._sourceType = SourceType.ARCH

        self._uri           = elements[1]
        self._distribution  = elements[2]
        self._components    = elements[3:]

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

