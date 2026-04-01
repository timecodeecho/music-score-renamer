# 曲谱图片批量重命名工具

使用 EasyOCR 识别曲谱图片中的调号和曲名，批量重命名文件。

## 功能特点

- **智能区域识别**：只识别图片上部 40% 区域（曲名和调号通常在此区域）
- **最大文字块识别**：自动识别面积最大的文字块作为曲名（通常曲名字号最大）
- **调号识别**：支持 `1=C`、`C调` 等多种格式

## 环境要求

- Python 3.8+
- easyocr
- opencv-python
- pillow
- tqdm

## 安装依赖

```bash
pip install easyocr opencv-python pillow tqdm
```

## 使用方法

修改 `main.py` 中的配置：

```python
FOLDER_PATH = r"你的曲谱文件夹路径"
```

运行：

```bash
python main.py
```

## 输出

- 重命名后的图片文件（格式：`调号-曲名.jpg`）
- `识别结果.csv` - 识别记录