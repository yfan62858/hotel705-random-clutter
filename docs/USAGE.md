# 操作與整合說明

## 產生可重現的配置

seed 與 level 共同決定配置。`medium / 705`、`medium / 706` 會產生不同位置，再使用 `medium / 705` 可以重現前一個配置。`clean` 保留原房間物件配置。

```powershell
.\start.bat -IsaacSimPath "C:\isaacsim" -Seed 20261110 -Level high
```

面板的 `New random layout` 依序將 seed 加一。要回到先前配置，輸入對應 seed 和程度，再按 `Generate this seed`。

產生位置包含迷你吧檯面、窗邊圓桌、床頭桌、入口長凳與選定地板區域。程式使用模型實際包圍盒安排位置，避免生成物彼此重疊，並保留約 1 mm 支撐間隙。啟動時額外以 PhysX raycast 檢查物件下方支撐。

## 相機與截圖

面板提供房間、迷你吧桌面、地板三個快捷視角。Isaac Sim viewport 可用滑鼠和預設視角操作工具移動相機。按 `Save screenshot` 會寫入目前 seed 目錄的 `snapshot.png`，重拍會更新這張圖。

`-Preview` 會依序輸出 `room_overview.png`、`minibar_tabletop.png`、`floor_litter.png`、`window_table.png`，完成後結束程式。這個功能輸出 PNG 圖片。

## 資料格式與座標

- 單位為公尺，Z 軸朝上。
- 原點在房門口地板中央，房間朝負 Y 延伸，窗戶約在 Y = -8 m。
- 房間 prim 位於 `/root`，新增雜物位於 `/Clutter`。
- `objects.json` 的 `center_world`、`bounds_min`、`bounds_max` 都是世界座標。
- `support`、`support_prim`、`support_z` 記錄採用的支撐面。
- `task_category` 使用 `return_amenity`、`trash` 與 `unassigned`，可依計畫重新定義分類規則。
- `runtime_validation.json` 記錄 USD 資產解析、包圍盒檢查與實際 PhysX 支撐結果。

生成 metadata 提供評估用 ground truth。物件搜尋系統的觀測資料由自己的相機或感測器取得。

## 從程式使用

使用 Isaac Sim 的 Python，可以單獨生成 USD 配置。

```python
from generator import generate, validate_scene

scene_path, metadata = generate(seed=705, level="medium")
print(scene_path)
print(validate_scene(scene_path))
```

執行中的 Isaac Sim 可載入產生的 USD。

```python
import omni.usd
await omni.usd.get_context().open_stage_async(str(scene_path))
```

載入後再加入計畫使用的 robot prim、感測器與控制程式。`assets/room7052/7052_ver3_0925.usda` 保有房間的關節與剛體資料，可與機器人整合。

新增雜物固定在每個 episode 的位置。需要推動或抓取時，請依任務調整 kinematic 設定、摩擦與碰撞參數，再檢查模擬穩定性。揉紙團使用剛體近似。

## 常見狀況

- 提示找不到 `python.bat` 時，`-IsaacSimPath` 應指向同時有 `python.bat`、`kit` 和 `extscache` 的安裝根目錄。
- 提示缺少房間或可樂時，請下載 Release 中檔名結尾為 `full.zip` 的完整包，保留 `assets/` 的資料夾結構。
- 初次 shader 載入可能較久，等待控制面板顯示 `Ready`。
- 同一配置重跑會更新該配置的生成檔案。需要保留多個 snapshot 時，先自行複製或改名。
- `-Preview` 若檢查失敗，會輸出錯誤狀態並回傳非零結束碼，細節見 `status.txt` 與場景內的 `runtime_validation.json`。
- Isaac Sim 官方文件提供目前支援的驅動、硬體與安裝需求。此版本的完整實測環境是 Windows、RTX 5070 與 Isaac Sim 5.1。
