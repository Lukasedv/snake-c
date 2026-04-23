@echo off
REM Build snake.exe using MSVC (Visual Studio Build Tools).
REM For MinGW / gcc users, just run `make` instead.

set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
for /f "usebackq tokens=*" %%i in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VSINSTALL=%%i"

if "%VSINSTALL%"=="" (
  echo Could not locate Visual Studio with MSVC tools.
  exit /b 1
)

call "%VSINSTALL%\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
cl /nologo /W3 /O2 /Fe:snake.exe src\main.c src\game.c src\render.c || exit /b 1
del /Q *.obj >nul 2>&1
echo.
echo Built snake.exe
