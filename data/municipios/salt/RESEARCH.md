# Salt (Girona) — investigación portal ayuntamiento

## URLs base y semillas

| Fuente | URL | Uso |
|--------|-----|-----|
| Web oficial | https://www.viladesalt.cat | WordPress Avada; redirige desde salt.cat |
| Planejament en tràmit | https://www.viladesalt.cat/ajuntament/documentacio-i-tramits-ppal/documentacio-i-tramits/planejament-urbanistic/planejament-en-tramit/ | Listado principal: bloques `<h2 class="content-box-heading">` con `(Exp. …)`, acuerdos de pleno y enlaces BPM / e-Tauler |
| Planejament derivat vigent | …/planejament-derivat-vigent/ | Planes parciales / especiales aprobados |
| Convenis urbanístics | …/convenis-urbanistics/ | Convenios |
| Suspensió llicències | …/suspensio-potestativa-de-llicencies/ | Ámbitos con suspensión potestativa |
| PGOU refós | …/pla-general-dordenacio-urbana/ | Normativa y plànols por zonas (PDF) |
| Llicències (formularis) | https://www.viladesalt.cat/arees-serveis/area-de-territori-i-mediambient/llicencies-i-comunicats-dobres/ | Enlaces a formularis OB* en seu-e.cat/documents |
| Seu-e | https://seu-e.cat/ca/web/salt | Catàleg tràmits (classificació urbanisme) |
| e-Tauler | https://tauler.seu.cat/inici.do?idens=1715570005 | Edictes IP / anuncios (SPA React; detalle vía tauler.seu-e.cat/detall?idEns=…&idEdicte=…) |
| BPM descargas | https://bpm.salt.cat/OAC/downloadR/… | Documentación técnica y acuerdos de planeamiento |
| Visor planejament | https://mapes.salt.cat/planejament/#/home | Mapa interactivo municipal |

## Cómo se listan expedientes

- **Planeamiento:** HTML estático en viladesalt.cat (Avada). Cada actuación = título h2 + párrafos con código expediente municipal (`2025S009000001`, etc.), fechas en catalán y enlaces a PDF (BPM, wp-content/uploads) o edicto en e-Tauler.
- **No hay API JSON** ni feed RSS de expedientes en trámite.
- **Licencias concedidas:** no hay listado tabular público tipo Sedipualba; solo trámites/formularios y tauler de edictos (SPA).

## Licencias de obra

- Trámites informativos: página de llicències + catàleg seu-e (urbanisme) + formularis PDF OB1–OB6.
- Concesiones publicadas: posiblemente en e-Tauler (requiere navegación SPA / idEdicte); no scrapeable de forma estable sin API documentada.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor municipal: https://mapes.salt.cat/planejament/ (aplicación SPA; sin REST ArcGIS/WFS público identificado en la web).
  - Visor MUC Generalitat: https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi=17155
  - Plànols de delimitación en PDF enlazados desde «planejament en tràmit» (p. ej. BPM downloadR o acuerdo de pleno con plano incorporado).
- **Estrategia adapter:** metadatos de expedientes + URL del documento/plànol cuando aparece «delimitació»; referencias al visor mapes/MUC. Sin `geom_geojson` automatizable (visor no responde en timeout desde entorno cloud; PDFs sin georreferencia parseada).
- **Limitaciones:** mapes.salt.cat timeout >15 s desde datacenter; e-Tauler y seu-e pueden devolver HTTP 429 con ráfagas; geometría de ámbito queda para enriquecimiento manual o futuro parseo de PDF vectorial.

## Limitaciones operativas

- Sin boletín regional asociado en cola (`bocm_count: 0`).
- Rate limiting ocasional en seu-e.cat.
- salt.cat es portal informativo secundario; contenido urbanístico completo en viladesalt.cat.
