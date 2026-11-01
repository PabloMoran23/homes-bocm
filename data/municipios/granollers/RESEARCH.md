# Granollers — investigación portal ayuntamiento

## Fuentes base

| Recurso | URL |
|---------|-----|
| Web municipal (Drupal 7) | https://www.granollers.cat/urbanisme |
| Sede electrónica (portal JSP) | https://seuelectronica.granollers.cat/portal/sede/ |
| Carpeta ciudadana STA | https://seuelectronica.granollers.cat/sta/CarpetaPublic/public?APP_CODE=STA&PAGE_CODE=FRONTAL_OVC |
| Tablón anuncios STA | https://seuelectronica.granollers.cat/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all |
| Catálogo trámites | https://seuelectronica.granollers.cat/portal/sede/se_contenedor1.jsp?seccion=s_ltra_d12_v1.jsp&codbusqueda=65 |
| Normativa urbanística (menú) | https://seuelectronica.granollers.cat/portal/sede/se_distribuidor1.jsp?language=ca&codResi=1&codMenuPN=21&codMenu=133 |
| e-Tauler (edictos) | https://tauler.seu-e.cat/inici?idEns=809610007 |
| Geoportal ciudadano | https://geoportal-ajuntament-granollers-ciutada-ajtgrano.hub.arcgis.com/ |

## Proyectos / planeamiento

Publicación principal en **transparencia → normativa urbanística** (sede JSP), no en Drupal:

- **Planejament en tràmit** (`codbusqueda=144`): bloques `<strong>TÍTULO PROYECTO</strong>` + lista PDF (`archivosrel`).
- **Planejament derivat aprovat** (`codbusqueda=145`): ~50+ instrumentos con documentación (memoria, planos, acuerdos).
- **Instruments de gestió** (`codbusqueda=151`): convenios y actuaciones (~50+ PDFs).
- **Instruments de planificació** (`codbusqueda=102`): visor interactivo embebido (sin API JSON pública en el HTML).

Ejemplo de estructura HTML (tramit):

```html
<strong>PLA DE MILLORA URBANA DEL SECTOR 136A DE GRANOLLERS.</strong>
<ul>
  <li class="archivosrel"><a href="./RecursosWeb/DOCUMENTOS/1/0_8868_1.pdf">Text refós</a></li>
  ...
</ul>
```

**Drupal** `/noticies/urbanisme` tiene muy poca actividad; no es fuente principal.

**Expedientes urbanísticos** en carpeta privada STA (`EXPEDIENTES_FULL`) requieren certificado / VÀLid.

## Licencias

- No hay listado público de licencias concedidas (tablón STA PTS2_TABLON carga filas vía `submitAjax.aa`, sin `dataset_*` en HTML estático).
- El adapter ingiere **páginas informativas del catálogo de trámites** (búsqueda `buscadorPalabrasClave`: llicència d'obres, comunicació prèvia, etc.) → URLs `se_contenedor2.jsp?seccion=s_ftra_d4_v1.jsp&contenido=...`.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - Geoportal Hub: capas `Urbanisme` / `Urbanisme Ciutadà` son páginas Hub (no FeatureServer de expedientes).
  - Open data del mismo portal: `LIMIT MUNICIPAL`, líneas tranviarias, etc. (`services-eu1.arcgis.com/5gP6kqiXxbTYBXpu/...`) sin campo de enlace a expediente/planeamiento.
  - AMB `Planejament/Expedients/MapServer/3` (`CODI_INE='08108'`): 0 features.
- **Estrategia adapter:** sin `_fetch_geometry`; el orquestador usará centroide municipal + jitter.
- **Limitaciones:** visor de instrumentos (102) es aplicación cliente; tablón y expedientes requieren auth o AJAX no replicado en scrape estático.

## Limitaciones

- PTS_TABLON / PTS_CATSERV STA devuelven error de menú o shell AJAX sin dataset (a diferencia de otros municipios TAO).
- Certificados SSL y codificación `latin-1` en páginas JSP de la sede.
- Documentos anonimitizados en transparencia (solo títulos de proyecto útiles).
