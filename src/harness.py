from colorama import Fore, Style, init
from src.agent import Agent
from src.memory_manager import MemoryManager

init(autoreset=True)

class AgentHarness:
    def __init__(self, use_mock=False):
        self.memory_manager = MemoryManager()
        self.agent = Agent(self.memory_manager, use_mock=use_mock)
        self.current_session_id = 0

    def start_new_session(self, session_title: str):
        self.current_session_id += 1
        print("\n" + "=" * 70)
        print(f"{Fore.CYAN}{Style.BRIGHT}>>> KHỞI TẠO PHIÊN MỚI: SESSION {self.current_session_id} - {session_title}{Style.RESET_ALL}")
        print("=" * 70)

        injected_context = self.memory_manager.get_injected_context()
        print(f"{Fore.YELLOW}[HARNESS - CONTEXT INJECTION]{Style.RESET_ALL}")
        print(f"{Fore.WHITE}{injected_context}{Style.RESET_ALL}")
        print("-" * 70)
        return injected_context

    def run_turn(self, user_message: str, session_context: str) -> dict:
        print(f"\n{Fore.GREEN}{Style.BRIGHT}[USER]:{Style.RESET_ALL} {user_message}")

        result = self.agent.process_message(user_message, session_context)

        tool_calls = result.get("tool_calls", [])
        if tool_calls:
            print(f"\n{Fore.MAGENTA}[TOOL CALLS ĐƯỢC THỰC THI]:{Style.RESET_ALL}")
            for tc in tool_calls:
                print(f"  ⚡ {Fore.MAGENTA}{tc['name']}{Style.RESET_ALL}({tc.get('args', {})})")
                if "result" in tc:
                    print(f"     => Kết quả: {tc['result']}")

        print(f"\n{Fore.BLUE}{Style.BRIGHT}[AGENT RESPONSE] ({result.get('mode', 'agent')}):{Style.RESET_ALL}")
        print(result["response"])
        return result
