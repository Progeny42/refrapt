"""Helper methods for use with Refrapt."""

import re

def SanitiseUri(uri: str) -> str:
    """Sanitise a Uri so it is suitable for filesystem use."""
    uri = re.sub(r"^(\w+)://", "", uri)
    uri = re.sub(r":\d+", "", uri) # Port information

    return uri
