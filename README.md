# Photo Watermark Tool

一个简单的命令行工具，用于给照片添加基于EXIF信息的日期水印。

## 功能特点

- 自动从图片EXIF数据中提取拍摄日期
- 支持自定义水印字体大小
- 支持自定义水印颜色和透明度
- 支持自定义水印位置（9个预设位置）
- 支持批量处理整个目录的图片
- 自动创建新目录保存处理后的图片

## 安装依赖

```bash
pip install pillow piexif
```

## 使用方法

### 基本用法

```bash
python photo_watermark.py 图片路径或目录路径
```

### 高级选项

```bash
python photo_watermark.py 图片路径或目录路径 [--font-size 字体大小] [--font-color 颜色] [--position 位置]
```

参数说明：

- `--font-size`: 水印字体大小，默认为36
- `--font-color`: 水印颜色，格式为"R,G,B,A"，例如"255,255,255,128"表示半透明白色
- `--position`: 水印位置，可选值为：
  - `top-left`: 左上角
  - `top-center`: 上方居中
  - `top-right`: 右上角
  - `center-left`: 左侧居中
  - `center`: 正中央
  - `center-right`: 右侧居中
  - `bottom-left`: 左下角
  - `bottom-center`: 下方居中
  - `bottom-right`: 右下角（默认）

### 示例

添加默认水印（右下角白色半透明）：
```bash
python photo_watermark.py photo.jpg
```

添加自定义水印：
```bash
python photo_watermark.py photo.jpg --font-size 48 --font-color 255,0,0,200 --position top-right
```

批量处理目录中的所有图片：
```bash
python photo_watermark.py photos_directory
```

## 输出

处理后的图片将保存在原目录的子目录中，子目录名为"原目录名_watermark"。

## 支持的图片格式

- JPEG (.jpg, .jpeg)
- PNG (.png)
- TIFF (.tiff)
- BMP (.bmp)

## 注意事项

- 如果图片没有EXIF数据或无法读取日期信息，水印将显示为"未知日期"
- 程序会自动尝试加载系统字体，如果加载失败则使用默认字体