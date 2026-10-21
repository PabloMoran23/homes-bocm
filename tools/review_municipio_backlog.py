"""Inventory municipal PRs locally; flags require review, never authorize a merge."""
import argparse,ast,json,re,subprocess,collections,pathlib
parser=argparse.ArgumentParser(__doc__)
parser.add_argument('--inventory', type=pathlib.Path)
parser.add_argument('--output', type=pathlib.Path, required=True)
parser.add_argument('--fetch', action='store_true')
args=parser.parse_args()
raw=json.loads(args.inventory.read_text()) if args.inventory else json.loads(subprocess.check_output(['gh','pr','list','--state','open','--limit','500','--json','number,title,headRefName,headRefOid,isDraft'],text=True))
rows=[r for r in raw if r['title'].startswith('feat(municipio)')]
if args.fetch and rows:
 subprocess.run(['git','fetch','--no-tags','origin',*[f'+refs/pull/{r["number"]}/head:refs/municipio-batch/{r["number"]}' for r in rows]],check=True)
def git(*args):return subprocess.check_output(['git',*args],text=True)
result=[]
for r in rows:
 ref=f'refs/municipio-batch/{r["number"]}'
 paths=git('diff','--name-only',f'origin/main...{ref}').splitlines()
 manifests=[p for p in paths if re.fullmatch(r'data/municipios/[^/]+/manifest.yaml',p)]
 adapters=[p for p in paths if re.fullmatch(r'municipio/adapters/[^/]+\.py',p)]
 flags=[]
 if len(manifests)!=1 or len(adapters)!=1:flags.append('ambiguous_scope')
 slug=manifests[0].split('/')[2] if len(manifests)==1 else None
 if slug and pathlib.Path(f'data/municipios/{slug}/manifest.yaml').exists():flags.append('already_present')
 extra=[p for p in paths if not p.startswith(f'data/municipios/{slug}/') and p not in adapters+['data/municipios/queue.yaml']]
 if extra:flags.append('extra_files')
 source=git('show',f'{ref}:{adapters[0]}') if len(adapters)==1 else ''
 try:ast.parse(source)
 except SyntaxError:flags.append('syntax_error')
 if re.search(r'(informativ|tr.mites?|formularios?).{0,80}(licenc|conces)|licenc.{0,80}(informativ|tr.mites?)',source,re.I):flags.append('procedure_licenses')
 if re.search(r'\{(?:max\(years\)|year|y)\}-01-01|datetime.now\(',source):flags.append('date_review')
 if re.search(r'LIKE.*%|best\[0\].*< 8|score.*\+= 8',source):flags.append('fuzzy_geometry')
 result.append({**r,'slug':slug,'ref':ref,'paths':paths,'adapters':adapters,'flags':flags})
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2))
print('Total',len(result),'flags',collections.Counter(f for r in result for f in r['flags']))
for r in sorted(result,key=lambda r:r['number']):
 if not r['flags']:print('NO_FLAGS_REQUIRES_REVIEW',r['number'],r['slug'])
print('Only procedure/date flags',sum(set(r['flags'])<= {'procedure_licenses','date_review'} for r in result))
