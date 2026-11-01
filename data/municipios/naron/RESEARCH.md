# Narón — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL | Notas |
|---------|-----|-------|
| Web corporativa | https://www.naron.gal | Bootstrap; PXOM en `/cat/gal/concello/pxom` |
| Sede electrónica | https://sedeelectronica.naron.es | OpenSIAC; consulta expedientes, tablón, catálogo trámites |
| Transparencia | https://transparencia.naron.gal/normativa-urbanistica-y-medio-ambiente/ | WordPress; PDFs BOP y documentos urbanísticos |
| SIOTUGA inventario | https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=15054&lang=es_ES | INE **15054**; token + POST `query_document.php` |
| SIOTUGA estado PXOM | https://siotuga.xunta.gal/siotuga/urb?lang=es_ES | Fila Concello de Narón |

## Expedientes / planeamiento

1. **SIOTUGA (principal):** API JSON con sesión (`token` en HTML + cookies). Clases `13` (desarrollo, ~22), `14` (PXOM, ~7), `16` (histórico, ~9). Campos: `docnome`, `figura`, `fechaaddef`, `fechadog`.
2. **Web PXOM:** listado estático de modificaciones puntuales y planes de sectorización (enlaces a visor Xunta en iframes antiguos).
3. **Transparencia:** enlaces a BOP A Coruña y PDFs locales (PMUS, cambios de uso, acuerdos plenario).
4. **Sede tablón:** `infopublica_search.action` (OpenSIAC). Desde entornos cloud suele **no responder** (timeout ~25 s); el adapter lo intenta y continúa con otras fuentes.
5. **DOG:** convenio urbanístico exp. EDI/2020/1660 (sectorización Río do Pozo), sep. 2025.

## Licencias de obra

- No hay dataset público de licencias concedidas con coordenadas.
- Trámites en catálogo sede (`/opensiac/action/tramites?method=enter`) — misma limitación de red.
- El adapter registra páginas informativas de trámites y cualquier fila del tablón que coincida con licencias/obra.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** SIOTUGA ofrece WMS por documento (`getIotpuWMS.php?codine=15054`) y visor cartográfico autonómico (`siotuga.xunta.gal/siotuga/carto`), pero las capas son por **instrumento de planeamiento**, no por expediente del tablón ni licencia.
- **Estrategia:** metadatos desde SIOTUGA + documentos transparencia; sin join estable expediente → polígono en portal municipal.
- **Limitaciones:** sede inaccesible desde CI; listados son PDF/BOP; visor municipal no expone API GeoJSON enlazable a expedientes.

## Limitaciones técnicas

- Timeout sede `sedeelectronica.naron.es` desde agentes cloud (probar con `sede_timeout_s` bajo).
- Token SIOTUGA ligado a cookie jar (obligatorio reutilizar sesión).
- PXOM en web enlaza a recursos Xunta legacy (`planeamentourbanistico.xunta.es`).
