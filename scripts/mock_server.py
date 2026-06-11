"""
客达天下 Mock API Server — 模拟后端，用于跑通 AI 生成的 Pytest 脚本
用法: .venv/Scripts/python scripts/mock_server.py [port]
"""
import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# 默认端口
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080


class MockHandler(BaseHTTPRequestHandler):

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def _parse_form(self):
        """解析 application/x-www-form-urlencoded"""
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return parse_qs(raw)

    # ====================== 登录模块 ======================

    def _handle_login(self, body):
        username = body.get("username", "")
        password = body.get("password", "")
        code = body.get("code", "")
        uuid = body.get("uuid", "")

        # Token 缺失场景 — 没传 token 是登录模块本身的参数校验
        # 校验必填参数
        missing = []
        if not username:
            missing.append("username")
        if not password:
            missing.append("password")
        if not code:
            missing.append("code")
        if not uuid:
            missing.append("uuid")
        if missing:
            return self._send_json({
                "code": 400,
                "msg": f"缺少必填参数: {', '.join(missing)}",
                "data": None
            }, 400)

        # 校验用户名/密码
        if username == "manager" and password == "123456" and code == "8888":
            return self._send_json({
                "code": 200,
                "msg": "操作成功",
                "data": {
                    "token": "eyJhbGciOiJIUzUxMiJ9.mock-token-for-testing",
                    "user": {"id": 1, "name": "管理员"}
                }
            })
        else:
            return self._send_json({
                "code": 401,
                "msg": "用户名或密码错误",
                "data": None
            }, 401)

    def _handle_captcha(self):
        return self._send_json({
            "code": 200,
            "msg": "操作成功",
            "data": {"uuid": "mock-uuid-8888", "img": "data:image/png;base64,mock-image-data"}
        })

    # ====================== 课程模块 ======================

    def _handle_course_create(self, body):
        name = body.get("name", "")
        subject = body.get("subject")
        price = body.get("price")
        applicablePerson = body.get("applicablePerson")

        missing = []
        if not name:
            missing.append("name")
        if subject is None:
            missing.append("subject")
        if price is None:
            missing.append("price")
        if not applicablePerson:
            missing.append("applicablePerson")
        if missing:
            return self._send_json({"code": 400, "msg": f"缺少必填参数: {', '.join(missing)}"}, 400)

        if len(name) > 64:
            return self._send_json({"code": 400, "msg": "课程名称不能超过64个字符"}, 400)
        if not isinstance(price, (int, float)) or price < 0 or price > 99999:
            return self._send_json({"code": 400, "msg": "价格必须在0-99999之间"}, 400)
        if str(subject) not in [str(i) for i in range(10)]:
            return self._send_json({"code": 400, "msg": "学科值无效"}, 400)
        if str(applicablePerson) not in ["1", "2"]:
            return self._send_json({"code": 400, "msg": "适用人群值无效"}, 400)

        return self._send_json({
            "code": 200, "msg": "操作成功",
            "data": {"id": 1000127925, "name": name}
        })

    def _handle_course_list(self, query):
        return self._send_json({
            "code": 200, "msg": "操作成功",
            "data": [{"id": 1000127924, "name": "测试课程", "subject": "6", "price": 899}]
        })

    def _handle_course_detail(self):
        return self._send_json({
            "code": 200, "msg": "操作成功",
            "data": {"id": 1000127924, "name": "测试课程", "subject": "6", "price": 899, "applicablePerson": "2"}
        })

    def _handle_course_update(self, body):
        cid = body.get("id")
        if not cid:
            return self._send_json({"code": 400, "msg": "缺少必填参数: id"}, 400)
        return self._send_json({
            "code": 200, "msg": "操作成功",
            "data": {"id": cid, "name": body.get("name", "测试课程")}
        })

    def _handle_course_delete(self):
        return self._send_json({"code": 200, "msg": "操作成功", "data": None})

    # ====================== 合同模块 ======================

    def _handle_contract_create(self, body):
        missing = []
        for f in ["contractNo", "phone", "name", "subject", "courseId", "fileName"]:
            if not body.get(f):
                missing.append(f)
        if missing:
            return self._send_json({"code": 400, "msg": f"缺少必填参数: {', '.join(missing)}"}, 400)

        phone = body.get("phone", "")
        if len(phone) != 11 or not phone.isdigit():
            return self._send_json({"code": 400, "msg": "手机号必须为11位数字"}, 400)

        return self._send_json({
            "code": 200, "msg": "操作成功",
            "data": {"id": 10950251898105099, "contractNo": body.get("contractNo")}
        })

    def _handle_contract_list(self, query):
        return self._send_json({
            "code": 200, "msg": "操作成功",
            "data": [{"id": 10950251898105098, "contractNo": "HT20240001", "phone": "13812345678"}]
        })

    def _handle_contract_remove(self, body):
        cid = body.get("id")
        if not cid:
            return self._send_json({"code": 400, "msg": "缺少必填参数: id"}, 400)
        return self._send_json({"code": 200, "msg": "操作成功", "data": None})

    # ====================== 上传 ======================

    def _handle_upload(self):
        return self._send_json({
            "code": 200, "msg": "操作成功",
            "data": {"url": "/profile/upload/test.pdf", "fileName": "test.pdf"}
        })

    # ====================== 路由 ======================

    def _route(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        method = self.command.upper()
        query = parse_qs(parsed.query)

        # GET /api/captchaImage
        if path == "/api/captchaImage" and method == "GET":
            return self._handle_captcha()

        # POST /api/login
        if path == "/api/login" and method == "POST":
            body = self._read_body()
            return self._handle_login(body)

        # GET /api/clues/course/list
        if path == "/api/clues/course/list" and method == "GET":
            return self._handle_course_list(query)

        # GET /api/clues/course/:id  — 需要处理动态参数
        if path.startswith("/api/clues/course/") and method == "GET":
            param = path.split("/")[-1]
            if param and param != "list":
                return self._handle_course_detail()

        # POST /api/clues/course
        if path == "/api/clues/course" and method == "POST":
            body = self._read_body()
            return self._handle_course_create(body)

        # PUT /api/clues/course
        if path == "/api/clues/course" and method == "PUT":
            body = self._read_body()
            return self._handle_course_update(body)

        # DELETE /api/clues/course/:id
        if path.startswith("/api/clues/course/") and method == "DELETE":
            return self._handle_course_delete()

        # POST /api/common/upload
        if path == "/api/common/upload" and method == "POST":
            return self._handle_upload()

        # POST /api/contract
        if path == "/api/contract" and method == "POST":
            body = self._read_body()
            return self._handle_contract_create(body)

        # GET /api/contract/list
        if path == "/api/contract/list" and method == "GET":
            return self._handle_contract_list(query)

        # POST /api/contract/remove
        if path == "/api/contract/remove" and method == "POST":
            body = self._read_body()
            return self._handle_contract_remove(body)

        # 404
        self._send_json({"code": 404, "msg": f"Not Found: {method} {path}"}, 404)

    def do_GET(self):
        self._route()

    def do_POST(self):
        self._route()

    def do_PUT(self):
        self._route()

    def do_DELETE(self):
        self._route()

    def log_message(self, fmt, *args):
        """控制台打印请求日志"""
        print(f"[Mock] {args[0]} {args[1]} → {args[2]}")


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), MockHandler)
    print(f"🎯 客达天下 Mock Server 启动 → http://localhost:{PORT}")
    print(f"   支持模块: 登录、课程(增删改查)、合同(增删查)、上传")
    print(f"   按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Mock Server 已停止")
        server.server_close()
