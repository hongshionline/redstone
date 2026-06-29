# 红石联机

版本：1.08 | 修复者：Sleep | 平台：Python

## 更新内容

### 1. 修复 `_add_shadow` 阴影效果
之前方法体仅为 `return None`，所有阴影参数被忽略，卡片/面板缺少视觉深度。已使用 `QGraphicsDropShadowEffect` 正确实现阴影效果，涉及侧栏、内容面板、信息卡等 6 处调用。

### 2. 清理大量死代码

| 删除内容 | 所在文件 | 说明 |
|---------|---------|------|
| `_on_bg_media_status` | layout.py | 空实现，从未连接信号 |
| `eventFilter` | layout.py | 空实现，从未安装为事件过滤器 |
| `_start_button_glow` | layout.py | 空实现，从未被调用 |
| 视频背景完整模块（~90行） | layout.py | `_start_label_video_background`、`_bg_decode_loop`、`_next_bg_video_frame` 从未被调用，相关属性始终为空值 |
| 视频背景残留属性（12个） | layout.py | `_bg_video_widget`、`_bg_player`、`_bg_frame_queue` 等从未使用 |
| 视频背景清理代码 | window.py | `closeEvent` 中停止视频计时器和线程的代码 |
| `QEvent.WindowStateChange` 分支 | window.py | `changeEvent` 中设置 `_bg_video_paused` 的已删除代码 |
| `_check_update` | window.py | 仅包装 `_check_update_async`，调用方已直接使用后者 |
| `_check_existing_tunnel` | window.py | 同上 |
| `parse_ping_ms` | tunnel.py | 与 `_parse_ping_samples` 功能重复，从未被调用 |
| `mix_color` | main.py | 从未被调用的颜色混合工具函数 |
| `get_avg_wallpaper_color` | main.py | 从未被调用 |
| `calc_mica_color` | main.py | 从未被调用 |
| `_cached_avg` / `_load_avg_color` | main.py | 仅被上述已删除函数使用 |
| `import cv2` | main.py | 视频背景删除后不再需要 |
| `from PIL import ImageStat` | main.py | 仅被已删除的 `_load_avg_color` 使用 |
| `QImage`、`QGraphicsOpacityEffect` | main.py | 未使用的 Qt 导入 |

### 3. 修复 `_handle_server_probe` 的类型检查顺序
`payload.get("ip")` 在 `isinstance(payload, dict)` 之前调用，如果 payload 非字典会崩溃。已改为先检查类型再访问。

### 4. 修复易混淆的条件表达式
- `_refresh_server_metric_widgets` 中的三元表达式当语句用，已改为标准的 `if/else`
- `_build_server_card` 中 `+` 和 `if/else` 优先级混杂，已用括号明确

### 5. 清理未使用的 Qt 导入
移除了 `QImage`、`QGraphicsOpacityEffect` 两个未使用的 Qtgui 组件导入。
