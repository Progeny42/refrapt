import sys
import logging
import click
from pathlib import Path

import classes

# Consider these as Constants
CONFIG_FILE = "refrapt.cfg"

settings = classes.Settings()
configData = []
urlDownloads = []

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

    print(settings.Architecture)

    ProcessSources()

@click.command()
def ProcessSources():
    sources = []

    for line in configData:
        sources.append(classes.Source(line))

    for source in sources:
        if source.SourceType == classes.SourceType.SRC:
            logging.debug("Processing SRC")

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
        elif source.SourceType == classes.SourceType.BIN:
            logging.debug("Processing BIN")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()