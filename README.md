# 曲谱图片批量重命名工具

使用 EasyOCR 识别曲谱图片中的曲名，Tesseract 识别调号，批量重命名文件。

## 文件夹配置

当前配置的处理文件夹：`D:\谱子\共享曲谱`

在 `main.py` 中修改：

```python
BASE_PATH = r"你的曲谱文件夹路径"
```

文件夹结构：
```
共享曲谱/
├── 0/          # 子文件夹，通过 python main.py 0 访问
├── 1/          # 通过 python main.py 1 访问
└── 2/          # 通过 python main.py 2 访问
```

## 功能特点

- **智能区域识别**：只识别图片上部 40% 区域（曲名和调号通常在此区域）
- **最大文字块识别**：自动识别面积最大的文字块作为曲名（通常曲名字号最大）
- **调号识别（Tesseract）**：
  - 左上角区域识别（30% x 30%）：匹配 `1=C`、`1=G`、`#C`、`bD` 等格式
  - 曲名下方区域识别：匹配 `C调`、`D调`、`bB调` 等格式
  - 整个上部区域识别（备选）

## 环境要求

- Python 3.8+
- easyocr
- pytesseract
- opencv-python
- pillow
- tqdm
- Tesseract OCR（需安装并配置路径）

## 安装依赖

```bash
pip install easyocr pytesseract opencv-python pillow tqdm
```

## Tesseract 配置

下载并安装 [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)，然后在 `main.py` 中配置路径：

```python
pytesseract.pytesseract.tesseract_cmd = r'你的Tesseract路径\tesseract.exe'
```

## 使用方法

运行：

```bash
python main.py <文件夹编号>
```

例如：`python main.py 0` 处理共享曲谱文件夹中的第 0 个子文件夹。

## 输出

- 重命名后的图片文件（格式：`调号-曲名.jpg`）
- `识别结果.csv` - 识别记录