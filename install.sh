#!/bin/bash

echo "Создание виртуального окружения..."
python3 -m venv venv

echo "Активация виртуального окружения и установка зависимостей..."
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt

echo "=========================================================="
echo "Установка завершена! Для запуска используйте команду:"
echo "./venv/bin/python client.py"