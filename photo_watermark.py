#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
照片水印工具
用于为照片添加水印，可以使用EXIF拍摄日期或自定义文本
支持Builder模式创建水印处理器
"""

import os
import sys
import logging
import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Union, List, Dict, Any
import concurrent.futures

from PIL import Image, ImageDraw, ImageFont, ExifTags
import piexif

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('PhotoWatermark')

class WatermarkBuilder:
    """Builder模式实现，用于构建PhotoWatermark实例"""
    
    def __init__(self):
        """初始化Builder"""
        self._font_size = 36
        self._font_color = (255, 255, 255, 128)
        self._position = "bottom-right"
        self._custom_font_path = None
        self._padding = 20
        self._text_format = "%Y-%m-%d"
        self._unknown_date_text = "未知日期"
        self._parallel_processing = True
        self._max_workers = None  # 默认使用CPU核心数
    
    def with_font_size(self, font_size: int) -> 'WatermarkBuilder':
        """设置字体大小"""
        if not isinstance(font_size, int) or font_size <= 0:
            raise ValueError("字体大小必须是正整数")
        self._font_size = font_size
        return self
    
    def with_font_color(self, font_color: Tuple[int, int, int, int]) -> 'WatermarkBuilder':
        """设置字体颜色"""
        if not isinstance(font_color, tuple) or len(font_color) not in (3, 4):
            raise ValueError("字体颜色必须是RGB或RGBA元组")
        
        # 确保所有值都在0-255范围内
        for value in font_color:
            if not isinstance(value, int) or value < 0 or value > 255:
                raise ValueError("颜色值必须在0-255范围内")
        
        # 如果只提供RGB，添加默认透明度
        if len(font_color) == 3:
            self._font_color = font_color + (128,)
        else:
            self._font_color = font_color
        return self
    
    def with_position(self, position: str) -> 'WatermarkBuilder':
        """设置水印位置"""
        valid_positions = [
            'top-left', 'top-center', 'top-right',
            'center-left', 'center', 'center-right',
            'bottom-left', 'bottom-center', 'bottom-right'
        ]
        if position not in valid_positions:
            raise ValueError(f"无效的位置: {position}，有效值为: {', '.join(valid_positions)}")
        self._position = position
        return self
    
    def with_custom_font(self, font_path: str) -> 'WatermarkBuilder':
        """设置自定义字体路径"""
        if not os.path.exists(font_path):
            raise FileNotFoundError(f"字体文件不存在: {font_path}")
        self._custom_font_path = font_path
        return self
    
    def with_padding(self, padding: int) -> 'WatermarkBuilder':
        """设置水印边距"""
        if not isinstance(padding, int) or padding < 0:
            raise ValueError("边距必须是非负整数")
        self._padding = padding
        return self
    
    def with_date_format(self, date_format: str) -> 'WatermarkBuilder':
        """设置日期格式"""
        try:
            # 测试格式是否有效
            datetime.now().strftime(date_format)
            self._text_format = date_format
            return self
        except ValueError as e:
            raise ValueError(f"无效的日期格式: {e}")
    
    def with_unknown_date_text(self, text: str) -> 'WatermarkBuilder':
        """设置未知日期的显示文本"""
        self._unknown_date_text = text
        return self
    
    def with_parallel_processing(self, enabled: bool = True, max_workers: Optional[int] = None) -> 'WatermarkBuilder':
        """启用或禁用并行处理"""
        self._parallel_processing = enabled
        self._max_workers = max_workers
        return self
    
    def with_parallel_processing(self, enabled: bool = True, max_workers: Optional[int] = None) -> 'WatermarkBuilder':
        """启用或禁用并行处理"""
        self._parallel_processing = enabled
        self._max_workers = max_workers
        return self
    
    def build(self) -> 'PhotoWatermark':
        """构建并返回PhotoWatermark实例"""
        return PhotoWatermark(
            font_size=self._font_size,
            font_color=self._font_color,
            position=self._position,
            custom_font_path=self._custom_font_path,
            padding=self._padding,
            text_format=self._text_format,
            unknown_date_text=self._unknown_date_text,
            parallel_processing=self._parallel_processing,
            max_workers=self._max_workers
        )

class PhotoWatermark:
    """处理照片水印的主类"""
    
    def __init__(self, 
                 font_size: int = 36, 
                 font_color: Tuple[int, int, int, int] = (255, 255, 255, 128), 
                 position: str = "bottom-right",
                 custom_font_path: Optional[str] = None,
                 padding: int = 20,
                 text_format: str = "%Y-%m-%d",
                 unknown_date_text: str = "未知日期",
                 parallel_processing: bool = True,
                 max_workers: Optional[int] = None):
        """
        初始化水印处理器
        
        参数:
            font_size (int): 水印字体大小
            font_color (tuple): 水印颜色 (R,G,B,A)
            position (str): 水印位置 ('top-left', 'top-center', 'top-right', 
                                    'center-left', 'center', 'center-right',
                                    'bottom-left', 'bottom-center', 'bottom-right')
            custom_font_path (str, optional): 自定义字体路径
            padding (int): 水印边距
            text_format (str): 日期格式
            unknown_date_text (str): 未知日期的显示文本
            parallel_processing (bool): 是否启用并行处理，默认为True
            max_workers (int, optional): 并行处理的最大工作线程数
        """
        self.font_size = font_size
        self.font_color = font_color
        self.position = position
        self.padding = padding
        self.text_format = text_format
        self.unknown_date_text = unknown_date_text
        self.parallel_processing = parallel_processing
        self.max_workers = max_workers
        
        # 尝试加载字体
        self._load_font(custom_font_path)
    
    def _load_font(self, custom_font_path: Optional[str] = None) -> None:
        """加载字体"""
        try:
            # 优先使用自定义字体
            if custom_font_path and os.path.exists(custom_font_path):
                self.font = ImageFont.truetype(custom_font_path, self.font_size)
                return
                
            # 尝试加载系统字体
            if os.name == 'nt':  # Windows
                self.font = ImageFont.truetype("arial.ttf", self.font_size)
            else:  # Linux/Mac
                self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", self.font_size)
        except IOError as e:
            # 如果找不到系统字体，使用默认字体
            logger.warning(f"无法加载字体: {e}，使用默认字体")
            self.font = ImageFont.load_default()
    
    def get_exif_date(self, image_path: str) -> Optional[str]:
        """
        从图片中提取EXIF拍摄日期
        
        参数:
            image_path (str): 图片文件路径
            
        返回:
            str: 格式化的日期字符串，如果没有EXIF数据则返回None
        """
        try:
            img = Image.open(image_path)
            
            # 尝试使用piexif获取EXIF数据
            try:
                exif_dict = piexif.load(img.info.get('exif', b''))
                if '0th' in exif_dict and piexif.ImageIFD.DateTime in exif_dict['0th']:
                    date_str = exif_dict['0th'][piexif.ImageIFD.DateTime].decode('utf-8')
                    # 格式通常是 'YYYY:MM:DD HH:MM:SS'
                    date_obj = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                    return date_obj.strftime(self.text_format)
            except Exception as e:
                logger.debug(f"使用piexif获取EXIF失败: {e}")
            
            # 如果piexif失败，尝试使用PIL的方法
            exif_data = img._getexif()
            if exif_data:
                # 查找日期时间原始信息
                for tag_id, tag_name in ExifTags.TAGS.items():
                    if tag_name == 'DateTimeOriginal':
                        if tag_id in exif_data:
                            date_str = exif_data[tag_id]
                            # 格式通常是 'YYYY:MM:DD HH:MM:SS'
                            date_obj = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                            return date_obj.strftime(self.text_format)
            
                # 如果找不到DateTimeOriginal，尝试其他日期字段
                for tag_id, tag_name in ExifTags.TAGS.items():
                    if tag_name in ['DateTime', 'DateTimeDigitized'] and tag_id in exif_data:
                        date_str = exif_data[tag_id]
                        date_obj = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                        return date_obj.strftime(self.text_format)
                    
            return None
        except Exception as e:
            logger.error(f"读取EXIF数据时出错: {e}")
            return None
    
    def calculate_position(self, img_width: int, img_height: int, text_width: int, text_height: int) -> Tuple[int, int]:
        """
        根据指定位置计算水印坐标
        
        参数:
            img_width (int): 图片宽度
            img_height (int): 图片高度
            text_width (int): 文本宽度
            text_height (int): 文本高度
            
        返回:
            tuple: 水印位置坐标 (x, y)
        """
        positions = {
            'top-left': (self.padding, self.padding),
            'top-center': ((img_width - text_width) // 2, self.padding),
            'top-right': (img_width - text_width - self.padding, self.padding),
            'center-left': (self.padding, (img_height - text_height) // 2),
            'center': ((img_width - text_width) // 2, (img_height - text_height) // 2),
            'center-right': (img_width - text_width - self.padding, (img_height - text_height) // 2),
            'bottom-left': (self.padding, img_height - text_height - self.padding),
            'bottom-center': ((img_width - text_width) // 2, img_height - text_height - self.padding),
            'bottom-right': (img_width - text_width - self.padding, img_height - text_height - self.padding)
        }
        
        # 默认为右下角
        return positions.get(self.position, positions['bottom-right'])
    
    def add_watermark(self, image_path, output_path):
        """
        向图片添加水印
        
        参数:
            image_path (str): 输入图片路径
            output_path (str): 输出图片路径
            
        返回:
            bool: 成功返回True，失败返回False
        """
        if not os.path.exists(image_path):
            logger.error(f"图片文件不存在: {image_path}")
            return False
            
        try:
            # 获取拍摄日期
            date_str = self.get_exif_date(image_path)
            if not date_str:
                logger.warning(f"无法从图片获取日期信息: {image_path}")
                date_str = self.unknown_date_text
            
            # 打开图片
            img = Image.open(image_path)
            
            # 创建一个可以绘制的图层
            watermark = Image.new('RGBA', img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(watermark)
            
            # 计算文本大小
            try:
                # PIL 9.0.0及以上版本使用textbbox
                text_bbox = draw.textbbox((0, 0), date_str, font=self.font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
            except AttributeError:
                # 旧版本使用textsize
                text_width, text_height = draw.textsize(date_str, font=self.font)
            
            # 计算水印位置
            position = self.calculate_position(img.width, img.height, text_width, text_height)
            
            # 绘制水印文本
            draw.text(position, date_str, font=self.font, fill=self.font_color)
            
            # 将水印图层与原图合并
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            watermarked = Image.alpha_composite(img, watermark)
            
            # 保存为新图片
            if watermarked.mode == 'RGBA':
                watermarked = watermarked.convert('RGB')
                
            # 确保输出目录存在
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
                
            watermarked.save(output_path)
            
            logger.info(f"已添加水印并保存到: {output_path}")
            return True
        except IOError as e:
            logger.error(f"无法打开或保存图片 {os.path.basename(image_path)}: {e}")
            return False
        except Exception as e:
            logger.error(f"添加水印时出错: {e}")
            return False
    
    def process_directory(self, input_dir):
        """
        处理目录中的所有图片
        
        参数:
            input_dir (str): 输入目录路径
            
        返回:
            int: 成功处理的图片数量
        """
        # 创建输出目录
        input_path = Path(input_dir)
        output_dir = input_path / f"{input_path.name}_watermark"
        output_dir.mkdir(exist_ok=True)
        
        # 支持的图片格式
        supported_formats = ['.jpg', '.jpeg', '.png', '.tiff', '.bmp']
        
        # 收集所有需要处理的文件
        image_files = []
        for file_path in input_path.glob('*'):
            if file_path.is_file() and file_path.suffix.lower() in supported_formats:
                output_path = output_dir / file_path.name
                image_files.append((str(file_path), str(output_path)))
        
        total_files = len(image_files)
        if total_files == 0:
            logger.warning(f"在目录 {input_dir} 中没有找到支持的图片文件")
            return 0
        
        # 计数器
        success_count = 0
        failed_files = []
        
        # 根据是否启用并行处理选择不同的处理方式
        if self.parallel_processing and total_files > 1:
            logger.info(f"使用并行处理模式处理 {total_files} 个文件")
            
            # 使用线程池并行处理
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交所有任务
                future_to_path = {
                    executor.submit(self.add_watermark, input_path, output_path): input_path
                    for input_path, output_path in image_files
                }
                
                # 处理结果
                for future in concurrent.futures.as_completed(future_to_path):
                    input_path = future_to_path[future]
                    try:
                        success = future.result()
                        if success:
                            success_count += 1
                        else:
                            failed_files.append(input_path)
                    except Exception as e:
                        logger.error(f"处理文件 {input_path} 时发生异常: {e}")
                        failed_files.append(input_path)
        else:
            logger.info(f"使用顺序处理模式处理 {total_files} 个文件")
            
            # 顺序处理
            for input_path, output_path in image_files:
                if self.add_watermark(input_path, output_path):
                    success_count += 1
                else:
                    failed_files.append(input_path)
        
        # 输出处理结果
        if failed_files:
            logger.warning(f"以下 {len(failed_files)} 个文件处理失败:")
            for file in failed_files[:10]:  # 只显示前10个失败文件
                logger.warning(f"  - {file}")
            if len(failed_files) > 10:
                logger.warning(f"  ... 以及其他 {len(failed_files) - 10} 个文件")
        
        return success_count


def parse_color(color_str):
    """解析颜色字符串为RGBA元组"""
    try:
        # 格式: "r,g,b,a" 或 "r,g,b"
        parts = [int(x) for x in color_str.split(',')]
        if len(parts) == 3:
            return (parts[0], parts[1], parts[2], 128)  # 默认半透明
        elif len(parts) == 4:
            return tuple(parts)
        else:
            raise ValueError("颜色格式不正确")
    except Exception:
        raise argparse.ArgumentTypeError("颜色格式应为'r,g,b'或'r,g,b,a'，例如'255,255,255,128'")


def main():
    """主函数，处理命令行参数并执行水印添加"""
    parser = argparse.ArgumentParser(description='给照片添加基于EXIF信息的日期水印')
    
    parser.add_argument('input_path', help='输入图片文件或目录路径')
    parser.add_argument('--font-size', type=int, default=36, help='水印字体大小 (默认: 36)')
    parser.add_argument('--font-color', type=parse_color, default="255,255,255,128", 
                        help='水印颜色，格式为"r,g,b,a" (默认: "255,255,255,128")')
    parser.add_argument('--position', choices=[
        'top-left', 'top-center', 'top-right',
        'center-left', 'center', 'center-right',
        'bottom-left', 'bottom-center', 'bottom-right'
    ], default='bottom-right', help='水印位置 (默认: bottom-right)')
    parser.add_argument('--custom-font', help='自定义字体文件路径', default=None)
    parser.add_argument('--date-format', help='日期格式，默认为YYYY-MM-DD', default='%Y-%m-%d')
    parser.add_argument('--unknown-text', help='无法获取EXIF日期时显示的文本', default='未知日期')
    parser.add_argument('--padding', type=int, help='水印边距', default=20)
    parser.add_argument('--parallel', action='store_true', help='启用并行处理')
    parser.add_argument('--workers', type=int, help='并行处理的最大工作线程数')
    
    args = parser.parse_args()
    
    # 使用Builder模式创建水印处理器
    builder = WatermarkBuilder()
    builder.with_font_size(args.font_size)
    builder.with_font_color(args.font_color)
    builder.with_position(args.position)
    
    if args.custom_font:
        builder.with_custom_font(args.custom_font)
    
    builder.with_date_format(args.date_format)
    builder.with_unknown_date_text(args.unknown_text)
    builder.with_padding(args.padding)
    
    # 设置并行处理选项
    if args.parallel:
        builder.with_parallel_processing(True, args.workers)
    
    watermarker = builder.build()
    
    input_path = Path(args.input_path)
    
    if input_path.is_file():
        # 处理单个文件
        output_dir = input_path.parent / f"{input_path.parent.name}_watermark"
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / input_path.name
        
        if watermarker.add_watermark(str(input_path), str(output_path)):
            logger.info("水印添加成功！")
            return 0
        else:
            logger.error("水印添加失败！")
            return 1
    
    elif input_path.is_dir():
        # 处理目录
        success_count = watermarker.process_directory(str(input_path))
        logger.info(f"已成功处理 {success_count} 张图片")
        return 0 if success_count > 0 else 1
    
    else:
        logger.error(f"输入路径不存在: {args.input_path}")
        return 1


if __name__ == "__main__":
    sys.exit(main())