"""Assemble the site: OUTDIR/index.html plus OUTDIR/data/<region>.json|.jpg

usage: build.py DATADIR OUTDIR       (DATADIR holds the prep.py output for every region)
"""
import json, base64, sys, re, os, shutil
SP = os.path.dirname(os.path.abspath(__file__))
DATA, OUT = sys.argv[1], sys.argv[2]
FLAG_DIR = '/root/geo/node_modules/flag-icons/flags/4x3/'
REGIONS = ['ea', 'sea', 'sa', 'ca', 'wa', 'ne', 'we', 'se', 'ee']

t = open(os.path.join(SP, 'template.html'), encoding='utf-8').read()
os.makedirs(os.path.join(OUT, 'data'), exist_ok=True)
meta = {}
for r in REGIONS:
    m = json.load(open(os.path.join(DATA, f'{r}.json')))
    meta[r] = {'n': sum(1 for c in m['countries'] if c['target'])}
    for ext in ('json', 'jpg'):
        shutil.copyfile(os.path.join(DATA, f'{r}.{ext}'), os.path.join(OUT, 'data', f'{r}.{ext}'))
codes = sorted(set(re.findall(r"flag: '([a-z]{2})'", t)))
os.makedirs(os.path.join(OUT, 'data', 'flags'), exist_ok=True)
for c in codes:
    shutil.copyfile(FLAG_DIR + c + '.svg', os.path.join(OUT, 'data', 'flags', c + '.svg'))
flags = {c: f'data/flags/{c}.svg' for c in codes}
t = t.replace('__LEVEL_META__', json.dumps(meta)).replace('__FLAGS__', json.dumps(flags))
open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(t)
total = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(os.path.join(OUT, 'data')) for f in fs)
print('index.html', len(t.encode()) // 1024, 'KB; data', total // 1024, 'KB;', len(codes), 'flags;', meta)
