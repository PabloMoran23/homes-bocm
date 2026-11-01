# Cambrils — investigación portal ayuntamiento

## Fuentes

| Área | URL | Formato |
|------|-----|---------|
| Web municipal | https://www.cambrils.cat | Plone |
| Urbanisme (hub) | https://www.cambrils.cat/ca/serveis/urbanisme | HTML |
| Informació pública | https://www.cambrils.cat/ca/serveis/urbanisme/informacio-publica | Plone folder listing + subcarpetas por expediente |
| POUM 2.1 | https://www.cambrils.cat/ca/serveis/urbanisme/poum-21 | PDFs enlazados |
| Tràmits i llicències | https://www.cambrils.cat/ca/serveis/urbanisme/tramits-i-llicencies | Acordeón Plone + PDFs @@download |
| Seu electrònica (web) | https://www.cambrils.cat/ca/seu-electronica/tauler-danuncis | Enlaces a OAC |
| OAC / tràmits | https://tramits.cambrils.cat/OAC/CdT.jsp | Catálogo trámites (JSP) |
| Consulta expedients | https://tramits.cambrils.cat/OAC/SegExpStandalone.jsp?idioma=ca&_UNITREE=CCIU | JSP (requiere sesión / red municipal) |

## Proyectos / planeamiento

- El listado principal de actuaciones en **informació pública** expone ~50 carpetas Plone (paginación `?b_start:int=20`).
- Cada carpeta tiene `og:title`, documentos PDF y, en algunos casos, enlaces internos.
- No hay API JSON pública; el adapter recorre el listado y parsea metadatos por página.
- POUM: documentos estáticos en la sección `poum-21`.

## Licencias

- No hay tablón público de licencias concedidas con dirección/fecha (como Madrid STA).
- La web publica **trámites y formularios** (solicitud de licencia de obra, piscina, grúa, enderroc, etc.) y enlaces al catálogo OAC (`CdT.jsp?tramit=…`).
- El adapter ingiere filas **informativas** de trámites (URLs + título), no concesiones históricas georreferenciadas.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** Visor municipal https://mapes.cambrils.cat/geoportal/ (enlace desde POUM; coordenadas UTM en URL de ejemplo). No se ha localizado REST ArcGIS/WFS público con campo de expediente enlazable al listado Plone.
- **Estrategia:** Sin join determinista expediente↔polígono; el orquestador usará centroide municipal + jitter (`centroid` en manifest).
- **Limitaciones:** `tramits.cambrils.cat` y `mapes.cambrils.cat` pueden no ser accesibles desde todas las redes (timeout); los proyectos se obtienen de `www.cambrils.cat` sin geometría.

## Notas técnicas

- CMS: Plone (meta `generator: Plone`).
- IDs estables: `cambrils-proy-*` / `cambrils-lic-*` (sha256 URL).
- Sin boletín regional asociado en cola (`bocm_count: 0`).
