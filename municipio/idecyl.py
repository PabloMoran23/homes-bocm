"""Verified HTTP for the Junta de Castilla y León's IDECyL service."""

import ssl
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from municipio.http import PortalReadError, fetch_text


@lru_cache(maxsize=1)
def _idecyl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    # IDECyL omits its issuer from the server's TLS chain. The missing
    # intermediate is published by Sectigo at the certificate's AIA URL:
    # http://crt.sectigo.com/SectigoPublicServerAuthenticationCAOVR36.crt
    # It must still chain to a system-trusted root, with normal hostname checks.
    if hasattr(ssl, "VERIFY_X509_PARTIAL_CHAIN"):
        context.verify_flags &= ~ssl.VERIFY_X509_PARTIAL_CHAIN
    context.load_verify_locations(
        cafile=Path(__file__).with_name("gis") / "sectigo-public-server-authentication-ca-ov-r36.pem"
    )
    return context


def fetch_text_with_idecyl_chain(request, *, opener=None, timeout: float = 60) -> str:
    if urlsplit(request.full_url).hostname != "idecyl.jcyl.es":
        return fetch_text(request, encoding="utf-8", opener=opener, timeout=timeout)

    def open_idecyl(req, *, timeout):
        return urllib.request.urlopen(req, timeout=timeout, context=_idecyl_context())

    try:
        return fetch_text(request, encoding="utf-8", opener=open_idecyl, timeout=timeout)
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, ssl.SSLCertVerificationError):
            raise PortalReadError(f"{request.full_url}: TLS certificate verification failed: {exc}") from exc
        raise
