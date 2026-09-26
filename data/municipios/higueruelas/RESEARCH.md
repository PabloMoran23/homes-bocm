# Higueruelas — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `higueruelas` |
| INE | 46129 |
| Provincia | Valencia |
| CCAA | comunitat-valenciana |
| Boletín | DOGV (`dogv`) |

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.higueruelas.es | Intermitente — Drupal (Adaptive Theme); SSL handshake timeout frecuente desde CI |
| Transparencia planeamiento | https://www.higueruelas.es/transparencia/planeamiento-urbanistico | Intermitente — enlace a instrumentos de planeamiento |
| Noticia PGOU | https://www.higueruelas.es/noticia/plan-general-ordenacion-urbana-higueruelas-pgou | Intermitente — PGOU aprobado (jun 2026) |
| Impresos urbanismo | https://www.higueruelas.es/transparencia/descargar-impresos | Intermitente — sección «Trámites Urbanismo» |
| Trámites | https://www.higueruelas.es/transparencia/tramites | Intermitente — enlace a sede electrónica |
| Sede electrónica | https://higueruelas.sedelectronica.es | Operativa — espublico gestiona |
| Tablón de anuncios | https://higueruelas.sedelectronica.es/board/ | Operativa — tabla HTML preview-document |
| Catálogo trámites | https://higueruelas.sedelectronica.es/dossier | Operativa (redirige a dossier.2) |
| Visor GVA | https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion | Operativo (referencia ICV) |
| Datos abiertos GVA | https://dadesobertes.gva.es/dataset/planeamiento-urbanistico-de-la-comunitat-valenciana-zonificacion-urbanistica | Operativo |

## Cómo se listan expedientes

| Tipo | Mecanismo |
|------|-----------|
| Licencias / actividades | Tablón sede — filas HTML con expediente, procedimiento, PDF preview |
| Planeamiento | Transparencia + noticia PGOU; instrumentos en PDF (sin listado estructurado) |
| Trámites | Catálogo sede /dossier (sin histórico público de concesiones) |
| Impresos | Formularios descargables en transparencia (obra mayor/menor, actividades) |

### Tablón sede (enero 2026)

- Único anuncio visible: resolución alcalde requisitos empadronamiento (exp. 7/2026) — no urbanístico.

## Cómo se publican licencias

- Edictos de licencias y actividades en tablón sede (`preview-document/...`) cuando se publican.
- Sin dataset histórico de concesiones con coordenadas.
- Formularios de licencias en transparencia → descargar impresos → Trámites Urbanismo.
- Trámites vía sede (catálogo dossier).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - ICV WFS: `https://terramapas.icv.gva.es/0702_Planeamiento`
  - TypeName: `Planeamiento.Zonificacion`
  - Filtro municipio: `cod_ine_mun=46129` — **0 polígonos** (PGOU recién aprobado, no publicado aún en ICV)
  - Visor GVA: referencia cartográfica regional (sin capa municipal individual)
- **Estrategia:** adapter consulta WFS paginado; cuando ICV publique zonificación, se enriquecerá automáticamente. Mientras tanto, orquestador usa centroide + jitter.
- **Limitaciones:**
  - PGOU disponible como PDF/noticia web, sin geometría vectorial pública
  - Web municipal con SSL intermitente (timeouts >60s); sede estable
  - Tablón sin anuncios urbanísticos recientes
  - Sin visor municipal propio identificado

## Limitaciones generales

- Web corporativa: handshake SSL timeout frecuente desde agente CI (requiere reintentos)
- Sede: certificado SSL caducado (`insecure_ssl: true`)
- Tablón: paginación Wicket (~1 fila visible en scrape estático)
- Escaneo ICV WFS completo ~2 min; sin resultados para 46129
- Provincia en `queue.yaml` incorrecta (`Higueruelas`); manifest usa `Valencia`

## Adapter implementado

- `municipio/adapters/higueruelas.py` — `HigueruelasAyuntamientoAdapter`
- Fuentes: sede tablón + dossier, transparencia web (con reintentos), ICV WFS (vacío), páginas informativas PGOU
