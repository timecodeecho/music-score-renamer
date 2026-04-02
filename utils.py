"""
曲谱识别公共模块
提取识别和调号提取的公共方法
"""

import re
import pytesseract
from PIL import Image
import numpy as np
import easyocr


# ============= 常量定义 =============

# 调号匹配正则
KEY_PATTERNS = [
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

# 需要排除的曲名关键词
TITLE_EXCLUDE_KEYWORDS = ['制谱', '编曲', '作曲', '记谱', '演奏']


# ============= 公共函数 =============

def init_easyocr():
    """初始化 EasyOCR（中文+英文）"""
    return easyocr.Reader(['ch_sim', 'en'], gpu=True, verbose=False)


def is_key_info(text):
    """判断是否是调号信息"""
    if '调' in text:
        return True
    # 检查是否包含数字
    if re.search(r'\d', text):
        return True
    # 排除制谱、编曲、作曲等信息
    if any(kw in text for kw in TITLE_EXCLUDE_KEYWORDS):
        return True
    return False


def is_renamed_file(filename):
    """检查文件名是否已重命名（以调号开头）"""
    return bool(re.match(r'^[#b]?[CDEFGAB]-', filename))


def remove_spaces(text):
    """移除字符串中的所有空格"""
    if text:
        return text.replace(' ', '').replace('\u3000', '')  # 普通空格和全角空格
    return text


def read_upper_region(img_path, ratio=0.4, reader=None):
    """只识别图片上部指定比例的区域，返回所有文字块及其位置

    Args:
        img_path: 图片路径
        ratio: 识别区域占图片高度的比例（默认40%）
        reader: EasyOCR Reader 实例，如果为None则创建新实例

    Returns:
        texts_with_position: 所有文字块列表（包含位置信息）
        best_text: 第一个非调号信息的文字块（曲名候选）
        img_width: 图片宽度
        img_height: 图片高度
    """
    # 如果没有传入 reader，创建一个临时使用
    temp_reader = None
    if reader is None:
        temp_reader = init_easyocr()
        use_reader = temp_reader
    else:
        use_reader = reader

    img = Image.open(img_path)
    width, height = img.size
    # 裁剪上部区域
    cropped = img.crop((0, 0, width, int(height * ratio)))

    # 转换为 numpy array 传给 EasyOCR
    img_array = np.array(cropped)

    # detail=1 返回位置信息 (bbox, text, confidence)
    ocr_result = use_reader.readtext(img_array, detail=1)

    # 释放临时 reader
    if temp_reader:
        del temp_reader

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

    # 按 y 坐标排序（越靠上越可能是曲名）
    texts_sorted = sorted(texts_with_position, key=lambda x: x['y_top'])

    # 找到第一个非调号信息文字块作为曲名
    best_text = None
    for t in texts_sorted:
        if not is_key_info(t['text']):
            best_text = t['text']
            break

    return texts_with_position, best_text, width, height


def extract_key_with_tesseract(img, region='corner'):
    """用 Tesseract 识别调号，支持多个区域

    Args:
        img: PIL Image 对象
        region: 识别区域
            - 'corner': 左上角 30% 区域，匹配 1=C, 1=G, #C, bD 等格式
            - 'upper': 整个上部 40% 区域，作为备选

    Returns:
        调号字母（如 'C', '#C', 'bD'）或 None
    """
    width, height = img.size

    if region == 'corner':
        # 裁剪左上角区域（30% x 30%）
        cropped = img.crop((0, 0, int(width * 0.3), int(height * 0.3)))
    elif region == 'upper':
        # 裁剪整个上部区域（40%）
        cropped = img.crop((0, 0, width, int(height * 0.4)))
    else:
        return None

    if cropped is None:
        return None

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


def check_key_prefix_by_tesseract(img, key_bbox):
    """使用 Tesseract 检查调号前方是否有升降号

    在调号前方（左侧）同等宽度、2倍高度的区域查找升降号

    Args:
        img: PIL Image 对象
        key_bbox: 调号字母的边界框 (x1, y1, x2, y2)

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


def extract_key_from_title_region(img, title_y_center):
    """Tesseract 识别曲名下方区域

    Args:
        img: PIL Image 对象
        title_y_center: 曲名中心的 Y 坐标

    Returns:
        调号字母或 None
    """
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


def extract_key_from_ocr_text(all_text):
    """从 EasyOCR 识别的文本中提取调号

    Args:
        all_text: EasyOCR 识别到的所有文本合并的字符串

    Returns:
        (调号字母, 识别方法) 或 (None, None)
    """
    for pattern in KEY_PATTERNS:
        match = re.search(pattern, all_text)
        if match:
            key = match.group(1).upper()
            return key, "EasyOCR文本匹配"
    return None, None


def extract_key_multi_method(img_path, texts_with_position, reader):
    """使用多种方法提取调号

    Args:
        img_path: 图片路径
        texts_with_position: EasyOCR 识别结果（包含位置信息）
        reader: EasyOCR Reader 实例

    Returns:
        (调号, 识别方法, 升降号检测文本)
    """
    key = None
    key_method = None
    key_prefix_text = ""

    # 收集所有文本用于正则匹配
    all_text = ' '.join([t['text'] for t in texts_with_position])

    # 方法1: EasyOCR 文本正则匹配
    key, key_method = extract_key_from_ocr_text(all_text)

    # 方法2: Tesseract 左上角
    if not key:
        img = Image.open(img_path)
        key = extract_key_with_tesseract(img, region='corner')
        if key:
            key_method = "Tesseract左上角"

    # 方法2.5: Tesseract 检测调号前方升降号
    if key:
        img = Image.open(img_path)
        # 查找调号字母的位置
        for t in texts_with_position:
            if t['text'].upper() == key or (len(key) == 1 and t['text'].upper() == key):
                key_bbox = (t['x_left'], t['y_top'], t['x_right'], t['y_bottom'])
                prefix, prefix_text = check_key_prefix_by_tesseract(img, key_bbox)
                key_prefix_text = prefix_text
                if prefix and len(key) == 1:
                    key = prefix + key
                    key_method = "Tesseract前方升降号"
                elif prefix:
                    key_method = "Tesseract前方升降号"
                break

    # 方法3: Tesseract 曲名下方
    if not key:
        # 找到曲名的位置
        for t in texts_with_position:
            if not is_key_info(t['text']):
                img = Image.open(img_path)
                key = extract_key_from_title_region(img, t['y_center'])
                if key:
                    key_method = "Tesseract曲名下方"
                break

    # 方法4: Tesseract 上部全区域（备选）
    if not key:
        img = Image.open(img_path)
        key = extract_key_with_tesseract(img, region='upper')
        if key:
            key_method = "Tesseract上部全区域"

    return key, key_method, key_prefix_text


def filter_title(title):
    """过滤曲名：去除空格，移除过短或像调号的

    Args:
        title: 原始曲名

    Returns:
        处理后的曲名或 None
    """
    if not title:
        return None
    # 去除空格
    title = remove_spaces(title)
    # 过滤掉太短的或像调号的
    if len(title) < 2 or title in KEY_LETTERS:
        return None
    return title


def build_new_filename(key, title, original_ext):
    """根据调号和曲名构建新文件名

    Args:
        key: 调号（如 'C', '#C', 'bD'）
        title: 曲名
        original_ext: 原文件扩展名

    Returns:
        新文件名
    """
    if key and title:
        return f"{key}-{title}{original_ext}"
    elif title:
        return f"{title}{original_ext}"
    return None