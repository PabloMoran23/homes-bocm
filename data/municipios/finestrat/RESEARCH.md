# Finestrat — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Municipio | Finestrat (Alicante, Comunitat Valenciana) |
| INE | 03054 |
| Población | ~7.500 hab. (casco + Cala de Finestrat) |
| CMS sede | espublico gestiona (Wicket) |
| Web municipal | ayto-finestrat.es (protección anti-bot / CDN) |

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Sede electrónica | https://finestrat.sedelectronica.es | Portal principal (redirect /info) |
| Tablón de anuncios | https://finestrat.sedelectronica.es/board | Edictos y notificaciones (HTML tabla Wicket) |
| Transparencia | https://finestrat.sedelectronica.es/transparency | Índice por secciones; **sección 7** = Urbanismo (162 docs) |
| Consulta expedientes | https://finestrat.sedelectronica.es/expedientes | Requiere identificación |
| Catálogo trámites | https://finestrat.sedelectronica.es/dossier | Trámites telemáticos (redirect) |
| Web urbanismo | https://ayto-finestrat.es/areas-y-servicios/urbanismo/ | Licencias, planeamiento, cita previa |
| Planos ordenación | https://ayto-finestrat.es/download/planos-ordenacion/ | PP-5, documento consultivo (PDFs) |
| Registro GVA | https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/2%20ALICANTE/03054%20FINESTRAT | Ficha planeamiento Conselleria |

## Cómo se listan expedientes

### Tablón de anuncios (`/board`)

- HTML estático con filas `<tr><td class="class_name">…</td>…</tr>`.
- Campos: documento, expediente (`class_folderCode`), procedimiento, categoría, fecha, enlace `preview-document/{uuid}`.
- En la investigación (sep 2026) predominan edictos de padrón (PMH); sin entradas urbanísticas activas, pero el scrape es determinista cuando aparecen.

### Transparencia (`/transparency`)

- Árbol jerárquico Wicket/AJAX. Sección **«7. URBANISME, OBRES PÚBLIQUES I MEDI AMBIENT»** con 162 documentos.
- Los subdocumentos no son accesibles sin sesión Wicket completa desde CI; el adapter indexa la sección y parsea `preview-document` si aparecen en HTML plano.

### Web municipal (`ayto-finestrat.es`)

- WordPress con protección anti-bot (challenge JS) desde el entorno del agente.
- Contenido conocido (vía búsqueda y caché): Normas Subsidiarias 1989, Plan Parcial PP-5 (mod. AD 2014), redacción PGE (consulta pública nov 2025).
- Seeds estáticos en el adapter para estos instrumentos.

### Licencias

- No hay dataset público de concesiones históricas.
- Trámites vía sede (`/dossier`) y presencial (cita 965 878 100).
- El adapter devuelve páginas informativas de trámites (patrón Pozuelo/Tomares).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes investigadas:**
  - ICV GVA WFS `https://terramapas.icv.gva.es/0702_Planeamiento` (`Planeamiento.Zonificacion`): sin features para `cod_ine_mun=03054` (escaneo 15k registros).
  - No hay visor urbanístico municipal propio (p. ej. ArcGIS/Geoportal como Calp o Alfafar).
  - Planos PP-5 en PDF sin georreferencia enlazable a expediente.
- **Estrategia:** el orquestador aplicará centroide municipal (`manifest.centroid`) + jitter vía `geocode`.
- **Limitaciones:** municipio regido por Normas Subsidiarias sin PGOU aprobado; PGE en tramitación. Sin API GIS pública.

## Limitaciones

- Web `ayto-finestrat.es` y `finestrat.es` (HTTPS) inaccesibles desde CI (anti-bot / timeout).
- Transparencia urbanismo requiere AJAX Wicket; solo índice scrapeable de forma fiable.
- Tablón sin licencias/urbanismo en el momento de la investigación.
- SSL sede: `insecure_ssl: true` (certificado gestionado por espublico).

## Datos BOCM

- 1 entrada DOGV (`boletin_source_id: dogv`) — ya en pipeline regional; no re-parseado.
