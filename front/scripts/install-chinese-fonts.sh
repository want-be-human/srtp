#!/bin/bash

# 安装中文字体支持的脚本
# 为jsPDF添加中文字体支持

echo "正在安装中文字体支持..."

# 安装html2canvas和canvas相关依赖（用于更好的中文渲染）
npm install html2canvas

# 如果需要服务端PDF生成，可以考虑安装puppeteer
# npm install puppeteer

echo "字体支持安装完成！"
echo "请确保在PDF生成前设置正确的字体。"