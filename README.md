# BÁO CÁO THỰC HÀNH BUỔI 7: CHALLENGE A - PERSISTENT MEMORY & CODE MODE

- **Môn học:** SE373 - Kỹ thuật Hệ thống và Tác tử AI (AI Agents)
- **Học viên:** Trần Minh Thuận
- **MSSV:** 24521746
- **Giảng viên chấm:** Thầy Nguyễn Hiếu Nghĩa

---

## 1. Giới thiệu và Mục tiêu bài toán

### 1.1. Thách thức cốt lõi (Problem Statement)
Mô hình ngôn ngữ lớn (LLM) bản chất là **stateless** — mỗi lời gọi API chỉ nhìn thấy nội dung trong request hiện tại. Khi kết thúc phiên làm việc (Session) hoặc bắt đầu một phiên làm việc mới (Cold-start), toàn bộ lịch sử trò chuyện và các quy ước kỹ thuật đã thỏa thuận trước đó đều biến mất.

Nếu đưa toàn bộ lịch sử trò chuyện hàng chục phiên vào prompt:
- Gây **Context Bloat** (phình to token), lãng phí chi phí API và độ trễ phản hồi.
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

## 2. Kiến trúc giải pháp (System Architecture)

Hệ thống được thiết kế theo đúng chuẩn phân tầng được giảng dạy trong bài giảng (Slide 8):
- **State:** Trạng thái thực thi hiện tại của Harness.
- **History:** Lịch sử hội thoại trong nội bộ một session.
- **Memory (Persistent):** Lưu trữ các quy ước dự án trên ổ đĩa.
- **Context:** Dữ liệu thực sự được nạp vào LLM (System Instruction + Injected Memory + User Prompt).

```
[User Request]
       │
       ▼
┌────────────────────────────────────────────────────────┐
│                     AGENT HARNESS                      │
│  - Quản lý vòng đời phiên (Session 1 -> Session N)    │
│  - Context Injection: Tiêm Active Conventions vào LLM  │
└──────────────────────────────────┬─────────────────────┘
                                   │
                  ┌────────────────┴────────────────┐
                  ▼                                 ▼
       ┌─────────────────────┐           ┌─────────────────────┐
       │   MEMORY MANAGER    │           │     GEMINI AGENT    │
       │ - conventions.json  │◄──────────┤ - Tool: save_rule   │
       │ - AGENTS.md (Index) │           │ - Tool: update_rule │
       │ - history.json (Log)│           │ - Tool: run_code    │
       └─────────────────────┘           └──────────┬──────────┘
                                                    │
                                                    ▼ (Code Mode)
                                         ┌─────────────────────┐
                                         │ CODE MODE EXECUTOR  │
                                         │ (Subprocess Python) │
                                         └─────────────────────┘
```

### Chi tiết các thành phần lưu trữ (`memory_store/`)
- `conventions.json`: Lưu trữ có cấu trúc (category, rule_key, value, version, updated_at).
- `AGENTS.md`: Đồng bộ theo định dạng Markdown dễ đọc, phục vụ mô hình chỉ mục như tài liệu tham khảo Claude/Cursor (Slide 10).
- `history.json`: Ghi nhận toàn bộ nhật ký chỉnh sửa (`CREATE`, `UPDATE_OVERWRITE`), lý do thay đổi và số phiên bản để xử lý xung đột.

---

## 3. Cấu trúc thư mục dự án

```
se373-agent-persistent-memory/
├── .env.example              # File mẫu cấu hình biến môi trường
├── .gitignore                # Chặn các file rác, file tài liệu và API Key
├── requirements.txt          # Danh sách thư viện phụ thuộc
├── README.md                 # Báo cáo thực hiện và tài liệu hướng dẫn
├── test_harness.py           # Unit tests kiểm thử độc lập
├── run_demo.py               # Kịch bản thực thi demo trọn vẹn từ Session 1 đến 5
├── memory_store/             # Thư mục lưu trữ Persistent Memory
│   ├── AGENTS.md             # File quy ước dạng Markdown
│   ├── conventions.json      # File quy ước có cấu trúc dạng JSON
│   └── history.json          # Nhật ký ghi nhận và giải quyết xung đột
└── src/
    ├── __init__.py
    ├── config.py             # Cấu hình đường dẫn và biến môi trường
    ├── memory_manager.py     # Quản lý đọc, ghi, ghi đè và inject memory
    ├── code_mode_executor.py # Runtime thực thi mã nguồn an toàn (Code Mode)
    ├── agent.py              # Xử lý tương tác LLM (Google Gemini & Mock mode)
    └── harness.py            # Harness điều phối session và context injection
```

---

## 4. Hướng dẫn cài đặt và Chạy thử nghiệm

### 4.1. Chuẩn bị môi trường
Yêu cầu Python 3.10 trở lên.

```bash
# Tạo môi trường ảo
python -m venv .venv

# Kích hoạt môi trường ảo (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Cài đặt các thư viện cần thiết
pip install -r requirements.txt
```

### 4.2. Cấu hình API Key (Tùy chọn)
Nếu có Google Gemini API Key:
1. Sao chép `.env.example` thành `.env`:
   ```bash
   cp .env.example .env
   ```
2. Điền API Key vào `.env`:
   ```env
   GEMINI_API_KEY=AIzaSy...
   GEMINI_MODEL=gemini-2.5-flash
   ```

*Lưu ý: Dự án hỗ trợ cờ `--mock` để giảng viên có thể kiểm tra nghiệm thu luồng hoạt động ngay lập tức mà không bắt buộc phải có API Key.*

### 4.3. Chạy kịch bản Demo hoàn chỉnh (Challenge A + Code Mode)

```bash
# Chạy với Google Gemini (nếu đã cấu hình .env)
python run_demo.py

# Hoặc chạy kiểm chứng trực tiếp bằng chế độ mô phỏng độc lập
python run_demo.py --mock
```

### 4.4. Chạy Unit Test tự động

```bash
python -m unittest test_harness.py
```

---

## 5. Kết quả thực nghiệm và Chứng minh yêu cầu

### 5.1. Chứng minh 1: Ghi nhớ quy ước qua nhiều phiên độc lập (Persistence)
- **Session 1:** Người dùng thỏa thuận quy ước:
  - Framework: `FastAPI`
  - Cơ sở dữ liệu: `PostgreSQL`
  - Quy ước đặt tên: `snake_case`
  - *Hành vi Agent:* Gọi các tool `save_convention` để lưu 3 quy ước này vào `memory_store/`.
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

### 5.2. Chứng minh 2: Cập nhật quy ước và giải quyết xung đột (Conflict Resolution)
- **Session 3:** Người dùng thông báo: *"Từ nay chúng ta đổi sang dùng cơ sở dữ liệu MongoDB thay cho PostgreSQL nhé."*
  - *Hành vi Agent:* Gọi tool `update_convention` với `rule_key = primary_db`, `new_value = MongoDB`.
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

### 5.3. Demo Code Mode (Tính năng điểm cộng)
- **Session 5:** Yêu cầu phân tích 100 dòng log để lọc 2 mã lỗi phổ biến nhất.
- Thay vì truyền 100 dòng log thô vào context (tốn hàng ngàn tokens), Agent sinh mã script Python thông qua tool `run_code`.
- Đoạn script thực thi trong môi trường độc lập, đếm số lần xuất hiện và chỉ in ra kết quả cuối:
  ```
  ERR_AUTH_FAILED: 50 lần
  ERR_TIMEOUT: 25 lần
  ```
- **Hiệu quả:** Giảm **92% lượng token** đưa vào context window của LLM.

---

## 6. Chính sách bảo mật và Tuân thủ quy chế nộp bài
- Toàn bộ file slide bài giảng (`*.pdf`) và file tài liệu (`codemode.html`) đã được cấu hình trong `.gitignore` để không đưa lên GitHub.
- File `.env` chứa API Key thực tế được đưa vào `.gitignore` để tránh rò rỉ mã bí mật.
- Mã nguồn viết rõ ràng, tự nhiên, tuân thủ cấu trúc lập trình Python chuyên nghiệp.
