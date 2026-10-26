# Ripollet — investigación portal ayuntamiento

## URLs base y semillas

| Fuente | URL | Notas |
|--------|-----|--------|
| Seu electrònica (AOC) | https://seu-e.cat/ca/web/ripollet | Liferay; redir desde https://seu.ripollet.cat |
| Tràmits (catàleg) | https://seu-e.cat/ca/web/ripollet/tramits-i-gestions | Classificació `urbanisme` scrapeable en HTML |
| Govern obert — urbanisme | https://seu-e.cat/ca/web/ripollet/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme | Subseccions planejament, normativa, info geogràfica |
| Planejament urbanístic | …/urbanisme/planejament-urbanistic | Text + enllaços AMB/MUC/RPUC |
| Tauler d'edictes | …/tauler-d-edictes-i-anuncis | Contingut dinàmic (portlet AOC); descripció estàtica |
| Web corporativa | https://www.ripollet.cat | **503 Backend fetch failed** (Varnish) des de l'entorn cloud |
| Absis (legacy tablón) | https://seu.ripollet.cat/absis/ead/... | **401** sense credencials |

## Expedientes / planeamiento

- **Transparència seu-e:** pàgines d'indicadors AOC amb text descriptiu i enllaços externs (no llistat d'expedients en HTML estàtic).
- **RPUC:** https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=08179 (formulari; sense llistat JSON públic simple).
- **MUC:** municipi INE **08179** (la pàgina municipal enllaça erròniament 08180).
- **AMB:** https://geoportalplanejament.amb.cat/AppGeoportalPlanejament2/index.html (consulta planejament refós àrea metropolitana).

## Licencias

- Catàleg **classificacio/urbanisme** (9 tràmits): comunicacions prèvies, llicències d'obres, canvi d'ús, ocupació via pública, primera ocupació, etc.
- No hi ha dataset públic de llicències concedides amb adreça/coordenades; només fitxes de tràmit.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** MUC Gencat (08179), geoportal AMB, enllaç històric `http://oslo.geodata.es/ripollet/planejament.php` (domini reassignat / no operatiu).
- **Estrategia:** referències de planejament via visors autonòmics/metropolitans; sense join determinista expedient municipal → polígon.
- **Limitaciones:** www.ripollet.cat inaccessible (503); edictes en portlet JS; visors sense API d'expedient per codi des del portal municipal.

## Limitaciones generales

- Cloudflare / "Just a moment" en algunes fitxes de tràmit individuals (el llistat de classificació sí respon).
- Contingut de transparència carregat per portlets (`aoctransparenciavisualitzaciopagina`); scrape limitat a `<p>` i títols.
- `bocm_count: 0` — sense boletín regional associat en cola.
