# Java2Bedrock Universal Converter & Scaffolding

Bộ công cụ ngoại tuyến toàn diện chuyển đổi **Minecraft Java Resource Pack (1.14 ➔ 26.3+)** sang **Minecraft Bedrock Edition (`.mcpack`)**, **GeyserMC Custom Mappings (`format_version: 2` & `v1`)**, và **Geyser Companion Extension (2.11+)** — tích hợp sẵn hệ thống **Project Scaffolding kiểu Nexo**.

---

## ✨ Ma trận Tính năng (Feature Matrix)

| Hạng mục | Hỗ trợ | Chi tiết kỹ thuật |
| :--- | :---: | :--- |
| **Items 2D & 3D** | ✅ | Hỗ trợ cả `CustomModelData` cổ điển (1.14 – 1.21.1) và `item_model` / Data Components (1.21.2 – 26.3+). Giải quyết đệ quy sâu chuỗi kế thừa `parent`. |
| **Display Transforms (Kas-tle 4-bone)** | ✅ | Phân tách ma trận xoay/dịch/tỉ lệ trên 4 xương (`root_item` ➔ `_x` ➔ `_y` ➔ `_z`), đồng bộ tay phải/trái (`main_hand`, `off_hand`/`offhand`), góc nhìn thứ nhất/thứ ba và slot đầu (`head`). |
| **Bow, Crossbow & Trident** | ✅ | Tự động tạo Render Controller riêng (`controller.render.j2b_bow`, `j2b_crossbow`, `j2b_trident`) hiển thị đầy đủ các frame kéo cung có mũi tên, nỏ nạp tên/pháo hoa, tư thế giơ ném đinh ba & thực thể đinh ba 3D bay trên không (`thrown_trident`). |
| **Icon 3D Isometric 128px** | ✅ | Tự động rasterize model 3D ra icon kho đồ 2D chuẩn góc chiếu Java GUI (`Pitch 30°, Yaw -45°`), hỗ trợ xoay từng khối (`elements[].rotation`), lật UV và khử răng cưa `2x Supersampling Lanczos`. |
| **Tranh treo tường & Nội thất (`ItemDisplay`)** | ✅ | Tự động bù trừ tọa độ giúp tranh treo tường (`wall_painting`) nằm sát mặt block (`y=0.0, z=tz+5`), thu nhỏ tỉ lệ cầm tay góc nhìn thứ nhất (`0.25x`) và xuất `furniture_registry.json`. |
| **Custom Armor, Tintindex & Flipbook** | ✅ | Chuyển đổi giáp tùy chỉnh (`equippable`) sang attachables giáp humanoid, hỗ trợ nhuộm màu (`tintindex`) và hoạt ảnh `.png.mcmeta` (`flipbook_textures.json`). |
| **Custom Blocks** | ✅ | Chuyển đổi trạng thái `NoteBlock`, `Tripwire`, `Mushroom` sang `blocks.json`, `terrain_texture.json` và `custom_mappings/blocks.json`. |
| **Custom Mobs (`.bbmodel`)** | ✅ | Đọc trực tiếp file Blockbench (`.bbmodel`), xuất thực thể Bedrock, geometry, keyframe animation, animation controller và `mob_registry.json`. |
| **Scaffolding kiểu Nexo (`scaffold` / `build`)** | ✅ | Khởi tạo khung dự án chuẩn từ YAML (`items/`, `blocks/`, `furniture/`, `mobs/`) và biên dịch đồng thời ra **Java Pack `.zip` + Bedrock `.mcpack` + Geyser Mappings** từ một nguồn duy nhất. |

---

## ⚖️ So sánh với Nexo Scaffolding

| Tiêu chí | Nexo Scaffolding | Java2Bedrock (`j2b`) |
| :--- | :--- | :--- |
| **Môi trường chạy** | Phụ thuộc plugin thương mại đóng mã nguồn | **100% Độc lập, Offline & Mã nguồn mở** (CLI + GitHub Actions) |
| **Đầu vào hỗ trợ** | Chỉ định dạng dự án Nexo | Mọi Java Pack (`ItemsAdder`, `Nexo`, `Oraxen`, Vanilla 1.14–26.3+) **VÀ** YAML Scaffold |
| **Bow / Crossbow / Trident 3D** | Thường mất mũi tên khi kéo cung trên Geyser | `j2b_bow`, `j2b_crossbow`, `j2b_trident` RC giữ nguyên mũi tên & thực thể đinh ba bay |
| **Geyser Mappings v2** | Xuất một kiểu cố định | Phân loại thông minh `"type": "legacy"` (cho CMD) và `"type": "definition"` (cho `item_model`) |
| **Báo cáo kiểm toán** | Không có | Xuất `conversion_report.json` chi tiết tới từng tài nguyên (`converted`, `approximated`, `skipped`) |

---

## 🚀 Hướng dẫn Sử dụng CLI

### 1. Chuyển đổi trực tiếp Java Resource Pack có sẵn (`convert`)
```bash
python3 cli.py convert \
  --input /path/to/java_pack.zip \
  --output ./output \
  --name MyServerPack \
  --namespace j2b \
  --icon-size 128 \
  --report ./output/conversion_report.json
```
*(Lưu ý: Cú pháp truyền thống `python3 cli.py --input ...` không cần từ khóa `convert` vẫn được hỗ trợ 100%).*

### 2. Khởi tạo & Build dự án mới theo phong cách Nexo (`scaffold` & `build`)
```bash
# Bước 1: Tạo khung dự án mẫu (items, blocks, furniture, mobs, textures, models)
python3 cli.py scaffold MyCustomPack --output ./projects

# Bước 2: Chỉnh sửa YAML hoặc thêm ảnh/model vào ./projects/MyCustomPack/

# Bước 3: Biên dịch đồng thời ra Java Pack (.zip) + Bedrock (.mcpack) + Geyser Mappings
python3 cli.py build --project ./projects/MyCustomPack --output ./projects/MyCustomPack/build
```

---

## 🛠️ Hướng dẫn Cài đặt lên Server GeyserMC

1. **Cài đặt Bedrock Resource Pack (`.mcpack`)**:
   Copy file `<PackName>.mcpack` vào thư mục:
   ```text
   plugins/Geyser-Spigot/packs/
   ```
2. **Cài đặt Geyser Custom Mappings (`items_v2.json` & `blocks.json`)**:
   Copy các file trong `custom_mappings/` (`items_v2.json`, `blocks.json`, `furniture_registry.json`, `mob_registry.json`, `trident_registry.json`) vào:
   ```text
   plugins/Geyser-Spigot/custom_mappings/
   ```
3. **Cài đặt Geyser Companion Extension (Tùy chọn cho Furniture / ModelEngine Mobs / Multi-Tridents)**:
   Copy `extension/J2BCompanionExtension.jar` vào:
   ```text
   plugins/Geyser-Spigot/extensions/
   ```
4. Khởi động lại server (hoặc chạy `/geyser reload`) và kết nối lại từ client Bedrock.

---

## 🤖 Tự động hóa qua GitHub Issues
1. Vào tab **Issues** trên kho lưu trữ GitHub của dự án.
2. Chọn mẫu **"📦 Convert Java Resource Pack to Bedrock (.mcpack)"**.
3. Dán link tải trực tiếp (Direct Download URL) của file `.zip` Java Resource Pack và nhấn **Submit new issue**.
4. GitHub Actions sẽ tự động chạy chuyển đổi, đính kèm gói `.mcpack` + `custom_mappings` và đóng Issue khi hoàn tất.
