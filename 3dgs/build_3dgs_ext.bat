@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
if errorlevel 1 exit /b 1
set CUDA_HOME=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4
set TORCH_CUDA_ARCH_LIST=8.9
set DISTUTILS_USE_SDK=1
cd /d D:\srtp-main\3dgs\gaussian-splatting
"D:\anaconda\envs\v8n-train\python.exe" -m pip install --no-build-isolation --no-deps -v submodules/diff-gaussian-rasterization 1>D:\srtp-main\3dgs\build_diff.log 2>&1
if errorlevel 1 exit /b 2
"D:\anaconda\envs\v8n-train\python.exe" -m pip install --no-build-isolation --no-deps -v submodules/simple-knn 1>D:\srtp-main\3dgs\build_knn.log 2>&1
if errorlevel 1 exit /b 3
echo BUILD_DONE
