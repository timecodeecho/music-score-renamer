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
    r'1=(#?[A-Ga-g])',         # 1=C, 1=G, 1=#C, 1=bD
    r'(#?[A-G])调',            # C调, G调, bB调, #F调
]

# 调号字母（单独的单个大写字母可能是调号）
KEY_LETTERS = ['C', 'D', 'E', 'F', 'G', 'A', 'B']


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
        text = pytesseract.image_to_string(cropped, config='--psm 6')
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


def check_key_prefix(img_path, key_y_center, key_x_right):
    """检查调号字母左侧是否有 # 或 b

    Args:
        img_path: 图片路径
        key_y_center: 调号字母的垂直中心位置
        key_x_right: 调号字母的右侧 x 坐标

    Returns:
        带升降号的调号，如 #C, bD，或 None
    """
    img = Image.open(img_path)
    width, height = img.size

    # 裁剪调号字母左侧区域（宽度为调号字母宽度的 2 倍）
    left_width = int((key_x_right) * 0.5) if key_x_right > 0 else int(width * 0.1)
    if left_width <= 0:
        left_width = int(width * 0.1)

    # 裁剪左侧区域（高度范围与调号字母相同）
    half_height = int(height * 0.05)
    y_top = max(0, int(key_y_center) - half_height)
    y_bottom = min(height, int(key_y_center) + half_height)

    left_region = img.crop((0, y_top, left_width, y_bottom))

    # 识别左侧内容
    text = pytesseract.image_to_string(left_region, config='--psm 6')
    text = text.strip().upper()

    # 检查是否有 # 或 b
    if '#' in text:
        return '#'
    elif 'B' in text:
        # 可能是 b，需要更精确判断 - 检查是否是降号符号
        # 降号 b 通常比较小且单独出现
        if re.search(r'^B$|^B\s', text) or re.search(r'\sB$|\sB\s', text):
            return 'b'
        # 如果是 B 调中的 B，不是降号
        if '调' in text:
            return None

    return None


def check_key_prefix_by_tesseract(img_path, key_x_center, key_y_center, img_width, img_height):
    """使用 Tesseract 检查调号左上方是否有升降号

    Args:
        img_path: 图片路径
        key_x_center: 调号字母的 x 中心坐标
        key_y_center: 调号字母的 y 中心坐标
        img_width: 图片宽度
        img_height: 图片高度

    Returns:
        '#' 或 'b' 或 None
    """
    img = Image.open(img_path)

    # 裁剪调号左上方区域
    # 左侧范围：从 0 到调号位置
    left_end = int(key_x_center)
    # 上方范围：从 0 到调号位置
    top_end = int(key_y_center)

    if left_end <= 0 or top_end <= 0:
        return None

    # 裁剪左上方区域
    left_top_region = img.crop((0, 0, left_end, top_end))

    # 用 Tesseract 识别
    text = pytesseract.image_to_string(left_top_region, config='--psm 6')
    text = text.strip().upper()

    # 检查是否是升号 #
    if '#' in text:
        return '#'

    # 检查是否是降号：B, 6, 0, b
    if 'B' in text or '6' in text or '0' in text:
        # 排除像 "B调" 这样的完整词
        if '调' not in text:
            return 'b'

    # 检查小写的 b（Tesseract 可能识别为小写）
    text_lower = text.lower()
    if 'b' in text_lower and '调' not in text_lower:
        # 确认是单独的 b 不是单词的一部分
        if text_lower == 'b' or text_lower.strip().startswith('b'):
            return 'b'

    return None


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
    text = pytesseract.image_to_string(cropped, config='--psm 6')
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
            'y_bottom': bbox[2][1]
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
        all_text = ' '.join([t['text'] for t in texts_with_position])

        # 方法1: 优先匹配 1=D、1=#C 格式（带升降号）
        for pattern in key_patterns:
            match = re.search(pattern, all_text)
            if match:
                key = match.group(1).upper()
                break

        # 方法2: Tesseract 识别左上角英文字母调号
        if not key:
            key = extract_key_with_tesseract(img_path, region='corner')

        # 方法2.5: 如果识别到调号，检查左侧是否有升降号
        if key and key in KEY_LETTERS:
            # 用 EasyOCR 查找调号字母的位置
            for t in texts_with_position:
                if t['text'].upper() == key:
                    # 用 Tesseract 检查左上方是否有 # 或 b
                    prefix = check_key_prefix_by_tesseract(img_path, t['x_center'], t['y_center'], img_width, img_height)
                    if prefix:
                        key = prefix + key
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

        # 方法4: Tesseract 识别整个上部区域（备选）
        if not key:
            key = extract_key_with_tesseract(img_path, region='upper')

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
        "曲名": title if title else "无",
        "新文件名": new_name,
        "状态": status
    })

# 写入 CSV
with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=["原文件名", "调号", "曲名", "新文件名", "状态"])
    writer.writeheader()
    writer.writerows(results)

# 打印汇总
print(f"\n{'='*50}")
print(f"处理完成！")
print(f"成功: {success_count} 个")
print(f"失败: {fail_count} 个")
print(f"CSV 报告: {OUTPUT_CSV}")
print(f"{'='*50}")