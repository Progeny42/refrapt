"""Run all tests in this directory using unittest."""

from unittest import TestLoader, TestResult
import sys
from pathlib import Path
import logging

import coverage
import colorama
from colorama import Fore, Style

def Suite():
    """Loads each of the test files in the test directory, runs them, and then prints the results."""
    
    testLoader = TestLoader()
    testResult = TestResult()

    sourceDirectory = str(Path(__file__).parent.parent.absolute()) + "/refrapt/"

    cov = coverage.Coverage(branch=True, source=[sourceDirectory])
    cov.start()

    logging.disable(logging.CRITICAL)

    testDirectory = str(Path(__file__).parent.absolute())
    testSuite = testLoader.discover(testDirectory, pattern='test_*.py')
    testSuite.run(result=testResult)

    logging.disable(logging.NOTSET)

    cov.stop()
    cov.save()
    cov.html_report()

    print("-------------------------------------")
    print("Refrapt Test Results")
    print("-------------------------------------\n")


    if testResult.skipped:
        print(f"{Style.DIM}Skipped:")
        print("-------------------------------------")
        for case, reason in testResult.skipped:
            print(f"{Fore.LIGHTBLUE_EX}{case.id()}{Fore.WHITE} - {reason}")
        print()

    if testResult.errors:
        print(f"{Fore.RED}Errors:")
        print("-------------------------------------")
        for case, error in testResult.errors:
            print(f"{Fore.LIGHTBLUE_EX}{case.id()}")
            print(f"{error}")

    if testResult.failures:
        print(f"{Fore.RED}Failures:")
        print("-------------------------------------")
        for case, failure in testResult.failures:
            print(f"{Fore.LIGHTBLUE_EX}{case.id()}")
            print(f"{failure}")

    if testResult.unexpectedSuccesses:
        print(f"{Fore.YELLOW}Unexpected Successes:")
        print("-------------------------------------")
        for case in testResult.unexpectedSuccesses:
            print(f"{Fore.LIGHTBLUE_EX}{case.id()}")

    PrintStats(testResult)

    sys.exit(testResult.wasSuccessful())

def PrintStats(testResult : TestResult):
    """Prints stats about the test run."""
    print("-------------------------------------")
    print("Statistics")
    print("-------------------------------------\n")

    passCount = testResult.testsRun

    if testResult.skipped:
        print(f"{Style.DIM}Skipped             : {len(testResult.skipped)}")
        passCount -= len(testResult.skipped)

    if testResult.errors:
        print(f"{Fore.RED}Errors              : {len(testResult.errors)}")
        passCount -= len(testResult.errors)

    if testResult.failures:
        print(f"{Fore.RED}Failures            : {len(testResult.failures)}")
        passCount -= len(testResult.failures)

    if testResult.expectedFailures:
        print(f"{Fore.MAGENTA}Expected Failures   : {len(testResult.expectedFailures)}")
        passCount -= len(testResult.expectedFailures)

    if testResult.unexpectedSuccesses:
        print(f"{Fore.YELLOW}Unexpected Successes: {len(testResult.unexpectedSuccesses)}")
        passCount -= len(testResult.unexpectedSuccesses)

    totalTestsRun = testResult.testsRun - len(testResult.skipped)

    colour = Fore.GREEN
    if passCount < totalTestsRun and passCount > 0:
        print()
        colour = Fore.YELLOW
    elif passCount == 0:
        print()
        colour = Fore.RED
    elif testResult.skipped:
        print()

    print(f"{colour}Pass {passCount} / {totalTestsRun}")
    print("-------------------------------------\n")

if __name__ == '__main__':
    colorama.init(autoreset=True)
    Suite()
