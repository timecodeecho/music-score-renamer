# 曲谱图片批量重命名工具 - 设计文档

## 系统架构

```
输入图片 → EasyOCR区域识别 → 曲名提取 + 调号识别 → CSV报告
                    ↓                    ↓
              文字块位置信息      多种调号识别方案

分步处理模式:
  1. recognizer.py → 输出 CSV（不重命名）
  2. renamer.py → 读取 CSV 重命名文件
```

## 文件结构

```
music-score-renamer/
├── utils.py                   # 公共方法模块
│   ├── KEY_PATTERNS           # 调号正则匹配模式
│   ├── KEY_LETTERS            # 调号字母列表
│   ├── TESSERACT_CONFIG       # Tesseract 配置
│   ├── init_easyocr()         # 初始化 EasyOCR
│   ├── read_upper_region()    # EasyOCR 识别图片上部
│   ├── extract_key_multi_method()  # 多种方法提取调号
│   ├── filter_title()         # 过滤曲名（去空格等）
│   ├── is_renamed_file()      # 检查文件是否已重命名
│   └── remove_spaces()        # 移除字符串空格
├── recognizer.py              # 仅识别，输出 CSV
├── renamer.py                 # 读取 CSV 重命名文件
├── recognize_and_rename.py     # 识别+重命名（一步完成）
└── README.md
```

## 当前架构问题

### 已识别的问题

1. **重复打开图片** - 当前多个函数各自独立打开图片
   - 已在 `extract_key_multi_method()` 中优化，使用路径字符串而非 Image 对象

2. **字符串常量重复** - `config='--psm 6'` 在多处重复
   - **已优化**：提取为 `TESSERACT_CONFIG` 常量

3. **调号识别方法字符串** - 散落在代码中的方法名称
   - **已优化**：记录到 CSV 新增列中便于调试

## 核心流程

### 方式一：分步处理（推荐）

```
1. recognizer.py
   获取文件夹图片列表 → EasyOCR 识别 → 调号提取 → 输出 CSV

2. renamer.py
   读取 CSV → 根据调号和曲名重命名文件 → 汇总报告
```

### 方式二：一步完成

```
recognize_and_rename.py
获取文件夹图片列表 → EasyOCR 识别 → 调号提取 → 重命名文件 → 输出 CSV
```

### 1. 文件过滤
```
获取文件夹所有文件 → 过滤图片格式 → 排除已重命名文件(C-*) → 待处理列表
```

### 2. 曲名识别流程
```
裁剪图片上部40% → EasyOCR识别 → 获取文字块及位置
→ 按y坐标排序 → 过滤调号信息(排除"调"/数字/制谱编曲等)
→ 取第一个文字块 → 曲名
```

### 3. 调号识别流程（4种方案依次尝试）

```
方案1: EasyOCR文本匹配
  ├─ 输入: EasyOCR识别结果(all_text)
  ├─ 正则: key_patterns (1=C, 1=#C, C调, #C调, ♯C调, ♭C调等)
  └─ 输出: 调号字母

方案2: Tesseract左上角
  ├─ 输入: 图片左上角30%区域
  ├─ 识别: 调号字母(C/D/E/F/G/A/B)
  └─ 输出: 调号字母

方案2.5: Tesseract升降号检测
  ├─ 输入: 调号字母位置(bbox)
  ├─ 区域: 调号前方(同宽, 2倍高)
  ├─ 识别: #, ♯, b, B, 6, 0, ♭, ь
  └─ 输出: 升降号前缀

方案3: Tesseract曲名下方
  ├─ 输入: 曲名位置下方区域
  ├─ 识别: C调, D调格式
  └─ 输出: 调号字母

方案4: Tesseract上部全区域(备选)
  ├─ 输入: 图片上部40%
  └─ 输出: 调号字母
```

### 4. 文件重命名逻辑
```
有调号+有曲名 → "调号-曲名.ext"
有曲名+无调号 → "曲名.ext"
无曲名 → 不重命名
原文件名相同 → 跳过(避免覆盖)
重名处理 → 添加原文件名后缀
```

## 数据结构

### 文字块信息
```python
{
    'text': str,        # 识别文字
    'prob': float,      # 置信度
    'area': int,        # 面积
    'y_center': float,  # Y中心坐标
    'x_center': float,  # X中心坐标
    'y_top': float,     # Y上边界
    'y_bottom': float,  # Y下边界
    'x_left': float,    # X左边界
    'x_right': float    # X右边界
}
```

### CSV输出字段

| 字段 | 说明 |
|------|------|
| 原文件名 | 原始图片文件名 |
| 调号 | 识别的调号(如C, #C, bA) |
| 调号识别方法 | 使用的识别方案 |
| 升降号检测文本 | Tesseract前方区域识别内容 |
| 曲名 | 识别的曲名（已去除空格） |
| 新文件名 | 重命名后的文件名（recognizer.py 无此列） |
| 状态 | 成功/失败/错误等 |

## 配置常量

```python
KEY_LETTERS = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
TESSERACT_CONFIG = '--psm 6'
KEY_PATTERNS = [...]  # 调号正则匹配模式
TITLE_EXCLUDE_KEYWORDS = ['制谱', '编曲', '作曲', '记谱', '演奏']
```

## 关键函数 (utils.py)

| 函数 | 功能 |
|------|------|
| init_easyocr() | 初始化 EasyOCR Reader |
| read_upper_region() | EasyOCR 识别图片上部区域 |
| extract_key_multi_method() | 多种方法提取调号 |
| extract_key_from_ocr_text() | 从 OCR 文本提取调号 |
| extract_key_with_tesseract() | Tesseract 多区域调号识别 |
| check_key_prefix_by_tesseract() | 检测调号前方升降号 |
| extract_key_from_title_region() | 曲名下方区域调号识别 |
| is_key_info() | 判断是否是调号信息 |
| filter_title() | 过滤曲名（去空格、过滤调号） |
| is_renamed_file() | 检查文件是否已重命名 |
| remove_spaces() | 移除字符串空格 |
| build_new_filename() | 构建新文件名 |

## 处理顺序图

```
开始
  │
  ▼
读取文件夹图片列表
  │
  ▼
遍历每张图片 ─────────────────────┐
  │                                 │
  ▼                                 │
EasyOCR识别(上部40%)               │
  │                                 │
  ├─ 提取曲名                      │
  │                                 │
  ▼                                 │
调号识别(4种方案依次尝试)           │
  │                                 │
  ├─ 方案1: EasyOCR正则匹配         │
  ├─ 方案2: Tesseract左上角         │
  ├─ 方案2.5: Tesseract升降号检测   │
  ├─ 方案3: Tesseract曲名下方       │
  └─ 方案4: Tesseract上部全区域     │
  │                                 │
  ▼                                 │
文件重命名（可选）                  │
  │                                 │
  ├─ 有调号+曲名 → 调号-曲名.ext   │
  ├─ 有曲名无调号 → 曲名.ext       │
  └─ 无曲名 → 不重命名             │
  │                                 │
  ▼                                 │
记录到results列表 ──────────────────┘
  │
  ▼
写入CSV报告
  │
  ▼
结束
```