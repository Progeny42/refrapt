import multiprocessing
import logging
from pathlib import Path
import platform
import locale

logger = logging.getLogger(__name__)

class Settings:
    _settings = {
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
    _force = False

    @staticmethod
    def Parse(config: list):
        """Parse the configuration file and set the settings defined."""
        for line in config:
            if line.startswith("set"):
                key = line.split("set ")[1].split("=")[0].strip()

                if key in Settings._settings:
                    value = line.split("=")[1].strip().split(" ")[0] # Allow for inline comments, but strip them here

                    if value.isdigit():
                        Settings._settings[key] = int(value)
                    elif "true" in value.lower() or "false" in value.lower():
                        Settings._settings[key] = value.lower() == "true"
                    else:
                        Settings._settings[key] = value.strip().strip('"')

                    logger.debug(f"Parsed setting: {key} = {Settings._settings.get(key)}")
                else:
                    logger.warning(f"Unknown setting in configuration file '{line}'")

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
    def AuthNoChallege() -> bool:
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
    def HttpProxy() -> str:
        """Get the httpProxy setting."""
        return str(Settings._settings["httpProxy"])

    @staticmethod
    def HttpsProxy() -> str:
        """Get the httpsProxy setting."""
        return str(Settings._settings["httpsProxy"])

    @staticmethod
    def ProxyUser() -> str:
        """Get the proxyUser setting."""
        return str(Settings._settings["proxyUser"])

    @staticmethod
    def ProxyPassword() -> str:
        """Get the proxyPass setting."""
        return str(Settings._settings["proxyPass"])

    @staticmethod
    def Certificate() -> str:
        """Get the certificate setting for SSL."""
        return str(Settings._settings["certificate"])

    @staticmethod
    def CaCertificate() -> str:
        """Get the ca certificate setting for SSL."""
        return str(Settings._settings["caCertificate"])

    @staticmethod
    def PrivateKey() -> str:
        """Get the private key setting for SSL."""
        return str(Settings._settings["privateKey"])

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
