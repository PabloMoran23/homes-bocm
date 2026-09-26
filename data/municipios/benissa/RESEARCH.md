# Benissa — investigación portal ayuntamiento

Municipio: **Benissa** (`benissa`) — Alicante, Comunitat Valenciana. INE `03018`. Boletín: DOGV.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal (WordPress, turismo) | https://www.benissa.es/ |
| Sede electrónica (espublico gestiona) | https://benissa.sedelectronica.es/ |
| Tablón de anuncios | https://benissa.sedelectronica.es/board |
| Portal transparencia | https://benissa.sedelectronica.es/transparency |
| Catálogo trámites | https://benissa.sedelectronica.es/dossier |
| Consulta expedientes | https://benissa.sedelectronica.es/expedientes |
| ICV GVA visor | https://visor.gva.es/visor/?idioma=es |

## Expedientes / planeamiento

- **Sede transparencia (espublico):** carpeta «7. URBANISME, OBRES PÚBLIQUES I MEDI AMBIENT» con **328 documentos** (planeamiento, obras, medio ambiente). Navegación vía Wicket AJAX (sin URL UUID estática en HTML); no se listan `preview-document` en la página raíz.
- **Tablón /board:** tabla Wicket espublico (~10 anuncios visibles; en la muestra actual predominan derechos funerarios y empleo público, sin urbanismo reciente).
- **Web benissa.es:** WordPress orientado a turismo; sin sección pública de urbanismo ni REST API con documentos de planeamiento.
- **Consulta expedientes:** requiere identificación en sede.

## Licencias

- No hay dataset público de licencias concedidas con coordenadas.
- El tablón puede publicar licencias de obra/actividad cuando hay edictos; histórico no paginable sin simular Wicket AJAX.
- Trámites de licencia vía sede (`/dossier`); sin listado histórico scrapeable.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV GVA WFS: `https://terramapas.icv.gva.es/0702_Planeamiento` — capa `Planeamiento.Zonificacion`, filtro `cod_ine_mun=03018` (~42 polígonos). Salida GML3 → GeoJSON WGS84.
  - InventarioSuSuz (ICV): **0** features para Benissa.
  - Transparencia sede: documentos PDF sin enlace GIS directo.
- **Estrategia:** agrupar polígonos WFS por `denominaci` + `expediente` (3 planes: PGOU «Plan general», PP Sector RS 8 Bellas Artes, Homologación PP Sector Mascarat); enriquecer filas del tablón/transparencia por keywords.
- **Limitaciones:** zonificación municipal agregada (no delimitación por expediente de información pública); transparencia con 328 docs no scrapeable sin AJAX Wicket; licencias sin georef; web corporativa sin urbanismo.

## Limitaciones generales

- Sede espublico: `insecure_ssl: true` por consistencia con otros adapters espublico de la CV.
- Tablón: solo primera página HTML.
- Sin re-parse DOGV en este adapter.
