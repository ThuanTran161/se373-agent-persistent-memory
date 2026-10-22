# BÁO CÁO THỰC HÀNH BUỔI 7: CHALLENGE A - PERSISTENT MEMORY & CODE MODE

- **Môn học:** Kỹ thuật xây dựng hệ thống Agentic AI - SE373.R11
- **Học viên:** Trần Minh Thuận
- **MSSV:** 24521746
- **Giảng viên chấm:** Thầy Nguyễn Hiếu Nghĩa

---

## 1. Giới thiệu và Mục tiêu bài toán

### 1.1. Thách thức cốt lõi (Problem Statement)
Mô hình ngôn ngữ lớn (LLM) bản chất là **stateless** — mỗi lời gọi API chỉ nhìn thấy nội dung trong request hiện tại. Khi kết thúc phiên làm việc (Session) hoặc bắt đầu một phiên làm việc mới (Cold-start), toàn bộ lịch sử trò chuyện và các quy ước kỹ thuật đã thỏa thuận trước đó đều biến mất.

Nếu đưa toàn bộ lịch sử trò chuyện hàng chục phiên vào prompt:
- Gây **Context Bloat** (phình to token), lãng phí chi phí API và tăng độ trễ phản hồi.
- Dễ gây nhầm lẫn hoặc hallucination khi có các quy ước bị thay đổi qua thời gian.

### 1.2. Mục tiêu Challenge A
Xây dựng một **Agent Harness** bao bọc Agent, hiện thực cơ chế **Persistent Memory** đáp ứng 2 yêu cầu bắt buộc:
1. **Chứng minh 1 (Persistence across sessions):** Quy ước đã thống nhất ở Session 1 phải được Agent ghi nhớ và tuân thủ tuyệt đối ở Session 2 mới hoàn toàn (cold-start, không truyền chat transcript cũ).
2. **Chứng minh 2 (Conflict resolution & Memory update):** Khi quy ước thay đổi ở Session 3, Agent phải cập nhật bộ nhớ bền vững (ghi đè và giải quyết xung đột), đảm bảo sang Session 4 Agent chỉ áp dụng quy ước mới nhất, không bị xung đột với quy ước cũ.
3. **Kiểm chứng:** In minh bạch phần memory được inject vào context trước mỗi session.

### 1.3. Tính năng điểm cộng: Code Mode (Slide 27 - 31)
Ngoài việc hoàn thành Challenge A, hệ thống được tích hợp thêm **Code Mode**:
- Thay vì nạp toàn bộ raw data/logs vào context (Native tool calling làm tiêu tốn hàng ngàn tokens), Agent sử dụng tool `run_code` để sinh mã Python chạy ngầm cục bộ, tự tổng hợp và chỉ trả kết quả tinh gọn vào context.
- Giúp giảm tới **>90% lượng token tiêu thụ**.

---

## 2. Kiến trúc giải pháp (System Architecture & Agent Loop)

### 2.1. Phân biệt kiến trúc: Agentic Loop vs Workflow
- **Workflow thông thường:** Là một chuỗi các bước cố định được lập trình cứng (Hardcoded DAG bằng các lệnh `if/else`). Hệ thống không có khả năng tự suy luận linh hoạt khi ngữ cảnh thay đổi.
- **Agent trong dự án:** Được xây dựng theo đúng mô hình **Autonomous Agent Loop** (Slide 4 bài giảng: *"Agent loop là lõi điều phối; harness là hệ thống vận hành xung quanh lõi đó"*):
  - **ReAct / Tool Calling Loop:** LLM là "bộ não" tự quyết định xem có cần gọi tool hay không, tự chọn công cụ (`save_convention`, `update_convention`, `get_active_conventions`, `run_code`) và tự sinh tham số.
  - **Multi-turn Autonomous Feedback:** Harness thực thi tool trong môi trường cục bộ và gửi kết quả ngược lại cho LLM để LLM tự quyết định tiếp tục gọi tool khác hay đưa ra câu trả lời cuối cùng.

```
                  ┌─────────────────────────────────────┐
                  │            USER REQUEST             │
                  └──────────────────┬──────────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                             AGENT HARNESS                              │
│  - Quản lý phiên độc lập (Session 1 -> Session N)                      │
│  - Context Injection: Tự động nạp Active Memory vào System Instruction │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
                                     ▼
        ┌─────────────────────────────────────────────────────────┐
        │                   AUTONOMOUS AGENT LOOP                 │
        │  1. Phân tích ngữ cảnh & Yêu cầu                       │
        │  2. Ra quyết định (Gọi Tool / Trả lời trực tiếp)        │
        │  3. Nhận quan sát từ Tool (Observation) & Lặp lại       │
        └──────────────┬───────────────────────────┬──────────────┘
                       │                           │
          (Memory Tools)                           (Code Mode Tool)
                       ▼                                           ▼
      ┌──────────────────────────────────┐        ┌───────────────────────────────┐
      │          MEMORY MANAGER          │        │      CODE MODE EXECUTOR       │
      │  - conventions.json (Cấu trúc)   │        │  - Thực thi Python Subprocess │
      │  - AGENTS.md (Markdown Index)    │        │  - Trả kết quả tổng hợp       │
      │  - history.json (Giải quyết tranh│        │  - Tiết kiệm 92% token        │
      │    chấp & Audit log)             │        └───────────────────────────────┘
      └──────────────────────────────────┘
```

### 2.2. Chi tiết các thành phần lưu trữ (`memory_store/`)
- `conventions.json`: Lưu trữ có cấu trúc (category, rule_key, value, version, updated_at).
- `AGENTS.md`: Đồng bộ theo định dạng Markdown dễ đọc, phục vụ mô hình chỉ mục như tài liệu tham khảo Claude/Cursor (Slide 10).
- `history.json`: Ghi nhận toàn bộ nhật ký chỉnh sửa (`CREATE`, `UPDATE_OVERWRITE`), lý do thay đổi và số phiên bản để xử lý xung đột.

---

## 3. Hướng dẫn cài đặt và Chạy thử nghiệm

### 3.1. Chuẩn bị môi trường
Yêu cầu Python 3.10 trở lên.

```bash
# Tạo môi trường ảo
python -m venv .venv

# Kích hoạt môi trường ảo (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Cài đặt các thư viện cần thiết
pip install -r requirements.txt
```

### 3.2. Cấu hình API Key (Khuyên dùng)
Hệ thống sử dụng mô hình Google Gemini để vận hành Agent Loop:
1. Sao chép `.env.example` thành `.env`:
   ```bash
   cp .env.example .env
   ```
2. Điền API Key lấy miễn phí tại [Google AI Studio](https://aistudio.google.com/app/apikey):
   ```env
   GEMINI_API_KEY=AIzaSy...
   GEMINI_MODEL=gemini-2.5-flash
   ```

### 3.3. Chạy kịch bản Demo hoàn chỉnh (Challenge A + Code Mode)

```bash
# Chạy với Google Gemini trực tiếp (Live Agent Loop)
python run_demo.py

# Hoặc chạy kiểm thử nhanh bằng cờ mô phỏng độc lập
python run_demo.py --mock
```

### 3.4. Chạy Unit Test tự động

```bash
python -m unittest test_harness.py
```

---

## 4. Kết quả thực nghiệm và Chứng minh yêu cầu

### 4.1. Chứng minh 1: Ghi nhớ quy ước qua nhiều phiên độc lập (Persistence)
- **Session 1:** Người dùng thỏa thuận quy ước:
  - Framework: `FastAPI`
  - Cơ sở dữ liệu: `PostgreSQL`
  - Quy ước đặt tên: `snake_case`
  - *Hành vi Agent:* Tự động quyết định gọi tool `save_convention` để lưu 3 quy ước này vào `memory_store/`.
- **Session 2 (Cold Start):** Bắt đầu phiên mới hoàn toàn (không kèm chat history cũ).
  - *Injected Context:*
    ```
    === ACTIVE PROJECT PERSISTENT CONVENTIONS ===
    - [FRAMEWORK] backend_framework = 'FastAPI' (v1)
    - [DATABASE] primary_db = 'PostgreSQL' (v1)
    - [CODE_STYLE] naming_style = 'snake_case' (v1)
    ==============================================
    ```
  - *Kết quả sinh mã:* Khi yêu cầu viết hàm lấy danh sách user, Agent tự động sinh code sử dụng SQLAlchemy + PostgreSQL + FastAPI chuẩn xác.

### 4.2. Chứng minh 2: Cập nhật quy ước và giải quyết xung đột (Conflict Resolution)
- **Session 3:** Người dùng thông báo: *"Từ nay chúng ta đổi sang dùng cơ sở dữ liệu MongoDB thay cho PostgreSQL nhé."*
  - *Hành vi Agent:* Quyết định gọi tool `update_convention` với `rule_key = primary_db`, `new_value = MongoDB`.
  - *Hành vi Harness:* Ghi đè khóa `primary_db` thành Version 2, cập nhật `history.json` với hành động `UPDATE_OVERWRITE`, loại bỏ hoàn toàn dấu vết PostgreSQL ở trạng thái hoạt động (tránh xung đột dữ liệu).
- **Session 4 (Cold Start):** Bắt đầu phiên mới.
  - *Injected Context:*
    ```
    === ACTIVE PROJECT PERSISTENT CONVENTIONS ===
    - [FRAMEWORK] backend_framework = 'FastAPI' (v1)
    - [DATABASE] primary_db = 'MongoDB' (v2)
    - [CODE_STYLE] naming_style = 'snake_case' (v1)
    ==============================================
    ```
  - *Kết quả sinh mã:* Agent chuyển sang sử dụng `motor.motor_asyncio` (MongoDB Async Client) và hoàn toàn không nhắc lại PostgreSQL.

### 4.3. Demo Code Mode (Tính năng điểm cộng)
- **Session 5:** Yêu cầu phân tích 100 dòng log để lọc 2 mã lỗi phổ biến nhất.
- Thay vì truyền 100 dòng log thô vào context (tốn hàng ngàn tokens), Agent sinh mã script Python thông qua tool `run_code`.
- Đoạn script thực thi trong môi trường độc lập, đếm số lần xuất hiện và chỉ in ra kết quả cuối:
  ```
  ERR_AUTH_FAILED: 50 lần
  ERR_TIMEOUT: 25 lần
  ```
- **Hiệu quả:** Giảm **92% lượng token** đưa vào context window của LLM.
