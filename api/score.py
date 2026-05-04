from http.server import BaseHTTPRequestHandler
import json
import math
import urllib.request

SUPABASE_URL = "https://bkshfiqinlinsttvtzxh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJrc2hmaXFpbmxpbnN0dHZ0enhoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NzI5Nzc4OCwiZXhwIjoyMDkyODczNzg4fQ.jKUcnRDFbcVIlVOf6d9jqsVNI-ve-wBDEp-bjMKfbak"

def supabase_get(table, filters):
    query = "&".join([f"{k}=eq.{v}" for k, v in filters.items()])
    url = f"{SUPABASE_URL}/rest/v1/{table}?{query}&limit=1"
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    })
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def supabase_post(table, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    })
    try:
        with urllib.request.urlopen(req) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code

def score(skin_temp, hrv, eda, hr):
    # Baselines for a healthy fit 23 year old male
    temp_base = 36.4
    hrv_base  = 56.0
    eda_base  = 4.7
    hr_base   = 68.0

    # Deviations — amplified to make changes visible
    temp_dev = max(0, (skin_temp - temp_base) / 0.3) * 15
    hrv_dev  = max(0, (hrv_base - hrv) / 8.0) * 20
    eda_dev  = max(0, (eda - eda_base) / 0.8) * 20
    hr_dev   = max(0, (hr - hr_base) / 6.0) * 15

    raw_score = 12 + temp_dev + hrv_dev + eda_dev + hr_dev
    return min(49, round(raw_score, 1))

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))

        record = body.get("record", {})
        window_id = record.get("window_id")
        user_id   = record.get("user_id")

        if not window_id or not user_id:
            self._respond(400, {"error": "bad_payload"})
            return

        rows = supabase_get("sensor_windows", {"window_id": window_id})
        if not rows:
            self._respond(404, {"error": "window_not_found"})
            return

        row = rows[0]
        skin_temp = row.get("skin_temp_c")
        hrv       = row.get("hrv_ms")
        eda       = row.get("eda_microsiemens")
        hr        = row.get("heart_rate_bpm")

        if skin_temp is None or hrv is None or eda is None or hr is None:
            self._respond(200, {"skipped": "incomplete_features"})
            return

        immune_score = score(float(skin_temp), float(hrv), float(eda), float(hr))
        risk_label   = 1 if immune_score >= 50 else 0

        status = supabase_post("inferences", {
            "window_id":    window_id,
            "user_id":      user_id,
            "immune_score": immune_score,
            "risk_label":   risk_label,
            "model_version": "v1"
        })

        self._respond(201, {
            "window_id":    window_id,
            "immune_score": immune_score,
            "risk_label":   risk_label
        })

    def _respond(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *args):
        pass
