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

# 获取所有 IMG 开头的图片文件
os.chdir(FOLDER_PATH_UNIX)
image_extensions = ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']
all_files = glob.glob("IMG_*")
image_files = [f for f in all_files if os.path.splitext(f)[1].lower() in image_extensions]

print(f"找到 {len(image_files)} 个 IMG 开头的图片文件")
print(f"输出 CSV: {OUTPUT_CSV}\n")

# 调号匹配正则
key_patterns = [
    r'1=(#?[A-Ga-g])',         # 1=C, 1=G, 1=#C, 1=bD
    r'(#?[A-G])调',            # C调, G调, bB调, #F调
]

# 调号字母（单独的单个大写字母可能是调号）
KEY_LETTERS = ['C', 'D', 'E', 'F', 'G', 'A', 'B']


def extract_key_with_tesseract(img_path):
    """用 Tesseract 识别左上角调号字母"""
    img = Image.open(img_path)
    width, height = img.size

    # 裁剪左上角区域（30% x 30%）
    corner = img.crop((0, 0, int(width * 0.3), int(height * 0.3)))

    # 使用 Tesseract 识别
    text = pytesseract.image_to_string(corner, config='--psm 6')
    text = text.upper()

    # 提取单个大写字母（C/D/E/F/G/A/B）
    # 优先找完整的调号格式如 1=C, 1=G
    match = re.search(r'1=([CDEFGAB])', text)
    if match:
        return match.group(1)

    # 找单独的调号字母
    match = re.search(r'([CDEFGAB])\s*$', text, re.MULTILINE)
    if match:
        return match.group(1)

    return None


def extract_key_from_corner(texts_with_position, width, height):
    """从左上角区域提取调号"""
    # 定义左上角区域（左上 20% x 20%）
    corner_x_limit = width * 0.3
    corner_y_limit = height * 0.3

    # 找左上角的文字块
    corner_texts = []
    for t in texts_with_position:
        if t['x_center'] < corner_x_limit and t['y_center'] < corner_y_limit:
            # 优先找单个大写字母
            if t['text'].upper() in KEY_LETTERS and len(t['text']) <= 2:
                corner_texts.append(t)

    if not corner_texts:
        return None

    # 按 y 坐标排序（越靠上越可能是调号）
    corner_texts.sort(key=lambda x: x['y_top'])

    # 返回最上面的小文字（调号通常较小，在曲名旁边）
    for t in corner_texts:
        if t['area'] < 5000:  # 面积较小的可能是调号
            return t['text'].upper()

    # 如果没找到小的，返回第一个
    return corner_texts[0]['text'].upper()


def read_upper_region(img_path, ratio=0.4):
    """只识别图片上部指定比例的区域，返回所有文字块及其位置"""
    from PIL import Image
    import numpy as np

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
        return False

    # 按面积排序
    texts_sorted = sorted(texts_with_position, key=lambda x: x['area'], reverse=True)

    # 找到最大的非调号信息文字块
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
        if title and (len(title) < 2 or title in ['C', 'D', 'E', 'F', 'G', 'A', 'B']):
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
            key = extract_key_with_tesseract(img_path)

        # 方法3: 如果没找到 1=X 格式，从曲名下方找 X调 格式
        if not key and title:
            title_y = None
            for t in texts_with_position:
                if t['text'] == title:
                    title_y = t['y_center']
                    break
            if title_y:
                for t in texts_with_position:
                    if t['y_center'] > title_y:
                        match = re.search(r'(#?[A-G])调', t['text'])
                        if match:
                            key = match.group(1).upper()
                            break

        # 方法3: 从左上角区域找调号字母
        if not key:
            key = extract_key_from_corner(texts_with_position, img_width, img_height)

        # 判断识别状态
        if key and title:
            new_name = f"{key}-{title}{ext}"
            new_path = os.path.join(FOLDER_PATH, new_name)

            # 检查是否重名
            if os.path.exists(new_path):
                new_name = f"{key}-{title}_{filename}{ext}"
                new_path = os.path.join(FOLDER_PATH, new_name)

            os.rename(img_path, new_path)
            status = "成功"
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