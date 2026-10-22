import json, base64, sys
SP, OUTF = sys.argv[1], sys.argv[2]
t = open(SP + '/template.html', encoding='utf-8').read()
data = json.load(open(SP + '/mapdata.json'))
terr = open(SP + '/terrain.b64').read()
flags = {}
for c in 'vn la kh th mm my sg id ph bn tl'.split():
    s = open(f'/root/geo/node_modules/flag-icons/flags/4x3/{c}.svg', 'rb').read()
    flags[c] = 'data:image/svg+xml;base64,' + base64.b64encode(s).decode()
t = t.replace('__MAPDATA__', json.dumps(data, separators=(',', ':'))).replace('__TERRAIN__', terr).replace('__FLAGS__', json.dumps(flags))
open(OUTF, 'w', encoding='utf-8').write(t)
print(len(t) // 1024, 'KB')
