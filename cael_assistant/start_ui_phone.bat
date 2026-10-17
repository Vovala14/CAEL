@echo off
cd /d %~dp0..
set /p TOK=<cael_assistant\ui_token.txt
echo Phone (same WiFi): http://192.168.1.229:8765/?k=%TOK%
..\.venv-rocm\Scripts\python.exe cael_assistant\web_ui.py --host 0.0.0.0 --port 8765 --token %TOK%
