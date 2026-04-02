# 曲谱图片批量重命名工具

使用 EasyOCR 识别曲谱图片中的曲名，Tesseract 识别调号，批量重命名文件。

## 项目结构

```
music-score-renamer/
├── utils.py                 # 公共方法模块
├── recognizer.py            # 仅识别（输出CSV，不重命名）
├── renamer.py               # 读取CSV重命名文件
├── recognize_and_rename.py  # 识别+重命名（原有功能）
└── README.md
```

## 文件夹配置

**父文件夹路径**：在脚本开头配置 BASE_PATH 变量

**运行命令**：

```bash
python <脚本名> <子文件夹名称>
```

例如：父文件夹是 `D:\谱子\共享曲谱`，包含子文件夹 `0`、`1`、`2`

- `python recognizer.py 0` 处理 `D:\谱子\共享曲谱\0` 目录（识别）
- `python recognize_and_rename.py 1` 处理 `D:\谱子\共享曲谱\1` 目录（识别+重命名）

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

下载并安装 [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)，然后在脚本开头配置路径：

```python
pytesseract.pytesseract.tesseract_cmd = r'你的Tesseract路径\tesseract.exe'
```
## 使用方法

### 方式一：分步处理（推荐）

1. **识别**：生成 CSV 文件（不重命名）
```bash
python recognizer.py <文件夹编号>
```
例如：`python recognizer.py 0`

2. **校对**：手动编辑 CSV 文件，修正调号和曲名

3. **重命名**：根据 CSV 重命名文件
```bash
python renamer.py <文件夹编号>
```
例如：`python renamer.py 0`

也支持完整路径：
```bash
python renamer.py test3/识别结果.csv
```

### 方式二：一步完成

```bash
python recognize_and_rename.py <文件夹编号>
```

## 输出

- 重命名后的图片文件（格式：`调号-曲名.jpg`）
- `识别结果.csv` - 识别记录