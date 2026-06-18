# Rivas-Vaciamadrid — investigación portal ayuntamiento

## Sitio oficial

- **Web principal:** https://www.rivasciudad.es (WordPress / Mindala Designer)
- **Sede electrónica (catálogo trámites):** https://sede-electronica.rivasciudad.es
- **Tablón espublico (Wicket):** https://rivasciudad.sedelectronica.es/board — tabla vacía en HTML inicial (carga vía AJAX/Wicket; no scrapeable sin sesión)
- **Tablón embebido (fuente principal):** https://inscripciones.rivasciudad.es/tablon-inicio/ — HTML con tabla (Descripción, Expediente, Procedimiento, Categoría, F.Publicación) y PDFs en iframe (`tablon-embebed-pdf`)
- **Urbanismo:** https://www.rivasciudad.es/urbanismo-y-vivienda/
- **Planeamiento:** https://www.rivasciudad.es/servicio/urbanismo-y-vivienda/2020/03/11/planeamiento-urbanistico/862600126897/
- **PGOU normativa vigente:** https://www.rivasciudad.es/geoportal/normativa-urbanistica-vigente/ (~194 PDF en `portal.rivasciudad.es`)
- **Avance PGOU:** https://www.rivasciudad.es/geoportal/avance-pgou/

## Formato y acceso

| Fuente | Formato | Acceso |
|--------|---------|--------|
| Tablón inscripciones | HTML tabla + PDF embebido | Público, sin auth |
| Geoportal PGOU | HTML con enlaces PDF | Público |
| Sede espublico board | Wicket/AJAX | Requiere POST con tokens de sesión |
| Trámites licencia | Páginas informativas WP | Público (tramitación requiere certificado) |
| Datos abiertos CKAN | API CKAN | Sin datasets de licencias/urbanismo |

## Licencias

- No hay listado público de concesiones con coordenadas (paridad Madrid licencias geo no disponible).
- Anuncios de licencia/disciplina urbanística aparecen en el **tablón** cuando se publican (procedimientos tipo Urbanismo, Disciplina Urbanística, etc.).
- Páginas informativas de trámites: `/tramite/licencia-de-obras-...`, `/servicio/urbanismo-y-vivienda/.../licencias-en-viviendas/`.

## Proyectos / expedientes

- **Tablón:** anuncios de información pública, edictos, acuerdos de pleno/junta (sección Órganos de gobierno).
- **PGOU:** documentación de planeamiento (memorias, planos, estudios) en geoportal.
- **Convenios** en `/ayuntamiento/informacion-juridica/convenios/` son mayoritariamente no urbanísticos; no se usan como fuente principal.

## Limitaciones

- `rivasvaciamadrid.es` está en venta; el dominio operativo es `rivasciudad.es`.
- Tablón espublico (`sedelectronica.es/board`) no expone filas en HTML estático.
- Tablón inscripciones solo muestra anuncios vigentes (~10–15 filas); el histórico no está indexado en URL pública simple.
- Sin API REST WP para custom post types (`servicio`, `tramite`).
- Licencias sin `lat`/`lon`/`distrito` en fuentes públicas.

## Estrategia adapter

1. Scrape determinista del tablón `inscripciones.rivasciudad.es/tablon-inicio/` (Anuncios + Plenos).
2. Extracción de PDFs PGOU desde normativa vigente y avance PGOU.
3. Páginas informativas de trámites de licencia urbanística.
