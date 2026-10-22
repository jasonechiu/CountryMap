"""Build regional puzzle data (usage: prep.py OUTDIR [sea|sa]): projected country paths, rivers, terrain image."""
import json, math, base64, io, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from shapely.geometry import shape, box, mapping, MultiPolygon, Polygon, LineString, MultiLineString
from shapely.ops import transform
from scipy import ndimage

GEO = '/root/geo/'
OUT = sys.argv[1]
REGION = sys.argv[2] if len(sys.argv) > 2 else 'sea'

REGIONS = {
    # Southeast Asia: 11 countries
    'sea': dict(box=(88.0, 146.0, -13.0, 29.0), clat=10,
                targets=['704', '418', '116', '764', '104', '458', '702', '360', '608', '096', '626'],
                ctx={'156': 'CN', '356': 'IN', '158': 'TW', '598': 'PG', '036': 'AU', '050': 'BD'}),
    # South Asia: 7 countries
    'sa': dict(box=(59.0, 99.0, -2.0, 38.0), clat=18,
               targets=['356', '586', '050', '524', '064', '144', '462'],
               ctx={'156': 'CN', '004': 'AF', '364': 'IR', '104': 'MM', '762': 'TJ'}),
}
CFG = REGIONS[REGION]
CORE = CFG['box']              # the area the game opens on
PAD_LON, PAD_LAT = 14.0, 5.0   # extra terrain around it, so wide or tall screens never show a cut edge
LON0, LON1, LAT0, LAT1 = CORE[0] - PAD_LON, CORE[1] + PAD_LON, CORE[2] - PAD_LAT, CORE[3] + PAD_LAT
K = 20.0                      # map units per degree latitude
C = math.cos(math.radians(CFG['clat']))
W = (LON1 - LON0) * K * C
H = (LAT1 - LAT0) * K
S = 2                         # terrain pixels per map unit

def proj(lon, lat, z=None):
    return ((np.asarray(lon) - LON0) * K * C, (LAT1 - np.asarray(lat)) * K)

TARGET = CFG['targets']
CONTEXT_LABEL = CFG['ctx']
TINY = {'702', '462'}         # keep every islet of these countries
def path_of(geom, prec=1):
    def ring(coords):
        pts = [f"{x:.{prec}f} {y:.{prec}f}" for x, y in coords[:-1]]
        return 'M' + 'L'.join(pts) + 'Z'
    polys = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
    out = []
    for p in polys:
        out.append(ring(list(p.exterior.coords)))
        for r in p.interiors:
            out.append(ring(list(r.coords)))
    return ''.join(out)

bbox_geo = box(LON0 - 1, LAT0 - 1, LON1 + 1, LAT1 + 1)
view = box(0, 0, W, H)
countries = json.load(open(GEO + 'countries50.geojson'))['features']
# the 1:50m Maldives has only a couple of atolls; take the full chain from the 1:10m data
DETAIL = {f['id']: f['geometry'] for f in json.load(open(GEO + 'countries10.geojson'))['features'] if f.get('id') in ('462',)}
for f in countries:
    if f.get('id') in DETAIL:
        f['geometry'] = DETAIL[f['id']]
out_c = []
land_polys = []
for f in countries:
    g = shape(f['geometry'])
    if not g.is_valid:
        g = g.buffer(0)
    if not g.intersects(bbox_geo):
        continue
    g = g.intersection(bbox_geo)
    gp = transform(lambda x, y, z=None: proj(x, y), g)
    f['id'] = f.get('id') or f['properties']['name']
    is_t = f['id'] in TARGET
    tol = 0.12 if is_t else 0.35
    if f['id'] == '462':
        gp = gp.buffer(2.2).buffer(-0.8).simplify(0.25)   # join the islets into one chain you can see and grab
    else:
        gp = gp.simplify(tol, preserve_topology=True)
    if not is_t:
        gp = gp.intersection(view.buffer(4))
    polys = [p for p in (gp.geoms if hasattr(gp, 'geoms') else [gp]) if isinstance(p, Polygon)]
    min_area = 0.15 if is_t else 1.5
    polys = [p for p in polys if p.area >= min_area or (is_t and f['id'] in TINY)]
    if not polys:
        continue
    gp = MultiPolygon(polys)
    land_polys.append(gp)
    big = max(polys, key=lambda p: p.area)
    rp = big.representative_point()
    x0, y0, x1, y1 = gp.bounds
    out_c.append({'id': f['id'], 'name': f['properties']['name'], 'target': is_t,
                  'd': path_of(gp), 'bbox': [round(x0, 1), round(y0, 1), round(x1 - x0, 1), round(y1 - y0, 1)],
                  'label': [round(rp.x, 1), round(rp.y, 1)], 'ctx': CONTEXT_LABEL.get(f['id'])})

# Rivers
rv = json.load(open(GEO + 'rivers50.geojson'))['features']
riv_major, riv_minor = [], []
for f in rv:
    if f['geometry'] is None:
        continue
    g = shape(f['geometry'])
    if not g.intersects(bbox_geo):
        continue
    g = g.intersection(bbox_geo)
    gp = transform(lambda x, y, z=None: proj(x, y), g).simplify(0.4)
    lines = gp.geoms if hasattr(gp, 'geoms') else [gp]
    sr = f['properties'].get('scalerank', 9) or 9
    for ln in lines:
        if not isinstance(ln, LineString) or ln.length < 3:
            continue
        d = 'M' + 'L'.join(f"{x:.1f} {y:.1f}" for x, y in ln.coords)
        (riv_major if sr <= 5 else riv_minor).append(d)

# Terrain image on the output grid
TW, TH = int(round(W * S)), int(round(H * S))
eto = Image.open(GEO + 'etopo1.jpg').convert('RGB')
EW, EH = eto.size
# output pixel (u,v) -> map unit (u/S, v/S) -> lon/lat -> etopo pixel
a = 1 / S / (K * C) * EW / 360
c0 = ((LON0 + 180) / 360) * EW - 0.5 + 0.5 * a
e = 1 / S / K * EH / 180
f0 = ((90 - LAT1) / 180) * EH - 0.5 + 0.5 * e
terr = eto.transform((TW, TH), Image.AFFINE, (a, 0, c0, 0, e, f0), resample=Image.BICUBIC)

# fine relief detail from the 2-arc-minute shaded relief image
sr = Image.open(GEO + 'shadedrelief.jpg').convert('L')
SW, SH = sr.size
a2 = 1 / S / (K * C) * SW / 360
c2 = ((LON0 + 180) / 360) * SW - 0.5 + 0.5 * a2
e2 = 1 / S / K * SH / 180
f2 = ((90 - LAT1) / 180) * SH - 0.5 + 0.5 * e2
srl = np.asarray(sr.transform((TW, TH), Image.AFFINE, (a2, 0, c2, 0, e2, f2), resample=Image.BICUBIC), dtype=np.float32)

# land mask
mask_img = Image.new('L', (TW, TH), 0)
dr = ImageDraw.Draw(mask_img)
for gp in land_polys:
    for p in gp.geoms:
        dr.polygon([(x * S, y * S) for x, y in p.exterior.coords], fill=255)
        for r in p.interiors:
            dr.polygon([(x * S, y * S) for x, y in r.coords], fill=0)
mask = np.asarray(mask_img) > 0
mask_d = ndimage.binary_dilation(mask, iterations=4)

rgb = np.asarray(terr, dtype=np.float32)
r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
sea_like = (b > np.maximum(r, g) - 4) | ((b > 170) & (g > 170) & (r > 150) & (b > r))
valid = mask & ~sea_like
ind = ndimage.distance_transform_edt(~valid, return_distances=False, return_indices=True)
filled = rgb[ind[0], ind[1]]

# add crisp relief: multiply by local contrast of the high-res shaded relief
blur = ndimage.gaussian_filter(srl, 6)
detail = np.clip(srl / np.maximum(blur, 1), 0.6, 1.5) ** 0.7
out = np.clip(filled * detail[..., None], 0, 255)
# slight saturation boost toward the reference look
gray = out.mean(axis=2, keepdims=True)
out = np.clip(gray + (out - gray) * 1.18, 0, 255)
out[~mask_d] = [120, 190, 200]
terr_img = Image.fromarray(out.astype(np.uint8))
terr_img.save(OUT + f'/terrain_preview_{REGION}.png')
buf = io.BytesIO()
terr_img.save(buf, 'JPEG', quality=84, optimize=True, progressive=True)
terr_b64 = base64.b64encode(buf.getvalue()).decode()

# Legend: order land colors by elevation proxy (three-globe topology bump map)
bump = Image.open(GEO + 'node_modules/three-globe/example/img/earth-topology.png').convert('L')
BW, BH = bump.size
a3 = 1 / S / (K * C) * BW / 360
c3 = ((LON0 + 180) / 360) * BW - 0.5 + 0.5 * a3
e3 = 1 / S / K * BH / 180
f3 = ((90 - LAT1) / 180) * BH - 0.5 + 0.5 * e3
bm = np.asarray(bump.transform((TW, TH), Image.AFFINE, (a3, 0, c3, 0, e3, f3), resample=Image.BILINEAR), dtype=np.float32)
sel = valid
vals = bm[sel]
cols = filled[sel]
qs = np.quantile(vals, [0, .35, .6, .8, .93, .985, 1])
legend = []
for i in range(6):
    m = (vals >= qs[i]) & (vals <= qs[i + 1])
    cc = np.median(cols[m], axis=0)
    cc = np.clip(cc.mean() + (cc - cc.mean()) * 1.18, 0, 255)
    legend.append('#%02x%02x%02x' % tuple(int(v) for v in cc))

vx0, vy0 = proj(CORE[0], CORE[3]); vx1, vy1 = proj(CORE[1], CORE[2])
data = {'W': round(W, 1), 'H': round(H, 1), 'S': S, 'countries': out_c,
        'view': [round(float(vx0), 1), round(float(vy0), 1), round(float(vx1 - vx0), 1), round(float(vy1 - vy0), 1)],
        'riversMajor': ''.join(riv_major), 'riversMinor': ''.join(riv_minor), 'legend': legend}
json.dump(data, open(OUT + f'/mapdata_{REGION}.json', 'w'))
open(OUT + f'/terrain_{REGION}.b64', 'w').write(terr_b64)
print('W,H', W, H, 'terrain', TW, TH, 'jpeg KB', len(buf.getvalue()) // 1024,
      'paths KB', sum(len(c['d']) for c in out_c) // 1024, 'rivers KB', (len(data['riversMajor']) + len(data['riversMinor'])) // 1024)
print('targets', [(c['id'], c['name'], c['bbox']) for c in out_c if c['target']])
print('legend', legend)
