@echo off
call C:\Users\arkoh\miniconda3\Scripts\activate.bat memos
:loop
python -m screen_recorder.record --once
timeout /t 5 /nobreak >nul
goto loop