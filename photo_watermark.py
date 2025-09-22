#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Photo Watermark Tool
A command-line tool to add date watermarks to photos based on EXIF data.
"""

import os
import sys
import argparse
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ExifTags
import piexif
from pathlib import Path
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PhotoWatermark:
    """处理照片水印的主类"""
    
    def __init__(self, font_size=36, font_color=(255, 255, 255, 128), position="bottom-right"):
        """
        初始化水印处理器
        
        参数:
            font_size (int): 水印字体大小
            font_color (tuple): 水印颜色 (R,G,B,A)
            position (str): 水印位置 ('top-left', 'top-center', 'top-right', 
                                    'center-left', 'center', 'center-right',
                                    'bottom-left', 'bottom-center', 'bottom-right')
        """
        self.font_size = font_size
        self.font_color = font_color
        self.position = position
        
        # 尝试加载默认字体
        try:
            # 尝试加载系统字体
            if os.name == 'nt':  # Windows
                self.font = ImageFont.truetype("arial.ttf", self.font_size)
            else:  # Linux/Mac
                self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", self.font_size)
        except IOError:
            # 如果找不到系统字体，使用默认字体
            logger.warning("无法加载系统字体，使用默认字体")
            self.font = ImageFont.load_default()
    
    def get_exif_date(self, image_path):
        """
        从图片中提取EXIF拍摄日期
        
        参数:
            image_path (str): 图片文件路径
            
        返回:
            str: 格式化的日期字符串 (YYYY-MM-DD)，如果没有EXIF数据则返回None
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
                    return date_obj.strftime('%Y-%m-%d')
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
                            return date_obj.strftime('%Y-%m-%d')
            
            # 如果找不到DateTimeOriginal，尝试其他日期字段
            for tag_id, tag_name in ExifTags.TAGS.items():
                if tag_name in ['DateTime', 'DateTimeDigitized'] and tag_id in exif_data:
                    date_str = exif_data[tag_id]
                    date_obj = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                    return date_obj.strftime('%Y-%m-%d')
                    
            return None
        except Exception as e:
            logger.error(f"读取EXIF数据时出错: {e}")
            return None
    
    def calculate_position(self, img_width, img_height, text_width, text_height):
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
        padding = 20  # 边距
        
        positions = {
            'top-left': (padding, padding),
            'top-center': ((img_width - text_width) // 2, padding),
            'top-right': (img_width - text_width - padding, padding),
            'center-left': (padding, (img_height - text_height) // 2),
            'center': ((img_width - text_width) // 2, (img_height - text_height) // 2),
            'center-right': (img_width - text_width - padding, (img_height - text_height) // 2),
            'bottom-left': (padding, img_height - text_height - padding),
            'bottom-center': ((img_width - text_width) // 2, img_height - text_height - padding),
            'bottom-right': (img_width - text_width - padding, img_height - text_height - padding)
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
        try:
            # 获取拍摄日期
            date_str = self.get_exif_date(image_path)
            if not date_str:
                logger.warning(f"无法从图片获取日期信息: {image_path}")
                date_str = "未知日期"
            
            # 打开图片
            img = Image.open(image_path)
            
            # 创建一个可以绘制的图层
            watermark = Image.new('RGBA', img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(watermark)
            
            # 计算文本大小
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
            watermarked.save(output_path)
            
            logger.info(f"已添加水印并保存到: {output_path}")
            return True
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
        
        # 计数器
        success_count = 0
        
        # 处理每个文件
        for file_path in input_path.glob('*'):
            if file_path.is_file() and file_path.suffix.lower() in supported_formats:
                output_path = output_dir / file_path.name
                if self.add_watermark(str(file_path), str(output_path)):
                    success_count += 1
        
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
    """主函数"""
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
    
    args = parser.parse_args()
    
    # 创建水印处理器
    watermarker = PhotoWatermark(
        font_size=args.font_size,
        font_color=args.font_color,
        position=args.position
    )
    
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