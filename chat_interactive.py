import sys
from colorama import Fore, Style, init
from src.harness import AgentHarness
from src.memory_manager import MemoryManager

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

init(autoreset=True)

def main():
    print(f"{Fore.GREEN}{Style.BRIGHT}{'=' * 75}")
    print(f"{Fore.GREEN}{Style.BRIGHT}   SE373 - CHƯƠNG TRÌNH CHAT TƯƠNG TÁC TRỰC TIẾP VỚI AI AGENT")
    print(f"{Fore.GREEN}{Style.BRIGHT}   Học viên: Trần Minh Thuận - MSSV: 24521746")
    print(f"{Fore.GREEN}{Style.BRIGHT}{'=' * 75}")
    print(f"{Fore.YELLOW}Các lệnh hỗ trợ:")
    print(f"  {Fore.CYAN}/new{Fore.YELLOW}     : Bắt đầu một Session mới (Cold-start kiểm chứng tiêm bộ nhớ)")
    print(f"  {Fore.CYAN}/memory{Fore.YELLOW}  : Xem danh sách quy ước hiện có trong Persistent Memory")
    print(f"  {Fore.CYAN}/clear{Fore.YELLOW}   : Xóa sạch bộ nhớ để thử nghiệm từ đầu")
    print(f"  {Fore.CYAN}/exit{Fore.YELLOW}    : Thoát chương trình{Style.RESET_ALL}\n")

    harness = AgentHarness(use_mock=False)
    session_title = "Khởi động ban đầu"
    current_context = harness.start_new_session(session_title)

    while True:
        try:
            user_input = input(f"\n{Fore.GREEN}{Style.BRIGHT}Bạn [{harness.current_session_id}]: {Style.RESET_ALL}").strip()
            if not user_input:
                continue

            if user_input.lower() in ["/exit", "/quit"]:
                print(f"{Fore.YELLOW}Tạm biệt!{Style.RESET_ALL}")
                break

            elif user_input.lower() in ["/new", "/new_session"]:
                title = input(f"{Fore.CYAN}Nhập tiêu đề cho Session mới (hoặc Enter): {Style.RESET_ALL}").strip()
                session_title = title if title else f"Phiên làm việc {harness.current_session_id + 1}"
                current_context = harness.start_new_session(session_title)
                continue

            elif user_input.lower() == "/memory":
                convs = harness.memory_manager.load_conventions()
                print(f"\n{Fore.CYAN}=== DANH SÁCH QUY ƯỚC ĐANG LƯU TRỮ ===")
                if not convs:
                    print("Chưa có quy ước nào được lưu.")
                else:
                    for k, v in convs.items():
                        print(f"  - [{v.get('category','general').upper()}] {k}: {v['value']} (v{v.get('version',1)})")
                print("========================================")
                continue

            elif user_input.lower() == "/clear":
                harness.memory_manager.clear()
                print(f"{Fore.RED}Đã xóa sạch bộ nhớ persistent memory.{Style.RESET_ALL}")
                current_context = harness.memory_manager.get_injected_context()
                continue

            harness.run_turn(user_input, current_context)

        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Đã dừng chương trình.{Style.RESET_ALL}")
            break
        except Exception as e:
            print(f"{Fore.RED}Lỗi: {e}{Style.RESET_ALL}")

if __name__ == "__main__":
    main()
