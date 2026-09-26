# Villar del Olmo — investigación portal ayuntamiento

## Fuentes

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal (Neosoft) | https://www.villardelolmo.es | CMS corporativo ASP.NET MVC |
| Urbanismo y Medio Ambiente | https://www.villardelolmo.es/servicios-al-ciudadano/territorio-y-medio-ambiente | Formularios licencia, NNSS, planos Eurovillas, ITE |
| Plan General de Urbanismo | https://www.villardelolmo.es/Pagina/plan-general-de-urbanismo | Documento Avance PGOU en exposición pública (36 PDFs en `/Ficheros/Documentos/`) |
| Convenio Agua Eurovillas | https://www.villardelolmo.es/convenio-agua-eurovillas-/ | Anuncios BOCM y borradores convenio agua |
| Sede espublico gestiona | https://villardelolmo.sedelectronica.es | Tablón, trámites, transparencia |
| Tablón de anuncios | https://villardelolmo.sedelectronica.es/board | Anuncios publicados (preview-document PDF) |
| Portal transparencia | https://villardelolmo.sedelectronica.es/transparency | Documentación municipal incl. urbanismo |
| Catálogo de trámites | https://villardelolmo.sedelectronica.es/dossier | Licencias obra/actividad, declaración responsable |

## Listado de expedientes / proyectos

- **PGOU (web):** exposición pública del Documento Avance (acuerdo pleno 17/11/2025, BOCM 28/11/2025). 36 PDFs descargables: memoria, planos de encuadre, planeamiento vigente NNSS, estructura catastral, usos del suelo, anexos ambientales, etc.
- **Urbanismo (web):** normativa vigente (NNSS, modificación plan especial Eurovillas, planos casco urbano y Eurovillas).
- **Tablón sede:** anuncios en formato `preview-document/{uuid}`; muestra actual mayoritariamente presupuesto/fiscal (sin urbanismo en muestra).
- **WFS SITCM:** sin ámbitos publicados para `VILLAR DEL OLMO` (PGOU aún en documento avance, no aprobado).

## Licencias

- No hay dataset público de concesiones con dirección/coords.
- Formularios informativos en web: declaración responsable de obra, modelos ITE.
- Trámites de licencia vía sede (`/dossier`); catálogo accesible pero sin listado de concesiones.
- Adapter incluye páginas informativas: formularios, tablón, catálogo trámites, transparencia.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - WFS Comunidad de Madrid IDEM: `https://idem.comunidad.madrid/geoserver3/ows`, capa `sitcm:VPLA_V_AMBITO` — **0 features** para `DS_MUNICIPIO='VILLAR DEL OLMO'`
  - PGOU documento avance: planimetría solo en PDF (no GeoJSON/WFS)
  - Sin visor urbanístico municipal ni ArcGIS por expediente
- **Estrategia:** adapter intenta WFS SITCM; si en el futuro se publican ámbitos tras aprobación PGOU, se enriquecerán automáticamente. Mientras tanto, orquestador usa centroide municipio + jitter.
- **Limitaciones:**
  - PGOU en fase de documento avance (no hay polígonos en SITCM)
  - Planos PDF sin georreferenciación machine-readable
  - Tablón sin anuncios urbanísticos geolocalizables en muestra actual

## Limitaciones generales

- Sede `/dossier` responde lento o vacío en algunos entornos automatizados.
- Tablón con volumen bajo de anuncios de planeamiento.
- Convenio Eurovillas es infraestructura hidráulica, no planeamiento territorial estricto, pero documentado por relevancia BOCM.
