# Pilar de la Horadada — investigación portal ayuntamiento

## Fuentes

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.pilardelahoradada.org | Urbanismo, PGOU (textos/planos), trámites |
| Sede electrónica (STA T-Systems) | https://sede.pilardelahoradada.org | Tablón `PTS2_TABLON`, catálogo `CATSERV`, ordenanzas |
| Tablón anuncios | https://sede.pilardelahoradada.org/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all | JSON embebido `dataset_PTS2_TABLON` (~12 entradas; poco urbanismo) |
| Catálogo trámites | https://sede.pilardelahoradada.org/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO | Trámites licencias/certificados urbanísticos (sin listado de concesiones) |
| Expedientes | https://sede.pilardelahoradada.org/sta/CarpetaPrivate/Login?APP_CODE=STA&PAGE_CODE=EXPEDIENTES_FULL | **Login** Cl@ve / certificado |
| PGOU web | https://www.pilardelahoradada.org/areas/urbanismo/pgou | Memoria, normas, planos OE-xx, enlace ordenanzas sede |
| Trámites urbanismo | https://www.pilardelahoradada.org/servicios/solicitudes/38 | Documentación presencial/telemática |
| Registro planeamiento GVA | https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/2%20ALICANTE/03902%20PILAR%20DE%20LA%20HORADADA/ | PDFs PGOU 1998 y planeamiento diferido |
| Visor GVA / ICV | https://visor.gva.es/visor/?capasids=0702_Planeamiento%3BPlaneamiento.Clasificacion | Clasificación/zonificación (informativo) |

## Listado de expedientes / licencias

- **Proyectos / planeamiento:** tablón sede (pocos anuncios), documentación PGOU en web + archivo GVA, inventario **ICV WFS** (`InventarioSuSuz`, sectores/UE del municipio).
- **Licencias de obra:** no hay dataset público de concesiones; solo trámites del catálogo STA y guías en web. El adapter expone trámites + filas del tablón cuando aplican.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS ICV: `https://terramapas.icv.gva.es/0702_Planeamiento` — capa `InventarioSuSuz`, filtro `cod_ine_mun='03902'`, geometría GML → GeoJSON EPSG:4326.
  - Visor cartográfico GVA (clasificación urbanística; no enlaza expediente concreto del ayuntamiento).
- **Estrategia:** ingestar polígonos de sectores/UE del inventario ICV como proyectos de planeamiento; enriquecer filas del tablón/GVA por coincidencia de título con sector/UE cuando sea posible.
- **Limitaciones:** sin visor municipal ArcGIS enlazado a expediente; consulta de expedientes en sede privada; tablón casi vacío de urbanismo; geometría ICV es ámbito de planeamiento aprobado, no licencia puntual.

## Limitaciones técnicas

- La web `www.pilardelahoradada.org` puede no responder desde algunos entornos (timeout/vacío); el adapter usa sede + GVA + ICV como fuentes principales.
- Expedientes urbanísticos en curso no accesibles sin identificación.
