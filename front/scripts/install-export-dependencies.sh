#!/bin/bash

# 安装图表导出所需的依赖包
echo "正在安装图表导出依赖包..."

# 安装 html2canvas 用于将DOM元素转换为图片
npm install html2canvas

# 安装 jspdf 用于生成PDF文件
npm install jspdf

echo "依赖包安装完成！"
echo ""
echo "已安装的包："
echo "- html2canvas: 用于将图表转换为图片"
echo "- jspdf: 用于生成PDF报告"
echo ""
echo "现在可以使用以下导出功能："
echo "1. 导出单个图表为PNG图片"
echo "2. 导出完整数据分析报告为PDF"
echo "3. 导出原始数据为CSV格式"
