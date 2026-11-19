import xml.etree.ElementTree as ET
import hashlib
import sys
import os

def mask_value(val: str, prefix: str = "MASK") -> str:
    if not val:
        return val
    h = hashlib.sha256(val.encode('utf-8')).hexdigest()[:8].upper()
    return f"{prefix}_{h}"

def anonymize_upd_xml(input_path: str, output_path: str):
    tree = ET.parse(input_path)
    root = tree.getroot()
    sensitive_attrs = {'ИННЮЛ', 'ИННФЛ', 'КПП', 'НаимОрг', 'Фамилия', 'Имя', 'Отчество', 'АдрТекст'}
    for elem in root.iter():
        for attr in list(elem.attrib.keys()):
            if attr in sensitive_attrs:
                elem.attrib[attr] = mask_value(elem.attrib[attr], attr[:4].upper())
        if elem.tag in sensitive_attrs and elem.text:
            elem.text = mask_value(elem.text, elem.tag[:4].upper())
    tree.write(output_path, encoding='windows-1251', xml_declaration=True)
    print(f"[OK] Обезличенный файл сохранён: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python3 anonymizer.py <путь_к_УПД.xml>")
        sys.exit(1)
    inp = sys.argv[1]
    out = os.path.join("outbox_upd", "ANON_" + os.path.basename(inp))
    anonymize_upd_xml(inp, out)
