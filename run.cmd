@echo off
rem Starts the widget with the project venv, without a console window.
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.pyw"
