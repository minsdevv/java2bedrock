# Java2Bedrock Universal Converter

Công cụ chuyển đổi toàn diện **Minecraft Java Resource Pack (1.14 ➔ 26.3+)** sang **Minecraft Bedrock Edition (`.mcpack`)** và **GeyserMC Custom Mappings (`format_version: 2` & `v1`)**, hỗ trợ:
- **Items 2D & 3D**: Hỗ trợ cả `CustomModelData` cổ điển (1.14 - 1.21.1) và hệ thống `item_model` / Data Components mới của **Minecraft 26.3 (1.21.2+)**.
- **Texture Atlas, UV & Custom Armor**: Tự động đóng gói đa texture (Atlas Stitching), xử lý `tintindex` và tạo giáp tùy chỉnh (`equippable`).
- **Custom Blocks & Display Furniture**: Chuyển đổi trạng thái khối tùy chỉnh (NoteBlock, Tripwire, Mushroom) sang `blocks.json` + Geyser `custom_mappings/blocks.json`, hỗ trợ nội thất `ItemDisplay`.
- **Custom Mobs (ModelEngine `.bbmodel`) & Geyser Companion Extension**: Chuyển đổi cây xương (Bone Hierarchy), hoạt ảnh Keyframe sang thực thể Bedrock native kèm Extension Geyser 2.11+ triệt tiêu giật lag.
- **GitHub Issues Automation** *(Phong cách `Kas-tle/java2bedrock.sh`)*: Mở Issue kèm link tải Java Pack để GitHub Actions tự động convert và trả file `.mcpack` ngay trong bình luận.

---

## Cách sử dụng qua CLI

```bash
python3 cli.py \
  --input /path/to/java_pack.zip \
  --output ./output \
  --name MyServerPack \
  --namespace j2b
```

## Cách sử dụng qua GitHub Issues

1. Vào tab **Issues** trên kho lưu trữ GitHub của dự án.
2. Chọn mẫu **"📦 Convert Java Resource Pack to Bedrock (.mcpack)"**.
3. Dán link tải trực tiếp (Direct Download URL) của file `.zip` Java Resource Pack và nhấn **Submit new issue**.
4. GitHub Actions sẽ tự động chạy chuyển đổi, đính kèm gói `.mcpack` + `custom_mappings` và đóng Issue khi hoàn tất.
