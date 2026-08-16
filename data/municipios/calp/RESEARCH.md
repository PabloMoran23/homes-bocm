# Calp — investigación portal ayuntamiento

Municipio: **Calp** (`calp`) — Alicante, Comunitat Valenciana. INE `03047`. Boletín: DOGV.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.calp.es/es/ |
| Portal transparencia urbanismo | https://www.calp.es/es/portal-de-transparencia/urbanismo-y-medio-ambiente |
| Planeamiento (Drupal node) | https://www.calp.es/es/node/10884 |
| Sede electrónica (espublico) | https://calp.sedelectronica.es/ |
| Tablón de anuncios | https://calp.sedelectronica.es/board |
| Transparencia planeamiento (sede) | https://calp.sedelectronica.es/transparency/a24a7907-f637-483f-9b3c-a736b5027b3e/ |
| Catálogo trámites | https://calp.sedelectronica.es/dossier |
| Geoportal municipal | https://geoportal.calp.es/ |
| ICV GVA visor | https://visor.gva.es/visor/?idioma=es |
| IDE Geonet (metadato PGOU) | https://ide.geonet.es/ide/srv/api/records/spaAYTCALPseriePGOUopzona2020 |

## Expedientes / planeamiento

- **Sede transparencia (espublico):** tabla HTML con enlaces `preview-document/{uuid}` — 7 documentos PGOU (modificaciones D-12, D-14, plan especial Baños de la Reina, DOGV, edictos). Sin paginación útil (repite las mismas entradas).
- **Tablón /board:** tabla Wicket con columnas expediente, procedimiento, categoría; ~10 anuncios visibles (licencias actividad, legalidad urbanística, etc.). Paginación AJAX Wicket («Mostrar más»).
- **Web calp.es:** Drupal 7; sección transparencia sin PDFs embebidos en HTML (contenido en sede).
- **Consulta expedientes:** https://calp.sedelectronica.es/expedientes — requiere identificación.

## Licencias

- No hay dataset público de licencias concedidas con coordenadas.
- Tablón publica licencias de **actividad** (edictos IP) y notificaciones de **legalidad urbanística**.
- Trámites de obra vía sede (`/dossier`); sin histórico scrapeable.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV GVA WFS: `https://terramapas.icv.gva.es/0702_Planeamiento` — capa `Planeamiento.Zonificacion`, filtro `cod_ine_mun=03047` (~56 polígonos zonificación PGOU). Salida GML3 → GeoJSON WGS84.
  - Geoportal municipal (Geonet): visor web sin servicio REST público enlazable a expediente; metadato IDE describe serie PGOU OP zonas.
  - DipCAS OpenDataSoft: sin registros para Calp (`cod_mun 03047`).
- **Estrategia:** tras scrape, matching por keywords en título (PGOU, D-12/D-14, Baños de la Reina, Morello/Fossa/Saladar) contra zonificación GVA; merge de polígonos «Plan general» cuando hay match.
- **Limitaciones:** zonificación municipal agregada, no delimitación por expediente/modificación; visor Geonet sin query por código de expediente; licencias sin georef.

## Limitaciones generales

- Sede espublico: SSL válido; `insecure_ssl` por consistencia con otros adapters espublico.
- Tablón: solo primera página sin simular Wicket AJAX.
- Sin re-parse BOCM/DOGV en este adapter.
