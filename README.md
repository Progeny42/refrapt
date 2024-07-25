# **Refrapt** 
![Build](https://github.com/progeny42/refrapt/actions/workflows/ci.yml/badge.svg)
![Release](https://img.shields.io/github/release-date/Progeny42/refrapt?label=Release%20Date) 
![Status](https://img.shields.io/pypi/status/Refrapt?color=silver&label=Status) 
![Issues](https://img.shields.io/github/issues/Progeny42/refrapt?label=Issues) 
![Downloads](https://img.shields.io/pypi/dm/Refrapt) 

-------------

## What is Refrapt?
Refrapt (Refract Apt) is originally a clone of [`apt-mirror`](https://github.com/apt-mirror/apt-mirror), rewritten in Python, and adding a handful of improvements and fixes as identified by Open Issues and Pull Requests.

I wanted a simple way of being able to clone Debian mirrors to create my own local repository. `apt-mirror` is what I had originally used, until it stopped working.

Refrapt was developed on Windows, but intended for use on a Linux machine.

## Features
-------------
If you've used `apt-mirror`, this should be familiar. However, there are a handful of new features available:
* Faster overall processing than `apt-mirror`, by intelligently checking whether a file has been modified after the download process, cutting down on processing files that have not changed.
* Progress Bars for each step of the application, and especially for downloads.
* Downloads and decompression tasks are multithreaded, by using `multiprocessing.Pools`, which leads to a more efficient use of threads when one thread is taking longer than others.
* Support for multiple architectures per line. No more duplicating lines with just a change to the `[arch=X]` parameter!
* SSL support for Wget. Simply populate the correct fields in the configuration file.
* Logging is now also performed to a file as well as the Console. Log files are limited in size to 500MB, and retain the last 3 copies.
* Download of `Contents-[arch].*` files is configurable via the configuration file.
* Download of `/by-hash/*` directories is configurable via the configuration file.
* Test mode to prevent doing the main download.
* Automatic cleaning of directories after mirroring.
* Safer partial download recovery in the event Refrapt is interrupted via file locking and detection at script start (see the section on partial downloads for an explanation).

# Getting Started
-------------
You will require Python 3.9 in order to install and run `refrapt`.

To install Refrapt, run the following `pip` command:
```sh
python3.9 -m pip install refrapt
```

The first time Refrapt is run, a default configuration file will be installed at ~/refrapt/refrapt.conf. To specify a custom location, issue the following command:
```sh
refrapt --conf "/path/to/your/config/file/refrapt.conf"
```

Edit the configuration file by adding each of the Repositories you wish to mirror. Examples are provided in the file.

For help with commands, run `refrapt --help`.

# Command Line Options
-------------
`--test` - Runs the application as normal, but does not perform the main download of files to the local mirror, and does not clean any files identified as no longer being required. Use this option to determine how large a download is going to be, and / or how many old files can be removed.

`--clean` - Only perform cleaning of files no longer required. No downloads are performed. Can be used in conjunction with the `--test` option to identify the size of files that can be cleaned, without actually removing them. Use this option if your Repositories are not set to clean during the mirror process, or cleaning is globally disabled with `disableClean` in the configuration file. In conjunction with the `disableClean` option in the configuration file, Refrapt could clean unecessary files on a schedule such as in a cronjob.

# Feature Explanation
-------------

## Test Mode
Test mode can be set either via the configuration file, or passed as an argument to Refrapt using `--test`. *Note that passing Test mode as an argument will allow you see if the parsed arguments from the Settings file*. Test mode still downloads the Index files that allow Refrapt to gather all the Packages and Sources that you have defined in the configuration file, but it will not attempt the main download. This is a useful feature if you wish to see how big a download will be before comitting to it.

## Why this project ***does not*** use Wget --continue or --no-if-modified-since for dealing with partial downloads
Partial downloads are a problem and there is not a simple way with `Wget` to resume a download without the possibility of either corrupting the file, or causing excess downloads to occur. 

Refrapt uses the `--timestamping` (`-N`) option with `Wget`, which checks with the server the modified time of the file, and compares it with the local copy. If the timestamps match, regardless of whether the download completed, `Wget` will ignore the file with a `304 Not Modified`. Under normal circumstances, this prevents redownloading files which you already have, saving on time and bandwidth. In the event a download was interrupted, a subsequent attempt will not succeed, as `Wget` will ignore the file until the file changes on the server.

Now, you could use `Wget --continue`, but it has problems. The `--continue` option compares the length of the local copy with the length of the requested file (if that option is supported by the server), and if they differ, `Wget` will request the remainder of the file, calculated by "(length(remote) - length(local))" in bytes. Now, if you were only downloading a log file, or an mp3, the file would likely only get longer, so appending the remaining bytes to the local copy would succeed. However, when dealing with the files in a mirror, if the contents have shifted at all, appending the remaining bytes will mean that while the sizes would match, the file is now corrupt. This will leave a corrupt version of the file in your local mirror, which will not be updated until a new update is released to the server.

Further, you could use the `--no-if-modified-since` option, which causes `Wget` to request the size and timestamp of the file which does circumvent the corruption possibilites of `--continue`. However not all servers are obligated, or able to return the size of the content being downloaded, which would mean that if unsupported, `Wget` will download the entire file each time Refrapt is run, as the sizes will not match, even though the timestamps do. This could cause unnecessary redownloads of perfectly good files.

To attain the best of both worlds, Refrapt uses lock files. Just before the call to `Wget` is made, a `Download-lock.*` file is created, with the Uri of the resource attempting to be downloaded. Once the `Wget` download is complete, the lock file is removed. In the event that Refrapt is interrupted, next time Refrapt is run, it will scan the `VarPath` for any `Download-lock.*` files. If any are found, this means the file on disk is only partial downloaded. Refrapt will then delete the local copy, to ensure that `Wget` will always get the file again.

# Donate
-------------
If you found this software helpful, consider a small contribution. Thanks very much!

[![paypal](https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/donate/?hosted_button_id=F9XAHN4UUCKFJ)
