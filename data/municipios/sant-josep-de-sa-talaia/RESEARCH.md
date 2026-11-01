# Sant Josep de sa Talaia — investigación portal ayuntamiento

Municipio: **Sant Josep de sa Talaia** (`sant-josep-de-sa-talaia`) — Illes Balears, Eivissa. INE **07046**. Sin boletín regional asociado en cola.

## URLs base

| Recurso | URL |
|---------|-----|
| Web municipal (WordPress) | https://www.santjosep.org |
| Urbanisme (NNSS, plànols) | https://www.santjosep.org/el-teu-municipi/urbanisme/ |
| Tràmits urbanisme | https://www.santjosep.org/tramits-gestions/urbanisme/ |
| Sede electrónica (espublico gestiona) | https://santjosep.sedelectronica.es |
| Tablón de anuncios | https://santjosep.sedelectronica.es/board |
| Transparencia (sección 7 Urbanismo) | https://santjosep.sedelectronica.es/transparency |
| MUIB — Mapa Urbanístic Illes Balears | http://muib.caib.es/mapurbibfront/visor_index.jsp |
| Plan Territorial Insular (enlace web) | https://www.santjosep.org/el-teu-municipi/urbanisme/ (PTI) |

## Cómo se listan expedientes

### Web WordPress (`/el-teu-municipi/urbanisme/`)

Contenido estático con enlaces a PDF:

- Text refós NNSS 1986 (BOIB)
- Modificacions puntuals 1–7 (PDF en `wp-content/uploads`)
- **Plànols de determinacions en sòl urbà** — 26 PDF por núcleos (Sant Jordi, Cala Tarida, Port des Torrent, etc.)
- Ordenances de llicències i residus de construcció

API REST usable: `GET /wp-json/wp/v2/pages/1467` (CA) y `/es/tu-municipio/urbanismo/` (ES).

### Tablón sede (espublico / Wicket)

HTML en `/board` con filas `<tr><td class="class_name">…`. Campos: documento, expediente (`class_folderCode`), procedimiento (`class_folderName`), categoría, descripción, fecha (`class_dateFrom` DD/MM/YYYY), enlace `preview-document/{uuid}`.

En la muestra (nov 2026) predominan anuncios de padrón y convocatorias de pleno; los anuncios de urbanismo son esporádicos.

### Tràmits (páginas informativas)

`/tramits-gestions/urbanisme/` lista bloques con enlaces relativos: comunicación previa, certificados, segregación, demolición, licencia obra mayor (sin dataset de concesiones).

### Transparencia sede

Bloque **«7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE»** (37 documentos) vía navegación Wicket/AJAX; no hay listado JSON público estable.

## Licencias de obra

No hay registro abierto tipo GeoJSON de licencias concedidas. Fuentes:

1. Páginas informativas de trámites (comunicación previa, obra major, etc.)
2. Tablón (anuncios puntuales)
3. Ordenança reguladora de llicències (PDF)

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - MUIB (`muib.caib.es`) — visor insular; backend ArcGIS `ideib.caib.es/pub_ideib` referenciado en el visor
  - Plànols PDF por núcleo en la web municipal (sin georreferencia machine-readable)
  - No hay capa WFS municipal tipo IDELMA Mallorca (`M046_URBANISME`) ni capa CIME enlazada a expedientes de Sant Josep accesible desde este entorno
- **Estrategia:** documentación PDF + enlace MUIB; el orquestador aplicará centroide municipal + jitter
- **Limitaciones:**
  - `ideib.caib.es` responde **403** desde el entorno cloud del agente (ArcGIS REST no consultable aquí)
  - Delimitaciones solo en PDF cartográfico
  - Tablón y trámites sin geometría embebida

## Limitaciones generales

- WordPress 5.6 + WPML (CA/ES)
- Sede espublico estable; SSL OK
- Sin visor municipal propio; dependencia del MUIB insular
- Proyectos de costa (Badia de Portmany) enlazados a portal externo `illessostenibles.travel`
