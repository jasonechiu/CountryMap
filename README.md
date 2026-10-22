# 東南亞地形拼圖

給國中生認識東南亞 11 國的網頁拼圖遊戲。把右邊的國家拼圖拖到地圖上的虛線國界位置，放對會吸附並跳出國旗與首都小卡。

## 怎麼玩

- 直接用瀏覽器打開 `index.html`，不需要安裝任何東西。
- 按住拼圖拖到地圖上；放錯會彈回，可以再試。
- 第一次就放對得 3 分，第二次 2 分，第三次 1 分。
- 滾輪可以放大地圖，新加坡、汶萊這類小國比較好放。
- 右上角可以切換中文／English、開關音效。
- 快捷鍵：`R` 重新開始、`L` 切換語言、`Esc` 關閉國家小卡。
- 最佳紀錄和放錯過的國家存在瀏覽器裡，下一局會先出現放錯過的國家。

## 用 GitHub Pages 上線

到 repository 的 **Settings → Pages**，Source 選 `Deploy from a branch`，Branch 選 `main`、資料夾選 `/ (root)`。幾分鐘後就能用 `https://<帳號>.github.io/<repository 名稱>/` 開來玩。

## 檔案

| 檔案 | 用途 |
| --- | --- |
| `index.html` | 遊戲本身，地圖、地形圖和國旗都已內嵌，單一檔案即可執行 |
| `tools/template.html` | 遊戲的原始碼（尚未填入地圖資料） |
| `tools/prep.py` | 把國界、河流、地形圖投影並切成東南亞區域地圖 |
| `tools/build.py` | 把資料填入 template，產生 `index.html` |

## 重新產生地圖資料

需要 Python 3（`shapely`、`numpy`、`scipy`、`pillow`）和 Node.js。

```bash
# 1. 下載原始資料到 ~/geo（prep.py 預設讀取 /root/geo/，可自行修改 GEO 變數）
npm i world-atlas topojson-client flag-icons three-globe
pip download basemap-data==2.0.0 --no-deps    # 取出 etopo1.jpg、shadedrelief.jpg
curl -O https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_rivers_lake_centerlines.geojson

# 2. 產生地圖資料，再組成 index.html
python3 tools/prep.py <輸出資料夾>
python3 tools/build.py <輸出資料夾> index.html
```

## 資料來源與授權

- 國界：Natural Earth 1:50m（公有領域），透過 [world-atlas](https://github.com/topojson/world-atlas) 取得
- 河流：[Natural Earth](https://www.naturalearthdata.com/) 1:50m 河流（公有領域）
- 地形色彩：NOAA ETOPO1 地形圖與 Natural Earth 陰影地形圖，取自 [basemap-data](https://pypi.org/project/basemap-data/)
- 國旗：[flag-icons](https://github.com/lipis/flag-icons)（MIT）
- 海拔色階圖例只標示「平原、丘陵、山地、高山」的相對高低，不是精確的公尺數。
