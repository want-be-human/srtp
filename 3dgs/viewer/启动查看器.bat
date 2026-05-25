@echo off
cd /d D:\3DGS1\srtp-main\3dgs\viewer
start http://localhost:8080
python -m http.server 8080
pause
