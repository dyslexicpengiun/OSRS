@echo off
REM OSRS Automation Suite - Windows Setup
REM Run this once to install all dependencies.

echo ===================================================
echo  OSRS Automation Suite - Setup
echo ===================================================
echo.

REM Check Python
python --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo ERROR: Python not found. Install Python 3.9+ from https://python.org
    pause
    exit /b 1
)

FOR /F "tokens=2" %%i IN ('python --version') DO SET PYVER=%%i
echo Python found: %PYVER%

REM Create virtual environment
IF NOT EXIST .venv (
    echo Creating virtual environment...
    python -m venv .venv
) ELSE (
    echo Virtual environment already exists.
)

REM Activate venv
call .venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip --quiet

REM Install core requirements
echo Installing core requirements...
pip install -r requirements.txt

echo.
echo ===================================================
echo  Attempting interception-python install...
echo  (Requires the Interception kernel driver to be
echo   pre-installed. See setup_interception.py for help)
echo ===================================================

pip install interception-python >nul 2>&1
IF ERRORLEVEL 1 (
    echo [WARN] interception-python could not be installed.
    echo        Hardware-level input will NOT be available.
    echo        The suite will fall back to SendInput.
    echo.
    echo        To enable hardware-level input later:
    echo          1. Install the Interception driver (see setup_interception.py)
    echo          2. Restart your PC
    echo          3. Run: .venv\Scripts\activate.bat
    echo          4. Run: pip install interception-python
    echo          5. Re-run this setup or just launch main.py
) ELSE (
    REM Verify it actually imports - driver must be present for this to work
    python -c "import interception; interception.auto_capture_devices()" >nul 2>&1
    IF ERRORLEVEL 1 (
        echo [WARN] interception-python installed but driver not detected.
        echo        Package is present - install the kernel driver, restart
        echo        your PC, and hardware-level input will activate automatically.
    ) ELSE (
        echo [OK] interception-python installed and driver verified.
        echo      Hardware-level input is ACTIVE.
    )
)

echo.
echo ===================================================
echo  Running diagnostics...
echo ===================================================
python diagnose.py --fast

echo.
echo ===================================================
echo  Setup complete.
echo  To run: .venv\Scripts\activate.bat ^& python main.py
echo ===================================================
pause
