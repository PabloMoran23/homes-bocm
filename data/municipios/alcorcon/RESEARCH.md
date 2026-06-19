# Alcorcón — investigación portal ayuntamiento

**Municipio:** Alcorcón (`alcorcon`)  
**Fecha:** 2026-06-19

## Resumen

Alcorcón publica urbanismo en dos plataformas:

1. **Web municipal Drupal 10** (`www.ayto-alcorcon.es`) — transparencia (PGOU, convenios), concejalía de Agenda Urbana con trámites DYC e impresos PDF.
2. **Sede electrónica** (`portalciudadano.ayto-alcorcon.es`) — catálogo de trámites urbanismo (apl. 4), anuncios y tramitación electrónica.

No hay tablón de anuncios con edictos de licencias concedidas (como Móstoles) ni dataset JSON embebido (como Getafe STA). Las licencias publicadas son **trámites e impresos informativos**, no concesiones con fecha/distrito.

## URLs principales

| Recurso | URL | Formato |
|---------|-----|---------|
| Web municipal | https://www.ayto-alcorcon.es/es | Drupal 10 |
| Concejalía Agenda Urbana | https://www.ayto-alcorcon.es/es/ayuntamiento/concejalias/concejalia-de-agenda-urbana-planificacion-desarrollo-y-mantenimiento | HTML + nodos `/es/node/*` con PDF |
| Transparencia ordenación | https://www.ayto-alcorcon.es/es/transparencia/publicidad-activa/informacion-en-materia-de-ordenacion-del-territorio-y-obras-publicas | HTML + PDF PGOU/convenios |
| Sede electrónica | https://portalciudadano.ayto-alcorcon.es/ | Java/JSP + Bootstrap |
| Catálogo urbanismo | https://portalciudadano.ayto-alcorcon.es/sede/catalogoTramites.do?opcion=detalle&idApl=4&ent_id=1&idioma=1 | HTML (sección apl4 vacía en scrape estático; trámites en mapa web) |
| Anuncios sede | https://portalciudadano.ayto-alcorcon.es/portal/contenedor.do?det_cod=37&pes_cod=-2&ent_id=1&idioma=1 | HTML estático (pocos anuncios) |
| Mapa web sede | https://portalciudadano.ayto-alcorcon.es/portal/mapaWeb.do?ent_id=1&opc_id=218&pes_cod=-2 | HTML con enlaces `tramitacionElectronica.do` |

## Proyectos / planeamiento

- **PGOU y normativa:** PDFs en transparencia (memorias, anexos normativos, NNUU, convenio Retamar de la Huerta 2024).
- **Trámites urbanísticos:** nodos Drupal de la concejalía (DYC-102 licencia, DYC-205 agrupación parcelas, DYC-403 viabilidad urbanística, ordenanzas).
- **Agenda Urbana 2030** (`agendaurbanaalcorcon.es`): documentación estratégica; no expedientes individuales — excluido del scrape.

## Licencias

- Impresos DYC (102, 101, 104, 201, 202, 203…) en nodos Drupal de la concejalía.
- Trámite sede «Declaración Responsable de obra Menor» (`tramitacionElectronica.do?asu_cod=153`).
- **Limitación:** no hay listado público de licencias concedidas con dirección/fecha; solo catálogo de trámites y formularios.

## Limitaciones

- Catálogo sede idApl=4 devuelve HTML con `collapse4` vacío (contenido posiblemente dinámico); se complementa con mapa web y concejalía.
- Buscador Drupal (`/es/buscador`) requiere JS; no scrapeado.
- Página `/servicios/desarrollo-de-la-ciudad/urbanismo-y-obras-publicas` devuelve 403/acceso denegado.
- Anuncios sede muy escasos y sin filtro urbanismo.
- Sin API REST ni datos abiertos de expedientes.

## Estrategia adapter

Modelo híbrido **Drupal (pozuelo/alcobendas) + sede (getafe/fuenlabrada)**:

1. PDFs transparencia ordenación → proyectos (PGOU, convenios).
2. Párrafos concejalía Agenda Urbana → licencias (DYC) y proyectos (normativa, instrucciones).
3. Nodos `/es/node/*` enlazados → PDFs con fecha desde ruta `/sites/default/files/YYYY-MM/`.
4. Mapa web sede + anuncios → trámites licencia adicionales.
