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
        self.max_agent_turns = 5

        if not self.use_mock:
            try:
                self.client = genai.Client(api_key=GEMINI_API_KEY)
            except Exception:
                self.use_mock = True

    def tool_save_convention(self, rule_key: str, value: str, category: str = "general", description: str = "") -> str:
        res = self.memory_manager.save_or_update(
            rule_key=rule_key,
            value=value,
            category=category,
            description=description,
            reason="Agent identified convention from user dialogue"
        )
        return json.dumps(res, ensure_ascii=False)

    def tool_update_convention(self, rule_key: str, new_value: str, reason: str = "") -> str:
        res = self.memory_manager.save_or_update(
            rule_key=rule_key,
            value=new_value,
            reason=reason or "Agent detected updated project convention"
        )
        return json.dumps(res, ensure_ascii=False)

    def tool_get_active_conventions(self) -> str:
        convs = self.memory_manager.load_conventions()
        return json.dumps(convs, ensure_ascii=False, indent=2)

    def tool_run_code(self, code: str) -> str:
        res = self.code_executor.execute(code)
        return json.dumps(res, ensure_ascii=False)

    def _execute_tool_call(self, tool_name: str, args: dict) -> str:
        if tool_name == "save_convention":
            return self.tool_save_convention(**args)
        elif tool_name == "update_convention":
            return self.tool_update_convention(**args)
        elif tool_name == "get_active_conventions":
            return self.tool_get_active_conventions()
        elif tool_name == "run_code":
            return self.tool_run_code(**args)
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    def process_message(self, user_message: str, session_context: str = "") -> dict:
        if self.use_mock:
            return self._mock_process(user_message, session_context)
        try:
            return self._live_agent_loop(user_message, session_context)
        except Exception as e:
            return self._mock_process(user_message, session_context, fallback_error=str(e))

    def _live_agent_loop(self, user_message: str, session_context: str) -> dict:
        tools = [
            self.tool_save_convention,
            self.tool_update_convention,
            self.tool_get_active_conventions,
            self.tool_run_code,
        ]

        system_instruction = (
            "You are an autonomous software engineering AI agent operating inside an Agent Harness.\n"
            "You have access to persistent memory tools and a Code Mode execution tool.\n"
            "Analyze the conversation and autonomously decide when to invoke tools:\n"
            "1. When conventions/architecture are defined, call save_convention.\n"
            "2. When existing conventions change or are replaced, call update_convention.\n"
            "3. When asked to analyze large logs or heavy datasets, use run_code to execute python locally and return aggregated metrics.\n"
            "4. Strictly adhere to all injected active conventions:\n\n"
            + session_context
        )

        messages = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_message)]
            )
        ]

        tool_calls_executed = []
        final_text = ""

        for step in range(self.max_agent_turns):
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=tools,
                temperature=0.2,
            )

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=messages,
                config=config,
            )

            candidate = response.candidates[0] if response.candidates else None
            if not candidate or not candidate.content:
                final_text = response.text or "Không nhận được phản hồi từ model."
                break

            messages.append(candidate.content)

            function_calls = response.function_calls
            if not function_calls:
                final_text = response.text or "Hoàn tất."
                break

            tool_response_parts = []
            for call in function_calls:
                call_args = dict(call.args) if call.args else {}
                result_str = self._execute_tool_call(call.name, call_args)
                tool_calls_executed.append({
                    "name": call.name,
                    "args": call_args,
                    "result": result_str,
                    "turn": step + 1
                })
                tool_response_parts.append(
                    types.Part.from_function_response(
                        name=call.name,
                        response={"result": result_str}
                    )
                )

            messages.append(
                types.Content(role="tool", parts=tool_response_parts)
            )

        return {
            "response": final_text,
            "tool_calls": tool_calls_executed,
            "mode": "live_gemini_agent_loop"
        }

    def _mock_process(self, user_message: str, session_context: str, fallback_error=None) -> dict:
        tool_calls_executed = []
        msg_lower = user_message.lower()

        if ("đổi" in msg_lower or "chuyển sang" in msg_lower or "thay thế" in msg_lower) and "mongodb" in msg_lower:
            self.tool_update_convention("primary_db", "MongoDB", "Chuyển đổi database từ PostgreSQL sang MongoDB theo yêu cầu mới")
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
            self.tool_save_convention("backend_framework", "FastAPI", "framework", "Framework phát triển API")
            self.tool_save_convention("primary_db", "PostgreSQL", "database", "Cơ sở dữ liệu chính của hệ thống")
            self.tool_save_convention("naming_style", "snake_case", "code_style", "Quy ước đặt tên biến và hàm")
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
