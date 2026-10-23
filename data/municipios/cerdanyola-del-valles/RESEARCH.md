# Cerdanyola del Vallès — investigación portal ayuntamiento

## Fuentes

| Fuente | URL | Formato |
|--------|-----|---------|
| Web corporativa | http://www.cerdanyola.cat | Drupal 7 |
| Urbanisme | http://www.cerdanyola.cat/urbanisme | Secciones actualitat, projectes-aprovats, informació urbanística |
| RSS actualitat | http://www.cerdanyola.cat/rss.xml | RSS (nodos PIG / cartografia) |
| Seu electrònica (STA) | https://seu.cerdanyola.cat | Portal clásico; enlace a e-Tauler |
| e-Tauler | https://tauler.seu.cat/inici.do?idens=826650006 | SPA (anuncios) |
| Transparència (seu-e) | https://seu-e.cat/web/cerdanyoladelvalles/... | Liferay — documentos urbanismo |
| SIG municipal | http://sig.cerdanyola.cat/enmapa/visor/alin | Angular Enmapa (alineaciones, capas T5248…) |
| Geoportal AMB cartografia | https://geoportalcartografia.amb.cat/ | Enlace desde web municipal |
| RPUC | municipiSel=08074 | Sin listado HTML útil en prueba rápida |

## Proyectos / expedientes

- **Drupal:** noticias de planeamiento (p. ej. Parc de l'Alba / TSJC), páginas PIG (cartografia, servidumbres, geodesia).
- **seu-e Liferay:** documentos bajo `accio-de-govern-i-normativa/urbanisme/*` (consulta previa, exposición pública Avanç Cerdanyola 2000, censos, ordenanzas).
- **Projectes aprovats:** página informativa sin listado estructurado de expedientes en HTML (solo menú lateral).
- **Tablón:** sede STA no expone `dataset_PTS2_TABLON` en las URLs probadas; tablón remitido a **e-Tauler** (idens 826650006).

## Licencias

- No hay listado público masivo de licencias concedidas.
- Trámites: https://seu.cerdanyola.cat y catálogo https://www.seu-e.cat/.../serveis-i-tramits/tramits (contenido mayormente dinámico).
- Adapter devuelve páginas informativas de trámites + e-Tauler (patrón Pozuelo / Badalona).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** SIG Enmapa (`sig.cerdanyola.cat`) con visor de alineaciones y capas internas; geoportal AMB cartografía; capa AMB `Planejament/Expedients` consultada con `CODI_INE='08074'` → **0** expedientes (08073 corresponde a Cornellà).
- **Estrategia:** sin join expediente↔polígono automatizable; MUC/RPUC con TLS débil en el entorno cloud (`DH_KEY_TOO_SMALL`).
- **Limitaciones:** visor SIG es SPA sin API GeoJSON pública por código de expediente; tablón en e-Tauler sin scrape determinista; geometría dependerá de centroide municipal + jitter en el orquestador.
