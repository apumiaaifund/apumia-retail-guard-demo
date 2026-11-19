#!/usr/bin/env bash
set -e
echo "=== [AMES v2.0] Запуск верификации АПУМИА: Контроль Отгрузок ==="
python3 prove.py
python3 run_demo.py
echo "=== [PASS] Все проверки пройдены успешно ==="
