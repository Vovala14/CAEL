@echo off
cd /d %~dp0..
set /p TOK=<cael_assistant\ui_token.txt
start "CAEL UI" ..\.venv-rocm\Scripts\python.exe cael_assistant\web_ui.py --host 127.0.0.1 --port 8765 --token %TOK%
echo Token: %TOK%  - open the https://....trycloudflare.com URL below with /?k=%TOK%
tools\cloudflared.exe tunnel --no-autoupdate --url http://127.0.0.1:8765
