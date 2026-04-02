"""
曲谱重命名器
读取识别结果 CSV，根据调号和曲名对文件进行重命名
"""

import os
import sys
import csv


def rename_files_from_csv(csv_path):
    """读取 CSV 文件并重命名文件

    Args:
        csv_path: CSV 文件路径
    """
    if not os.path.exists(csv_path):
        print(f"错误：CSV 文件不存在: {csv_path}")
        return

    # 读取 CSV
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # 获取 CSV 所在目录
    folder_path = os.path.dirname(csv_path)

    # 统计
    success_count = 0
    skip_count = 0
    fail_count = 0

    print(f"\n开始处理 {len(rows)} 条记录...\n")

    for row in rows:
        original_filename = row.get('原文件名', '')
        key = row.get('调号', '')
        title = row.get('曲名', '')
        status = row.get('状态', '')

        # 跳过错误记录
        if '错误' in status or key == '错误' or title == '无':
            print(f"跳过: {original_filename} (状态: {status})")
            skip_count += 1
            continue

        # 跳过没有曲名的记录
        if not title or title == '无':
            print(f"跳过: {original_filename} (无曲名)")
            skip_count += 1
            continue

        # 构建新文件名
        ext = os.path.splitext(original_filename)[1]

        if key and key != '未知' and key != '无':
            new_name = f"{key}-{title}{ext}"
        else:
            new_name = f"{title}{ext}"

        original_path = os.path.join(folder_path, original_filename)
        new_path = os.path.join(folder_path, new_name)

        # 检查原文件是否存在
        if not os.path.exists(original_path):
            print(f"错误: 文件不存在: {original_filename}")
            fail_count += 1
            continue

        # 如果文件名没变，跳过
        if new_name == original_filename:
            print(f"跳过: {original_filename} (文件名未改变)")
            skip_count += 1
            continue

        # 检查是否重名
        if os.path.exists(new_path):
            new_name = f"{key}-{title}_{original_filename}{ext}" if key and key != '未知' else f"{title}_{original_filename}{ext}"
            new_path = os.path.join(folder_path, new_name)

        # 重命名
        try:
            os.rename(original_path, new_path)
            print(f"重命名: {original_filename} -> {new_name}")
            success_count += 1
        except Exception as e:
            print(f"错误: {original_filename} 重命名失败: {str(e)}")
            fail_count += 1

    # 打印汇总
    print(f"\n{'='*50}")
    print(f"重命名完成！")
    print(f"成功: {success_count} 个")
    print(f"跳过: {skip_count} 个")
    print(f"失败: {fail_count} 个")
    print(f"{'='*50}")


def main():
    if len(sys.argv) < 2:
        print("请指定文件夹编号或CSV文件路径")
        print("用法: python renamer.py <文件夹编号>")
        print("示例: python renamer.py 0")
        sys.exit(1)

    arg = sys.argv[1]

    # 如果输入的是完整路径，直接使用
    if os.path.isabs(arg):
        csv_path = arg
    else:
        # 相对路径，拼接 BASE_PATH
        BASE_PATH = r"D:\谱子\共享曲谱"
        # 如果包含路径分隔符，直接拼接
        if '/' in arg or '\\' in arg:
            csv_path = os.path.join(BASE_PATH, arg)
        else:
            # 只是文件夹编号
            csv_path = os.path.join(BASE_PATH, arg, "识别结果.csv")

    rename_files_from_csv(csv_path)


if __name__ == "__main__":
    main()