# Santa Fe (Granada) — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | http://www.santafe.es |
| Urbanismo e Infraestructuras | http://www.santafe.es/index.php?g=1&c=2&c2=&f1=contenidos&s1=see&f2=&s2=&ob=&sp=fd758a562efe887ea5300b37463fe9e3 |
| Planeamiento urbanístico (NNSS / planos PDF) | http://www.santafe.es/index.php?g=1&c=2&c2=&f1=contenidos&s1=see&f2=&s2=&ob=&sp=fd758a562efe887ea5300b37463fe9e3&spp=767729668d7e514416a282aeaa988187 |
| Formularios e impresos (licencias / DR) | http://www.santafe.es/index.php?g=1&c=2&c2=&f1=contenidos&s1=see&f2=&s2=&ob=&spp=04a26d0be3e8c1ef3fd08330825579 |
| Sede electrónica (espublico gestiona) | https://santafe.sedelectronica.es |
| Tablón de anuncios | https://santafe.sedelectronica.es/board/ |
| Callejero (Google Maps embebido) | `f1=googlemaps&s1=callejero` en web Artico |

## CMS y listado de expedientes

- **Web:** CMS propio **Artico Estudio** (PHP, charset ISO-8859-1). Contenidos estáticos con adjuntos PDF vía `MM_openBrWindow('data/ficherosadjuntos_contenidosweb/...pdf')`.
- **Sede:** **espublico gestiona** (Wicket). Tablón en `/board/` con filas HTML `class_name`, `class_folderCode`, enlaces `/preview-document/{uuid}`.
- **Licencias:** no hay listado histórico de licencias concedidas; solo formularios (licencia de obra, DR, ocupación, etc.) y anuncios puntuales en tablón.
- **Planeamiento vigente:** Normas Subsidiarias 1998 + adaptación parcial LOUA (2012); memoria y planos de clasificación / ordenación en PDF en la web.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDE Diputación de Granada — `URBANISMO/DELIMITACION_MUNICIPAL` MapServer capa 2 (`Municipio` = código INE `18175`), query ArcGIS `f=geojson&outSR=4326`.
  - VITUA (Junta de Andalucía) — instrumentos urbanísticos autonómicos sin enlace por expediente del tablón.
  - Callejero municipal — solo localización de calles, sin polígonos de expediente.
- **Estrategia:** consulta ArcGIS por código INE `18175` en `DELIMITACION_MUNICIPAL/2` (probado en investigación). El adapter **no** adjunta polígono: el límite IDE no encaja con el `official_boundary` IGN usado en validación (`outside_municipality_scope`). El orquestador aplica centroide manifest + jitter.
- **Limitaciones:** sin visor urbanístico municipal por expediente; sin geometría por fila en `proyectos.jsonl`; PDFs de planos sin vector público enlazable.

## Limitaciones generales

- Web sin HTTPS en `www.santafe.es` (HTTP).
- Tablón mezcla anuncios no urbanísticos (empleo, elecciones, regantes); filtro por regex en adapter.
- SITUA / VITUA son consulta manual, sin API por expediente del ayuntamiento.
