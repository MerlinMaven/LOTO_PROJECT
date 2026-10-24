@echo off
cd /d "%~dp0.."
echo ===================================================
echo   SmartLOTO - Demarrage des Services Backend Unity
echo ===================================================
echo [1/2] Lancement de field-service sur port 8000...
start /B "Field-Service" cmd /c "cd apps\field-service && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
echo [2/2] Lancement de authoring-service sur port 8001...
start /B "Authoring-Service" cmd /c "cd apps\authoring-service && python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload"
echo.
echo Les services tournent en arriere-plan :
echo   - Field Service (Unity AR)   : http://127.0.0.1:8000
echo   - Authoring Service (Export) : http://127.0.0.1:8001
echo ===================================================
