# Los Molinos — investigación portal ayuntamiento

Municipio: **Los Molinos** (`los-molinos`) — Comunidad de Madrid  
Investigación: 2026-07-09

## URLs base y páginas semilla

| Recurso | URL | CMS / formato |
|---------|-----|---------------|
| Web institucional | https://www.ayuntamiento-losmolinos.es | WordPress (Pressville) |
| Urbanismo | https://www.ayuntamiento-losmolinos.es/?page_id=36668 | WP: PDFs PGOU, normas, formularios licencias |
| Sede electrónica | https://sede.ayuntamiento-losmolinos.es/eAdmin/Sede.do | eAdmin (add4u) |
| Tablón de anuncios | https://sede.ayuntamiento-losmolinos.es/eAdmin/Tablon.do?action=verAnuncios | HTML tabla + `abrirOriginal(token)` |
| Catálogo trámites | https://sede.ayuntamiento-losmolinos.es/eAdmin/Registrar.do?action=listadoEntradas | Modales `modalInformacion{id}` |
| Transparencia | https://transparencia.ayuntamiento-losmolinos.es | WordPress |
| Planeamiento (transp.) | https://transparencia.ayuntamiento-losmolinos.es/?page_id=185 | `javascript:abrir('code')` → ValidarDocumento.do |
| Tributos | https://tributoslosmolinos.eadministracion.es | eAdministración (no urbanismo) |

**Nota:** `www.losmolinos.es` y `losmolinos.org` son dominios ajenos (bodega / parking).  
**Nota:** `losmolinos.sedelectronica.es` (espublico) tiene tablón **deshabilitado**; la sede activa es `sede.ayuntamiento-losmolinos.es`.

## Expedientes / planeamiento

### Tablón digital (sede eAdmin)

- Listado HTML con columnas: documento, periodo exposición.
- Enlaces detalle: `Tablon.do?action=verAnuncio&id={HEX}`.
- PDFs embebidos vía `javascript:abrirOriginal('{token}')` → `ValidarDocumento.do?id_Documento=...`.
- Contenido urbanístico relevante (jun 2026): **Avance Plan General** (6 bloques + índice + anuncio BOCM), ORCC 17/2026 y 26/2026.
- Búsqueda POST `referenciaBusqueda` sobre el mismo endpoint.

### WordPress urbanismo

- ~30 PDFs estáticos en `/wp-content/uploads/2017/12/`: PGOU (5 tomos), planos P1–P54, normas subsidiarias 1991, memoria, estudio económico-financiero, formularios licencia/comunicación previa.
- Sin REST API pública (`/wp-json/` → 404).

### Transparencia planeamiento

- `page_id=185`: documentos con `abrir('{code}')` (p. ej. estudio de detalle Finca La Cerca).
- Sección padre `page_id=17` (Urbanismo y Medio Ambiente) enlaza a planeamiento y medio ambiente.

## Licencias de obra

- **No hay dataset público** de concesiones con dirección/coords.
- Formularios informativos en web urbanismo (obra mayor, comunicación previa, licencia primera ocupación).
- Catálogo sede: trámites 34 (obra menor), 35 (obra mayor), 36–37 (actividades DR), 51 (plusvalía).
- Tablón: sin licencias de obra individuales publicadas en el periodo actual; ORCC son ordenanzas regulatorias.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - SITCM WFS Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows` capa `sitcm:VPLA_V_AMBITO`, `DS_MUNICIPIO='LOS MOLINOS'`.
  - 12 ámbitos: UA-01 La Cerquilla, UA-02 Cerca de En Medio, UA-03 Matadero, UA-05/06/07/08, U-A04 Molino de la Cruz Norte, SAU-01.N/01.S/02.S/03.S.
  - Sin visor urbanístico municipal (ArcGIS/GeoJSON) enlazado a expedientes.
  - Catastro: enlace informativo a sedecatastro.gob.es (sin geometría automatizable).
- **Estrategia:** el orquestador `enrich_geometry` consulta SITCM por tokens UA/UE en título; sin match → centroide municipio + jitter en `geocode`.
- **Limitaciones:** PDFs del tablón y PGOU sin georreferencia; títulos del avance PGOU no incluyen código de ámbito explícito → baja tasa de match SITCM.

## Limitaciones técnicas

- Certificado TLS inválido en `*.ayuntamiento-losmolinos.es` → `insecure_ssl: true`.
- Sede codificación `iso-8859-1`.
- `losmolinos.sedelectronica.es/board/` deshabilitado (no usar).
- WP REST API deshabilitada en web y transparencia.
