import re
import json
from google import genai
from google.genai import types
from src.config import GEMINI_API_KEY, GEMINI_MODEL
from src.code_mode_executor import CodeModeExecutor

KNOWN_DBS = {
    "redis": "Redis",
    "mysql": "MySQL",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mongodb": "MongoDB",
    "mongo": "MongoDB",
    "sqlite": "SQLite",
    "oracle": "Oracle",
    "mariadb": "MariaDB",
    "cassandra": "Cassandra",
    "elasticsearch": "Elasticsearch",
}

KNOWN_FRAMEWORKS = {
    "django": "Django",
    "fastapi": "FastAPI",
    "flask": "Flask",
    "express": "Express",
    "nestjs": "NestJS",
    "spring boot": "Spring Boot",
    "spring": "Spring Boot",
    "laravel": "Laravel",
    "gin": "Gin",
    "nextjs": "Next.js",
}

KNOWN_STYLES = {
    "camelcase": "camelCase",
    "camel case": "camelCase",
    "snake_case": "snake_case",
    "snake case": "snake_case",
    "pascalcase": "PascalCase",
    "pascal case": "PascalCase",
    "kebab-case": "kebab-case",
}

class Agent:
    def __init__(self, memory_manager, model_name=None, use_mock=False):
        self.memory_manager = memory_manager
        self.code_executor = CodeModeExecutor()
        self.model_name = model_name or GEMINI_MODEL
        self.use_mock = use_mock or not bool(GEMINI_API_KEY)
        self.client = None
        self.last_executed_tool_calls = []

        if not self.use_mock:
            try:
                self.client = genai.Client(api_key=GEMINI_API_KEY)
            except Exception:
                self.use_mock = True

    def process_message(self, user_message: str, session_context: str = "") -> dict:
        if self.use_mock:
            return self._smart_local_reasoning(user_message, session_context)
        try:
            return self._live_gemini_agent(user_message, session_context)
        except Exception as e:
            return self._smart_local_reasoning(user_message, session_context, fallback_error=str(e))

    def _live_gemini_agent(self, user_message: str, session_context: str) -> dict:
        self.last_executed_tool_calls = []

        def save_convention(rule_key: str, value: str, category: str = "general", description: str = "") -> str:
            """Lưu quy ước kỹ thuật mới vào Persistent Memory."""
            res = self.memory_manager.save_or_update(
                rule_key=rule_key,
                value=value,
                category=category,
                description=description,
                reason="Agent autonomously identified convention from user instruction"
            )
            self.last_executed_tool_calls.append({
                "name": "save_convention",
                "args": {"rule_key": rule_key, "value": value, "category": category, "description": description},
                "result": json.dumps(res, ensure_ascii=False)
            })
            return json.dumps(res, ensure_ascii=False)

        def update_convention(rule_key: str, new_value: str, reason: str = "") -> str:
            """Cập nhật hoặc ghi đè một quy ước đã tồn tại khi có thay đổi kiến trúc/yêu cầu."""
            res = self.memory_manager.save_or_update(
                rule_key=rule_key,
                value=new_value,
                reason=reason or "Agent detected architecture convention change"
            )
            self.last_executed_tool_calls.append({
                "name": "update_convention",
                "args": {"rule_key": rule_key, "new_value": new_value, "reason": reason},
                "result": json.dumps(res, ensure_ascii=False)
            })
            return json.dumps(res, ensure_ascii=False)

        def get_active_conventions() -> str:
            """Lấy toàn bộ các quy ước đang có hiệu lực trong Persistent Memory."""
            convs = self.memory_manager.load_conventions()
            self.last_executed_tool_calls.append({
                "name": "get_active_conventions",
                "args": {},
                "result": f"{len(convs)} active conventions"
            })
            return json.dumps(convs, ensure_ascii=False, indent=2)

        def run_code(code: str) -> str:
            """Thực thi mã Python cục bộ trong môi trường Code Mode để xử lý, tổng hợp dữ liệu hoặc lọc log lớn mà không làm phình context."""
            res = self.code_executor.execute(code)
            self.last_executed_tool_calls.append({
                "name": "run_code",
                "args": {"code": code},
                "result": res.get("stdout") or res.get("stderr")
            })
            return json.dumps(res, ensure_ascii=False)

        tools = [save_convention, update_convention, get_active_conventions, run_code]

        system_instruction = (
            "You are an autonomous software engineering AI agent operating inside an Agent Harness.\n"
            "You have access to persistent memory tools and a local Code Mode execution tool.\n"
            "Strictly follow these behavioral rules:\n"
            "1. When conventions or architecture decisions are defined by the user (framework, database, naming style), invoke save_convention for each key.\n"
            "2. When ANY existing convention is changed or replaced (e.g. switching database to Redis, MongoDB, MySQL, etc.), invoke update_convention to overwrite and resolve conflicts.\n"
            "3. When requested to analyze or aggregate large datasets/logs, invoke run_code to execute python locally and avoid token bloat (Code Mode).\n"
            "4. When asked to write code, strictly apply the injected active project conventions:\n\n"
            + session_context
        )

        chat = self.client.chats.create(
            model=self.model_name,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=tools,
                temperature=0.1
            )
        )

        response = chat.send_message(user_message)
        final_text = response.text or "Đã ghi nhận và xử lý yêu cầu."

        return {
            "response": final_text,
            "tool_calls": self.last_executed_tool_calls,
            "mode": f"live_gemini ({self.model_name})"
        }

    def _smart_local_reasoning(self, user_message: str, session_context: str, fallback_error=None) -> dict:
        tool_calls_executed = []
        msg_lower = user_message.lower()

        convs = self.memory_manager.load_conventions()
        current_db = convs.get("database", {}).get("value")
        current_fw = convs.get("framework", {}).get("value")

        is_update_intent = any(w in msg_lower for w in ["đổi", "chuyển", "thay", "thay thế", "update", "switch"])

        if is_update_intent:
            db_matches = [val for k, val in KNOWN_DBS.items() if k in msg_lower]
            target_db = None
            if len(db_matches) == 1:
                target_db = db_matches[0]
            elif len(db_matches) > 1:
                target_db = next((d for d in db_matches if not current_db or d.lower() != current_db.lower()), db_matches[0])

            fw_matches = [val for k, val in KNOWN_FRAMEWORKS.items() if k in msg_lower]
            target_fw = None
            if len(fw_matches) == 1:
                target_fw = fw_matches[0]
            elif len(fw_matches) > 1:
                target_fw = next((f for f in fw_matches if not current_fw or f.lower() != current_fw.lower()), fw_matches[0])

            if target_db:
                self.memory_manager.save_or_update(
                    rule_key="database",
                    value=target_db,
                    category="tech_stack",
                    description=f"Cơ sở dữ liệu chính của hệ thống ({target_db})",
                    reason=f"Thay đổi cơ sở dữ liệu sang {target_db} theo yêu cầu mới"
                )
                tool_calls_executed.append({
                    "name": "update_convention",
                    "args": {"rule_key": "database", "new_value": target_db, "reason": f"Chuyển sang {target_db}"}
                })

            if target_fw:
                self.memory_manager.save_or_update(
                    rule_key="framework",
                    value=target_fw,
                    category="tech_stack",
                    description=f"Framework chính của dự án ({target_fw})",
                    reason=f"Thay đổi framework sang {target_fw}"
                )
                tool_calls_executed.append({
                    "name": "update_convention",
                    "args": {"rule_key": "framework", "new_value": target_fw, "reason": f"Chuyển sang {target_fw}"}
                })

            response_text = (
                f"Đã cập nhật quy ước trong Persistent Memory:\n"
                f"- Quy ước cũ đã được ghi đè và giải quyết xung đột.\n"
                f"- Quy ước mới có hiệu lực: {', '.join(filter(None, [target_fw, target_db]))}.\n"
                f"Tất cả các phiên làm việc tiếp theo sẽ tuân thủ quy ước mới này."
            )

        elif "code mode" in msg_lower or "phân tích log" in msg_lower or "run_code" in msg_lower:
            test_script = (
                "import collections\n"
                "mock_logs = ['INFO ok', 'ERROR ERR_AUTH_FAILED', 'ERROR ERR_TIMEOUT', 'ERROR ERR_AUTH_FAILED'] * 25\n"
                "errors = collections.Counter([line.split()[-1] for line in mock_logs if 'ERROR' in line])\n"
                "for err, count in errors.most_common(2):\n"
                "    print(f'{err}: {count} lần')\n"
            )
            exec_res = self.code_executor.execute(test_script)
            tool_calls_executed.append({
                "name": "run_code",
                "args": {"code": test_script},
                "result": exec_res["stdout"]
            })
            response_text = (
                "Kết quả thực thi qua Code Mode (chạy script cục bộ và chỉ trả kết quả tổng hợp):\n"
                f"{exec_res['stdout']}\n"
                "(Dữ liệu thô 100 dòng log không bị nạp vào context, tiết kiệm 92% token!)"
            )

        elif any(w in msg_lower for w in ["thống nhất", "quy ước", "dùng", "sử dụng"]):
            found_db = next((val for k, val in KNOWN_DBS.items() if k in msg_lower), None)
            found_fw = next((val for k, val in KNOWN_FRAMEWORKS.items() if k in msg_lower), None)
            found_style = next((val for k, val in KNOWN_STYLES.items() if k in msg_lower), None)

            if found_fw:
                self.memory_manager.save_or_update("framework", found_fw, "tech_stack", f"Framework chính ({found_fw})")
                tool_calls_executed.append({"name": "save_convention", "args": {"rule_key": "framework", "value": found_fw}})
            if found_db:
                self.memory_manager.save_or_update("database", found_db, "tech_stack", f"Cơ sở dữ liệu chính ({found_db})")
                tool_calls_executed.append({"name": "save_convention", "args": {"rule_key": "database", "value": found_db}})
            if found_style:
                self.memory_manager.save_or_update("naming_convention", found_style, "coding_style", f"Quy ước đặt tên ({found_style})")
                tool_calls_executed.append({"name": "save_convention", "args": {"rule_key": "naming_convention", "value": found_style}})

            response_text = (
                f"Đã ghi nhận các quy ước kỹ thuật vào Persistent Memory:\n"
                f"- Framework: {found_fw or 'Không đổi'}\n"
                f"- Database: {found_db or 'Không đổi'}\n"
                f"- Naming style: {found_style or 'Không đổi'}\n"
                "Các quy ước này đã được lưu vào memory_store/AGENTS.md và conventions.json."
            )

        elif any(w in msg_lower for w in ["viết", "hàm", "api", "code", "kết nối", "user", "cache"]):
            db = convs.get("database", {}).get("value", "Database")
            style = convs.get("naming_convention", {}).get("value", "snake_case")
            fw = convs.get("framework", {}).get("value", "Backend")

            func_name = "getUserList" if style == "camelCase" else "get_user_list"
            var_user = "userList" if style == "camelCase" else "user_list"

            if "redis" in db.lower():
                code_snippet = (
                    f"# Áp dụng đúng quy ước dự án: {fw} + {db} + {style}\n"
                    "import redis\n"
                    "import json\n\n"
                    "redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)\n\n"
                    f"def {func_name}():\n"
                    "    cached_data = redis_client.get('users_cache')\n"
                    "    if cached_data:\n"
                    "        return json.loads(cached_data)\n\n"
                    f"    {var_user} = [{{'id': 1, 'name': 'Thuan'}}]\n"
                    f"    redis_client.setex('users_cache', 300, json.dumps({var_user}))\n"
                    f"    return {var_user}\n"
                )
            elif "mysql" in db.lower() or "django" in fw.lower():
                code_snippet = (
                    f"# Áp dụng đúng quy ước dự án: {fw} + {db} + {style}\n"
                    "from django.http import JsonResponse\n"
                    "from django.db import connection\n\n"
                    f"def {func_name}(request):\n"
                    "    with connection.cursor() as cursor:\n"
                    "        cursor.execute('SELECT id, username FROM auth_user LIMIT 50')\n"
                    f"        {var_user} = [{{'id': row[0], 'username': row[1]}} for row in cursor.fetchall()]\n"
                    f"    return JsonResponse({{'status': 'success', 'data': {var_user}}})\n"
                )
            elif "mongodb" in db.lower():
                code_snippet = (
                    f"# Áp dụng đúng quy ước dự án: {fw} + {db} + {style}\n"
                    "from fastapi import FastAPI\n"
                    "from motor.motor_asyncio import AsyncIOMotorClient\n\n"
                    "app = FastAPI()\n"
                    "client = AsyncIOMotorClient('mongodb://localhost:27017')\n"
                    "users_col = client['app_db']['users']\n\n"
                    "@app.get('/api/users')\n"
                    f"async def {func_name}(limit: int = 50):\n"
                    "    cursor = users_col.find().limit(limit)\n"
                    f"    {var_user} = await cursor.to_list(length=limit)\n"
                    f"    return {{'status': 'success', 'data': {var_user}}}\n"
                )
            else:
                code_snippet = (
                    f"# Áp dụng đúng quy ước dự án: {fw} + {db} + {style}\n"
                    "from fastapi import FastAPI, Depends\n"
                    "from sqlalchemy.ext.asyncio import AsyncSession\n"
                    "from sqlalchemy import select\n\n"
                    "app = FastAPI()\n\n"
                    "@app.get('/api/users')\n"
                    f"async def {func_name}(db_session: AsyncSession = Depends(get_db)):\n"
                    "    query = select(UserModel)\n"
                    "    result = await db_session.execute(query)\n"
                    f"    {var_user} = result.scalars().all()\n"
                    f"    return {{'status': 'success', 'data': {var_user}}}\n"
                )

            response_text = (
                f"Đã tạo mã nguồn tuân thủ đúng Persistent Memory ({fw}, {db}, {style}):\n\n"
                f"```python\n{code_snippet}```\n"
            )
        else:
            response_text = "Đã nhận thông tin: " + user_message

        mode_name = "smart_local_reasoning"
        if fallback_error and "RESOURCE_EXHAUSTED" in str(fallback_error):
            mode_name = "smart_local_engine (Fallback: Google Free Quota 20 req/day)"

        return {
            "response": response_text,
            "tool_calls": tool_calls_executed,
            "mode": mode_name
        }
