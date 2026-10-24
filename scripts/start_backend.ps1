Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  SmartLOTO - Démarrage des Services Backend Unity" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

Write-Host "[1/2] Lancement de field-service sur port 8000..." -ForegroundColor Yellow
Start-Process python -ArgumentList "-m uvicorn main:app --host 0.0.0.0 --port 8000 --reload" -WorkingDirectory "$PSScriptRoot\..\apps\field-service" -WindowStyle Hidden

Write-Host "[2/2] Lancement de authoring-service sur port 8001..." -ForegroundColor Yellow
Start-Process python -ArgumentList "-m uvicorn main:app --host 0.0.0.0 --port 8001 --reload" -WorkingDirectory "$PSScriptRoot\..\apps\authoring-service" -WindowStyle Hidden

Write-Host "`nLes services tournent en arrière-plan :" -ForegroundColor Green
Write-Host "  - Field Service (Unity AR)   : http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "  - Authoring Service (Export) : http://127.0.0.1:8001" -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Cyan
