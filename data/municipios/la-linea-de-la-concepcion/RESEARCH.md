# La Línea de la Concepción — investigación portal ayuntamiento

**Municipio:** La Línea de la Concepción (Cádiz, Andalucía)  
**Slug:** `la-linea-de-la-concepcion`  
**Boletín:** BOJA (`boja`, 5 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://lalinea.es | **Operativa** — WordPress + Elementor |
| Urbanismo | https://lalinea.es/areas/economia-hacienda-y-gestion-interna/urbanismo/ | PGOU provisional/inicial, PDFs y ZIPs |
| Instrumentos planeamiento | https://lalinea.es/instrumentos-de-planeamiento-urbanistico/ | PGOU 1985, catálogo protección |
| PGOU revisión | https://lalinea.es/plan-general-de-ordenacion-urbanistica/ | Documentación aprobación inicial/provisional |
| Sede electrónica | https://www.sedeelectronica.lalinea.es | **Operativa** — Liferay (EPICSA/Diputación Cádiz) |
| Tablón edictos | https://www.sedeelectronica.lalinea.es/edictos/publico?idOrgan=23 | **Operativa** — tabla HTML Struts (~54 edictos) |
| Trámites | https://www.sedeelectronica.lalinea.es/tramites-disponibles | Catálogo procedimientos (sin listado licencias histórico) |
| Transparencia | https://gobiernoabierto.dipucadiz.es/catalogo-de-informacion-publica?entidadId=10801 | Portal Diputación Cádiz |
| GIS municipal | https://lalinea.fisotec.es | **No accesible** desde CI (sin respuesta HTTP) |

## Web municipal (WordPress Elementor)

- **CMS:** WordPress 6.x + Elementor Pro.
- **Urbanismo:** documentación PGOU en `/recursos/Urbanismo web/` (PDFs firmados, ZIPs por tomo).
- **Enlaces semilla:** urbanismo, instrumentos de planeamiento, PGOU revisión.
- **Formato:** enlaces directos a PDF/ZIP; sin API REST de expedientes.

### Documentos PGOU encontrados

- Revisión PGOU: memorias, planos (series 01–04), normas, EAE, catálogo protección (aprobación inicial 2019 y provisional 2021).
- PGOU 1985: tomos y planos de unidades urbanísticas, clasificación suelo, usos globales.
- Catálogo de protección (anuncio BOP).

## Tablón de edictos (sede Diputación Cádiz)

- **CMS:** aplicación Struts `/edictos/` integrada en sede Liferay.
- **Entrada pública:** `idOrgan=23` (Ayuntamiento de La Línea de la Concepción).
- **Listado:** tabla HTML con columnas Publicación, Caducidad, Título, acciones (descarga, visualización, sello).
- **Detalle:** `/edictos/edicto/publico.action?codigo=YYYY-NNNNNN` con PDF firmado electrónicamente.
- **SSL:** certificado con CA intermedia no reconocida; requiere `insecure_ssl: true`.
- **Paginación:** listado único en página pública (~54 filas en ago 2026).

### Ejemplos urbanísticos (ago 2026)

| Fecha | Título |
|-------|--------|
| 04/08/2026 | Notificación infructuosa — subrogación expediente realidad física alterada (ref. catastral) |
| 30/07/2026 | Inicio expediente protección legalidad urbanística |
| 28/07/2026 | Información pública — expropiación finca (calle…) |
| 06/08/2026 | Notificaciones infructuosas LIDIS — EXPTE 2026_11022_URB61_* |

Códigos expediente visibles: `2026_11022_URB61_00013` (departamento urbanismo).

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Licencias y comunicaciones previas se tramitan por sede electrónica (sin histórico descargable).
- Edictos de notificación/licencia aparecen en tablón cuando procede (códigos URB61).
- Páginas informativas de urbanismo en web municipal.

## Proyectos / planeamiento

- **Tablón:** notificaciones, información pública, expropiaciones, subrogaciones urbanísticas.
- **Web:** PGOU revisión + instrumentos históricos (PGOU 1985).
- **BOJA:** revisión PGOU en tramitación (informe desfavorable parcial 2025).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - **Fisotec GIS** (`https://lalinea.fisotec.es`): plataforma QGIS/Web GIS municipal anunciada en 2024; incluye PGOU y trámites urbanísticos. **No responde** desde entorno CI (timeout/vacío).
  - **VITUA/SITUA** (Junta de Andalucía): planeamiento regional por municipio; sin campo expediente enlazable al tablón.
  - **Google Maps** embebido en web (mapa general municipio): sin polígonos por expediente.
  - **Callejero Digital Andalucía** (WFS): vías/portales, no ámbitos urbanísticos.
- **Estrategia:** los edictos son PDF firmados sin georreferencia embebida; Fisotec no expone API REST/WFS pública verificable. El orquestador aplicará centroide municipio + jitter.
- **Limitaciones:**
  - Sin WFS/ArcGIS enlazable por código de expediente.
  - GIS municipal inaccesible desde red del agente.
  - Documentación PGOU en PDF/planos raster sin vectorización automática.

## Limitaciones generales

- Certificado SSL inválido en sede (CA intermedia).
- Tablón sin paginación AJAX visible (listado completo en una página).
- Sin visor de expedientes público fuera del tablón.
- Fisotec GIS no verificable en CI.

## Adapter implementado

- `municipio.adapters.la_linea_de_la_concepcion:LaLineaDeLaConcepcionAyuntamientoAdapter`
- Fuentes: tablón edictos sede + documentos PGOU/planeamiento web WordPress + páginas informativas trámites.
