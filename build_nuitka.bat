@echo off
setlocal EnableExtensions

REM One-click Nuitka build script for SocietyPro
set "PROJECT_DIR=%~dp0"
pushd "%PROJECT_DIR%" >nul

set "PYTHON_EXE=%PROJECT_DIR%.venv\Scripts\python.exe"

echo [1/4] Validating project Python environment...
if not exist "%PYTHON_EXE%" (
    echo ERROR: Project virtual environment not found at:
    echo        "%PYTHON_EXE%"
    echo Create it first, then install dependencies.
    popd >nul
    exit /b 1
)

echo [2/4] Installing/refreshing build tooling with uv...
uv pip install --python "%PYTHON_EXE%" nuitka ordered-set zstandard
if errorlevel 1 (
    echo ERROR: Failed to install Nuitka build dependencies.
    popd >nul
    exit /b 1
)

set "BUILD_JOBS=%NUITKA_JOBS%"
if not defined BUILD_JOBS set "BUILD_JOBS=%NUMBER_OF_PROCESSORS%"
if not defined BUILD_JOBS set "BUILD_JOBS=8"

echo [3/4] Building standalone executable with Nuitka...
echo       Using %BUILD_JOBS% parallel compile jobs.
"%PYTHON_EXE%" -m nuitka ^
    --jobs=%BUILD_JOBS% ^
    --standalone ^
    --windows-console-mode=disable ^
    --enable-plugin=tk-inter ^
    --include-package=customtkinter ^
    --include-package=tkcalendar ^
    --include-package=fpdf ^
    --include-package=openpyxl ^
    --include-data-files=*.jpeg=.\ ^
    --output-dir=build ^
    --output-filename=SocietyPro.exe ^
    society-membership.py
if errorlevel 1 (
    echo ERROR: Nuitka build failed.
    popd >nul
    exit /b 1
)

echo [4/4] Build complete.
echo Output folder: "%PROJECT_DIR%build\society-membership.dist"
echo Executable   : "%PROJECT_DIR%build\society-membership.dist\SocietyPro.exe"

popd >nul
exit /b 0
