@echo off
cd /d %~dp0..
start http://127.0.0.1:8765
..\.venv-rocm\Scripts\python.exe cael_assistant\web_ui.py
