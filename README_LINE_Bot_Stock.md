
# 📈 台灣股市 LINE Bot 股票分析系統

一個支援台股即時查詢、股價趨勢圖表、生動標註、價格警示推播的 LINE Bot，採用 Python 開發，整合 Flask 後端、twstock 資料來源、matplotlib 圖表繪製，並部署於 Render 雲端平台。

---

## 🔧 功能亮點

- ✅ 即時股價查詢：輸入 `2330` 查詢台積電價格
- ✅ 股票圖表查詢：`2330 30天` 或 `查 2330 2881`
- ✅ 多股查詢與圖表回傳
- ✅ 圖表自動標註最高 / 最低點
- ✅ 使用者價格警示推播：如 `設定 2330 > 800`
- ✅ 使用者首次加入自動推播使用教學
- ✅ Seaborn 美化圖表、支援中文字型
- ✅ Webhook 驅動 + UptimeRobot 定時觸發 `/check_alerts`
- ✅ Render 雲端部署，公開可使用

---

## 📸 使用展示範例

（請加入下列圖片示意截圖）
- [ ] 即時查詢 `2330` 回覆畫面
- [ ] 多股圖表 `查 2330 2317`
- [ ] 自動價格推播通知
- [ ] `/check_alerts` Webhook 回傳成功畫面

---

## ⚙️ 技術架構與工具

### 🧠 核心技術
- Python 3.x
- Flask（提供 Web API）
- LINE Bot SDK（訊息處理）
- twstock（台股資料來源）
- matplotlib + seaborn（股價圖表與標註）
- dotenv + os.environ（密鑰環境變數安全管理）

### ☁️ 雲端與部署
- Render（Flask Web App 雲端部署）
- GitHub 版本控管與自動部署
- Webhook URL：`/callback`
- 價格警示觸發 Webhook：`/check_alerts`

---

## 🚀 如何使用

### ✅ 專案安裝（本地測試）

```bash
git clone https://github.com/your-username/linebot-stock.git
cd linebot-stock
pip install -r requirements.txt
```

建立 `.env` 檔案，並放入以下內容：

```env
CHANNEL_ACCESS_TOKEN=你的LINE_CHANNEL_TOKEN
CHANNEL_SECRET=你的LINE_CHANNEL_SECRET
```

執行：

```bash
python app.py
```

### ✅ Render 雲端部署

1. 建立 Render Web Service ➜ Python ➜ gunicorn 啟動
2. 設定環境變數（與 `.env` 相同）
3. 部署後將 Webhook URL 設為：
   ```
   https://your-project-name.onrender.com/callback
   ```

---

## 🔁 自動價格警示檢查（Webhook）

使用 `/check_alerts` endpoint 進行即時比對，用 UptimeRobot 定時 ping 此網址即可：

```
GET https://your-project-name.onrender.com/check_alerts
```

---

## 📌 指令總覽

| 指令範例        | 說明                       |
|-----------------|----------------------------|
| `2330`          | 查詢台積電即時股價         |
| `查 2330 2881`  | 查詢多支股票價格與圖表     |
| `2330 30天`     | 查詢近 30 日趨勢圖         |
| `設定 2330 > 800` | 設定價格提醒推播           |

---

## 📈 未來可擴充功能

- 技術指標支援（如 MA、KD）
- 使用者資料儲存（持久化警示）
- 圖表樣式切換 / 暗黑主題
- 互動式查詢指令建議回饋
