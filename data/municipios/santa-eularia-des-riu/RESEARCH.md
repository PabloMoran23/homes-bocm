# Santa Eulària des Riu — portal ayuntamiento

Municipio: **Santa Eulària des Riu** (`santa-eularia-des-riu`) — Illes Balears (Eivissa). INE 07046. Sin boletín regional asociado en cola.

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal (Joomla 5 / YOOtheme) | https://www.santaeulariadesriu.com |
| Departamento urbanismo | https://www.santaeulariadesriu.com/ca/departaments/territori-urbanisme-i-activitats |
| Ordenació del territori i urbanisme | https://www.santaeulariadesriu.com/ca/departaments/territori-urbanisme-i-activitats/ordenacio-del-territori-i-urbanisme |
| Sede electrónica (espublico gestiona) | https://santaeulariadesriu.sedelectronica.es |
| Tablón de anuncios | https://santaeulariadesriu.sedelectronica.es/board |
| Consulta expedientes | https://santaeulariadesriu.sedelectronica.es/expedientes |
| Visor GeoXarc | https://www.santaeularia.com:444/geoxarc/ |

## Cómo se listan expedientes / proyectos

- **Planeamiento:** artículos Joomla enlazados desde la página de ordenación (normes subsidiàries, plans especials, estudi de detall, catàleg patrimoni, estudi acústic, modificacions NNSS). Muchos son páginas informativas con PDFs descargables (`/images/...pdf`).
- **Tablón sede:** HTML tabular Wicket (`class_name`, `class_folderCode`, …) con enlaces `preview-document/{uuid}`. En la fecha de investigación predominan anuncios de personal/ple; el filtro del adapter conserva filas urbanísticas cuando aparecen.
- **No hay** listado público machine-readable de expedientes en curso (consulta `/expedientes` es interfaz ciudadana, no catálogo scrapeable).

## Licencias de obra

- Trámites documentados en la web municipal (comunicació prèvia, llicència d'obra major/sense projecte, segregació, declaracions responsables DL 6/2023).
- **No** hay dataset público de licencias concedidas con dirección/fecha (como Madrid Open Data).
- El adapter ingiere páginas de trámite + tablón cuando hay anuncios de obra.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** Visor **GeoXarc** (OpenLayers 2 + capas WMS locales `https://www.santaeularia.com:444/map`). El visor referencia servicios en red interna (`172.16.x`) y el endpoint `/map?SERVICE=WMS&REQUEST=GetCapabilities` responde **404** desde internet.
- **IDELMA / Consell:** no existe capa `M046_URBANISME` en `ide.idelma.cat` (Pollença usa `M042_URBANISME:exp_absis`; Santa Eulària no está en ese WFS).
- **Estrategia adapter:** sin `geom_geojson`; el orquestador usará centroide municipal + jitter (`centroid` en manifest).
- **Limitaciones:** visor cartográfico útil para humanos; sin join expediente↔polígono para automatización. Certificado urbanístico vía trámites presenciales/sede.

## Limitaciones generales

- Web Joomla exige `User-Agent` identificable (403 sin él).
- Dominio SIG `santaeularia.com:444` requiere `insecure_ssl` en algunos entornos (certificado gestionado por el ayuntamiento).
- Tablón sede sin RSS; paginación Wicket no explorada (pocas filas visibles).
- Sin re-parse BOCM/BOIB automatizado en este adapter.
