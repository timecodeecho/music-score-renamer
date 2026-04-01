"""
曲谱图片批量重命名工具
使用 EasyOCR 识别曲谱图片中的调号和曲名
"""

import os
import re
import csv
import glob
import easyocr
from PIL import Image
from tqdm import tqdm

# 配置
FOLDER_PATH = r"D:\谱子\共享曲谱\0"
FOLDER_PATH_UNIX = "D:/谱子/共享曲谱/0"
OUTPUT_CSV = os.path.join(FOLDER_PATH, "识别结果.csv")

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
    r'1=([A-Ga-g])',           # 1=C, 1=G
    r'([A-G])调',              # C调, G调
    r'(b?[A-G])$',             # 升降号结尾
]


def read_upper_region(img_path, ratio=0.4):
    """只识别图片上部指定比例的区域，找到最大的文字块作为曲名"""
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
        return []

    # 找出面积最大的文字块（通常是曲名）
    # bbox 是四个角坐标: [(x1,y1), (x2,y1), (x2,y2), (x1,y2)]
    max_area = 0
    best_text = None

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
            'x_center': (bbox[0][0] + bbox[2][0]) / 2
        })

        if area > max_area:
            max_area = area
            best_text = text

    return texts_with_position, best_text


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
        texts_with_position, largest_text = read_upper_region(img_path, ratio=0.3)

        if not texts_with_position:
            raise Exception("未识别到文字")

        # 1. 从所有文字中提取调号
        all_text = ' '.join([t['text'] for t in texts_with_position])
        for pattern in key_patterns:
            match = re.search(pattern, all_text)
            if match:
                key = match.group(1).upper()
                break

        # 2. 取最大的文字块作为曲名
        title = largest_text

        # 过滤掉太短的或像调号的
        if title and (len(title) < 2 or title in ['C', 'D', 'E', 'F', 'G', 'A', 'B']):
            title = None

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
            status = "未识别到调号或曲名"
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