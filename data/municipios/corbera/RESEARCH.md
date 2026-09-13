# Corbera — investigación portal ayuntamiento

Municipio: **Corbera** (`corbera`) — provincia Valencia, Comunitat Valenciana.  
INE municipio: **46098**. Boletín regional: **DOGV** (`boletin_source_id: dogv`).

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.corbera.es (redirect desde https://corbera.es) |
| Sede electrónica | https://corbera.sedelectronica.es |
| Tablón de anuncios | https://corbera.sedelectronica.es/board |
| Info pública (transparencia) | https://www.corbera.es/ca/transparencia/informacio-publica |
| Info pública (ES) | https://www.corbera.es/es/transparencia/informacion-publica |
| Sede — normativa/IP | https://corbera.sedelectronica.es/info.4 |
| Ordenanzas urbanísticas | https://www.corbera.es/ca/pagina/ordenances-urbanistiques |
| PAI UE 4.1 (IP activa) | https://www.corbera.es/ca/pagina-transparencia/informacio-publica-linici-del-procediment-laprovacio-del-programa-dactuacio-integrada-mitjancant-gestio-directa-subunitat-41-unitat-dexecucio-zona-4-fins-l11 |
| Agenda Urbana | https://agendaurbanacorbera.com/ |
| PGE (PDF) | https://www.corbera.es/sites/www.corbera.es/files/46098_PGE_CORBERA_INICIAL_DN1_NORMATIVA_0.pdf |
| POP (PDF) | https://www.corbera.es/sites/www.corbera.es/files/46098_POP_CORBERA_INICIAL_DN1_NORMATIVA.pdf |

## CMS y sede

- **Web:** Drupal 10 (`portalesmunicipales.es`, módulos `digital_value/*`), bilingüe valenciano/castellano.
- **Sede:** espublico gestiona (Wicket/YUI), tablón HTML con filas `class_name`, `preview-document/{uuid}`.
- **Trámites urbanísticos:** catálogo en `/dossier`; consulta expedientes en `/expedientes` (requiere Cl@ve, sin histórico público).

## Expedientes / planeamiento

- **Listado:** no hay visor de expedientes urbanísticos abierto; proyectos se publican en transparencia (páginas Drupal + PDFs) y avisos en homepage/sede.
- **Instrumentos vigentes en tramitación/publicación:** PGE y POP (Dip. Valencia, 2019–2021), PAI subunidad 4.1 zona 4 (información pública con PDFs de programa y proyecto).
- **Tablón:** edictos administrativos generales (IAE, créditos, empleo); sin licencias de obra recientes indexadas.

## Licencias de obra

- Sin dataset ni tablón dedicado a licencias concedidas.
- Trámites informativos vía sede (`/dossier`, `/expedientes`).
- El adapter expone páginas de referencia (tablón + trámites) siguiendo patrón Alfafar/Pozuelo.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `Planeamiento.Zonificacion` — `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Filtro cliente `cod_ine_mun=46098`
  - Visor GVA: `https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion`
- **Estrategia:** paginar WFS (`outputFormat=application/json; subtype=geojson`, `EPSG:4326`), agrupar polígonos por `(denominaci, expediente)`, enriquecer filas ICV y matching por título.
- **Datos encontrados:** 1 instrumento ICV — *Homologación de las normas subsidiarias* (exp. 19990124), 13 fragmentos poligonales. PGE/POP recientes **no** aparecen aún en ICV WFS.
- **Limitaciones:** sin visor municipal propio; PAI/PGE/POP sin geometría enlazable en portal; sede `/info.4` con timeout intermitente desde CI; `www.corbera.es/es/*` más lento que `/ca/*`.

## Limitaciones generales

- Portal bilingüe (contenido urbanístico principalmente en `/ca/`).
- SSL sede: certificado gestionado por espublico (`insecure_ssl: true` por compatibilidad CI).
- Sin API JSON de expedientes; scrape HTML determinista.
