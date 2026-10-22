"""World-map levels: 'cont' (seven continents + three oceans) and 'world' (random countries from the whole world).

usage: prep_world.py OUTDIR
Equal Earth projection, central meridian 11°E; the map is cut at 169°W so Russia, Fiji and Polynesia stay whole.
writes OUTDIR/cont.json|jpg and OUTDIR/world.json|jpg
"""
import json, math, sys, os
import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import shape, box, mapping, MultiPolygon, Polygon, LineString, Point
from shapely.ops import transform, unary_union
from shapely import affinity
from scipy import ndimage

GEO = '/root/geo/'
OUT = sys.argv[1]
CUT = -169.0                     # map edge (longitude); everything west of it is moved 360° east
LAM0 = math.radians(CUT + 180)   # central meridian = 11°E
R = 406.0                        # map units per Earth radius -> map about 2200 x 1070
A1, A2, A3, A4 = 1.340264, -0.081106, 0.000893, 0.003796
SQ3 = math.sqrt(3)
XMAX = 2 * SQ3 * math.pi / (3 * A1)
TH_MAX = math.asin(SQ3 / 2)
YMAX = A4 * TH_MAX ** 9 + A3 * TH_MAX ** 7 + A2 * TH_MAX ** 3 + A1 * TH_MAX
W, H = 2 * XMAX * R, 2 * YMAX * R
S = 2

def fwd(lon, lat):
    lam = np.radians(np.asarray(lon, dtype=float)) - LAM0
    phi = np.radians(np.asarray(lat, dtype=float))
    th = np.arcsin(SQ3 / 2 * np.sin(phi))
    t2 = th * th; t6 = t2 ** 3
    x = 2 * SQ3 * lam * np.cos(th) / (3 * (9 * A4 * t6 * t2 + 7 * A3 * t6 + 3 * A2 * t2 + A1))
    y = th * (A4 * t6 * t2 + A3 * t6 + A2 * t2 + A1)
    return x * R + W / 2, H / 2 - y * R

def inv(X, Y):
    x = (np.asarray(X) - W / 2) / R; y = (H / 2 - np.asarray(Y)) / R
    th = np.clip(y / A1, -TH_MAX, TH_MAX)
    for _ in range(12):
        t2 = th * th; t6 = t2 ** 3
        f = th * (A4 * t6 * t2 + A3 * t6 + A2 * t2 + A1) - y
        fp = 9 * A4 * t6 * t2 + 7 * A3 * t6 + 3 * A2 * t2 + A1
        th = np.clip(th - f / fp, -TH_MAX, TH_MAX)
    t2 = th * th; t6 = t2 ** 3
    fp = 9 * A4 * t6 * t2 + 7 * A3 * t6 + 3 * A2 * t2 + A1
    lam = 3 * x * fp / (2 * SQ3 * np.cos(th))
    phi = np.arcsin(np.clip(2 * np.sin(th) / SQ3, -1, 1))
    inside = (np.abs(lam) <= math.pi) & (np.abs(y) <= YMAX)
    return np.degrees(lam + LAM0), np.degrees(phi), inside

project = lambda g: transform(lambda x, y, z=None: fwd(x, y), g)

# ---------------------------------------------------------------- source shapes (same clean-up as prep.py)
def fix_antimeridian(geom):
    if geom['type'] not in ('Polygon', 'MultiPolygon'):
        return geom
    polys = [geom['coordinates']] if geom['type'] == 'Polygon' else geom['coordinates']
    if not any(abs(a[0] - b[0]) > 180 for poly in polys for ring in poly for a, b in zip(ring, ring[1:])):
        return geom
    parts = []
    for poly in polys:
        rings = []
        for ring in poly:
            out, shift = [], 0.0
            for i, (x, y) in enumerate(ring):
                if i and abs((x + shift) - out[-1][0]) > 180:
                    shift += 360 if out[-1][0] > x + shift else -360
                out.append((x + shift, y))
            rings.append(out)
        pg = Polygon(rings[0], rings[1:]).buffer(0)
        for k in (-1, 0, 1):
            piece = pg.intersection(box(-180 + 360 * k, -90, 180 + 360 * k, 90))
            if not piece.is_empty:
                parts.append(affinity.translate(piece, xoff=-360 * k))
    return mapping(unary_union(parts))

def shift_east(g):
    west = g.intersection(box(-180, -90, CUT, 90)); east = g.intersection(box(CUT, -90, 180, 90))
    return east if west.is_empty else unary_union([east, affinity.translate(west, xoff=360)])

countries = json.load(open(GEO + 'countries50.geojson'))['features']
seen = set()
for f in countries:
    f['id'] = f.get('id') or f['properties']['name']
    if f['id'] in seen:
        f['id'] = f['properties']['name']
    seen.add(f['id'])
    f['geometry'] = fix_antimeridian(f['geometry'])
for f in json.load(open(GEO + 'countries10.geojson'))['features']:
    if f.get('id') == '798':
        countries.append({'id': '798', 'properties': {'name': 'Tuvalu'}, 'geometry': fix_antimeridian(f['geometry'])})
byname = lambda n: next(f for f in countries if f['properties']['name'] == n)
byid = lambda i: next(f for f in countries if f['id'] == i)
def merge(into, name):
    a, b = byid(into), byname(name)
    a['geometry'] = mapping(shape(a['geometry']).buffer(0).union(shape(b['geometry']).buffer(0)).buffer(0.002).buffer(-0.002))
    countries.remove(b)
merge('196', 'N. Cyprus'); merge('706', 'Somaliland')
ru, ua = byid('643'), byid('804')
crimea_box = box(32.3, 44.2, 36.62, 46.3)
g_ru = shape(ru['geometry']).buffer(0)
crimea = g_ru.intersection(crimea_box)
ru['geometry'] = mapping(g_ru.difference(crimea_box))
ua['geometry'] = mapping(shape(ua['geometry']).buffer(0).union(crimea).buffer(0.002).buffer(-0.002))
# the world-atlas Antarctica lost its coastline; use the original Natural Earth outline
byname('Antarctica')['geometry'] = json.load(open(GEO + 'antarctica.geojson'))['geometry']
for f in countries:
    f['g'] = shift_east(shape(f['geometry']).buffer(0))

# ---------------------------------------------------------------- continents
REGION_IDS = {
    'AS': '158 156 392 410 408 496 344 446 704 418 116 764 104 458 702 360 608 096 626 356 586 050 524 064 144 462 398 860 795 417 762 '
          '364 004 792 196 268 051 031 368 760 422 376 275 400 682 887 512 784 634 048 414',
    'EU': '826 372 352 578 752 246 208 233 428 440 250 528 056 442 492 276 756 438 040 620 724 020 380 674 336 470 300 705 191 070 688 '
          '499 Kosovo 807 008 643 804 112 498 616 203 703 348 642 100',
    'AF': '012 818 434 504 729 788 204 854 132 384 270 288 324 624 430 466 478 562 566 686 694 768 024 120 140 148 178 180 226 266 678 '
          '108 174 262 232 231 404 450 454 480 508 646 690 706 728 834 800 894 716 072 748 426 516 710 732',
    'NA': '124 840 084 188 222 320 340 484 558 591 028 044 052 192 212 214 308 332 388 659 662 670 780 304 630',
    'SA': '032 068 076 152 170 218 328 600 604 740 858 862 238',
    'OC': '036 554 598 090 548 242 585 583 584 520 296 798 882 776 540 258',
}
CONT_OF = {i: k for k, ids in REGION_IDS.items() for i in ids.split()}

def continent_of(fid, poly):
    p = poly.representative_point(); lon, lat = p.x, p.y
    if lat < -60:
        return 'AN'
    if fid == '643':                                  # Russia: west of the Urals is Europe
        return 'EU' if lon < 60 else 'AS'
    if fid == '792':                                  # Türkiye: East Thrace is Europe
        return 'EU' if (lon < 29.6 and lat > 40.6) else 'AS'
    if fid in CONT_OF:
        c = CONT_OF[fid]
        if c == 'EU' and lat < 34:                    # French Guiana, Réunion, Canary Islands, Madeira...
            return locate(lon, lat)
        # Pacific outliers of other continents' countries (Hawaii) belong to Oceania
        if c != 'OC' and (lon > 180 or lon < -120) and -60 < lat < 30:
            return 'OC'
        return c
    return locate(lon, lat)

def locate(lon, lat):
    # territories and anything else: by location
    if lon > 180:                     # moved east of the cut: Pacific islands
        return 'OC'
    if lon < -25:
        return 'SA' if (lat < 11 and lon > -82) else 'NA'
    if (lon > 110 and lat < -10) or (lon > 130 and lat < 0):
        return 'OC'
    if lat > 36 and lon < 60:
        return 'EU'
    if lon < 52 and lat < 37 and not (lon > 34 and lat > 12):
        return 'AF'
    return 'AS'

cont_parts = {k: [] for k in ['AS', 'EU', 'AF', 'NA', 'SA', 'OC', 'AN', 'XX']}
for f in countries:
    for poly in (f['g'].geoms if hasattr(f['g'], 'geoms') else [f['g']]):
        if isinstance(poly, Polygon) and poly.area > 0:
            k = continent_of(f['id'], poly); lon = poly.representative_point().x
            # keep each continent on one side of the map edge: the western Aleutians and the eastern Pacific islands
            # (Hawaii, French Polynesia, Kiribati's Line Islands) stay on the map as plain land, outside the pieces
            lat = poly.representative_point().y
            if (k in ('NA', 'SA') and lon > 0) or (k == 'OC' and lon < 0) or (k in ('AF', 'AS', 'EU') and lat < -40):
                k = 'XX'   # Guam, Kerguelen, Prince Edward Is. ... stay as plain land
            cont_parts[k].append(poly)

def path_of(geom, prec=1):
    def ring(coords):
        return 'M' + 'L'.join(f"{x:.{prec}f} {y:.{prec}f}" for x, y in coords[:-1]) + 'Z'
    out = []
    for p in (geom.geoms if isinstance(geom, MultiPolygon) else [geom]):
        out.append(ring(list(p.exterior.coords)))
        out += [ring(list(r.coords)) for r in p.interiors]
    return ''.join(out)

def entry(fid, name, g, target, tol, min_area, pool=None, ctx=None):
    gp = project(g.segmentize(1.0)).simplify(tol, preserve_topology=True)
    polys = [p for p in (gp.geoms if hasattr(gp, 'geoms') else [gp]) if isinstance(p, Polygon) and p.area >= min_area]
    if not polys:
        return None, None
    gp = MultiPolygon(polys)
    rp = max(polys, key=lambda p: p.area).representative_point()
    x0, y0, x1, y1 = gp.bounds
    e = {'id': fid, 'name': name, 'target': target, 'd': path_of(gp),
         'bbox': [round(x0, 1), round(y0, 1), round(x1 - x0, 1), round(y1 - y0, 1)], 'label': [round(rp.x, 1), round(rp.y, 1)], 'ctx': ctx}
    if pool is not None:
        e['pool'] = pool
    return e, gp

# ---------------------------------------------------------------- shared raster
def terrain(land_polys, name):
    TW, TH = int(round(W * S)), int(round(H * S))
    uu, vv = np.meshgrid((np.arange(TW) + 0.5) / S, (np.arange(TH) + 0.5) / S)
    LON, LAT, inside = inv(uu, vv)
    LON = (LON + 180) % 360 - 180
    def sample(img, order=1):
        a = np.asarray(img, dtype=np.float32); h, w = a.shape[:2]
        col = (LON + 180) / 360 * w - 0.5; row = (90 - LAT) / 180 * h - 0.5
        if a.ndim == 2:
            return ndimage.map_coordinates(a, [row, col], order=order, mode='nearest')
        return np.stack([ndimage.map_coordinates(a[..., k], [row, col], order=order, mode='nearest') for k in range(3)], -1)
    rgb = sample(Image.open(GEO + 'etopo1.jpg').convert('RGB'), 3)
    srl = sample(Image.open(GEO + 'shadedrelief.jpg').convert('L'), 3)
    bm = sample(Image.open(GEO + 'node_modules/three-globe/example/img/earth-topology.png').convert('L'), 1)
    mask_img = Image.new('L', (TW, TH), 0); dr = ImageDraw.Draw(mask_img)
    for gp in land_polys:
        for p in gp.geoms:
            dr.polygon([(x * S, y * S) for x, y in p.exterior.coords], fill=255)
            for r in p.interiors:
                dr.polygon([(x * S, y * S) for x, y in r.coords], fill=0)
    mask = np.asarray(mask_img) > 0
    mask_d = ndimage.binary_dilation(mask, iterations=4)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    bluish = (b - np.minimum(r, g)) > 14
    sea_like = bluish & ((b > np.maximum(r, g) - 4) | ((b > 170) & (g > 170) & (r > 150) & (b > r)))
    valid = mask & ~sea_like
    ind = ndimage.distance_transform_edt(~valid, return_distances=False, return_indices=True)
    filled = rgb[ind[0], ind[1]]
    blur = ndimage.gaussian_filter(srl, 6)
    detail = np.clip(srl / np.maximum(blur, 1), 0.6, 1.5) ** 0.7
    out = np.clip(filled * detail[..., None], 0, 255)
    gray = out.mean(axis=2, keepdims=True)
    out = np.clip(gray + (out - gray) * 1.18, 0, 255)
    out[~mask_d] = [120, 190, 200]
    img = Image.fromarray(out.astype(np.uint8))
    img.save(os.path.join(OUT, f'terrain_preview_{name}.png'))
    img.save(os.path.join(OUT, f'{name}.jpg'), 'JPEG', quality=78, optimize=True, progressive=True)
    vals, cols = bm[valid], filled[valid]
    qs = np.quantile(vals, [0, .35, .6, .8, .93, .985, 1]); legend = []
    for i in range(6):
        m = (vals >= qs[i]) & (vals <= qs[i + 1])
        cc = np.median(cols[m], axis=0); cc = np.clip(cc.mean() + (cc - cc.mean()) * 1.18, 0, 255)
        legend.append('#%02x%02x%02x' % tuple(int(v) for v in cc))
    return legend

def outline_path():
    pts = [fwd(CUT + 360 - 1e-6, lat) for lat in np.linspace(-90, 90, 181)] + [fwd(CUT + 1e-6, lat) for lat in np.linspace(90, -90, 181)]
    return 'M' + 'L'.join(f'{float(x):.1f} {float(y):.1f}' for x, y in pts) + 'Z'

def rivers():
    out = []
    for f in json.load(open(GEO + 'rivers50.geojson'))['features']:
        if f['geometry'] is None or (f['properties'].get('scalerank', 9) or 9) > 4:
            continue
        gp = project(shift_east(shape(f['geometry'])).segmentize(1.0)).simplify(0.6)
        for ln in (gp.geoms if hasattr(gp, 'geoms') else [gp]):
            if isinstance(ln, LineString) and ln.length >= 3:
                out.append('M' + 'L'.join(f"{x:.1f} {y:.1f}" for x, y in ln.coords))
    return ''.join(out)

PROJ = {'type': 'ee', 'R': R, 'lam0': LAM0, 'W': W, 'H': H, 'cut': CUT}
VIEW = [0.0, 0.0, round(W, 1), round(H, 1)]
riv = rivers(); outline = outline_path()

# ---------------------------------------------------------------- level: world (country pool)
items, polys_all = [], []
for f in countries:
    if f['g'].is_empty:
        continue
    e, gp = entry(f['id'], f['properties']['name'], f['g'], False, 0.25, 0.4)
    if not e:
        continue
    w_, h_ = e['bbox'][2], e['bbox'][3]
    # pool: big enough to grab on a world map, and not spread over half the map (Kiribati)
    e['pool'] = bool(min(w_, h_) >= 6 and w_ < W * 0.35 and f['id'] not in ('010',))
    items.append(e); polys_all.append(gp)
legend = terrain(polys_all, 'world')
json.dump({'W': round(W, 1), 'H': round(H, 1), 'S': S, 'countries': items, 'proj': PROJ, 'view': VIEW, 'outline': outline,
           'riversMajor': riv, 'riversMinor': '', 'legend': legend, 'pickN': 20},
          open(os.path.join(OUT, 'world.json'), 'w'), separators=(',', ':'))
print('world', round(W), round(H), 'countries', len(items), 'pool', sum(1 for e in items if e['pool']))

# ---------------------------------------------------------------- level: cont (7 continents + 3 oceans)
NAMES = {'AS': 'Asia', 'EU': 'Europe', 'AF': 'Africa', 'NA': 'North America', 'SA': 'South America', 'OC': 'Oceania', 'AN': 'Antarctica', 'XX': 'other land'}
items, polys_all = [], []
for k, parts in cont_parts.items():
    g = unary_union([p.buffer(0.02) for p in parts]).buffer(-0.02)
    e, gp = entry(k, NAMES[k], g, k != 'XX', 0.35, 0.6 if k == 'XX' else 2.0)
    if e:
        items.append(e); polys_all.append(gp)

# ocean map: flood-fill the sea on a 0.25° grid, with barriers along the usual ocean boundaries
G = 4                                       # cells per degree
GW, GH = 360 * G, 180 * G
def gx(lon): return (lon - CUT) * G
def gy(lat): return (90 - lat) * G
land = Image.new('L', (GW, GH), 0); dl = ImageDraw.Draw(land)
for parts in cont_parts.values():
    for p in parts:   # all land, the background islands included
        dl.polygon([(gx(x), gy(y)) for x, y in p.exterior.coords], fill=255)
land_arr = np.asarray(land) > 0
land_arr[: int(gy(66.5)), :] = True                                   # the Arctic is not one of the three oceans
land_im = Image.fromarray((land_arr * 255).astype(np.uint8)); bar = ImageDraw.Draw(land_im)
def wall(pts, wdt=3):
    bar.line([(gx(x), gy(y)) for x, y in pts], fill=255, width=wdt)
wall([(20.0, -34.8), (20.0, -90)])                                    # Cape Agulhas: Atlantic | Indian
wall([(146.8, -43.6), (146.8, -90)])                                  # Tasmania: Indian | Pacific
wall([(146.3, -38.7), (146.9, -41.3)])                                # Bass Strait
wall([(-68.6, -52.3), (-68.6, -90)])                                  # Cape Horn / Magellan: Pacific | Atlantic
wall([(103.9, 1.9), (104.2, 1.0), (104.2, -3.0), (105.8, -5.9), (106.0, -9.0), (127.5, -9.0), (130.3, -13.2)], 4)   # Indonesia: Indian | Pacific
water = ~(np.asarray(land_im) > 0)
lab, n = ndimage.label(water)
# the map edges meet on the globe: join components across the left/right edge
parent = list(range(n + 1))
def find(a):
    while parent[a] != a:
        parent[a] = parent[parent[a]]; a = parent[a]
    return a
for row in range(GH):
    a, b = lab[row, 0], lab[row, -1]
    if a and b:
        parent[find(a)] = find(b)
def comp_at(lon, lat):
    return find(lab[int(gy(lat)), int(gx(lon))])
OCEAN_SEEDS = {'P': [(-140, 0), (170, 0)], 'A': [(-30, 0), (-40, 35)], 'I': [(75, -20)]}
code_of = {}
for code, seeds in OCEAN_SEEDS.items():
    for lon, lat in seeds:
        c = comp_at(lon, lat); assert c, (code, lon, lat)
        code_of[c] = code
seed_comps = {code: {comp_at(lo, la) for lo, la in seeds} for code, seeds in OCEAN_SEEDS.items()}
for a in seed_comps:
    for b in seed_comps:
        assert a == b or not (seed_comps[a] & seed_comps[b]), f'oceans {a} and {b} leaked into each other'
assert len(seed_comps['P']) == 1, 'the two halves of the Pacific are not joined across the map edge'
# grid in map units for the page
STEP = 8
cols, rows = int(math.ceil(W / STEP)), int(math.ceil(H / STEP))
cx, cy = np.meshgrid((np.arange(cols) + .5) * STEP, (np.arange(rows) + .5) * STEP)
LON, LAT, inside = inv(cx, cy)
LONs = np.where(LON < CUT, LON + 360, LON); LONs = np.where(LONs >= CUT + 360, LONs - 360, LONs)
ix = np.clip(((LONs - CUT) * G).astype(int), 0, GW - 1); iy = np.clip(((90 - LAT) * G).astype(int), 0, GH - 1)
labs = lab[iy, ix]
grid = []
for r_ in range(rows):
    line = []
    for c_ in range(cols):
        l = labs[r_, c_]
        line.append(code_of.get(find(l), '.') if (inside[r_, c_] and l) else '.')
    grid.append(''.join(line))
anchors = {'P': [(-150, 10), (-120, -28), (165, 22), (175, -28)], 'A': [(-40, 30), (-15, -22)], 'I': [(78, -18)]}
labels = [{'id': code, 'code': code, 'at': [[round(float(v), 1) for v in fwd(lon if lon >= CUT else lon + 360, lat)] for lon, lat in pts]}
          for code, pts in anchors.items()]
legend = terrain(polys_all, 'cont')
json.dump({'W': round(W, 1), 'H': round(H, 1), 'S': S, 'countries': items, 'proj': PROJ, 'view': VIEW, 'outline': outline,
           'riversMajor': riv, 'riversMinor': '', 'legend': legend,
           'oceans': labels, 'oceanGrid': {'step': STEP, 'cols': cols, 'rows': rows, 'data': grid}},
          open(os.path.join(OUT, 'cont.json'), 'w'), separators=(',', ':'))
cnt = {k: sum(r_.count(k) for r_ in grid) for k in 'PAI.'}
print('cont', round(W), round(H), [(e['id'], e['bbox']) for e in items], 'ocean cells', cnt)
