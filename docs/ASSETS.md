# 資產與模型

## 房間

房間使用提供的 `7052 ver3` 場景，原版本日期為 2026-09-26。主檔為 `assets/room7052/7052_ver3_0925.usda`，`textures/` 包含 55 個貼圖檔案。

`assets/room7052/source/7052_ver2_fixed_balcony_glass.blend` 是隨包提供的可編輯 Blender 原檔，原資料說明標示使用 Blender 4.5，貼圖已打包。USD 場景另含碰撞、燈光和物理關節。

房間保有以下互動結構，關節位於 `/root/Joints/`。

| 關節 | 作用與範圍 |
| --- | --- |
| EntryDoorHingeJoint | 大門，0 至 -92 度 |
| BathroomSlidingDoorJoint | 浴室拉門，0 至 -0.94 m |
| ShowerDoorHingeJoint | 淋浴玻璃門，0 至 -100 度 |
| ToiletLidHingeJoint | 馬桶蓋，0 至 100 度 |
| DoorJoint | 冰箱門，0 至 90 度 |
| OuterDoorJoint | 迷你吧外門，0 至 85 度 |
| DrawerJoint_Top / Middle / Bottom | 三個抽屜，0 至 0.38 m |
| Joint_Left_* / Joint_Right_* | 窗簾滑動關節 |

原場景的面紙、枕頭等仍使用各自原有的視覺與物理近似。浴缸掃描群組有一個空 mesh collider，Isaac Sim 可能對該空網格顯示警告，隨機雜物的支撐檢查另行驗證。

發布版把 USD 中 29 個歷史來源檔案的電腦絕對路徑註記整理為檔名。可解析的模型與貼圖引用使用隨包路徑。

## 可樂

`assets/so101_cola/` 使用本專案提供的 SO-101 250 mL 可樂模型與照片貼圖。

| 檔案 | 用途 |
| --- | --- |
| cola_can.usda | USD 模型、材質、碰撞與質量設定 |
| label_atlas.png | 罐身照片貼圖 |
| top.jpg | 罐頂照片 |
| bottom.jpg | 罐底照片 |

模型 Z 軸朝上，高約 0.0916 m、直徑約 0.06622 m，估計質量 0.275 kg。生成場景引用 `/ColaCan`，保留外觀、慣量與碰撞結構，並依 episode 設定為 kinematic。Coca-Cola 字樣與外觀來自模型照片中的品牌包裝。

## 完整性

根目錄 `asset_manifest.json` 列出 61 個模型、原始檔與貼圖的相對路徑、大小及 SHA-256。可執行 `verify_assets.py` 核對。Release 另提供完整 ZIP 的 `SHA256SUMS.txt`。
