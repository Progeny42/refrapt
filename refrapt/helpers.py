import logging
import re
import time

def SanitiseUri(uri) -> str:
    uri = re.sub("^(\w+)://", "", uri)

    if '@' in uri:
        uri = re.sub("^([^@]+)?@?/", "", uri)

    uri = re.sub(":\d+", "", uri) # Port information
   
    return uri

def WaitForThreads(processes):
    i = len(processes)

    logging.info(f"Begin time: " + time.strftime("%H:%M:%S", time.localtime()))
    #print(f"[" + str(len(processes) - i) + "]...", end="", flush=True)
    for process in processes:
        process.join()
        i -= 1
        print(f"[" + str(len(processes) - i) + "]...", end="", flush=True)
    print("")
    logging.info(f"End time: " + time.strftime("%H:%M:%S", time.localtime()) + "\n\n")