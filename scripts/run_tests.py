"""
AI 测试用例全链路 Demo
用法: .venv/Scripts/python scripts/run_tests.py [project] [module] [port]
"""
import sys
import os
import json
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PORT = int(sys.argv[3]) if len(sys.argv) > 2 else 53536
PROJECT = sys.argv[1] if len(sys.argv) > 1 else "客达天下"
MODULE = sys.argv[2] if len(sys.argv) > 2 else "登录"

print("=" * 60)
print("Step 1: 生成测试用例")
print("=" * 60)
from src.agents.api_agent import APITestAgent
agent = APITestAgent()
cases = agent.generate(PROJECT, MODULE, "")
print(f"  -> {len(cases)} 条用例\n")

print("=" * 60)
print("Step 2: 写入 Runner 脚本")
print("=" * 60)
ts = datetime.now().strftime("%H%M%S")
runner_path = ROOT / "pytest_scripts" / f"runner_{MODULE}_{ts}.py"

# 使用 __PORT__ 和 __CASES__ 作为占位符，之后 replace
TEMPLATE = r'''# -*- coding: utf-8 -*-
"""AI 生成的接口自动化测试脚本（增强版）"""
import pytest, requests, json, os

BASE_URL = "http://localhost:__PORT__"
session = requests.Session()
test_results = {}

def get_nested(obj, key_path):
    """尝试嵌套查找，如果第一层key不存在则回退到扁平查找"""
    keys = key_path.split(".")
    # 先试完整嵌套路径
    cur = obj
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            break
    else:
        return cur
    # 回退：忽略第一级，说明响应没有外包装body/data
    if len(keys) > 1:
        cur = obj
        for k in keys[1:]:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                return None
        return cur
    return None

def check_assertions(case, resp):
    errors = []
    for key, exp in case.get("assert", {}).items():
        actual = resp.status_code if key == "status_code" else get_nested(resp.json(), key)
        if actual != exp:
            errors.append("%s: expect %s, got %s" % (key, exp, actual))
    return errors

TEST_CASES = __CASES__

@pytest.mark.parametrize("case", TEST_CASES, ids=lambda x: x.get("case_id","?"))
def test_api(case):
    cid, title = case["case_id"], case["title"]
    url = BASE_URL + case["url"]
    method = case["method"].upper()
    headers = case.get("headers", {"Content-Type": "application/json"})
    body = case.get("body", {})
    try:
        if method == "GET":
            resp = session.get(url, headers=headers, params=body)
        elif method == "POST":
            resp = session.post(url, headers=headers, json=body)
        elif method == "PUT":
            resp = session.put(url, headers=headers, json=body)
        elif method == "DELETE":
            resp = session.delete(url, headers=headers)
        else:
            pytest.fail("unsupported method: " + method)
        errors = check_assertions(case, resp)
        if errors:
            test_results[cid] = {"title": title, "status": "FAIL", "code": resp.status_code, "resp": resp.text[:300], "errors": errors}
            pytest.fail("; ".join(errors))
        else:
            test_results[cid] = {"title": title, "status": "PASS", "code": resp.status_code, "resp": "", "errors": []}
    except Exception as e:
        test_results[cid] = {"title": title, "status": "ERROR", "code": 0, "resp": "", "errors": [str(e)]}
        pytest.fail(str(e))

@pytest.fixture(scope="session", autouse=True)
def _gen_report(request):
    yield
    r = test_results
    if not r:
        return
    total = len(r)
    passed = sum(1 for v in r.values() if v["status"] == "PASS")
    failed = sum(1 for v in r.values() if v["status"] == "FAIL")
    errs = sum(1 for v in r.values() if v["status"] == "ERROR")
    rows = ""
    for cid in sorted(r.keys()):
        v = r[cid]
        icon = {"PASS": "PASS", "FAIL": "FAIL", "ERROR": "ERROR"}[v["status"]]
        err_html = "<br>".join(v["errors"]) if v["errors"] else ""
        rh = ""
        if v["resp"]:
            try:
                rh = "<pre>" + json.dumps(json.loads(v["resp"]), ensure_ascii=False, indent=2)[:200] + "</pre>"
            except:
                rh = "<pre>" + v["resp"][:200] + "</pre>"
        rows += "<tr><td>%s</td><td>%s</td><td style='color:%s'>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            cid, v["title"], "green" if v["status"]=="PASS" else "red", icon, v["code"], err_html, rh)
    pass_rate = "%.1f%%" % (passed/total*100) if total else "N/A"
    rp = os.path.join(os.path.dirname(__file__), "..", "test_report.html")
    with open(rp, "w", encoding="utf-8") as f:
        f.write("""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>__PROJECT__/__MODULE__ report</title>
<style>
body{font-family:-apple-system,sans-serif;margin:20px;background:#f5f5f5}
.container{max-width:1200px;margin:auto;background:#fff;padding:20px;border-radius:8px}
.summary{display:flex;gap:20px;margin:20px 0}
.stat{padding:15px 25px;border-radius:8px;text-align:center;min-width:100px}
.stat-pass{background:#e8f5e9}.stat-fail{background:#ffebee}
.stat-error{background:#fff3e0}.stat-total{background:#e3f2fd}
.stat-number{font-size:28px;font-weight:bold}
table{width:100%;border-collapse:collapse}
th,td{padding:8px 12px;text-align:left;border-bottom:1px solid #ddd}
th{background:#f8f9fa}
tr:hover{background:#f1f1f1}
pre{background:#f5f5f5;padding:8px;border-radius:4px;font-size:12px;max-height:200px;overflow:auto}
</style></head><body><div class="container">
<h1>__PROJECT__ / __MODULE__</h1>
<p>__TIME__ | Mock: localhost:__PORT__</p>
<div class="summary">
<div class="stat stat-total"><div class="stat-number">""" + str(total) + """</div>Total</div>
<div class="stat stat-pass"><div class="stat-number">""" + str(passed) + """</div>Pass</div>
<div class="stat stat-fail"><div class="stat-number">""" + str(failed) + """</div>Fail</div>
<div class="stat stat-error"><div class="stat-number">""" + str(errs) + """</div>Error</div>
</div>
<p>Pass rate: """ + pass_rate + """</p>
<table><tr><th>ID</th><th>Title</th><th>Status</th><th>Code</th><th>Errors</th><th>Response</th></tr>""" + rows + """</table>
</div></body></html>""")
    print("\\nHTML report: file:///" + rp.replace("\\\\", "/"))
'''

# 替换占位符
CASES_JSON = json.dumps(cases, ensure_ascii=False)
NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

code = TEMPLATE
code = code.replace("__PORT__", str(PORT))
code = code.replace("__CASES__", CASES_JSON)
code = code.replace("__PROJECT__", PROJECT)
code = code.replace("__MODULE__", MODULE)
code = code.replace("__TIME__", NOW)

with open(runner_path, "w", encoding="utf-8") as f:
    f.write(code)
print(f"  -> {runner_path}")

print("\n" + "=" * 60)
print("Step 3: 执行 pytest")
print("=" * 60)
env = os.environ.copy()
env["PYTHONIOENCODING"] = "utf-8"
result = subprocess.run(
    [sys.executable, "-m", "pytest", str(runner_path), "-v", "--tb=short", "--no-header"],
    capture_output=True, text=True, encoding='utf-8', cwd=str(ROOT), env=env
)
out = result.stdout or ""
print(out[:3000] if len(out) > 3000 else out)
stderr_text = result.stderr or ""
if stderr_text:
    print("STDERR:", stderr_text[:500])
print("Done!")
