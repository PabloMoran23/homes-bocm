# Baeza — investigación portal ayuntamiento

**Municipio:** Baeza (Jaén, Andalucía)  
**Slug:** `baeza`  
**Boletín:** BOJA (`boja`, 6 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.baeza.net | **Operativa** — WordPress + Yoast; REST API bloqueada (Kadence Security) |
| Urbanismo (web) | https://www.baeza.net/urbanismo/ | Noticias de obras/urbanismo; sin listado de expedientes |
| Plan especial / PEPRI | https://www.baeza.net/el-ayuntamiento-auto/plan-especial-de-proteccion-reforma-interior-y-mejora-urbana/ | PDFs catálogo y planos (duplican transparencia) |
| Portal transparencia | https://transparencia.baeza.net | **Operativa** — ATM2 Informática (ASP.NET) |
| Registro IOU | https://transparencia.baeza.net/transparencia/registro-de-instrumentos-de-ordenacion-urbanistica | PEPRI, PGOU, información pública, convenios |
| PGOU (SITUA) | https://transparencia.baeza.net/.../plan-general-de-ordenacion-urbana--pgou- | Iframe a SITUADIFUSION Junta de Andalucía |
| SITUADIFUSION | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Planeamiento digitalizado regional (Jaén → Baeza) |
| Sede electrónica | https://baeza.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón sede | https://baeza.sedelectronica.es/board/ | ~10 filas; mayoría personal/normativa no urbanística |
| Sede legacy | https://sede.baeza.net/PortalCiudadano/Tablon/wfrTablon.aspx | Portal antiguo; respuesta mínima en CI |
| Catálogo trámites | Transparencia → relación ciudadana → catálogo procedimientos | Licencias apertura, cambio titularidad, urbanismo |

## Registro de instrumentos de ordenación urbanística

- **CMS:** Portal transparencia ATM2 (menú vertical + páginas con `tituloPagina` + PDF en `/Temporal/{uuid}.pdf`).
- **Secciones:**
  - Información pública
  - Protección del patrimonio (PEPRI: catálogos, planos I–IX, ordenanzas)
  - Planes de ordenación urbana → PGOU vía iframe SITUADIFUSION
  - Convenios urbanísticos
  - Consultas públicas previas
- **Expediente PGOU local:** `URB/PLAN/1/2023` con documentos indexados (ej. planos PGOU 97 clasificación suelo, usos La Yedra, alineaciones). URLs slug `expediente-urb_plan_1_2023---{n}-...` no aparecen en sitemap; descubrimiento parcial vía seeds.
- **Búsqueda:** Google CSE embebido en portal transparencia.

## Tablón de anuncios (espublico gestiona)

- Misma estructura que Cómpeta/Móstoles: `class_name`, `class_folderCode`, `class_folderName`, etc.
- En agosto 2026: anuncios de normativa (circulación), personal; sin licencias de obra recientes en primera página.

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Trámites documentados en catálogo transparencia: licencia primera utilización locales, cambio titularidad licencias apertura, actividades extraordinarias.
- Adapter incluye páginas informativas de trámites (sin filas de concesión histórica).

## Proyectos / planeamiento

| Origen | Contenido |
|--------|-----------|
| Transparencia PEPRI | Catálogos y planos centro histórico (PDF Temporal) |
| Transparencia PGOU | Expediente URB/PLAN/1/2023 (planos PGOU 97) |
| SITUADIFUSION | PGOU Baeza aprobado 1997 (visor regional) |
| Web municipal | PDFs PEPRI en plan especial; noticias urbanismo |
| Tablón sede | Filtrado urbanístico cuando aparece |

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - SITUADIFUSION / VITUA (Junta de Andalucía): planeamiento escaneado; sin API REST enlazable por expediente del ayuntamiento.
  - DERA IDEAndalucía (WFS sistema urbano, usos suelo): cartografía regional; sin capa de ámbitos de expediente municipal.
  - PGOU y PEPRI: PDFs/planos sin georreferencia embebida en portal.
- **Estrategia:** no hay visor municipal ArcGIS ni WFS con campo expediente. El orquestador aplicará centroide municipio + jitter.
- **Limitaciones:** expedientes PGOU hijos no listados en sitemap (solo indexación parcial); SITUADIFUSION requiere selección interactiva de municipio.

## Limitaciones generales

- REST API WordPress bloqueada (`itsec_rest_api_access_restricted`).
- Expedientes PGOU locales: grid/árbol no expuesto en HTML estático del sitemap.
- Tablón sede sin licencias urbanísticas recientes.
- `baeza.net` sin `/sede-electronica/` (404); sede en subdominio espublico.

## Adapter implementado

- `municipio.adapters.baeza:BaezaAyuntamientoAdapter`
- Fuentes: crawl transparencia registro IOU + seeds PGOU + web PDFs/noticias + tablón sede + trámites informativos.
