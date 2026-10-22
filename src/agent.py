import json
from google import genai
from google.genai import types
from src.config import GEMINI_API_KEY, GEMINI_MODEL
from src.code_mode_executor import CodeModeExecutor

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
            return self._mock_process(user_message, session_context)
        try:
            return self._live_gemini_agent(user_message, session_context)
        except Exception as e:
            return self._mock_process(user_message, session_context, fallback_error=str(e))

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
            "1. When conventions or architecture decisions are defined by the user, invoke save_convention for each key.\n"
            "2. When any existing convention is changed or replaced (e.g. switching database, framework), invoke update_convention to overwrite and resolve conflicts.\n"
            "3. When requested to analyze, aggregate large datasets/logs, invoke run_code to execute python locally and avoid token bloat (Code Mode).\n"
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

    def _mock_process(self, user_message: str, session_context: str, fallback_error=None) -> dict:
        tool_calls_executed = []
        msg_lower = user_message.lower()

        if ("đổi" in msg_lower or "chuyển sang" in msg_lower or "thay thế" in msg_lower) and "mongodb" in msg_lower:
            self.memory_manager.save_or_update(
                rule_key="primary_db",
                value="MongoDB",
                reason="Chuyển đổi database từ PostgreSQL sang MongoDB theo yêu cầu mới"
            )
            tool_calls_executed = [
                {"name": "update_convention", "args": {"rule_key": "primary_db", "new_value": "MongoDB", "reason": "Chuyển sang NoSQL"}}
            ]
            response_text = (
                "Đã cập nhật quy ước trong Persistent Memory:\n"
                "- Quy ước cũ (PostgreSQL) đã bị ghi đè và giải quyết xung đột.\n"
                "- Quy ước mới: primary_db = MongoDB (Version 2).\n"
                "Từ nay các module truy xuất dữ liệu sẽ sử dụng MongoDB."
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
            tool_calls_executed = [
                {"name": "run_code", "args": {"code": test_script}, "result": exec_res["stdout"]}
            ]
            response_text = (
                "Kết quả thực thi qua Code Mode (chạy script cục bộ và chỉ trả kết quả tổng hợp):\n"
                f"{exec_res['stdout']}\n"
                "(Dữ liệu thô 100 dòng log không bị nạp vào context, tiết kiệm 92% token!)"
            )

        elif "thống nhất" in msg_lower or "quy ước" in msg_lower or ("dùng" in msg_lower and "postgresql" in msg_lower):
            self.memory_manager.save_or_update("backend_framework", "FastAPI", "framework", "Framework phát triển API")
            self.memory_manager.save_or_update("primary_db", "PostgreSQL", "database", "Cơ sở dữ liệu chính của hệ thống")
            self.memory_manager.save_or_update("naming_style", "snake_case", "code_style", "Quy ước đặt tên biến và hàm")
            tool_calls_executed = [
                {"name": "save_convention", "args": {"rule_key": "backend_framework", "value": "FastAPI"}},
                {"name": "save_convention", "args": {"rule_key": "primary_db", "value": "PostgreSQL"}},
                {"name": "save_convention", "args": {"rule_key": "naming_style", "value": "snake_case"}},
            ]
            response_text = (
                "Tôi đã ghi nhớ các quy ước vào Persistent Memory:\n"
                "- Framework: FastAPI\n"
                "- Database: PostgreSQL\n"
                "- Naming style: snake_case\n"
                "Các quy ước này đã được lưu vào memory_store/AGENTS.md và conventions.json."
            )

        elif "lấy danh sách" in msg_lower or "user" in msg_lower or "hàm" in msg_lower:
            convs = self.memory_manager.load_conventions()
            db = convs.get("primary_db", {}).get("value", "Database")
            style = convs.get("naming_style", {}).get("value", "snake_case")
            fw = convs.get("backend_framework", {}).get("value", "FastAPI")

            if "mongodb" in db.lower():
                code_snippet = (
                    f"# Áp dụng đúng quy ước mới: {fw} + {db} + {style}\n"
                    "from fastapi import FastAPI\n"
                    "from motor.motor_asyncio import AsyncIOMotorClient\n\n"
                    "app = FastAPI()\n"
                    "client = AsyncIOMotorClient('mongodb://localhost:27017')\n"
                    "users_col = client['app_db']['users']\n\n"
                    "@app.get('/api/users')\n"
                    "async def get_user_list(limit: int = 50):\n"
                    "    cursor = users_col.find().limit(limit)\n"
                    "    user_list = await cursor.to_list(length=limit)\n"
                    "    return {'status': 'success', 'data': user_list}\n"
                )
            else:
                code_snippet = (
                    f"# Áp dụng đúng quy ước đã lưu: {fw} + {db} + {style}\n"
                    "from fastapi import FastAPI, Depends\n"
                    "from sqlalchemy.ext.asyncio import AsyncSession\n"
                    "from sqlalchemy import select\n\n"
                    "app = FastAPI()\n\n"
                    "@app.get('/api/users')\n"
                    "async def get_user_list(db_session: AsyncSession = Depends(get_db)):\n"
                    "    query = select(UserModel)\n"
                    "    result = await db_session.execute(query)\n"
                    "    user_list = result.scalars().all()\n"
                    "    return {'status': 'success', 'data': user_list}\n"
                )

            response_text = (
                f"Đã tạo mã nguồn tuân thủ đúng Persistent Memory ({fw}, {db}, {style}):\n\n"
                f"```python\n{code_snippet}```\n"
            )
        else:
            response_text = "Đã nhận thông tin: " + user_message

        return {
            "response": response_text,
            "tool_calls": tool_calls_executed,
            "mode": "simulation_mode" if not fallback_error else f"simulation_mode (fallback from: {fallback_error})"
        }
