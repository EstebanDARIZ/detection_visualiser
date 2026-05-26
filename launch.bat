@echo off
setlocal

set "SCRIPT_DIR=%~dp0"

if "%~1"=="" (
    echo.
    echo  Utilisation :
    echo    Glissez-deposez un fichier CSV sur ce .bat
    echo    Ou en ligne de commande :
    echo      launch.bat "detections.csv"
    echo      launch.bat "detections.csv" --classes 3
    echo      launch.bat "detections.csv" --classes 1 3 5
    echo.
    pause
    exit /b 0
)

call "%SCRIPT_DIR%venv\Scripts\activate.bat" 2>nul
if errorlevel 1 (
    echo.
    echo [ERREUR] Environnement virtuel introuvable.
    echo Lancez d'abord setup.bat pour installer les dependances.
    echo.
    pause
    exit /b 1
)

python "%SCRIPT_DIR%view_detections.py" %*
if errorlevel 1 (
    echo.
    echo [ERREUR] Le script s'est termine avec une erreur.
    pause
)

endlocal
