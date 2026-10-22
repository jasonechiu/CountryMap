# 世界地形拼圖

給國中生認識世界各國的網頁拼圖遊戲。把右邊的國家拼圖拖到地圖上的虛線國界位置，放對會吸附並跳出國旗與首都小卡。

區域依慣用的地理分區劃分。亞洲採華文地理常見的分法，其他洲採聯合國地理分區。目前完成亞洲五區與歐洲四區：

| 區域 | 國家 |
| --- | --- |
| 東亞（8） | 台灣、中國、日本、南韓、北韓、蒙古、香港、澳門 |
| 東南亞（11） | 越南、寮國、柬埔寨、泰國、緬甸、馬來西亞、新加坡、印尼、菲律賓、汶萊、東帝汶 |
| 南亞（7） | 印度、巴基斯坦、孟加拉、尼泊爾、不丹、斯里蘭卡、馬爾地夫 |
| 中亞（5） | 哈薩克、烏茲別克、土庫曼、吉爾吉斯、塔吉克 |
| 西亞（20） | 伊朗、阿富汗、土耳其、賽普勒斯、喬治亞、亞美尼亞、亞塞拜然、伊拉克、敘利亞、黎巴嫩、以色列、巴勒斯坦、約旦、沙烏地阿拉伯、葉門、阿曼、阿拉伯聯合大公國、卡達、巴林、科威特 |
| 北歐（10） | 英國、愛爾蘭、冰島、挪威、瑞典、芬蘭、丹麥、愛沙尼亞、拉脫維亞、立陶宛 |
| 西歐（9） | 法國、荷蘭、比利時、盧森堡、摩納哥、德國、瑞士、列支敦斯登、奧地利 |
| 南歐（16） | 葡萄牙、西班牙、安道爾、義大利、聖馬利諾、梵蒂岡、馬爾他、希臘、斯洛維尼亞、克羅埃西亞、波士尼亞與赫塞哥維納、塞爾維亞、蒙特內哥羅、科索沃、北馬其頓、阿爾巴尼亞 |
| 東歐（10） | 俄羅斯（歐洲部分）、烏克蘭、白俄羅斯、摩爾多瓦、波蘭、捷克、斯洛伐克、匈牙利、羅馬尼亞、保加利亞 |

## 怎麼玩

- 用 GitHub Pages 的網址開來玩最簡單。地圖放在 `data/` 資料夾，選到區域時才下載，所以直接雙擊打開 `index.html` 會載不到地圖；在電腦上要用網頁伺服器開，例如在資料夾裡執行 `python3 -m http.server`，再打開 `http://localhost:8000`。
- 開頭先選區域；遊戲中可以按右上角「換區域」。
- 按住拼圖拖到地圖上；放錯會彈回，可以再試。放對時會念出中文和英文國名（用瀏覽器內建的語音，關掉音效就不會念）。
- 全部放好後，按「完成」可以看拼好的地圖。
- 第一次就放對得 3 分，第二次 2 分，第三次 1 分。
- 滾輪可以放大地圖，新加坡、汶萊這類小國比較好放。
- 右上角可以切換中文／English、開關音效。
- 快捷鍵：`R` 重新開始、`L` 切換語言、`Esc` 關閉國家小卡。
- 每個區域的最佳紀錄和放錯過的國家分開存在瀏覽器裡，下一局會先出現放錯過的國家。

## 用 GitHub Pages 上線

到 repository 的 **Settings → Pages**，Source 選 `Deploy from a branch`，Branch 選 `main`、資料夾選 `/ (root)`。幾分鐘後就能用 `https://<帳號>.github.io/<repository 名稱>/` 開來玩。

## 檔案

| 檔案 | 用途 |
| --- | --- |
| `index.html` | 遊戲本身 |
| `data/<區域>.json`、`data/<區域>.jpg` | 每個區域的國界、河流與地形圖，選到區域時才下載 |
| `data/flags/` | 國旗 |
| `tools/template.html` | 遊戲的原始碼（尚未填入地圖資料） |
| `tools/prep.py` | 把國界、河流、地形圖投影並切成區域地圖（區域設定在 `REGIONS`） |
| `tools/build.py` | 組出 `index.html` 和 `data/` 資料夾 |

## 重新產生地圖資料

需要 Python 3（`shapely`、`numpy`、`scipy`、`pillow`）和 Node.js。

```bash
# 1. 下載原始資料到 ~/geo（prep.py 預設讀取 /root/geo/，可自行修改 GEO 變數）
npm i world-atlas topojson-client flag-icons three-globe
# 用 topojson-client 把 countries-50m.json、countries-10m.json 轉成 countries50.geojson、countries10.geojson
pip download basemap-data==2.0.0 --no-deps    # 取出 etopo1.jpg、shadedrelief.jpg
curl -O https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_rivers_lake_centerlines.geojson

# 2. 產生地圖資料，再組成 index.html
for r in ea sea sa ca wa ne we se ee; do python3 tools/prep.py <資料夾> $r; done   # 亞洲五區、歐洲四區
python3 tools/build.py <資料夾> <網站輸出資料夾>
```

## 資料來源與授權

- 國界：Natural Earth 1:50m（公有領域），透過 [world-atlas](https://github.com/topojson/world-atlas) 取得
- 河流：[Natural Earth](https://www.naturalearthdata.com/) 1:50m 河流（公有領域）
- 地形色彩：NOAA ETOPO1 地形圖與 Natural Earth 陰影地形圖，取自 [basemap-data](https://pypi.org/project/basemap-data/)
- 國旗：[flag-icons](https://github.com/lipis/flag-icons)（MIT）
- 國界採用 Natural Earth 的預設畫法；喀什米爾等有爭議的地區依實際控制線劃分。
- 克里米亞依聯合國大會的立場畫在烏克蘭境內（原始資料畫在俄羅斯）。
- 東歐的俄羅斯只拼歐洲部分，以東經 60 度（約烏拉山）為界，其餘當背景。
- 每塊拼圖只保留區域主畫面內的部分，例如葡萄牙不含亞速群島、挪威不含斯瓦巴群島。
- 歐洲改用蘭伯特圓錐投影，高緯度地區不會被拉寬。梵蒂岡、摩納哥、聖馬利諾等迷你國家略為放大以便拖曳。
- 北賽普勒斯併入賽普勒斯；香港、澳門、巴林、馬爾地夫改用 1:10m 資料，很小的地方略為放大以便拖曳。
- 以色列、巴勒斯坦的首都有爭議，國家小卡會註明實際情況。
- 馬爾地夫改用 1:10m 資料的完整環礁鏈，並把小島連成一長條，方便看見和拖曳。
- 海拔色階圖例只標示「平原、丘陵、山地、高山」的相對高低，不是精確的公尺數。
