@echo off
echo 安装PDF生成器依赖...
echo.

pip install -r requirements.txt

echo.
echo 依赖安装完成！
echo 现在可以运行: python standalone_pdf_generator.py
pause