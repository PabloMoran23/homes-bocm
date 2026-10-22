# Sanlúcar de Barrameda — investigación portal ayuntamiento

**Municipio:** Sanlúcar de Barrameda (Cádiz, Andalucía)  
**Slug:** `sanlucar-de-barrameda`  
**INE:** 11032 — Sin boletín regional asociado en cola BOCM

## URLs base y páginas semilla

| Recurso | URL | Notas |
|---------|-----|--------|
| Gerencia Municipal de Urbanismo (GMU) | https://www.gmusanlucar.es | Drupal 10 (dxpr_theme) |
| Tablón GMU (45 días) | https://www.gmusanlucar.es/anuncios | Nodos `/node/{id}` con título + PDF |
| Planeamiento vigente | https://www.gmusanlucar.es/planeamiento-vigente | Modificaciones PGOU (nodos 145, 146, 257…) |
| Índice PGOU | https://www.gmusanlucar.es/indicepgou | PDFs `/system/files?file=Documento Item/…` |
| Adaptación PGOU | https://www.gmusanlucar.es/indiceadaptacionpgou | Documentación adaptación |
| Avance planeamiento | https://www.gmusanlucar.es/avance | Memoria y plano guía |
| Tramitaciones | https://www.gmusanlucar.es/tramitaciones | Tabla orientativa licencias (sin histórico) |
| Web ayuntamiento | https://www.sanlucardebarrameda.es | Drupal 11 |
| Tablón virtual ayuntamiento | https://www.sanlucardebarrameda.es/es/anuncios | ~200 páginas; adapter recorre primeras 12 |
| Urbanismo (área) | https://www.sanlucardebarrameda.es/es/content/urbanismo-y-suelo | Enlace a GMU / sede |
| Sede electrónica | https://sede.sanlucardebarrameda.es | Plataforma propia (no espublico) |
| Sede GMU | https://sede.sanlucardebarrameda.es/portal/entidades.do?ent_id=3&idioma=1 | Registro y expedientes autenticados |
| Catálogo trámites GMU | https://sede.sanlucardebarrameda.es/sede/catalogoTramites.do?ent_id=3&idioma=1 | Licencias vía registro |
| SITUA Junta | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | PGOU regional raster |

## Cómo se listan expedientes / proyectos

1. **GMU `/anuncios`:** vista Drupal con enlaces a nodos (información pública, estudios de detalle, calificación ambiental, etc.). Fecha en `<time datetime="…">`.
2. **Ayuntamiento `/es/anuncios`:** tablón virtual municipal; mezcla urbanismo con plenos y empleo. El adapter filtra por regex urbanística y excluye sesiones de gobierno/empleo.
3. **Planeamiento:** nodos bajo `/planeamiento-vigente` y PDFs en `/indicepgou`, `/avance` y subcarpeta estática `planeamientovigente/Planeamiento_de_desarrollo/index.html`.
4. **Sede:** expedientes solo tras login («Mis expedientes»); no hay `/board/` público tipo espublico.

## Licencias de obra

- No existe listado histórico abierto de licencias concedidas.
- Tramitación obligatoria en sede GMU (`catalogoTramites.do`); GMU publica tabla de tipos en `/tramitaciones`.
- Edictos puntuales pueden aparecer en tablones GMU o ayuntamiento (p. ej. actuaciones, calificación ambiental con expte.).
- Adapter incluye páginas informativas de sede/tablon + filas del tablón que coinciden con regex de licencia.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - SITUA Junta de Andalucía — planeamiento digitalizado (municipio 11032), raster sin WFS/ArcGIS REST por código de expediente.
  - GMU — planos en PDF e índice HTML estático; sin visor ArcGIS ni GeoJSON enlazado a expediente.
  - Ayuntamiento — sin visor urbanístico público en `/es/content/urbanismo-y-suelo`.
  - Sede GMU — documentos administrativos sin coordenadas.
- **Estrategia:** centroide municipal en manifest (`centroid: [36.7781, -6.3527]`) + jitter del orquestador.
- **Limitaciones:** geometría de ámbito solo en PDF/planos no vectoriales públicos; tablón ayuntamiento muy paginado.

## Limitaciones generales

- Sede sin tablón HTML scrapeable (`/board/` → 404).
- Tablón ayuntamiento: 200+ páginas; crawl acotado a 12 páginas recientes en CI.
- GMU tablón limitado a ~45 días (texto en menú).
- Licencias: solo trámites y edictos, no registro completo.

## Adapter

- `municipio.adapters.sanlucar_de_barrameda:SanlucarDeBarramedaAyuntamientoAdapter`
- IDs: `sanlucar-de-barrameda-lic-*` / `sanlucar-de-barrameda-proy-*` (sha256[:14]).
