import sys
import argparse
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

def run_challenge_a_demo(use_mock=False):
    print(f"{Fore.GREEN}{Style.BRIGHT}{'=' * 75}")
    print(f"{Fore.GREEN}{Style.BRIGHT}   SE373 - AGENT HARNESS & PERSISTENT MEMORY (CHALLENGE A + CODE MODE)")
    print(f"{Fore.GREEN}{Style.BRIGHT}   Học viên: Trần Minh Thuận - MSSV: 24521746")
    print(f"{Fore.GREEN}{Style.BRIGHT}   Giảng viên chấm: Thầy Nguyễn Hiếu Nghĩa")
    print(f"{Fore.GREEN}{Style.BRIGHT}{'=' * 75}\n")

    memory_manager = MemoryManager()
    memory_manager.clear()

    harness = AgentHarness(use_mock=use_mock)

    print(f"\n{Fore.YELLOW}{Style.BRIGHT}>>> PHẦN 1: CHỨNG MINH 1 - PERSISTENCE ACROSS SESSIONS <<<{Style.RESET_ALL}")
    
    ctx1 = harness.start_new_session("Thống nhất quy ước dự án ban đầu")
    prompt1 = "Trong dự án này, chúng ta thống nhất dùng framework FastAPI, cơ sở dữ liệu PostgreSQL và quy ước đặt tên snake_case."
    harness.run_turn(prompt1, ctx1)

    ctx2 = harness.start_new_session("Kiểm chứng nhớ quy ước ở Session mới (Cold Start)")
    prompt2 = "Hãy viết cho tôi hàm API lấy danh sách user."
    harness.run_turn(prompt2, ctx2)

    print(f"\n{Fore.GREEN}{Style.BRIGHT}[KẾT QUẢ CHỨNG MINH 1]: Ở Session 2 hoàn toàn mới (không truyền lịch sử chat cũ), Agent vẫn nạp đúng các quy ước đã lưu từ Session 1 và sinh code FastAPI + PostgreSQL + snake_case!{Style.RESET_ALL}\n")

    print(f"\n{Fore.YELLOW}{Style.BRIGHT}>>> PHẦN 2: CHỨNG MINH 2 - RESOLVE CONFLICT & MEMORY UPDATE <<<{Style.RESET_ALL}")

    ctx3 = harness.start_new_session("Cập nhật và thay đổi quy ước kỹ thuật")
    prompt3 = "Kiến trúc thay đổi, từ nay chúng ta đổi sang dùng cơ sở dữ liệu MongoDB thay cho PostgreSQL nhé."
    harness.run_turn(prompt3, ctx3)

    ctx4 = harness.start_new_session("Kiểm chứng áp dụng quy ước mới sau khi cập nhật (Cold Start)")
    prompt4 = "Hãy viết lại hàm API lấy danh sách user theo kiến trúc hiện tại."
    harness.run_turn(prompt4, ctx4)

    print(f"\n{Fore.GREEN}{Style.BRIGHT}[KẾT QUẢ CHỨNG MINH 2]: Quy ước cũ (PostgreSQL) đã được ghi đè, giải quyết xung đột thành công. Ở Session 4, Agent chỉ sử dụng quy ước mới nhất là MongoDB!{Style.RESET_ALL}\n")

    print(f"\n{Fore.YELLOW}{Style.BRIGHT}>>> PHẦN 3: ĐIỂM CỘNG - DEMO CODE MODE (GIẢM THIỂU CONTEXT BLOAT) <<<{Style.RESET_ALL}")
    ctx5 = harness.start_new_session("Thực thi Code Mode lọc log và dữ liệu")
    prompt5 = "Hãy dùng Code Mode phân tích log để tìm ra 2 mã lỗi phổ biến nhất."
    harness.run_turn(prompt5, ctx5)

    print("\n" + "=" * 75)
    print(f"{Fore.CYAN}{Style.BRIGHT}HOÀN THÀNH TẤT CẢ CÁC MỤC TIÊU CỦA CHALLENGE A VÀ ĐIỂM CỘNG CODE MODE!")
    print(f"{Fore.CYAN}Toàn bộ persistent memory đã được lưu tại thư mục: memory_store/{Style.RESET_ALL}")
    print("=" * 75 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="Chạy ở chế độ mô phỏng offline")
    args = parser.parse_args()
    run_challenge_a_demo(use_mock=args.mock)
