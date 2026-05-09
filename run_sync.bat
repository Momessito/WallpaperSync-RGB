@echo off
echo Matando processos antigos...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :16040 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
echo.
echo Instalando dependencias...
pip install mss numpy pillow pyaudiowpatch
echo.
echo ================================================
echo   Wallpaper Engine -^> SignalRGB Color Sync
echo ================================================
echo.
echo Copiando efeito para pasta do SignalRGB...
copy /Y "%~dp0WallpaperSync.html" "%userprofile%\OneDrive\Documents\WhirlwindFX\Effects\WallpaperSync.html" >nul 2>&1
echo Efeito copiado!
echo.
echo NAO FECHE ESTA JANELA
echo.
python "%~dp0wallpaper_to_signalrgb.py"
pause
