@echo off
setlocal
REM Build the CUDA variant.  Uses .venv-gpu so it stays isolated from the CPU env.
REM First run will create the venv and install dependencies (large download).
REM Default targets cu121; change CUDA_INDEX below if you need a different toolkit.

set CUDA_INDEX=https://download.pytorch.org/whl/cu121

cd /d "%~dp0"

if not exist .venv-gpu (
    echo [build_gpu] Creating GPU virtualenv...
    python -m venv .venv-gpu || goto :err
    call .venv-gpu\Scripts\activate.bat
    echo [build_gpu] Installing CUDA PyTorch + deps...
    python -m pip install --upgrade pip || goto :err
    python -m pip install torch --index-url %CUDA_INDEX% || goto :err
    python -m pip install torch_geometric numpy PySide6 PyInstaller || goto :err
) else (
    call .venv-gpu\Scripts\activate.bat
)

set BUILD_VARIANT=gpu
echo [build_gpu] Running PyInstaller...
pyinstaller --noconfirm app.spec || goto :err

echo.
echo [build_gpu] Done. Output: dist\SCCargoOptimizer-gpu\SCCargoOptimizer.exe
goto :eof

:err
echo [build_gpu] FAILED.
exit /b 1
