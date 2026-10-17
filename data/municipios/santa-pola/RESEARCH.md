# Santa Pola — investigación portal ayuntamiento

**Municipio:** Santa Pola (Alicante / Alacant, Comunitat Valenciana)  
**Slug:** `santa-pola`  
**INE:** `03122`  
**Boletín:** DOGV (`dogv`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://santapola.es | Operativa — WordPress (Divi) |
| Urbanismo | https://santapola.es/areas-municipales/urbanismo/ | Operativa — PDFs PG, sectores, estudios de detalle, trámites |
| Sede electrónica | https://santapola.sedelectronica.es | Operativa — espublico gestiona / eHome (Wicket) |
| Tablón de anuncios | https://santapola.sedelectronica.es/board | Operativa — tabla HTML (~10 filas oct 2026) |
| Catálogo trámites | https://santapola.sedelectronica.es/dossier | Urbanismo: licencia urbanística, DR obras, etc. |
| Consulta expedientes | https://santapola.sedelectronica.es/expedientes | Requiere identificación electrónica |
| Portal transparencia sede | https://santapola.sedelectronica.es/transparency | Operativa — carpetas LGT |
| Reg. planeamiento GVA | https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/4%20VALENCIA/03122%20SANTA%20POLA/ | Índice instrumentos (timeouts SSL frecuentes desde CI) |
| Visor cartografía GVA | https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion | Referencia ICV |
| Datos abiertos GVA | https://dadesobertes.gva.es/dataset/planeamiento-urbanistico-de-la-comunitat-valenciana-zonificacion-urbanistica | WFS/WMS zonificación CV |

## Cómo se listan expedientes / proyectos

| Tipo | Mecanismo | Formato |
|------|-----------|---------|
| Planeamiento / IP | Web `/urbanismo/` | HTML + enlaces PDF (`wp-content/uploads/...`) |
| Instrumentos oficiales | Registro planeamiento GVA | Índice carpetas + PDFs |
| Zonificación | ICV WFS `Planeamiento.Zonificacion` | GeoJSON (`CQL_FILTER cod_ine_mun='03122'`) |
| Anuncios / IP | Tablón sede `/board` | HTML tabla Wicket + `preview-document/{uuid}` |
| Transparencia | Sede `/transparency` | Wicket AJAX |

**No hay** API JSON de expedientes ni visor urbanístico municipal propio con enlace a expediente.

### PDFs destacados (urbanismo, 2025–2026)

| Título | URL |
|--------|-----|
| Registro urbanístico 2025 | https://santapola.es/wp-content/uploads/2025/11/Registro-urbanistico-2025.pdf |
| Sector 3 CJ5 — PAI | https://santapola.es/wp-content/uploads/2025/04/Sector3-CJ5-PAI.pdf |
| Polígono 5.1 Gran Alacant — estudio de detalle | https://santapola.es/wp-content/uploads/2026/07/Poligono-5.1-de-Gran-Alacant-Estudio-de-detalle_Anonimizado.pdf |
| Equipamiento deportivo — estudio de detalle | https://santapola.es/wp-content/uploads/2025/11/Estudio-de-detalle-sobre-Parcela-de-Equipamiento-Deportivo_Censurado.pdf |
| Plan reforma interior Barranco Catarra | https://santapola.es/wp-content/uploads/2024/02/Plan-de-Reforma-Interior-Barranco-Catarra.pdf |
| Ordenanzas edificación y uso del suelo | https://santapola.es/wp-content/uploads/bsk-pdf-manager/2021/01/Ordenanzas-Municipales-de-la-edificacion-y-uso-del-suelo_BOP_2_5-01-2021.pdf |

## Cómo se publican licencias

- **Tablón sede** (`/board`): edictos estándar espublico; en oct 2026 predominan anuncios no urbanísticos (empleo, cultura). Licencias urbanísticas aparecen de forma esporádica.
- **Trámites sede** (sin histórico de concesiones):
  - [Solicitud de Licencia Urbanística](https://santapola.sedelectronica.es/catalog/t/c81fa8bc-8484-4fd8-a633-57533fde9f63)
  - [Declaración Responsable de Obras](https://santapola.sedelectronica.es/catalog/t/14d180ae-cc99-4e7a-9905-faf01fde2a46) (+ PDF en web)
- **Consulta expedientes** requiere login; no hay dataset abierto de licencias con dirección.

## Geometría / visor

- **geometry_status:** `partial`
- **Motivo:** ICV WFS aporta polígonos de zonificación por expediente de planeamiento (PG/PP), pero no geometría de licencias ni expedientes del tablón. Sin visor municipal ArcGIS enlazado a expediente.

### Fuentes GIS

| Servicio | URL / capa | Notas |
|----------|------------|-------|
| ICV WFS | `https://terramapas.icv.gva.es/0702_Planeamiento` | `typeName=Planeamiento.Zonificacion` |
| GeoJSON | `outputFormat=application/json; subtype=geojson`, `srsName=EPSG:4326` | Filtro `cod_ine_mun='03122' AND expediente='…'` |
| Visor GVA | `https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion` | Visualización regional |

### Estrategia adapter

1. Catálogo ICV: expedientes reales `03122` (p. ej. `19950751`, `20041496`, `20050776`, `19950683`, …) como filas de referencia al visor GVA.
2. PDFs web `/urbanismo/` → proyectos; `_match_icv_zone` preparado para cruce por tokens (sector, Gran Alacant, etc.).
3. Tablón → licencias/proyectos urbanos cuando el texto coincide con patrones.

### Limitaciones

- **WFS ICV:** el servicio ignora `CQL_FILTER`; hay que paginar y filtrar por `cod_ine_mun` en cliente. Los polígonos etiquetados `03122` no intersectan el límite municipal IGN usado en validación h03 (p. ej. sectores en Gran Alacant), por lo que el adapter no persiste `geom_geojson` (evita cuarentena).
- Sin coordenadas en tablón ni en PDFs.
- Registro GVA a veces inaccesible por red/SSL desde entornos automatizados.
- Geometría de licencia individual no publicada.
