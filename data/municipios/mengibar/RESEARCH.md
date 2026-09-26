# Mengíbar — investigación portal ayuntamiento

**Municipio:** Mengíbar (Jaén, Andalucía)  
**Slug:** `mengibar`  
**INE:** 23061  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://aytomengibar.com | **Operativa** — WordPress + Yoast; REST API `/wp-json/wp/v2/` accesible |
| PGOM | https://aytomengibar.com/pgom-plan-general-de-ordenacion-municipal-de-mengibar/ | PDFs avance (participación, diagnóstico, cuestionario) |
| Categoría Urbanismo (WP) | `categories=97` (86 posts) | Noticias, expedientes, PGOM, obras urbanas |
| Posts expediente | búsqueda WP `search=expediente` (~90 posts) | Muchos son contratación; filtrados por regex urbanística |
| Sede electrónica | https://aytomengibar.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón sede | https://aytomengibar.sedelectronica.es/board/ | ~10 filas activas; urbanismo intermitente |
| Transparencia sede | https://aytomengibar.sedelectronica.es/transparency | Expediente 1520/2022 (innovación normas subsidiarias) |
| Catálogo trámites | https://aytomengibar.sedelectronica.es/dossier | Timeout frecuente en CI (>30s); trámites vía sede |
| SITUADIFUSION | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=23061 | Planeamiento digitalizado regional |

## Cómo se listan expedientes

| Canal | Formato | Detalle |
|-------|---------|---------|
| WordPress REST | JSON (`/wp-json/wp/v2/posts`) | Categoría 97 + búsquedas `expediente`, `pgom`, `planeamiento` |
| Tablón espublico | HTML tabla (`class_name`, `class_folderCode`, …) | Misma estructura que Vera/Móstoles |
| Transparencia sede | HTML + `preview-document/{uuid}` | Documentos de información pública (exp. 1520/2022) |
| PGOM web | HTML + PDFs en `/wp-content/uploads/pgom/` | Avance PGOM en tramitación |
| Consulta expedientes | `/expedientes` | Requiere identificación Cl@ve; sin listado público |

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- El tablón publica licencias/actuaciones urbanísticas de forma intermitente (ej. área de servicio A-44, exp. 464/2024).
- Trámites de licencia vía sede (`/dossier`); sin histórico descargable.
- Adapter incluye páginas informativas de trámites (patrón Pozuelo/Vera).

## Proyectos / planeamiento

| Origen | Contenido |
|--------|-----------|
| WP categoría Urbanismo | Expedientes, PGOM, reordenación tráfico, asfaltado |
| WP posts expediente | Anuncios de contratación y urbanismo (filtrados) |
| PGOM | 4 PDFs avance + consulta pública |
| Transparencia sede | Innovación normas subsidiarias 1520/2022 (2 docs) |
| Tablón sede | Actuaciones urbanísticas cuando activas |
| SITUADIFUSION | Planeamiento general aprobado (visor regional) |

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - SITUADIFUSION / VITUA (Junta de Andalucía): planeamiento escaneado por municipio; sin API REST enlazable por código de expediente.
  - PGOM y expedientes: PDFs y noticias sin polígonos georreferenciados.
  - No hay visor urbanístico municipal (ArcGIS/WFS) en web ni sede.
  - VisualUrb (tercero) referencia proyectos pero no es fuente pública del ayuntamiento.
- **Estrategia:** no hay GIS municipal consultable por expediente. El orquestador aplicará centroide municipio + jitter.
- **Limitaciones:** dossier sede con timeout en CI; tablón sin urbanismo permanente; expedientes WP mezclan contratación y urbanismo.

## Limitaciones generales

- `dossier` sede a veces no responde en <30s (Wicket/YUI).
- Posts WordPress «Expediente N/AAAA» incluyen contratos de obra pública no urbanísticos; filtro por regex.
- Sin listado histórico de licencias concedidas.
- Transparencia sede: solo expedientes publicados activamente (no índice completo IOU).

## Adapter implementado

- `municipio.adapters.mengibar:MengibarAyuntamientoAdapter`
- Fuentes: WP REST (urbanismo + expedientes + PGOM) + tablón sede + transparencia + PDFs PGOM + SITUA metadata.
