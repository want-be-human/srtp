# 独立PDF教案生成器

一个完全独立的Python程序，用于生成精美的焊接教学教案PDF报告。

## ✨ 功能特点

- 🎯 **完全独立运行** - 不依赖前端，直接生成PDF
- 📊 **模拟数据生成** - 自动生成真实的教学数据
- 🎨 **多种精美模板** - 专业蓝色、绿色环保、橙色活力三种主题
- 📈 **图表支持** - 自动生成技能分析图表
- 🔤 **中文完美支持** - 解决中文显示问题
- 📋 **专业排版** - 表格、列表、分页等专业布局

## 🚀 快速开始

### 1. 安装依赖
```bash
# 方法1: 使用批处理文件
install.bat

# 方法2: 手动安装
pip install -r requirements.txt
```

### 2. 运行程序
```bash
# 方法1: 使用批处理文件
run.bat

# 方法2: 直接运行
python standalone_pdf_generator.py
```

### 3. 查看结果
程序会在当前目录生成3个不同主题的PDF文件：
- `焊接教案报告_专业蓝色_YYYYMMDD_HHMMSS.pdf`
- `焊接教案报告_绿色环保_YYYYMMDD_HHMMSS.pdf`
- `焊接教案报告_橙色活力_YYYYMMDD_HHMMSS.pdf`

## 📝 PDF内容结构

生成的PDF包含以下章节：
1. **教学概况** - 学生数量、检测次数、平均分数等统计
2. **技能分析** - 各项技能得分和可视化图表
3. **缺陷分析** - 常见缺陷类型、频率和改进情况
4. **学习进度** - 学生表现分级和进步统计
5. **教学建议** - AI智能生成的教学改进建议
6. **下节课计划** - 基于数据分析的课程安排
7. **重点关注领域** - 需要特别关注的技能领域

## 🎨 自定义模板

### 修改主题颜色
编辑 `standalone_pdf_generator.py` 中的 `PDFTemplate` 类：

```python
"custom": {
    "primary_color": colors.HexColor("#your_color"),    # 主色调
    "secondary_color": colors.HexColor("#your_color"),  # 次要色
    "accent_color": colors.HexColor("#your_color"),     # 强调色
    "background_color": colors.HexColor("#your_color"), # 背景色
    # ... 其他配置
}
```

### 修改数据内容
编辑 `MockDataGenerator` 类中的方法：
- `generate_skill_analysis()` - 修改技能项目
- `generate_common_defects()` - 修改缺陷类型
- `generate_teaching_recommendations()` - 修改教学建议

## 🔧 技术实现

- **PDF生成**: ReportLab库 - 专业PDF生成
- **图表绘制**: Matplotlib - 数据可视化
- **中文支持**: TTFont字体注册
- **数据模拟**: 随机数据生成，模拟真实教学场景

## 📊 生成的数据示例

```
学生总数: 45人
检测次数: 238次
平均分数: 87.5分
技能分析:
  - 光滑度控制: 89.2分
  - 焊缝间距: 85.7分
  - 缺陷识别: 91.3分
常见缺陷:
  - 气孔缺陷: 25次 (中等) 改进率+8%
  - 夹渣问题: 18次 (轻微) 改进率+12%
```

## 💡 使用建议

1. **首次运行**: 先运行 `install.bat` 安装依赖
2. **批量生成**: 修改 `main()` 函数可批量生成多个PDF
3. **自定义数据**: 可以修改 `MockDataGenerator` 使用真实数据
4. **字体问题**: 如果中文显示异常，请检查系统中文字体

## 📄 输出示例

每个PDF文件约8-10页，包含：
- 专业的封面设计
- 数据统计表格
- 技能分析图表
- 详细的教学建议
- 完整的课程规划

完全可以直接用于实际教学场景！