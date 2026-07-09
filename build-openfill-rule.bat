@echo off
setlocal
cd /d "%~dp0.."
python "openfill-rule\build-openfill-rule.py" %*
