"""Helper methods for use with Refrapt."""

import logging
import re
import time

def SanitiseUri(uri: str) -> str:
    """Sanitise a Uri so it is suitable for filesystem use."""
    uri = re.sub("^(\w+)://", "", uri)

    # if '@' in uri:
    #     uri = re.sub("^([^@]+)?@?/", "", uri)

    uri = re.sub(":\d+", "", uri) # Port information
   
    return uri