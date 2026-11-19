import http.server
import socketserver
import json
import os
import time
import threading
import urllib.parse
from ames_fresh_guard import run_ames_audit

PORT = 8765
LATEST_REPORT = {}
ORDERS_FILE = "inbox_orders/ORDERS_X5_VORONEZH_001.xml"
UPD_FILE = "outbox_upd/UPD_503_1C_OUT_001.xml"

BAD_UPD_XML = """<?xml version="1.0" encoding="utf-8"?>
<Файл ВерсФорм="5.03">
    <Документ>
        <ТаблСчФакт>
            <СведТов НомСтр="1" КодТов="4607001234561" НаимТов="Молоко пастеризованное 3.2% 1л (ПЭТ)" КолТов="1200" ЦенаТов="68.50" НалСт="10%" МассаНетто="1236.000" ОстСрокГодн="9" />
            <СведТов НомСтр="2" КодТов="4607001234578" НаимТов="Сыр Российский 50% весовой (голова)" КолТов="100" ЦенаТов="540.00" НалСт="10%" МассаНетто="847.200" ОстСрокГодн="40" />
        </ТаблСчФакт>
    </Документ>
</Файл>"""

GOOD_UPD_XML = """<?xml version="1.0" encoding="utf-8"?>
<Файл ВерсФорм="5.03">
    <Документ>
        <ТаблСчФакт>
            <СведТов НомСтр="1" КодТов="4607001234561" НаимТов="Молоко пастеризованное 3.2% 1л (ПЭТ)" КолТов="1200" ЦенаТов="61.20" НалСт="10%" МассаНетто="1236.000" ОстСрокГодн="9" />
            <СведТов НомСтр="2" КодТов="4607001234578" НаимТов="Сыр Российский 50% весовой (голова)" КолТов="100" ЦенаТов="540.00" НалСт="10%" МассаНетто="850.000" ОстСрокГодн="50" />
        </ТаблСчФакт>
    </Документ>
</Файл>"""

def folder_watcher():
    global LATEST_REPORT
    last_mtime = 0
    while True:
        if os.path.exists(ORDERS_FILE) and os.path.exists(UPD_FILE):
            mtime = os.path.getmtime(UPD_FILE)
            if mtime != last_mtime:
                last_mtime = mtime
                try:
                    LATEST_REPORT = run_ames_audit(ORDERS_FILE, UPD_FILE)
                    with open("reports/latest_audit.json", "w", encoding="utf-8") as f:
                        json.dump(LATEST_REPORT, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    LATEST_REPORT = {"status": "FAIL", "network": "Ошибка парсинга XML", "checked_lines": 0, "errors_count": 1, "timestamp": "", "integrity_sha256": "-", "errors": [{"line": 0, "item": "Файл УПД", "type": "НЕКОРРЕКТНЫЙ ФОРМАТ", "detail": str(e), "risk": "Файл не читается"}]}
        time.sleep(0.5)

HTML_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>АПУМИА: Контроль Отгрузок — Пульт Оператора</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 24px; max-width: 1000px; margin: 0 auto; }
  .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 16px; margin-bottom: 20px; flex-wrap: wrap; gap: 12px; }
  .controls { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; align-items: center; }
  .btn { border: none; padding: 10px 16px; border-radius: 8px; font-weight: 600; font-size: 14px; cursor: pointer; transition: opacity 0.2s; }
  .btn:hover { opacity: 0.9; }
  .btn-red { background: #dc2626; color: white; }
  .btn-green { background: #059669; color: white; }
  .drop-zone { border: 2px dashed #475569; border-radius: 8px; padding: 10px 16px; font-size: 13px; color: #94a3b8; cursor: pointer; flex-grow: 1; text-align: center; }
  .drop-zone.dragover { border-color: #38bdf8; color: #38bdf8; background: #1e293b; }
  .status-box { padding: 24px; border-radius: 12px; margin-bottom: 24px; }
  .status-PASS { background: #064e3b; border: 2px solid #10b981; }
  .status-FAIL { background: #7f1d1d; border: 2px solid #ef4444; }
  .status-title { font-size: 26px; font-weight: 800; margin: 0 0 8px 0; }
  .meta { font-size: 13px; opacity: 0.9; font-family: monospace; }
  .err-card { background: #1e293b; border-left: 4px solid #ef4444; padding: 16px; border-radius: 8px; margin-bottom: 12px; }
  .err-type { color: #fca5a5; font-weight: 700; font-size: 13px; text-transform: uppercase; }
  .err-item { font-size: 18px; font-weight: 600; margin: 4px 0; }
  .err-detail { color: #cbd5e1; font-size: 15px; }
  .err-risk { color: #fbbf24; font-size: 13px; margin-top: 6px; font-weight: 500; }
</style>
</head>
<body>
  <div class="header">
    <div>
      <h1 style="margin:0; font-size:22px;">🛡 АПУМИА: Контроль Отгрузок (АМЕС 2.0)</h1>
      <div style="color:#94a3b8; font-size:13px; margin-top:4px;">Автономный детерминированный шлюз (Без 1С • Без Контура • No-Float)</div>
    </div>
    <div style="background:#1e293b; border:1px solid #475569; padding:6px 12px; border-radius:6px; font-size:12px; color:#94a3b8;">
      Контур: Локальный (Air-Gapped)
    </div>
  </div>

  <div class="controls">
    <button class="btn btn-red" onclick="simulate('bad')">🔴 Симулировать ошибку 1С</button>
    <button class="btn btn-green" onclick="simulate('good')">🟢 Исправить документ</button>
    <div class="drop-zone" id="dropZone" onclick="document.getElementById('fileInput').click()">
      📂 Перетащите сюда свой XML УПД (или нажмите для выбора)
      <input type="file" id="fileInput" accept=".xml" style="display:none" onchange="uploadFile(this.files[0])">
    </div>
  </div>

  <div id="content">Загрузка данных...</div>

<script>
async function simulate(mode) {
  await fetch('/api/simulate?mode=' + mode);
  setTimeout(refresh, 300);
}

const dz = document.getElementById('dropZone');
dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('dragover'); });
dz.addEventListener('dragleave', () => dz.classList.remove('dragover'));
dz.addEventListener('drop', e => {
  e.preventDefault();
  dz.classList.remove('dragover');
  if (e.dataTransfer.files.length) uploadFile(e.dataTransfer.files);
});

async function uploadFile(file) {
  if (!file) return;
  const text = await file.text();
  await fetch('/api/upload', { method: 'POST', body: text });
  setTimeout(refresh, 300);
}

async function refresh() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    if (!data.status) return;
    const isPass = data.status === 'PASS';
    let html = `
      <div class="status-box status-${data.status}">
        <div class="status-title">${isPass ? '🟢 ОТГРУЗКА РАЗРЕШЕНА (ОШИБОК НЕТ)' : '🔴 СТОП! ВЫГРУЗКА В ЭДО ЗАБЛОКИРОВАНА'}</div>
        <div class="meta">Контрагент: ${data.network} | Строк: ${data.checked_lines} | Ошибок: ${data.errors_count} | Время: ${data.timestamp}</div>
        <div class="meta" style="margin-top:4px;">SHA-256 целостности: ${data.integrity_sha256}</div>
      </div>
    `;
    if (!isPass) {
      html += `<h3 style="margin-bottom:12px;">Обнаруженные расхождения (до отправки в Контур):</h3>`;
      data.errors.forEach(e => {
        html += `
          <div class="err-card">
            <div class="err-type">Строка №${e.line} • ${e.type}</div>
            <div class="err-item">${e.item}</div>
            <div class="err-detail">${e.detail}</div>
            <div class="err-risk">⚠ Последствие на РЦ: ${e.risk}</div>
          </div>
        `;
      });
    } else {
      html += `<div style="background:#1e293b; padding:16px; border-radius:8px; color:#a7f3d0; font-size:15px;">
        ✅ Все цены, кванты, веса (Меркурий) и остаточные сроки годности (ОСГ ≥ 75%) соответствуют заказу сети. Документ готов к отправке в Контур.Диадок / СБИС.
      </div>`;
    }
    document.getElementById('content').innerHTML = html;
  } catch (err) {}
}
setInterval(refresh, 1000);
refresh();
</script>
</body>
</html>"""

class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/status':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(LATEST_REPORT, ensure_ascii=False).encode('utf-8'))
        elif parsed.path == '/api/simulate':
            qs = urllib.parse.parse_qs(parsed.query)
            mode = qs.get('mode', ['bad'])
            with open(UPD_FILE, "w", encoding="utf-8") as f:
                f.write(GOOD_UPD_XML if mode == 'good' else BAD_UPD_XML)
            self.send_response(200)
            self.end_headers()
        else:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))

    def do_POST(self):
        if self.path == '/api/upload':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length).decode('utf-8', errors='replace')
            with open(UPD_FILE, "w", encoding="utf-8") as f:
                f.write(body)
            self.send_response(200)
            self.end_headers()

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    t = threading.Thread(target=folder_watcher, daemon=True)
    t.start()
    with ReusableTCPServer(("127.0.0.1", PORT), Handler) as httpd:
        httpd.serve_forever()
