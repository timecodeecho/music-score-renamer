"""
曲谱图片批量重命名工具
使用 EasyOCR 识别曲名 + Tesseract 识别调号
"""

import os
import sys
import re
import csv
import glob
import easyocr
import pytesseract
import numpy as np
from PIL import Image
from tqdm import tqdm

# 配置 Tesseract 路径
pytesseract.pytesseract.tesseract_cmd = r'D:\app\ai\Tesseract-OCR\tesseract.exe'

# 配置
BASE_PATH = r"D:\谱子\共享曲谱"
# 通过命令行参数获取子文件夹，如 python main.py /0 或 python main.py /1
if len(sys.argv) < 2:
    print("请指定文件夹位置，例如: python main.py /0")
    print("用法: python main.py <文件夹名称>")
    sys.exit(1)

sub_folder = "/" + sys.argv[1]
FOLDER_PATH = BASE_PATH + sub_folder
FOLDER_PATH_UNIX = BASE_PATH.replace('\\', '/') + sub_folder
OUTPUT_CSV = os.path.join(FOLDER_PATH, "识别结果.csv")

print(f"处理文件夹: {FOLDER_PATH}\n")

# 初始化 EasyOCR（中文+英文）
print("正在加载 OCR 模型...")
reader = easyocr.Reader(['ch_sim', 'en'], gpu=True, verbose=False)
print("模型加载完成\n")

# 获取所有图片文件（排除已重命名的如 C-曲名.jpg）
os.chdir(FOLDER_PATH_UNIX)
image_extensions = ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']
all_files = glob.glob("*")
# 过滤：只处理图片文件，且不是以调号开头的文件（排除已完整重命名的如 C-曲名.jpg）
# 曲名.jpg 文件仍包含进去，后续可能修复调号
image_files = [f for f in all_files
               if os.path.splitext(f)[1].lower() in image_extensions
               and not re.match(r'^[#b]?[CDEFGAB]-', f)]

print(f"找到 {len(image_files)} 个需要处理的图片文件")
print(f"输出 CSV: {OUTPUT_CSV}\n")

# 调号匹配正则
key_patterns = [
    r'1=(#?[A-Ga-g])',                   # 1=C, 1=G, 1=#C, 1=bD
    r'1=(♯?[A-Ga-g])',                   # 1=♯C, 1=♯G (Unicode升号)
    r'1=(♭?[A-Ga-g])',                   # 1=♭C, 1=♭D (Unicode降号)
    r'(#?[A-G])调',                      # C调, G调, bB调, #F调
    r'(♯?[A-G])调',                      # ♯C调, ♯G调 (Unicode升号)
    r'(♭?[A-G])调',                      # ♭C调, ♭D调 (Unicode降号)
]

# 调号字母（单独的单个大写字母可能是调号）
KEY_LETTERS = ['C', 'D', 'E', 'F', 'G', 'A', 'B']

# Tesseract 配置
TESSERACT_CONFIG = '--psm 6'


def extract_key_with_tesseract(img_path, region='corner'):
    """用 Tesseract 识别调号，支持多个区域

    region 参数:
    - 'corner': 左上角 30% 区域，匹配 1=C, 1=G, #C, bD 等格式
    - 'below_title': 曲名下方区域，匹配 C调, D调, bB调 等格式
    - 'upper': 整个上部 40% 区域，作为备选
    - 'check_left': 检查调号字母左侧是否有升降号
    """
    img = Image.open(img_path)
    width, height = img.size

    if region == 'corner':
        # 裁剪左上角区域（30% x 30%）
        cropped = img.crop((0, 0, int(width * 0.3), int(height * 0.3)))
    elif region == 'upper':
        # 裁剪整个上部区域（40%）
        cropped = img.crop((0, 0, width, int(height * 0.4)))
    elif region == 'below_title':
        # 曲名下方区域，需要 title_y 参数
        cropped = None  # 下面单独处理
    elif region == 'check_left':
        # 左侧区域，在主循环中调用，需要 img 和 y_center 参数
        cropped = None
    else:
        cropped = None

    if cropped is not None:
        # 使用 Tesseract 识别
        text = pytesseract.image_to_string(cropped, config=TESSERACT_CONFIG)
        text = text.upper()

        # 优先匹配完整的调号格式如 1=C, 1=G
        match = re.search(r'1=([CDEFGAB])', text)
        if match:
            return match.group(1)

        # 匹配带升降号的格式 1=#C, 1=bD
        match = re.search(r'1=(#?[CDEFGAB])', text)
        if match:
            return match.group(1)

        # 匹配 X调 格式
        match = re.search(r'(#?[A-G])调', text)
        if match:
            return match.group(1)

        # 单独大写字母：需要检查左侧
        match = re.search(r'(#?[CDEFGAB])\b', text)
        if match:
            return match.group(1)

    return None


def check_key_prefix_by_tesseract(img_path, key_bbox, img_width, img_height):
    """使用 Tesseract 检查调号前方是否有升降号

    在调号前方（左侧）同等宽度、2倍高度的区域查找升降号

    Args:
        img_path: 图片路径
        key_bbox: 调号字母的边界框 (x1, y1, x2, y2)
        img_width: 图片宽度
        img_height: 图片高度

    Returns:
        ('#' 或 'b' 或 None, 识别到的文本)
    """
    x1, y1, x2, y2 = key_bbox
    key_width = x2 - x1
    key_height = y2 - y1

    # 调号前方区域：左侧同等宽度，2倍高度
    left = max(0, x1 - key_width)
    top = max(0, y1 - key_height // 2)  # 向上扩展 key_height 的高度
    right = x1
    bottom = y2 + key_height // 2  # 向下扩展 key_height 的高度

    if right <= left or bottom <= top:
        return None, ""

    img = Image.open(img_path)
    # 裁剪调号前方的区域
    prefix_region = img.crop((left, top, right, bottom))

    # 用 Tesseract 识别
    text = pytesseract.image_to_string(prefix_region, config=TESSERACT_CONFIG)
    text = text.strip()

    # 检查升号：#, ♯, 井
    if '#' in text or '♯' in text or '井' in text:
        return '#', text

    # 检查降号：b, B, 6, 0, ♭, ь
    flat_chars = ['b', 'B', '6', '0', '♭', 'ь']
    for c in flat_chars:
        if c in text:
            # 排除包含"调"的词（如"B调"）
            if '调' not in text:
                return 'b', text

    return None, text


def extract_key_from_title_region(img_path, title_y_center):
    """Tesseract 识别曲名下方区域"""
    img = Image.open(img_path)
    width, height = img.size

    # 裁剪曲名下方区域（从 title_y 向下 30% 区域）
    y_start = int(title_y_center)
    y_end = int(height * 0.6)
    if y_end > height:
        y_end = height
    if y_start >= y_end:
        return None

    cropped = img.crop((0, y_start, width, y_end))

    # 使用 Tesseract 识别
    text = pytesseract.image_to_string(cropped, config=TESSERACT_CONFIG)
    text = text.upper()

    # 匹配 X调 格式
    match = re.search(r'(#?[A-G])调', text)
    if match:
        return match.group(1)

    # 匹配单独的调号字母
    match = re.search(r'(#?[A-G])\b', text)
    if match:
        return match.group(1)

    return None


def read_upper_region(img_path, ratio=0.4):
    """只识别图片上部指定比例的区域，返回所有文字块及其位置"""
    img = Image.open(img_path)
    width, height = img.size
    # 裁剪上部区域
    cropped = img.crop((0, 0, width, int(height * ratio)))

    # 转换为 numpy array 传给 EasyOCR
    img_array = np.array(cropped)

    # detail=1 返回位置信息 (bbox, text, confidence)
    ocr_result = reader.readtext(img_array, detail=1)

    if not ocr_result:
        return [], None, width, height

    # 收集所有文字块
    texts_with_position = []
    for bbox, text, prob in ocr_result:
        if prob < 0.5:  # 过滤低置信度
            continue
        # 计算文字块面积
        area = (bbox[2][0] - bbox[0][0]) * (bbox[2][1] - bbox[0][1])
        texts_with_position.append({
            'text': text,
            'prob': prob,
            'area': area,
            'y_center': (bbox[0][1] + bbox[2][1]) / 2,
            'x_center': (bbox[0][0] + bbox[2][0]) / 2,
            'y_top': bbox[0][1],
            'y_bottom': bbox[2][1],
            'x_left': bbox[0][0],
            'x_right': bbox[2][0]
        })

    # 找出最大的非调号文字块作为曲名
    # 排除包含"调"或数字的文字（这些是调号信息，如"C调筒音作5"）
    def is_key_info(text):
        """判断是否是调号信息"""
        if '调' in text:
            return True
        # 检查是否包含数字
        if re.search(r'\d', text):
            return True
        # 排除制谱、编曲、作曲等信息
        if any(kw in text for kw in ['制谱', '编曲', '作曲', '记谱', '演奏']):
            return True
        return False

    # 按 y 坐标排序（越靠上越可能是曲名）
    texts_sorted = sorted(texts_with_position, key=lambda x: x['y_top'])

    # 找到第一个非调号信息文字块作为曲名
    best_text = None
    for t in texts_sorted:
        if not is_key_info(t['text']):
            best_text = t['text']
            break

    return texts_with_position, best_text, width, height


# 处理结果
results = []
success_count = 0
fail_count = 0

for img_path in tqdm(image_files, desc="识别进度"):
    filename = os.path.basename(img_path)
    ext = os.path.splitext(filename)[1]
    key = None
    title = None

    try:
        # 使用新的区域识别方法
        texts_with_position, largest_text, img_width, img_height = read_upper_region(img_path, ratio=0.4)

        if not texts_with_position:
            raise Exception("未识别到文字")

        # 找出最大的文字块作为曲名
        title = largest_text
        # 过滤掉太短的或像调号的
        if title and (len(title) < 2 or title in KEY_LETTERS):
            title = None

        # 提取调号
        key = None
        key_method = None  # 记录调号识别方法
        key_prefix_text = ""  # 记录升降号检测的识别文本
        all_text = ' '.join([t['text'] for t in texts_with_position])

        # 方法1: 优先匹配 1=D、1=#C 格式（带升降号）
        for pattern in key_patterns:
            match = re.search(pattern, all_text)
            if match:
                key = match.group(1).upper()
                key_method = "EasyOCR文本匹配"
                break

        # 方法2: Tesseract 识别左上角英文字母调号
        if not key:
            key = extract_key_with_tesseract(img_path, region='corner')
            if key:
                key_method = "Tesseract左上角"

        # 方法2.5: 无论是否已有升降号，都搜索左上角区域检测升降号
        if key:
            # 用 EasyOCR 查找调号字母的位置
            for t in texts_with_position:
                if t['text'].upper() == key or (len(key) == 1 and t['text'].upper() == key):
                    # 用 Tesseract 检查前方是否有 # 或 b
                    key_bbox = (t['x_left'], t['y_top'], t['x_right'], t['y_bottom'])
                    prefix, prefix_text = check_key_prefix_by_tesseract(img_path, key_bbox, img_width, img_height)
                    key_prefix_text = prefix_text  # 保存升降号检测结果
                    if prefix and len(key) == 1:
                        # 原本是纯字母，加上升降号
                        key = prefix + key
                        key_method = "Tesseract前方升降号"
                    elif prefix:
                        # 原本已有升降号
                        key_method = "Tesseract前方升降号"
                    break

        # 方法3: 用 Tesseract 识别曲名下方区域的调号
        if not key and title:
            title_y = None
            for t in texts_with_position:
                if t['text'] == title:
                    title_y = t['y_center']
                    break
            if title_y:
                key = extract_key_from_title_region(img_path, title_y)
                if key:
                    key_method = "Tesseract曲名下方"

        # 方法4: Tesseract 识别整个上部区域（备选）
        if not key:
            key = extract_key_with_tesseract(img_path, region='upper')
            if key:
                key_method = "Tesseract上部全区域"

        # 判断识别状态
        if key and title:
            # 调号和曲名都识别到
            new_name = f"{key}-{title}{ext}"
            new_path = os.path.join(FOLDER_PATH, new_name)

            # 检查是否重名
            if os.path.exists(new_path):
                new_name = f"{key}-{title}_{filename}{ext}"
                new_path = os.path.join(FOLDER_PATH, new_name)

            os.rename(img_path, new_path)
            status = "成功"
            success_count += 1
        elif title and not key:
            # 只识别到曲名，没有调号
            new_name = f"{title}{ext}"
            new_path = os.path.join(FOLDER_PATH, new_name)

            # 如果新文件名和原文件名相同，跳过重命名
            if new_name == filename:
                new_path = img_path
                status = "已存在"
            else:
                # 检查是否重名
                if os.path.exists(new_path):
                    new_name = f"{title}_{filename}{ext}"
                    new_path = os.path.join(FOLDER_PATH, new_name)

                os.rename(img_path, new_path)
                status = "成功（无调号）"
            success_count += 1
        else:
            new_name = filename
            new_path = img_path
            if not title and not key:
                status = "未识别到曲名和调号"
            elif not title:
                status = "未识别到曲名"
            elif not key:
                status = "未识别到调号"
            else:
                status = "未知错误"
            fail_count += 1
            key = key if key else "未知"
            title = title if title else "无"

    except Exception as e:
        new_name = filename
        new_path = img_path
        status = f"错误: {str(e)}"
        key = "错误"
        title = "无"
        fail_count += 1

    results.append({
        "原文件名": filename,
        "调号": key if key else "未知",
        "调号识别方法": key_method if key_method else "无",
        "升降号检测文本": key_prefix_text if key_prefix_text else "无",
        "曲名": title if title else "无",
        "新文件名": new_name,
        "状态": status
    })

# 写入 CSV
with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=["原文件名", "调号", "调号识别方法", "升降号检测文本", "曲名", "新文件名", "状态"])
    writer.writeheader()
    writer.writerows(results)

# 打印汇总
print(f"\n{'='*50}")
print(f"处理完成！")
print(f"成功: {success_count} 个")
print(f"失败: {fail_count} 个")
print(f"CSV 报告: {OUTPUT_CSV}")
print(f"{'='*50}")