# San Bartolomé de Tirajana — investigación portal

## Fuentes

| Recurso | URL | Contenido |
|---------|-----|-----------|
| Web corporativa (Joomla / YOOtheme) | https://www.maspalomas.com | Ayuntamiento de San Bartolomé de Tirajana (dominio histórico Maspalomas) |
| Tablón exposición pública | https://www.maspalomas.com/mnutablonexposicion | Tabla HTML: expediente + título + enlace PDF por fila (~30+ expedientes urbanísticos) |
| Sede electrónica (Galileo GIYS) | https://sede.maspalomas.com | Trámites, edictos, territorio |
| PGOU expediente 1994/0550 | https://sede.maspalomas.com/publico/contenido/PLANGRAL | Secciones acuerdos, memorias, planos, anexos |
| Visor localización expedientes | https://sede.maspalomas.com/publico/territorio/cexp | Visormin (JavaScript; mapas callejero, informe urbanístico, localización) |
| Informe urbanístico | https://sede.maspalomas.com/publico/territorio/informeurbanistico | Mapa parcelario / certificado urbanístico por finca |
| Edictos RSS | https://sede.maspalomas.com/publico/sindicacion/edictos/RSS | Pocos ítems; filtro urbanístico en adapter |
| eAdmin PGOU memorias | https://eadmin.maspalomas.com/publico/contenido/PGOUSBT01 … PGOUSBT05 | Documentación PGOU por bloques |
| Trámites licencias (informativos) | `/publico/procedimiento/CPOINST`, `CPPUOEE` | Comunicación previa obras / primera ocupación |

## Listado de expedientes

- **Proyectos / planeamiento:** el tablón Joomla es la fuente principal: cada fila enlaza un PDF bajo `/images/stories/documents/TablonAnuncios/ExposicionPublica/`. Metadatos: número de expediente en `title` del enlace y descripción en el `<p>` siguiente.
- **Licencias:** no hay tablón ni dataset de licencias concedidas. Solo procedimientos de sede (comunicación previa) y edictos puntuales en RSS.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** visor Galileo `visormin` en sede (callejero parcelario, informe urbanístico por parcela, capa “localización de expedientes” en `/publico/territorio/cexp`). Requiere JavaScript; no expone API REST/ArcGIS/WFS pública enlazable por código de expediente del tablón Joomla.
- **Estrategia:** el adapter no puede correlacionar expediente ↔ polígono sin automatizar el visor. El orquestador usará centroide municipal + jitter.
- **Limitaciones:** PDFs del tablón sin georreferencia embebida scrapeable; visor orientado a consulta por parcela/finca, no a descarga masiva de geometrías de expediente.

## Limitaciones generales

- Dominio `maspalomas.com` = municipio completo (Maspalomas, Meloneras, San Agustín, etc.).
- RSS de edictos con volumen bajo y muchos avisos no urbanísticos.
- Procedimientos URBANISMO en catálogo sede cargados vía postback ASP.NET (no scrapeables sin sesión).
