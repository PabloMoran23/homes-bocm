# Calella — 08035

Official live public-works catalogue verified 2026-11-07 HTTP200:
https://www.calella.cat/ajuntament-seu-electronica/informacio-oficial/normativa/urbanisme/obra-publica
Three listing pages currently expose named works: sewers, street urbanisation,
sports facilities and public-building interventions. Parse actual article-item
entries and their municipal detail URLs, excluding navigation. Pagination links are discovered dynamically (currently three pages); a 20-page
safety limit fails explicitly rather than silently truncating the catalogue.
Exposure-period text is preserved as description, never converted to publication
or approval dates. This is the public-works catalogue, not private licences.

Geometry investigated: https://www.calella.cat/ciutat/informacio-geografica links
http://sitmun.diba.cat/idelocals?id=08035. Generic municipal SITMUN is not a verified
join to these work records. No project-linked vector geometry in catalogue; no
centroid/jitter substituted. publication_ready false and schedule/licences off.
Direct live extraction evidence and validation stored in task artifacts/calella.
