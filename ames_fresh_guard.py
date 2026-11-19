import xml.etree.ElementTree as ET
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
import hashlib
import json

NETWORK_CONTRACT = {
    "network_name": "РЦ X5 (Воронеж / Москва)",
    "min_osg_percent": Decimal("75.0"),
    "max_weight_diff_kg": Decimal("0.050"),
    "price_tolerance": Decimal("0.00"),
    "allowed_vat_rates": {"10%", "20%", "22%", "5%", "7%"}
}

def parse_orders_xml(orders_path: str) -> dict:
    tree = ET.parse(orders_path)
    root = tree.getroot()
    items = {}
    for line in root.findall(".//LineItem"):
        gtin = line.findtext("GTIN", "").strip()
        items[gtin] = {
            "name": line.findtext("Description", "Без названия"),
            "price": Decimal(line.findtext("Price", "0")),
            "qty": Decimal(line.findtext("Quantity", "0")),
            "weight": Decimal(line.findtext("NetWeight", "0")),
            "shelf_life_days": int(line.findtext("TotalShelfLife", "14"))
        }
    return items

def parse_upd_503_xml(upd_path: str) -> list:
    tree = ET.parse(upd_path)
    root = tree.getroot()
    upd_lines = []
    for idx, item in enumerate(root.findall(".//СведТов"), start=1):
        gtin = item.attrib.get("КодТов", "")
        dop = item.find("ДопСведТов")
        if dop is not None and "КодТов" in dop.attrib:
            gtin = dop.attrib["КодТов"]
        upd_lines.append({
            "line_num": idx,
            "gtin": gtin,
            "name": item.attrib.get("НаимТов", ""),
            "qty": Decimal(item.attrib.get("КолТов", "0")),
            "price": Decimal(item.attrib.get("ЦенаТов", "0")),
            "vat_rate": item.attrib.get("НалСт", ""),
            "weight": Decimal(item.attrib.get("МассаНетто", item.attrib.get("КолТов", "0"))),
            "rem_days": int(item.attrib.get("ОстСрокГодн", "12")),
            "chz_codes_count": len(item.findall(".//КИЗ")) + len(item.findall(".//КИТУ"))
        })
    return upd_lines

def run_ames_audit(orders_path: str, upd_path: str) -> dict:
    expected = parse_orders_xml(orders_path)
    actual = parse_upd_503_xml(upd_path)
    errors = []

    for row in actual:
        gtin = row["gtin"]
        if gtin not in expected:
            errors.append({
                "line": row["line_num"],
                "item": row["name"],
                "type": "ПЕРЕСОРТ / НЕТ В ЗАКАЗЕ",
                "detail": f"Код {gtin} отсутствует в заказе ORDERS сети.",
                "risk": "Разворот всей паллеты на РЦ"
            })
            continue

        exp = expected[gtin]

        if abs(row["price"] - exp["price"]) > NETWORK_CONTRACT["price_tolerance"]:
            errors.append({
                "line": row["line_num"],
                "item": row["name"],
                "type": "РАСХОЖДЕНИЕ ЦЕНЫ",
                "detail": f"В УПД: {row['price']} ₽ | В заказе сети: {exp['price']} ₽",
                "risk": "Холд оплаты на 14 дней + штраф за УКД"
            })

        if abs(row["weight"] - exp["weight"]) > NETWORK_CONTRACT["max_weight_diff_kg"]:
            errors.append({
                "line": row["line_num"],
                "item": row["name"],
                "type": "ОШИБКА ВЕСА (РИСК ВСД)",
                "detail": f"В УПД: {row['weight']} кг | Ожидалось: {exp['weight']} кг",
                "risk": "Расхождение с Меркурием -> отказ в приёмке"
            })

        osg_pct = (Decimal(row["rem_days"]) / Decimal(exp["shelf_life_days"]) * Decimal("100")).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        if osg_pct < NETWORK_CONTRACT["min_osg_percent"]:
            errors.append({
                "line": row["line_num"],
                "item": row["name"],
                "type": "НАРУШЕНИЕ ОСГ (СРОК ГОДНОСТИ)",
                "detail": f"ОСГ = {osg_pct}% (минимум по договору: {NETWORK_CONTRACT['min_osg_percent']}%)",
                "risk": "100% возврат и списание скоропорта"
            })

        if row["vat_rate"] not in NETWORK_CONTRACT["allowed_vat_rates"]:
            errors.append({
                "line": row["line_num"],
                "item": row["name"],
                "type": "НЕКОРРЕКТНАЯ СТАВКА НДС",
                "detail": f"Указана ставка: {row['vat_rate']}",
                "risk": "Отказ в приёме документа по ЭДО"
            })

    status = "PASS" if len(errors) == 0 else "FAIL"
    audit_payload = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "engine": "АМЕС 2.0 (Детерминированное ядро без float)",
        "network": NETWORK_CONTRACT["network_name"],
        "status": status,
        "checked_lines": len(actual),
        "errors_count": len(errors),
        "errors": errors
    }

    raw_bytes = json.dumps(audit_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    audit_payload["integrity_sha256"] = hashlib.sha256(raw_bytes).hexdigest()
    return audit_payload
