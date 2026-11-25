"""Transport options for the Generalitat Valenciana planning WFS."""

from urllib.request import Request


def enable_icv_compression(request: Request) -> None:
    """Reduce the amount of data transferred for ICV's large regional pages."""
    if request.host == "terramapas.icv.gva.es":
        request.add_header("Accept-Encoding", "gzip")
