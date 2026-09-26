# Algarrobo — investigación portal ayuntamiento

**Municipio:** Algarrobo (Málaga, Andalucía)  
**Slug:** `algarrobo`  
**Boletín:** BOJA (`boja`, 2 entradas en histórico)  
**Código INE:** 29007

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.algarrobo.es | **Operativa** — Joomla 4 + Helix Ultimate (Hostinger/Cloudflare) |
| Urbanismo | https://www.algarrobo.es/index.php/ayuntamiento/urbanismo | **Operativa** — categoría con 4 artículos + RSS |
| RSS urbanismo | https://www.algarrobo.es/index.php/ayuntamiento/urbanismo?format=feed&type=rss | **Operativa** — 4 ítems |
| Sede electrónica | https://algarrobo.sedelectronica.es | **Operativa** — espublico gestiona (requiere `insecure_ssl` en CI) |
| Tablón de anuncios | https://algarrobo.sedelectronica.es/board/ | **Operativa** — tabla HTML con preview-document |
| Portal transparencia | https://algarrobo.sedelectronica.es/transparency | **Operativa** — árbol Wicket AJAX; solo docs visibles en HTML inicial |
| Catálogo trámites | https://algarrobo.sedelectronica.es/dossier | Redirige a `/dossier.0` |
| Consulta expedientes | https://algarrobo.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |

## Web municipal (Joomla)

- **CMS:** Joomla 4 con plantilla Helix Ultimate (`templates/indigo`).
- **Urbanismo:** listado de artículos en categoría con enlaces a PDFs en `/images/docs/Urbanismo/`.
- **Artículos encontrados (RSS jun 2025):**
  1. Normas Subsidiarias — Adaptación a la LOUA (memoria + 14 planos PDF)
  2. Normas Subsidiarias — Texto Refundido (RAR documentación + planos)
  3. Plan Municipal de Vivienda y Suelo (PMVS 2019: memoria, reglamento, planos…)
  4. Archivo histórico catastral (ZIP rústica/urbana)
- **Listado:** HTML tabla Joomla + feed RSS/Atom.

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Cómpeta, Coín, Lepe.
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}`.
- **Paginación:** botón «Mostrar más» vía Wicket AJAX; el adapter parsea la primera página (~8 filas).

### Ejemplos urbanísticos encontrados (ago 2026)

| Fecha | Procedimiento | Categoría | Descripción |
|-------|---------------|-----------|-------------|
| 07/08/2026 | Actuaciones Urbanísticas | Urbanismo | Proyecto de actuación extraordinaria en suelo rústico (exp. 462/2026) |

## Portal de transparencia

- Sección **7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE** (16 documentos según contador).
- Navegación por Wicket AJAX; sin API REST pública.
- En HTML inicial: documentos recientes con `preview-document` (p. ej. calificación ambiental en exposición pública).

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Trámites vía sede electrónica (`/dossier`) y consulta de expedientes autenticada.
- Las licencias concedidas publicadas aparecen en el tablón como edictos (cuando existan).
- El adapter incluye páginas informativas de sede (tablón, trámites, consulta expedientes).

## Proyectos / planeamiento

- **Web Joomla:** NNSS, PMVS, documentación catastral histórica (PDFs/ZIP).
- **Tablón:** actuaciones urbanísticas y anuncios de información pública.
- **Transparencia:** calificación ambiental y documentación urbanística (parcial, vía HTML inicial).
- **SITUA:** visor regional Junta de Andalucía para consulta de planeamiento aprobado.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - SITUA/Situadifusión (Junta de Andalucía): https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf — visor regional de planeamiento; sin WFS/REST enlazable por código de expediente del ayuntamiento.
  - PRP Málaga / Diputación: visores cartográficos provinciales; sin API REST accesible desde CI.
  - PDFs de planos en web municipal (NNSS, PMVS): sin georreferencia embebida ni servicio GIS municipal.
- **Estrategia:** los documentos publicados son PDF/ZIP sin coordenadas. No hay visor urbanístico municipal con query por expediente.
- **Limitaciones:**
  - Sin WFS/GeoJSON por código de expediente.
  - Transparencia con carga AJAX (solo documentos visibles en primera carga).
  - El orquestador aplicará centroide municipio + jitter para coordenadas.

## Limitaciones generales

- Tablón paginado con AJAX Wicket (solo primera página en adapter).
- Sede requiere `insecure_ssl: true` en algunos entornos CI.
- Sin geometría por expediente.
- Consulta de expedientes requiere login.

## Adapter implementado

- `municipio.adapters.algarrobo:AlgarroboAyuntamientoAdapter`
- Fuentes: RSS urbanismo Joomla + PDFs, tablón sede, transparencia (parcial), metadato SITUA.
