# Investigación portal — Pinilla del Valle

Municipio: **Pinilla del Valle** (`pinilla-del-valle`) — Comunidad de Madrid, provincia Madrid.  
BOCM (`bocm`): 8 entradas históricas.

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | http://www.pinilladelvalle.org | WordPress Hello Elementor + HFE |
| Sede electrónica (WP) | http://www.pinilladelvalle.org/sede-electronica/ | Enlaces sede + PDFs ordenanzas BOCM urbanismo |
| Trámites municipales | http://www.pinilladelvalle.org/tramites-municipales/ | Impresos licencia, DR, acto comunicado |
| Sede espublico | https://pinilladelvalle.sedelectronica.es | espublico gestiona (Wicket) |
| Tablón anuncios | https://pinilladelvalle.sedelectronica.es/board | ~5 filas HTML tabla |
| Transparencia | https://pinilladelvalle.sedelectronica.es/transparency | Sección 7 Urbanismo (1 doc BOCM) |
| Mancomunidad | Mancomunidad de Servicios Urbanísticos Sierra Norte de Madrid | Gestión urbanística delegada (PDFs) |

## Cómo se listan expedientes / proyectos

1. **Página sede-electronica (WP)** — PDFs estáticos de ordenanzas urbanísticas publicadas en BOCM (títulos habilitantes, tasas ICO/TH, aprobación definitiva 2022).
2. **Tablón sede** — HTML tabla con `preview-document/{uuid}`; actualmente plenos, bandos fiscales y anuncios genéricos (sin expedientes de planeamiento activos).
3. **Transparencia sede** — 1 documento en «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE»: BOCM-20210422-50.
4. **WordPress REST** — Sin categoría urbanismo; blog orientado a turismo y plenos.

No hay visor urbanístico municipal ni listado estructurado de expedientes en curso.

## Cómo se publican licencias

- **No hay registro público** de licencias concedidas (fecha, tipo, ubicación).
- Trámites informativos en `/tramites-municipales/`: SOLICITUD-LICENCIA.pdf, DECLARACION-RESPONSABLE.pdf, ACTO-COMUNICADO-REVISADO-2.pdf.
- Urbanismo gestionado por Mancomunidad Sierra Norte (mencionado en impresos).
- Tablón podría publicar licencias pero no hay filas urbanísticas en el momento de la investigación.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes consultadas:**
  - WFS SITCM `sitcm:VPLA_V_AMBITO` con `DS_MUNICIPIO='PINILLA DEL VALLE'` → **0 features**
  - Sin visor ArcGIS ni datos abiertos georreferenciados en web municipal
- **Estrategia:** N/A — el orquestador aplicará centroide municipal + jitter
- **Limitaciones:** municipio pequeño sin NNSS digitalizados en SITCM; solo PDFs sin georreferencia; sin enlace expediente→polígono

## Limitaciones generales

- Sede requiere `insecure_ssl` en algunos entornos CI.
- Tablón ~5 filas sin paginación.
- Web municipal HTTP (no HTTPS en dominio principal).
- Sin API de expedientes; scrape determinista sobre HTML/PDF links.
- Mancomunidad externa para tramitación urbanística.

## Referencia adapter

Patrón: `la_hiruela.py` (WP ordenanzas PDF + espublico sede tablón, sin WFS).
