"""Fill template.html with every region's map data, terrain and flags (usage: build.py DATADIR OUT.html)."""
import json, base64, sys, re
SP, OUTF = sys.argv[1], sys.argv[2]
FLAG_DIR = '/root/geo/node_modules/flag-icons/flags/4x3/'
t = open(SP + '/template.html', encoding='utf-8').read()
levels = {}
for r in ['sea', 'sa']:
    levels[r] = {'map': json.load(open(f'{SP}/mapdata_{r}.json')), 'terrain': open(f'{SP}/terrain_{r}.b64').read()}
codes = sorted(set(re.findall(r"flag: '([a-z]{2})'", t)))
flags = {c: 'data:image/svg+xml;base64,' + base64.b64encode(open(FLAG_DIR + c + '.svg', 'rb').read()).decode() for c in codes}
t = t.replace('__LEVELS__', json.dumps(levels, separators=(',', ':'))).replace('__FLAGS__', json.dumps(flags))
open(OUTF, 'w', encoding='utf-8').write(t)
print(len(t) // 1024, 'KB, flags:', ' '.join(codes))
