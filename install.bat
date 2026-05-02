@echo off
chcp 65001 >nul

echo Создание виртуального окружения...
python -m venv venv

echo Активация виртуального окружения и установка зависимостей...
call venv\Scripts\activate.bat
python -m pip install -U pip
pip install -r requirements.txt

echo ==========================================================
echo Установка завершена! Для запуска используйте команду:
echo venv\Scripts\python.exe client.py
pause