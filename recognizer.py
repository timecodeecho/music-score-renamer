"""
曲谱识别器
仅执行 OCR 识别，输出 CSV 结果，不对文件进行重命名
"""

import os
import sys
import csv
import glob
from tqdm import tqdm
from utils import (
    init_easyocr,
    read_upper_region,
    extract_key_multi_method,
    filter_title,
    is_renamed_file
)

import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'D:\app\ai\Tesseract-OCR\tesseract.exe'

# 配置
BASE_PATH = r"D:\谱子\共享曲谱"
if len(sys.argv) < 2:
    print("请指定文件夹位置，例如: python recognizer.py 0")
    print("用法: python recognizer.py <文件夹名称>")
    sys.exit(1)

sub_folder = "/" + sys.argv[1]
FOLDER_PATH = BASE_PATH + sub_folder
FOLDER_PATH_UNIX = BASE_PATH.replace('\\', '/') + sub_folder
OUTPUT_CSV = os.path.join(FOLDER_PATH, "识别结果.csv")

print(f"处理文件夹: {FOLDER_PATH}\n")

# 初始化 EasyOCR（中文+英文）
print("正在加载 OCR 模型...")
reader = init_easyocr()
print("模型加载完成\n")

# 获取所有图片文件（排除已重命名的如 C-曲名.jpg）
os.chdir(FOLDER_PATH_UNIX)
image_extensions = ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']
all_files = glob.glob("*")
# 过滤：只处理图片文件，且不是以调号开头的文件（排除已完整重命名的如 C-曲名.jpg）
# 曲名.jpg 文件仍包含进去，后续可能修复调号
image_files = [f for f in all_files
               if os.path.splitext(f)[1].lower() in image_extensions
               and not is_renamed_file(f)]

print(f"找到 {len(image_files)} 个需要处理的图片文件")
print(f"输出 CSV: {OUTPUT_CSV}\n")

# 处理结果
results = []
success_count = 0
fail_count = 0

for img_path in tqdm(image_files, desc="识别进度"):
    filename = os.path.basename(img_path)
    ext = os.path.splitext(filename)[1]
    key = None
    title = None
    key_method = None
    key_prefix_text = ""

    try:
        # 使用 utils 中的区域识别方法
        texts_with_position, raw_title, img_width, img_height = read_upper_region(img_path, ratio=0.4, reader=reader)

        if not texts_with_position:
            raise Exception("未识别到文字")

        # 过滤曲名（去空格，移除过短或像调号的）
        title = filter_title(raw_title)

        # 提取调号
        key, key_method, key_prefix_text = extract_key_multi_method(
            img_path, texts_with_position, reader
        )

        # 判断识别状态
        if key and title:
            status = "成功"
            success_count += 1
        elif title and not key:
            status = "成功（无调号）"
            success_count += 1
        else:
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
        status = f"错误: {str(e)}"
        key = "错误"
        title = "无"
        fail_count += 1

    results.append({
        "原文件名": filename,
        "调号": key,
        "调号识别方法": key_method if key_method else "无",
        "升降号检测文本": key_prefix_text if key_prefix_text else "无",
        "曲名": title,
        "状态": status
    })

# 写入 CSV（不含"新文件名"列）
with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=["原文件名", "调号", "调号识别方法", "升降号检测文本", "曲名", "状态"])
    writer.writeheader()
    writer.writerows(results)

# 打印汇总
print(f"\n{'='*50}")
print(f"识别完成！")
print(f"成功: {success_count} 个")
print(f"失败: {fail_count} 个")
print(f"CSV 报告: {OUTPUT_CSV}")
print(f"{'='*50}")