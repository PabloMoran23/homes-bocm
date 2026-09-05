# Albaida del Aljarafe — investigación portal ayuntamiento

Municipio: **Albaida del Aljarafe** (`albaida-del-aljarafe`), provincia Sevilla, Andalucía. Boletín: BOJA (1 entrada). INE: **41003**. CIF: **P4100300E**.

## URLs base y páginas semilla

| Fuente | URL | Tipo |
|--------|-----|------|
| Web municipal | https://www.albaidadelaljarafe.es | OpenCMS INPRO (theme4) |
| Sede electrónica | https://albaidadelaljarafe.sedelectronica.es | espublico gestiona |
| Tablón sede | https://albaidadelaljarafe.sedelectronica.es/board | Tablón edictos (HTML tabla) |
| Transparencia | https://albaidadelaljarafe.sedelectronica.es/transparency | Árbol Wicket (123 docs urbanismo) |
| PGOM aprobación inicial | https://albaidadelaljarafe.sedelectronica.es/transparency/fa19010b-6c57-4d97-abdb-42d0229b8c63/ | 10 PDFs preview-document |
| Ordenanzas (transparencia) | https://albaidadelaljarafe.sedelectronica.es/transparency/dcd13aaa-0b2b-47c5-9626-0e58a9590220/ | Subcarpetas AJAX (23 ordenanzas reguladoras) |
| Ordenanzas web | https://www.albaidadelaljarafe.es/es/ayuntamiento/ordenanzas-municipales/ | Enlace a transparencia |
| Tablón Diputación Sevilla | https://portal.dipusevilla.es/tablon-1.0/do/entradaPublica?ine=41003 | INPRO tablón provincial (vacío al scrape) |
| Licencias Diputación | https://portal.dipusevilla.es/LicytalPub/jsp/pub/index.faces?cif=P4100300E | Portal provincial LicytalPub |
| SITUA / VITUA | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Planeamiento Andalucía (PGOM en tramitación) |
| P.I.C. | https://www.albaidadelaljarafe.es/es/ayuntamiento/punto-de-informacion-catastral/ | Trámite informativo |

## Expedientes / proyectos

1. **Transparencia sede — PGOM:** Carpeta `fa19010b-…` con certificado de aprobación inicial (Pleno 3-abr-2025), memoria, normas urbanísticas y anexos. Enlaces `preview-document/{uuid}` scrapeables en HTML estático.
2. **Transparencia sede — urbanismo (123 docs):** Índice principal con sección «3. URBANISMO»; subcarpetas cargadas vía AJAX Wicket (no todas expuestas en HTML inicial). Seeds conocidas: PGOM + ordenanzas.
3. **Tablón sede (`/board`):** ~9 edictos recientes; mayoría administrativos (cobranza IBI, personal). Sin planeamiento urbanístico en el listado actual.
4. **Tablón Diputación (INE 41003):** Activo pero sin filas en el listado público al momento del scrape.
5. **Consulta expedientes sede:** Requiere identificación (`/expedientes`); no hay listado público de expedientes individuales.

## Licencias de obra

- **Sin listado histórico** de licencias concedidas en el portal municipal.
- Trámites vía sede (`/dossier`); licencias y comunicaciones previas requieren identificación.
- Portal **LicytalPub** Diputación Sevilla (CIF P4100300F) como consulta provincial.
- Tablón sede puede publicar edictos de licencia; ninguno urbanístico en el scrape actual.
- Adapter devuelve páginas informativas (tablón, trámites, LicytalPub, PIC) + edictos del tablón filtrados.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - SITUA/VITUA Junta de Andalucía: PGOM en tramitación (aprobación inicial abr-2025); documentación raster/PDF, sin WFS/ArcGIS REST enlazable por código de expediente.
  - Transparencia sede: PDFs de planeamiento sin coordenadas embebidas.
  - Web OpenCMS: sin visor urbanístico ni datos abiertos GIS.
  - Tablón Diputación / sede: solo PDFs administrativos.
- **Estrategia:** No aplicable; orquestador usará centroide municipio + jitter.
- **Limitaciones:** Sin capa vectorial pública por expediente; PGOM reciente solo en PDF; subcarpetas transparencia parcialmente behind AJAX.

## Limitaciones técnicas

- Sede espublico gestiona (patrón Tomares/Almensilla Sevilla).
- Web OpenCMS INPRO compartida con otros ayuntamientos diputación.
- `insecure_ssl: true` en sede (certificado gestiona; patrón adapters Sevilla).
- Transparencia: documentos en subcarpetas con UUID; algunas ramas solo vía Wicket AJAX.
- Tablón Diputación vacío no bloquea ingesta (PGOM transparencia aporta ≥10 proyectos).
