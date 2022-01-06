"""Contains the Settings singleton class."""

import multiprocessing
import logging
from pathlib import Path
import platform
import locale
from typing import Any, Optional

logger = logging.getLogger(__name__)

class Settings:
    """Settings singleton for the application."""

    _settings = { "rootPath"          : f"{str(Path.home())}/refrapt" } # type: dict[str, Any]
    _force = False

    @staticmethod
    def Init():
        """Initialise default settings."""

        Settings._settings = {
            "architecture"      : platform.machine(),
            "rootPath"          : f"{str(Path.home())}/refrapt",
            "mirrorPath"        : f"{str(Path.home())}/refrapt/mirror",
            "skelPath"          : f"{str(Path.home())}/refrapt/skel",
            "varPath"           : f"{str(Path.home())}/refrapt/var",
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
            "certificate"       : None,
            "caCertificate"     : None,
            "privateKey"        : None,
            "limitRate"         : "500m", # Wget syntax
            "language"          : locale.getdefaultlocale()[0],
            "forceUpdate"       : False,  # Use this to flag every single file as requiring an update, regardless of if the size matches. Use this if you know a file has changed, but you still have the old version (sizes were equal)
            "logLevel"          : "INFO",
            "test"              : False,
            "byHash"            : False,
        }
        Settings._force = False

        # Shorten specific locales like en_GB to en to catch more files
        if "_" in Settings.Language():
            Settings._settings["language"] = Settings.Language().split("_")[0]

    @staticmethod
    def Parse(config: list):
        """Parse the configuration file and set the settings defined."""

        if not config:
            logger.warning("Configuration file is empty!")
            return

        for line in config:
            if line.startswith("set ") and len(line.strip()) > 4:
                key = line.split("set ")[1].split("=")[0].strip()

                if key in Settings._settings:
                    value = line.split("=")[1].strip().split(" ")[0] # Allow for inline comments, but strip them here

                    if value.isdigit():
                        Settings._settings[key] = int(value)
                    elif "true" in value.lower() or "false" in value.lower():
                        Settings._settings[key] = value.lower() == "true"
                    else:
                        if isinstance(Settings._settings[key], str) or Settings._settings[key] is None:
                            if key == "logLevel" and not value.strip().strip('"') in logging._nameToLevel:
                                logger.warning(f"logLevel setting value ({value}) is not a valid logging level.")
                            else:
                                Settings._settings[key] = value.strip().strip('"')
                        else:
                            logger.warning(f"Setting '{key}' value ({value}) is the wrong type. Should be {type(Settings._settings[key])}")

                    logger.debug(f"Parsed setting: {key} = {Settings._settings.get(key)}")
                else:
                    logger.warning(f"Unknown setting in configuration file: '{key}'")

        # Shorten specific locales like en_GB to en to catch more files
        if "_" in Settings.Language():
            Settings._settings["language"] = Settings.Language().split("_")[0]

    @staticmethod
    def Test() -> bool:
        """Get whether Test mode is enabled."""
        return bool(Settings._settings["test"])

    @staticmethod
    def EnableTest():
        """Enable Test mode."""
        Settings._settings["test"] = True

    @staticmethod
    def Architecture() -> str:
        """Get the default Architecture."""
        return str(Settings._settings["architecture"])

    @staticmethod
    def GetRootPath() -> str:
        """Get the root path."""
        return str(Settings._settings["rootPath"])

    @staticmethod
    def MirrorPath() -> str:
        """Get the path to the /mirror directory."""
        return str(Settings._settings["mirrorPath"])

    @staticmethod
    def SkelPath() -> str:
        """Get the path to the /skel directory."""
        return str(Settings._settings["skelPath"])

    @staticmethod
    def VarPath() -> str:
        """Get the path to the /var directory."""
        return str(Settings._settings["varPath"])

    @staticmethod
    def Contents() -> bool:
        """Get whether Contents files should be included."""
        return bool(Settings._settings["contents"])

    @staticmethod
    def Threads() -> int:
        """Get the number of threads to use for multiprocessing tasks."""
        return int(str(Settings._settings["threads"]))

    @staticmethod
    def AuthNoChallenge() -> bool:
        """Get whether Wget should use the --auth-no-challenge parameter."""
        return bool(Settings._settings["authNoChallenge"])

    @staticmethod
    def NoCheckCertificate() -> bool:
        """Get whether Wget should use the --no-check-certificate parameter."""
        return bool(Settings._settings["noCheckCertificate"])

    @staticmethod
    def Unlink() -> bool:
        """Get whether Wget should use the --unlink parameter."""
        return bool(Settings._settings["unlink"])

    @staticmethod
    def UseProxy() -> bool:
        """Get whether Wget should use the -e use_proxy=yes parameter."""
        return bool(Settings._settings["useProxy"])

    @staticmethod
    def HttpProxy() -> Optional[str]:
        """Get the httpProxy setting."""
        return Settings._settings["httpProxy"] # type: ignore

    @staticmethod
    def HttpsProxy() -> Optional[str]:
        """Get the httpsProxy setting."""
        return Settings._settings["httpsProxy"] # type: ignore

    @staticmethod
    def ProxyUser() -> Optional[str]:
        """Get the proxyUser setting."""
        return Settings._settings["proxyUser"] # type: ignore

    @staticmethod
    def ProxyPassword() -> Optional[str]:
        """Get the proxyPass setting."""
        return Settings._settings["proxyPass"] # type: ignore

    @staticmethod
    def Certificate() -> Optional[str]:
        """Get the certificate setting for SSL."""
        return Settings._settings["certificate"] # type: ignore

    @staticmethod
    def CaCertificate() -> Optional[str]:
        """Get the ca certificate setting for SSL."""
        return Settings._settings["caCertificate"] # type: ignore

    @staticmethod
    def PrivateKey() -> Optional[str]:
        """Get the private key setting for SSL."""
        return Settings._settings["privateKey"] # type: ignore

    @staticmethod
    def LimitRate() -> str:
        """Get the value of the --limit-rate setting used for Wget."""
        return str(Settings._settings["limitRate"])

    @staticmethod
    def Language() -> str:
        """Get the local languge setting."""
        return str(Settings._settings["language"])

    @staticmethod
    def ForceUpdate() -> bool:
        """Get whether updates of files should be forced."""
        return bool(Settings._settings["forceUpdate"])

    @staticmethod
    def LogLevel() -> int:
        """Get the log level used for application logger."""
        return int(logging._nameToLevel[str(Settings._settings["logLevel"])])

    @staticmethod
    def ByHash() -> bool:
        """Get whether the by-hash directories should be included in downloads."""
        return bool(Settings._settings["byHash"])

    @staticmethod
    def SetForce():
        """Set whether the application should force full processing in the event of an interrupted run."""
        Settings._force = True

    @staticmethod
    def Force() -> bool:
        """Get whether the application should force full processing in the event of an interrupted run."""
        return bool(Settings._force)
