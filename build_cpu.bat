@echo off
setlocal
REM Build the CPU-only variant.  Uses .venv-cpu so it doesn't fight the GPU env.
REM First run will create the venv and install dependencies (a few minutes).

cd /d "%~dp0"

if not exist .venv-cpu (
    echo [build_cpu] Creating CPU virtualenv...
    python -m venv .venv-cpu || goto :err
    call .venv-cpu\Scripts\activate.bat
    echo [build_cpu] Installing CPU PyTorch + deps...
    python -m pip install --upgrade pip || goto :err
    python -m pip install torch --index-url https://download.pytorch.org/whl/cpu || goto :err
    python -m pip install torch_geometric numpy PySide6 PyInstaller || goto :err
) else (
    call .venv-cpu\Scripts\activate.bat
)

set "BUILD_VARIANT=cpu"
echo [build_cpu] Running PyInstaller...
pyinstaller --noconfirm app.spec || goto :err

echo.
echo [build_cpu] Done. Output: dist\SCCargoOptimizer-cpu\SCCargoOptimizer.exe
goto :eof

:err
echo [build_cpu] FAILED.
exit /b 1
