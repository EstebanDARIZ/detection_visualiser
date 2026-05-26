@echo off
echo ================================================
echo   Installation de l'environnement Python
echo ================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python non trouve.
    echo Installez Python 3.8 ou plus depuis https://python.org
    echo Cochez "Add Python to PATH" lors de l'installation.
    pause
    exit /b 1
)

echo [1/3] Creation de l'environnement virtuel...
python -m venv venv
if errorlevel 1 (
    echo [ERREUR] Impossible de creer l'environnement virtuel.
    pause
    exit /b 1
)

echo [2/3] Activation de l'environnement...
call venv\Scripts\activate.bat

echo [3/3] Installation des dependances...
pip install --upgrade pip --quiet
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERREUR] L'installation a echoue.
    pause
    exit /b 1
)

echo.
echo ================================================
echo   Installation terminee avec succes !
echo ================================================
echo.
pause
