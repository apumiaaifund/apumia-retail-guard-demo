import os
import json
from ames_fresh_guard import run_ames_audit

orders_sample = """<?xml version="1.0" encoding="utf-8"?>
<Order>
    <LineItem>
        <GTIN>4607001234561</GTIN>
        <Description>Молоко пастеризованное 3.2% 1л (ПЭТ)</Description>
        <Price>61.20</Price>
        <Quantity>1200</Quantity>
        <NetWeight>1236.000</NetWeight>
        <TotalShelfLife>10</TotalShelfLife>
    </LineItem>
    <LineItem>
        <GTIN>4607001234578</GTIN>
        <Description>Сыр Российский 50% весовой (голова)</Description>
        <Price>540.00</Price>
        <Quantity>100</Quantity>
        <NetWeight>850.000</NetWeight>
        <TotalShelfLife>60</TotalShelfLife>
    </LineItem>
</Order>"""

upd_sample = """<?xml version="1.0" encoding="utf-8"?>
<Файл ВерсФорм="5.03">
    <Документ>
        <ТаблСчФакт>
            <СведТов НомСтр="1" КодТов="4607001234561" НаимТов="Молоко пастеризованное 3.2% 1л (ПЭТ)" КолТов="1200" ЦенаТов="68.50" НалСт="10%" МассаНетто="1236.000" ОстСрокГодн="9" />
            <СведТов НомСтр="2" КодТов="4607001234578" НаимТов="Сыр Российский 50% весовой (голова)" КолТов="100" ЦенаТов="540.00" НалСт="10%" МассаНетто="847.200" ОстСрокГодн="40" />
        </ТаблСчФакт>
    </Документ>
</Файл>"""

os.makedirs("inbox_orders", exist_ok=True)
os.makedirs("outbox_upd", exist_ok=True)
os.makedirs("reports", exist_ok=True)

orders_file = "inbox_orders/ORDERS_X5_VORONEZH_001.xml"
upd_file = "outbox_upd/UPD_503_1C_OUT_001.xml"

with open(orders_file, "w", encoding="utf-8") as f:
    f.write(orders_sample)
with open(upd_file, "w", encoding="utf-8") as f:
    f.write(upd_sample)

result = run_ames_audit(orders_file, upd_file)

print("\n" + "="*65)
print(f" ПУЛЬТ ОПЕРАТОРА: АПУМИА: КОНТРОЛЬ ОТГРУЗОК (v1.0)")
print("="*65)
print(f" Статус проверки : [{'ЗЕЛЁНЫЙ - РАЗРЕШЕНО' if result['status']=='PASS' else 'КРАСНЫЙ - БЛОКИРОВКА ЭДО'}]")
print(f" Контрагент      : {result['network']}")
print(f" Проверено строк : {result['checked_lines']} | Найдено ошибок: {result['errors_count']}")
print(f" Контроль SHA256 : {result['integrity_sha256'][:24]}...")
print("-"*65)

for err in result["errors"]:
    print(f" [!] Строка {err['line']}: {err['item']}")
    print(f"     Тип ошибки : {err['type']}")
    print(f"     Детали     : {err['detail']}")
    print(f"     Последствия: {err['risk']}\n")

report_path = "reports/audit_result_001.json"
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f" Полный протокол сохранён в: {report_path}\n")
