@echo off
rem Starts the banner and research-page editor and opens it in your browser.
rem Needs Python 3 (for example from Miniconda or python.org). Close this window to stop the editor.
cd /d "%~dp0\.."
python tools\banner_editor.py
pause
