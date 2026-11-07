# San Bartolomé, Lanzarote — 35018

Verified live official Gobierno de Canarias SITCAN dataset 2026-11-07 HTTP200:
https://opendata.sitcan.es/api/3/action/package_show?id=planeamiento-urbanistico-de-san-bartolome
Actual named adopted instruments (NNSS modifications, plans, architectural
catalogue). One HTML GRAFCAN dossier resource per instrument avoids multiplying
SIPU/PDF/FIP formats into separate projects. Stable ID uses official dossier URL.
Dataset identity checked to avoid confusion with San Bartolomé de Tirajana.
Published dates parsed only when explicitly stated in resource names. Multiple
BOC/BOP dates retained as list; CKAN modification timestamp is never an approval.
Source is explicitly gobierno_canarias, not a fabricated municipal grant register.

Geometry resources investigated: each instrument has linked SIPU/FIP ZIP exports,
but no directly joined GeoJSON was validated in this bounded pass. Dossier HTML
links retained. Further FIP/SIPU parsing can supply authoritative geometry; no
centroid substituted. publication_ready false, schedules/licences/jitter off.
Live extraction and tests saved under task artifacts/san-bartolome.
