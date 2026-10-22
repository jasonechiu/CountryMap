"""Build one region's puzzle data: projected country paths, rivers, terrain image.

usage: prep.py OUTDIR REGION      (REGION is a key of REGIONS below)
writes OUTDIR/<region>.json, OUTDIR/<region>.jpg and OUTDIR/terrain_preview_<region>.png
"""
import json, math, io, sys
import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import shape, box, mapping, MultiPolygon, Polygon, LineString
from shapely.ops import transform
from scipy import ndimage

GEO = '/root/geo/'
OUT = sys.argv[1]
REGION = sys.argv[2] if len(sys.argv) > 2 else 'sea'

REGIONS = {
    # ---- Asia (plate carrée with a standard parallel)
    'ea': dict(box=(73.0, 147.0, 17.0, 54.0), clat=36,
               targets=['158', '156', '392', '410', '408', '496', '344', '446'],
               ctx={'643': 'RU', '356': 'IN', '398': 'KZ', '104': 'MM', '704': 'VN', '608': 'PH'}),
    'sea': dict(box=(88.0, 146.0, -13.0, 29.0), clat=10,
                targets=['704', '418', '116', '764', '104', '458', '702', '360', '608', '096', '626'],
                ctx={'156': 'CN', '356': 'IN', '158': 'TW', '598': 'PG', '036': 'AU', '050': 'BD'}),
    'sa': dict(box=(59.0, 99.0, -2.0, 38.0), clat=18,
               targets=['356', '586', '050', '524', '064', '144', '462'],
               ctx={'156': 'CN', '004': 'AF', '364': 'IR', '104': 'MM', '762': 'TJ'}),
    'ca': dict(box=(45.0, 89.0, 34.0, 56.0), clat=45,
               targets=['398', '860', '795', '417', '762'],
               ctx={'643': 'RU', '156': 'CN', '364': 'IR', '004': 'AF', '496': 'MN', '031': 'AZ'}),
    'wa': dict(box=(25.0, 76.0, 11.0, 43.5), clat=27,
               targets=['364', '004', '792', '196', '268', '051', '031', '368', '760', '422', '376', '275',
                        '400', '682', '887', '512', '784', '634', '048', '414'],
               ctx={'818': 'EG', '586': 'PK', '643': 'RU', '795': 'TM', '729': 'SD', '300': 'GR'}),
    # ---- Europe (Lambert conformal conic: meridians converge northward, so high latitudes are not stretched)
    'ne': dict(box=(-25.0, 32.0, 49.5, 71.5), proj='lcc', par=(54, 68),
               targets=['826', '372', '352', '578', '752', '246', '208', '233', '428', '440'],
               ctx={'643': 'RU', '112': 'BY', '616': 'PL', '276': 'DE', '250': 'FR', '528': 'NL'}),
    'we': dict(box=(-5.5, 17.5, 41.2, 55.3), proj='lcc', par=(44, 53),
               targets=['250', '528', '056', '442', '492', '276', '756', '438', '040'],
               ctx={'826': 'GB', '380': 'IT', '724': 'ES', '203': 'CZ', '616': 'PL', '208': 'DK'}),
    'se': dict(box=(-10.0, 29.0, 34.6, 47.2), proj='lcc', par=(37, 45),
               targets=['620', '724', '020', '380', '674', '336', '470', '300', '705', '191', '070', '688',
                        '499', 'Kosovo', '807', '008'],
               ctx={'250': 'FR', '756': 'CH', '040': 'AT', '348': 'HU', '642': 'RO', '100': 'BG', '792': 'TR',
                    '012': 'DZ', '788': 'TN', '504': 'MA'}),
    'ee': dict(box=(12.0, 60.0, 41.0, 70.0), proj='lcc', par=(47, 63),
               targets=['643', '804', '112', '498', '616', '203', '703', '348', '642', '100'],
               ctx={'276': 'DE', '040': 'AT', '688': 'RS', '792': 'TR', '398': 'KZ', '268': 'GE', '246': 'FI',
                    '440': 'LT', '428': 'LV', '233': 'EE', '752': 'SE'},
               split={'643': 60.0}),   # Russia: only the European part (west of ~60°E, the Urals) is a piece
    # ---- Africa (UN geoscheme)
    'naf': dict(box=(-18.0, 38.0, 14.0, 38.0), clat=26,
                targets=['012', '818', '434', '504', '729', '788'],
                ctx={'732': 'EH', '562': 'NE', '466': 'ML', '148': 'TD', '728': 'SS', '682': 'SAU', '724': 'ES', '380': 'IT', '231': 'ET'}),
    'waf': dict(box=(-26.0, 17.0, 3.0, 28.0), clat=14,
                targets=['204', '854', '132', '384', '270', '288', '324', '624', '430', '466', '478', '562', '566', '686', '694', '768'],
                ctx={'012': 'DZ', '148': 'TD', '120': 'CM', '732': 'EH', '504': 'MA', '434': 'LY'}),
    'caf': dict(box=(6.0, 33.0, -19.0, 24.0), clat=3,
                targets=['024', '120', '140', '148', '178', '180', '226', '266', '678'],
                ctx={'566': 'NG', '729': 'SD', '728': 'SS', '800': 'UG', '834': 'TZ', '894': 'ZM', '516': 'NA', '562': 'NE', '434': 'LY'}),
    'eaf': dict(box=(20.0, 60.0, -27.0, 19.0), clat=-4,
                targets=['108', '174', '262', '232', '231', '404', '450', '454', '480', '508', '646', '690', '706', '728', '834', '800', '894', '716'],
                ctx={'180': 'CD', '024': 'AO', '729': 'SD', '682': 'SAU', '887': 'YE', '516': 'NA', '072': 'BW', '710': 'ZA', '818': 'EG'}),
    'saf': dict(box=(10.0, 34.0, -35.5, -16.5), clat=-26,
                targets=['072', '748', '426', '516', '710'],
                ctx={'024': 'AO', '894': 'ZM', '716': 'ZW', '508': 'MZ', '450': 'MG'}),
    # ---- Americas (UN geoscheme)
    'nam': dict(box=(-170.0, -50.0, 24.0, 75.0), proj='lcc', par=(35, 65), tol=0.35,
                targets=['124', '840'],
                ctx={'304': 'GL', '484': 'MX', '192': 'CU', '643': 'RU'}),
    'cam': dict(box=(-118.0, -77.0, 6.5, 33.0), clat=19,
                targets=['084', '188', '222', '320', '340', '484', '558', '591'],
                ctx={'840': 'US', '192': 'CU', '170': 'CO', '388': 'JM'}),
    'car': dict(box=(-86.0, -59.0, 9.5, 27.5), clat=18,
                targets=['028', '044', '052', '192', '212', '214', '308', '332', '388', '659', '662', '670', '780'],
                ctx={'840': 'US', '484': 'MX', '862': 'VE', '170': 'CO', '591': 'PA', '630': 'PR', '558': 'NI', '340': 'HN'}),
    'sam': dict(box=(-82.0, -34.0, -56.0, 13.0), clat=-20,
                targets=['032', '068', '076', '152', '170', '218', '328', '600', '604', '740', '858', '862'],
                ctx={'591': 'PA', '238': 'FK', '188': 'CR'}),
    # ---- Oceania: one region; it straddles the 180° meridian, so longitudes run 110..215
    'oc': dict(box=(110.0, 215.0, -48.0, 12.0), clat=-18, wrap=True,
               targets=['036', '554', '598', '090', '548', '242', '585', '583', '584', '520', '296', '798', '882', '776'],
               ctx={'360': 'ID', '626': 'TL', '608': 'PH', '540': 'NC', '258': 'PF'}),
}
CFG = REGIONS[REGION]
CORE = CFG['box']
TARGET = CFG['targets']
CONTEXT_LABEL = CFG['ctx']
K = 20.0          # map units per degree of latitude
S = 2             # terrain pixels per map unit
MIN_ASPECT = 1.9  # map width / height, at least as wide as a wide laptop screen's map area
TINY = {'702', '462', '344', '446', '048', '336', '492', '674', '438', '020', '470'}   # keep every islet
# places only a few km across, swollen (map units) so they can be seen and grabbed
SWELL = {'446': 0.9, '048': 0.9, '336': 2.4, '492': 2.0, '674': 1.6, '438': 1.3, '020': 1.1, '470': 0.9}


# ---------------------------------------------------------------- projections
class Equirect:
    PAD_LON, PAD_LAT = 14.0, 5.0
    def __init__(self):
        self.lon0, self.lon1 = CORE[0] - self.PAD_LON, CORE[1] + self.PAD_LON
        self.lat0, self.lat1 = CORE[2] - self.PAD_LAT, CORE[3] + self.PAD_LAT
        self.kx = K * math.cos(math.radians(CFG['clat']))
        self.W, self.H = (self.lon1 - self.lon0) * self.kx, (self.lat1 - self.lat0) * K
        if self.W < MIN_ASPECT * self.H:      # tall region: add terrain at the sides so a wide screen still shows its full height
            extra = (MIN_ASPECT * self.H - self.W) / 2 / self.kx
            self.lon0 -= extra; self.lon1 += extra
            self.W = (self.lon1 - self.lon0) * self.kx
        self.clip = box(self.lon0 - 1, max(-89, self.lat0 - 1), self.lon1 + 1, min(89, self.lat1 + 1))
    def fwd(self, lon, lat):
        return (np.asarray(lon) - self.lon0) * self.kx, (self.lat1 - np.asarray(lat)) * K
    def inv(self, x, y):
        return self.lon0 + np.asarray(x) / self.kx, self.lat1 - np.asarray(y) / K
    def js(self):
        return {'type': 'eq', 'lon0': self.lon0, 'lat1': self.lat1, 'kx': round(self.kx, 5), 'ky': K}

class LCC:
    PAD_X, PAD_Y = 9.0, 4.5          # margins around the core box, in degrees of latitude
    def __init__(self):
        p1, p2 = (math.radians(v) for v in CFG['par'])
        self.lam0 = math.radians((CORE[0] + CORE[1]) / 2)
        phi0 = math.radians((CORE[2] + CORE[3]) / 2)
        t = lambda p: math.tan(math.pi / 4 + p / 2)
        self.n = math.log(math.cos(p1) / math.cos(p2)) / math.log(t(p2) / t(p1))
        self.F = math.cos(p1) * t(p1) ** self.n / self.n
        self.R = K * 180 / math.pi
        self.rho0 = self.R * self.F / t(phi0) ** self.n
        # map rectangle = projected core box (sampled along its edges) plus margins
        lons = np.linspace(CORE[0], CORE[1], 200); lats = np.linspace(CORE[2], CORE[3], 200)
        ex = np.concatenate([lons, lons, np.full(200, CORE[0]), np.full(200, CORE[1])])
        ey = np.concatenate([np.full(200, CORE[2]), np.full(200, CORE[3]), lats, lats])
        rx, ry = self._raw(ex, ey)
        self.core_rect = (rx.min(), rx.max(), ry.min(), ry.max())
        self.xmin, self.xmax = rx.min() - self.PAD_X * K, rx.max() + self.PAD_X * K
        self.ymin, self.ymax = ry.min() - self.PAD_Y * K, ry.max() + self.PAD_Y * K
        self.W, self.H = self.xmax - self.xmin, self.ymax - self.ymin
        if self.W < MIN_ASPECT * self.H:
            extra = (MIN_ASPECT * self.H - self.W) / 2
            self.xmin -= extra; self.xmax += extra
            self.W = self.xmax - self.xmin
        self.clip = box(CORE[0] - 55, max(-80, CORE[2] - 12), CORE[1] + 55, min(84, CORE[3] + 14))
    def _raw(self, lon, lat):
        phi = np.radians(np.asarray(lat, dtype=float)); lam = np.radians(np.asarray(lon, dtype=float))
        rho = self.R * self.F / np.tan(np.pi / 4 + phi / 2) ** self.n
        th = self.n * (lam - self.lam0)
        return rho * np.sin(th), self.rho0 - rho * np.cos(th)
    def fwd(self, lon, lat):
        x, y = self._raw(lon, lat)
        return x - self.xmin, self.ymax - y
    def inv(self, x, y):
        rx = np.asarray(x) + self.xmin; ry = self.ymax - np.asarray(y)
        rho = np.sign(self.n) * np.hypot(rx, self.rho0 - ry)
        th = np.arctan2(rx, self.rho0 - ry)
        lam = self.lam0 + th / self.n
        phi = 2 * np.arctan((self.R * self.F / rho) ** (1 / self.n)) - np.pi / 2
        return np.degrees(lam), np.degrees(phi)
    def js(self):
        return {'type': 'lcc', 'n': self.n, 'F': self.F, 'R': self.R, 'rho0': self.rho0,
                'lam0': self.lam0, 'xmin': self.xmin, 'ymax': self.ymax}

P = LCC() if CFG.get('proj') == 'lcc' else Equirect()
W, H = P.W, P.H
if isinstance(P, LCC):
    _x0, _x1, _y0, _y1 = P.core_rect
    VIEW = (_x0 - P.xmin, P.ymax - _y1, _x1 - _x0, _y1 - _y0)
else:
    (_vx, _vy), (_vx1, _vy1) = P.fwd(CORE[0], CORE[3]), P.fwd(CORE[1], CORE[2])
    VIEW = (float(_vx), float(_vy), float(_vx1 - _vx), float(_vy1 - _vy))
# a piece keeps only the islands inside the opening view (Azores, Madeira, Canaries, Svalbard... are left out)
CORE_AREA = box(VIEW[0] - 30, VIEW[1] - 30, VIEW[0] + VIEW[2] + 30, VIEW[1] + VIEW[3] + 30)
view = box(0, 0, W, H)
project = lambda g: transform(lambda x, y, z=None: P.fwd(x, y), g)

def path_of(geom, prec=1):
    def ring(coords):
        return 'M' + 'L'.join(f"{x:.{prec}f} {y:.{prec}f}" for x, y in coords[:-1]) + 'Z'
    out = []
    for p in (geom.geoms if isinstance(geom, MultiPolygon) else [geom]):
        out.append(ring(list(p.exterior.coords)))
        out += [ring(list(r.coords)) for r in p.interiors]
    return ''.join(out)

def densify(g, step=0.5):
    """add points along long straight edges (clip lines) so they curve correctly in a conic projection"""
    return g.segmentize(step) if hasattr(g, 'segmentize') else g


# ---------------------------------------------------------------- countries
from shapely import affinity
from shapely.ops import unary_union

def fix_antimeridian(geom):
    """rings that jump across the 180° meridian turn planar polygons inside-out: unwrap them, then fold back"""
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

countries = json.load(open(GEO + 'countries50.geojson'))['features']
seen = set()
for f in countries:
    f['id'] = f.get('id') or f['properties']['name']
    if f['id'] in seen:                 # e.g. Ashmore and Cartier Is. share Australia's id: keep it as background land
        f['id'] = f['properties']['name']
    seen.add(f['id'])
    f['geometry'] = fix_antimeridian(f['geometry'])
# Tuvalu is missing from the 1:50m data
for f in json.load(open(GEO + 'countries10.geojson'))['features']:
    if f.get('id') == '798':
        countries.append({'id': '798', 'properties': {'name': 'Tuvalu'}, 'geometry': fix_antimeridian(f['geometry'])})
byname = lambda n: next(f for f in countries if f['properties']['name'] == n)
byid = lambda i: next(f for f in countries if f['id'] == i)

# tiny places: take the full shape from the 1:10m data
DETAIL = {f['id']: f['geometry'] for f in json.load(open(GEO + 'countries10.geojson'))['features']
          if f.get('id') in ('462', '344', '446', '048', '336', '492', '674', '438', '020', '470')}
for f in countries:
    if f['id'] in DETAIL and shape(DETAIL[f['id']]).buffer(0).area > 0:   # the 1:10m Vatican is degenerate; keep 1:50m then
        f['geometry'] = DETAIL[f['id']]
# Northern Cyprus is drawn as its own unit; the piece is the whole island of Cyprus
cy, ncy = byid('196'), byname('N. Cyprus')
cy['geometry'] = mapping(shape(cy['geometry']).union(shape(ncy['geometry'])).buffer(0.001).buffer(-0.001))
countries.remove(ncy)
# Somaliland is drawn as its own unit; the piece is the whole of Somalia (as recognised by the UN)
so, sl = byid('706'), byname('Somaliland')
so['geometry'] = mapping(shape(so['geometry']).buffer(0).union(shape(sl['geometry']).buffer(0)).buffer(0.002).buffer(-0.002))
countries.remove(sl)
# Crimea: the source draws it in Russia; follow the UN General Assembly position and draw it in Ukraine
ru, ua = byid('643'), byid('804')
crimea_box = box(32.3, 44.2, 36.62, 46.3)
g_ru = shape(ru['geometry']).buffer(0)
crimea = g_ru.intersection(crimea_box)
ru['geometry'] = mapping(g_ru.difference(crimea_box))
ua['geometry'] = mapping(shape(ua['geometry']).buffer(0).union(crimea).buffer(0.002).buffer(-0.002))
# a region across the 180° meridian: move the western hemisphere 360° east so the Pacific is contiguous
def shift_east(geom, cut=-20.0):
    g = shape(geom).buffer(0) if geom['type'] in ('Polygon', 'MultiPolygon') else shape(geom)
    west = g.intersection(box(-180, -90, cut, 90)); east = g.intersection(box(cut, -90, 180, 90))
    if west.is_empty:
        return geom
    return mapping(unary_union([east, affinity.translate(west, xoff=360)]) if geom['type'] in ('Polygon', 'MultiPolygon')
                   else unary_union([east, affinity.translate(west, xoff=360)]))
if CFG.get('wrap'):
    for f in countries:
        f['geometry'] = shift_east(f['geometry'])
# split a huge country: the piece is the part west of the given meridian, the rest stays as background land
for cid, lon_cut in CFG.get('split', {}).items():
    f = byid(cid); g = shape(f['geometry']).buffer(0)
    west, east = g.intersection(box(-180, -90, lon_cut, 90)), g.intersection(box(lon_cut, -90, 180, 90))
    f['geometry'] = mapping(west)
    countries.append({'id': cid + '-rest', 'properties': {'name': f['properties']['name'] + ' (rest)'}, 'geometry': mapping(east)})

out_c, land_polys = [], []
for f in countries:
    g = shape(f['geometry'])
    if not g.is_valid:
        g = g.buffer(0)
    if g.is_empty or not g.intersects(P.clip):
        continue
    g = densify(g.intersection(P.clip))
    gp = project(g)
    is_t = f['id'] in TARGET
    tiny_state = is_t and gp.area < 9 and f['id'] not in SWELL and f['id'] != '462'
    if f['id'] in SWELL:
        gp = gp.buffer(SWELL[f['id']]).simplify(0.15)
    elif tiny_state:
        gp = gp.buffer(1.3).simplify(0.15)   # island states a few km across (Nauru, Tuvalu, St Kitts, Seychelles...)
    elif f['id'] == '462':
        # Maldives: join the islets into one continuous chain you can see and grab
        gp = gp.buffer(4.0).buffer(-1.6)
        gp = MultiPolygon([Polygon(q.exterior) for q in (gp.geoms if hasattr(gp, 'geoms') else [gp])]).simplify(0.3)
    else:
        gp = gp.simplify(CFG.get('tol', 0.12) if is_t else max(0.35, CFG.get('tol', 0)), preserve_topology=True)
    if not is_t:
        gp = gp.intersection(view.buffer(4))
    polys = [p for p in (gp.geoms if hasattr(gp, 'geoms') else [gp]) if isinstance(p, Polygon)]
    min_area = 0.15 if is_t else 1.5
    polys = [p for p in polys if p.area >= min_area or (is_t and (f['id'] in TINY or tiny_state))]
    if is_t and polys:
        near = [p for p in polys if CORE_AREA.contains(p.representative_point())]
        polys = near or [max(polys, key=lambda p: p.area)]
    if not polys:
        continue
    gp = MultiPolygon(polys)
    land_polys.append(gp)
    rp = max(polys, key=lambda p: p.area).representative_point()
    x0, y0, x1, y1 = gp.bounds
    out_c.append({'id': f['id'], 'name': f['properties']['name'], 'target': is_t,
                  'd': path_of(gp), 'bbox': [round(x0, 1), round(y0, 1), round(x1 - x0, 1), round(y1 - y0, 1)],
                  'label': [round(rp.x, 1), round(rp.y, 1)], 'ctx': CONTEXT_LABEL.get(f['id'])})
missing = [t for t in TARGET if t not in {c['id'] for c in out_c}]
assert not missing, f'targets missing from the map: {missing}'

# ---------------------------------------------------------------- rivers
riv_major, riv_minor = [], []
for f in json.load(open(GEO + 'rivers50.geojson'))['features']:
    if f['geometry'] is None:
        continue
    g = shape(shift_east(f['geometry'])) if CFG.get('wrap') else shape(f['geometry'])
    if not g.intersects(P.clip):
        continue
    gp = project(densify(g.intersection(P.clip))).intersection(view.buffer(4)).simplify(0.4)
    sr = f['properties'].get('scalerank', 9) or 9
    for ln in (gp.geoms if hasattr(gp, 'geoms') else [gp]):
        if isinstance(ln, LineString) and ln.length >= 3:
            (riv_major if sr <= 5 else riv_minor).append('M' + 'L'.join(f"{x:.1f} {y:.1f}" for x, y in ln.coords))

# ---------------------------------------------------------------- terrain raster
TW, TH = int(round(W * S)), int(round(H * S))
uu, vv = np.meshgrid((np.arange(TW) + 0.5) / S, (np.arange(TH) + 0.5) / S)
LON, LAT = P.inv(uu, vv)
LON = (LON + 180) % 360 - 180

def sample(img, order=1):
    """sample a global plate-carrée image at every output pixel"""
    a = np.asarray(img, dtype=np.float32)
    h, w = a.shape[:2]
    col = (LON + 180) / 360 * w - 0.5
    row = (90 - LAT) / 180 * h - 0.5
    if a.ndim == 2:
        return ndimage.map_coordinates(a, [row, col], order=order, mode='nearest')
    return np.stack([ndimage.map_coordinates(a[..., k], [row, col], order=order, mode='nearest') for k in range(a.shape[2])], -1)

rgb = sample(Image.open(GEO + 'etopo1.jpg').convert('RGB'), order=3)
srl = sample(Image.open(GEO + 'shadedrelief.jpg').convert('L'), order=3)
bm = sample(Image.open(GEO + 'node_modules/three-globe/example/img/earth-topology.png').convert('L'), order=1)

mask_img = Image.new('L', (TW, TH), 0)
dr = ImageDraw.Draw(mask_img)
for gp in land_polys:
    for p in gp.geoms:
        dr.polygon([(x * S, y * S) for x, y in p.exterior.coords], fill=255)
        for r in p.interiors:
            dr.polygon([(x * S, y * S) for x, y in r.coords], fill=0)
mask = np.asarray(mask_img) > 0
mask_d = ndimage.binary_dilation(mask, iterations=4)

r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
bluish = (b - np.minimum(r, g)) > 14          # white or grey ice is not water
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
terr_img = Image.fromarray(out.astype(np.uint8))
terr_img.save(OUT + f'/terrain_preview_{REGION}.png')
terr_img.save(OUT + f'/{REGION}.jpg', 'JPEG', quality=80, optimize=True, progressive=True)

# legend: land colours ordered by an elevation proxy
vals, cols = bm[valid], filled[valid]
qs = np.quantile(vals, [0, .35, .6, .8, .93, .985, 1])
legend = []
for i in range(6):
    m = (vals >= qs[i]) & (vals <= qs[i + 1])
    cc = np.median(cols[m], axis=0)
    cc = np.clip(cc.mean() + (cc - cc.mean()) * 1.18, 0, 255)
    legend.append('#%02x%02x%02x' % tuple(int(v) for v in cc))

vx, vy, vw, vh = VIEW
data = {'W': round(W, 1), 'H': round(H, 1), 'S': S, 'countries': out_c, 'proj': P.js(),
        'view': [round(float(v), 1) for v in (vx, vy, vw, vh)],
        'riversMajor': ''.join(riv_major), 'riversMinor': ''.join(riv_minor), 'legend': legend}
json.dump(data, open(OUT + f'/{REGION}.json', 'w'), separators=(',', ':'))
import os
print(REGION, 'W,H', round(W), round(H), 'jpeg KB', os.path.getsize(OUT + f'/{REGION}.jpg') // 1024,
      'json KB', os.path.getsize(OUT + f'/{REGION}.json') // 1024,
      'small pieces', [(c['name'], c['bbox'][2:]) for c in out_c if c['target'] and min(c['bbox'][2:]) < 12])
