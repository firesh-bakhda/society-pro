#!/usr/bin/env bash
set -euo pipefail

# One-click Nuitka build script for SocietyPro
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pushd "$PROJECT_DIR" >/dev/null

PYTHON_EXE="$PROJECT_DIR/.venv/bin/python"

echo "[1/4] Validating project Python environment..."
if [[ ! -f "$PYTHON_EXE" ]]; then
    echo "ERROR: Project virtual environment not found at:"
    echo "       $PYTHON_EXE"
    echo "Create it first, then install dependencies."
    popd >/dev/null
    exit 1
fi

echo "[2/4] Installing/refreshing build tooling with uv..."
if ! uv pip install --python "$PYTHON_EXE" nuitka ordered-set zstandard; then
    echo "ERROR: Failed to install Nuitka build dependencies."
    popd >/dev/null
    exit 1
fi

if [[ -n "${NUITKA_JOBS:-}" ]]; then
    BUILD_JOBS="$NUITKA_JOBS"
elif command -v nproc >/dev/null 2>&1; then
    BUILD_JOBS="$(nproc)"
elif command -v getconf >/dev/null 2>&1; then
    BUILD_JOBS="$(getconf _NPROCESSORS_ONLN)"
elif [[ -n "${NUMBER_OF_PROCESSORS:-}" ]]; then
    BUILD_JOBS="$NUMBER_OF_PROCESSORS"
else
    BUILD_JOBS=8
fi

echo "[3/4] Building standalone executable with Nuitka..."
echo "      Using ${BUILD_JOBS} parallel compile jobs."
if ! "$PYTHON_EXE" -m nuitka \
    --jobs="$BUILD_JOBS" \
    --standalone \
    --windows-console-mode=disable \
    --enable-plugin=tk-inter \
    --include-package=customtkinter \
    --include-package=tkcalendar \
    --include-package=fpdf \
    --include-package=openpyxl \
    --include-data-files=*.jpeg=./ \
    --output-dir=build \
    --output-filename=SocietyPro.exe \
    society-membership.py; then
    echo "ERROR: Nuitka build failed."
    popd >/dev/null
    exit 1
fi

echo "[4/4] Build complete."
echo "Output folder: $PROJECT_DIR/build/society-membership.dist"
echo "Executable   : $PROJECT_DIR/build/society-membership.dist/SocietyPro.exe"

popd >/dev/null
exit 0
