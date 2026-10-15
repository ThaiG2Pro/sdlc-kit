# Mô hình Known - Unknown & Cơ chế Triệt tiêu Điểm mù trong Multi-Agent SDLC

> Tài liệu chuẩn hóa nhận thức, bóc tách các điểm mù nhận thức (blind spots) và định hình bộ kỹ năng phòng vệ cho hệ thống Multi-Agent (Analyst, Architect, Developer, QA) cùng Người phê duyệt (Human Supervisor).

---

## 1. Giải phẫu các "Căn bệnh ngầm" phá vỡ Multi-Agent SDLC

Trong mô hình cộng tác giữa **Người chủ quản (Human Approver)** và **Hệ thống Agent chuyên trách (Analyst, Architect, Developer, QA)**, thất bại hiếm khi đến từ năng lực viết code hay ngữ pháp prompt, mà thường bắt nguồn từ **sự đứt gãy nhận thức** (cognitive breakdown) qua các khâu bàn giao:

```
[Chủ quản] ──(Lệch ngữ nghĩa)──► [Analyst] ──(Giả định ngầm)──► [Architect]
                                                                     │
                                                             (Thiên kiến xác nhận)
                                                                     ▼
[Sản phẩm sai thực tế] ◄──(Test pass theo spec sai)── [QA] ◄── [Developer]
```

### ① Ảo tưởng đồng thuận & Lệch pha ngữ nghĩa (False Consensus & Semantic Drift)
* **Hiện tượng:** Cả hai bên cùng sử dụng chung một danh từ/thuật ngữ, nhưng trong "đầu" mỗi bên lại gán cho nó một định nghĩa hoàn toàn khác biệt. Không ai hỏi lại vì nghĩ từ ngữ đó quá quen thuộc.
* **Nguyên nhân cốt lõi:**
  * Thiếu **Ubiquitous Language (Ngôn ngữ chung)** theo chuẩn Domain-Driven Design (DDD).
  * **LLM hoạt động theo xác suất thống kê:** Khi gặp thuật ngữ đa nghĩa (ví dụ: *"active status"*, *"session timeout"*, *"idempotent"*, *"sync"*, *"soft delete"*), Agent sẽ tự động chọn phân phối xác suất phổ biến nhất trên Internet thay vì hỏi rõ ngữ cảnh nội bộ của dự án.
* **Hậu quả:** Tất cả các bên đều dùng chung từ vựng trong tài liệu, tạo ra "vỏ bọc đồng thuận" giả tạo cho đến khi hệ thống vận hành thực tế mới vỡ lở.

### ② Thiên kiến xác nhận (Confirmation Bias) & Tính nịnh đầm của AI (LLM Sycophancy)
* **Hiện tượng:** Khi một thực thể (Người hoặc Agent) đã có sẵn một giả định hay mô hình tư duy trong đầu, khi tiếp nhận tài liệu từ người khác, họ có xu hướng:
  * Chỉ chăm chú tìm những chi tiết củng cố cho góc nhìn của mình.
  * Tự động "bóp méo", "làm mịn" hoặc phớt lờ hoàn toàn các chi tiết trái ngược hoặc điều kiện biên.
* **Bản chất của Agent (LLM Sycophancy):** Các mô hình ngôn ngữ lớn luôn có thiên hướng làm hài lòng người đối thoại (*eager to please*). Agent rất dễ:
  * Âm thầm tự điền vào chỗ trống (*auto-fill blind spots*) thay vì dừng lại đặt câu hỏi làm rõ.
  * Mặc định tin rằng tài liệu của Agent trước là hoàn hảo và chỉ tìm cách triển khai tiếp thay vì thách thức tính đúng đắn.
* **Bản chất của Người phê duyệt:** Não bộ con người có phản xạ đọc lướt (*skimming*), tự động ánh xạ câu chữ của Agent về kỳ vọng cá nhân và phê duyệt mà không phát hiện các lỗ hổng tiềm ẩn.

### ③ Hiệu ứng Domino sai lệch (Cascading Hallucination / Compounding Errors)
* Một **giả định sai không được kiểm chứng** tại khâu S1 (Analyst) sẽ trở thành "sự thật nền tảng" cho S3 (Architect) vẽ kiến trúc.
* S4 (Developer) viết code hoàn toàn sạch và chuẩn xác theo bản vẽ kiến trúc sai đó.
* S5 (QA) viết test scenario và assertion bám sát tài liệu đặc tả sai đó.
* **Kết cục:** Toàn bộ chuỗi CI/CD pass 100%, test xanh toàn bộ, nhưng hệ thống bàn giao thực tế lại hoàn toàn đi chệch mục tiêu kinh doanh của chủ quản.

---

## 2. Mô hình hóa Nhận thức theo Ma trận Known - Unknown

Áp dụng ma trận nhận thức vào vòng đời phát triển phần mềm (SDLC):

```
                      ┌────────────────────────────┬────────────────────────────┐
                      │        THỰC TẾ BIẾT        │     THỰC TẾ CHƯA BIẾT      │
┌─────────────────────┼────────────────────────────┼────────────────────────────┤
│                     │       KNOWN KNOWNS         │       KNOWN UNKNOWNS       │
│ Ý THỨC ĐƯỢC         │   (Đã rõ ràng & Thống nhất)│     (Rủi ro đã lộ diện)    │
│ (Explicit)          │                            │                            │
│                     │ • Acceptance Criteria (AC) │ • Câu hỏi làm rõ (Spikes)  │
│                     │ • Hợp đồng API / DB Schema │ • Rủi ro hiệu năng, tải    │
│                     │ • Test assertions tự động  │ • Vấn đề cần User quyết    │
├─────────────────────┼────────────────────────────┼────────────────────────────┤
│                     │      UNKNOWN KNOWNS        │      UNKNOWN UNKNOWNS      │
│ KHÔNG Ý THỨC ĐƯỢC   │    (Giả định ngầm / Ẩn)    │    (Điểm mù tuyệt đối)     │
│ (Tacit / Blind)     │                            │                            │
│                     │ • Thuật ngữ hiểu theo thói │ • Lỗ hổng nghiệp vụ chưa   │
│                     │   quen cá nhân             │   ai từng nghĩ tới         │
│                     │ • Logic ngầm trong mã cũ   │ • Xung đột kiến trúc tiềm  │
│                     │ • "Tôi tưởng bạn đã hiểu"  │   ẩn chưa có tiền lệ       │
└─────────────────────┴────────────────────────────┴────────────────────────────┘
```

### Dòng chảy dịch chuyển Nhận thức Bắt buộc:

```
[Unknown Unknowns] ──(1. Bóc tách & Phản biện)──► [Known Unknowns] ──(2. Hợp đồng & Kiểm chứng)──► [Known Knowns]
  (Điểm mù tuyệt đối)                                (Xác định rõ chỗ hổng)                         (Đóng băng chuẩn mực)
```

1. **Giai đoạn 1 (`Unknown Unknowns` → `Known Unknowns`):**
   * Phá hủy ảo tưởng "mọi thứ đã rõ ràng".
   * Kéo toàn bộ giả định ngầm, các case biên (*edge cases*), xung đột thuật ngữ lên mặt bàn dưới dạng câu hỏi cụ thể.
2. **Giai đoạn 2 (`Known Unknowns` → `Known Knowns`):**
   * Đưa ra quyết định nghiệp vụ, thống nhất định nghĩa từ vựng, đóng băng spec và viết test cases tự động để bảo vệ.

---

## 3. Bộ Skill & Cơ chế Kỹ thuật Trang bị cho Hệ thống Agent

Để triệt tiêu điểm mù, các Agent không được phép vận hành như những người "thực thi thụ động", mà phải được trang bị các cơ chế phòng vệ phản xạ:

| Bộ Skill / Cơ chế | Mục tiêu nhận thức | Hành động cụ thể của Agent |
|---|---|---|
| **1. Assumption & Bias Invalidator** *(Bóc tách giả định ngầm)* | `Unknown Unknowns` → `Known Unknowns` | Bắt buộc phân loại mọi thông tin đầu vào thành: `[VERIFIED_FACT]`, `[ASSUMPTION_NEEDS_CONFIRMATION]`, hoặc `[UNRESOLVED_GAP]`. Cấm suy diễn tự động khi gặp dữ liệu thiếu. |
| **2. Semantic Disambiguator** *(Chuẩn hóa ngữ nghĩa / Glossary Guard)* | Triệt tiêu Semantic Drift | Mọi danh từ nghiệp vụ phải được tra cứu đối chiếu trong `context/glossary.md`. Nếu phát hiện từ đa nghĩa, Agent bắt buộc phải dừng lại yêu cầu định nghĩa tường minh. |
| **3. Intent Mirroring & Back-Translation** *(Kỹ thuật soi gương nhận thức)* | Khử Confirmation Bias | Trước khi thực hiện, Agent phải tóm tắt ngược lại: *"Theo tôi hiểu, mục tiêu là A, phạm vi KHÔNG BAO GỒM B, điều kiện biên C sẽ gây lỗi nếu xử lý theo cách D. Có đúng ý bạn không?"* |
| **4. Adversarial Red-Teaming** *(Phản biện độc lập / Chống tin tưởng mù)* | Chống Sycophancy giữa các Agent | Agent tuyến sau **không mặc định tin** Agent tuyến trước: Architect phải chất vấn Analyst; Developer phải rà soát lỗ hổng logic của Architect; QA phải giả định code của Dev luôn có lỗi. |
| **5. Cross-Artifact Audit** *(Kiểm toán chéo tự động)* | `Known Unknowns` → `Known Knowns` | Dùng quy tắc đối soát ma trận: Mỗi Acceptance Criteria (AC) phải có Task tương ứng, mỗi Entity phải có Schema, mỗi Endpoint phải có kịch bản kiểm thử. |

---

## 4. Ma trận Trách nhiệm & Quy tắc Thực chiến cho từng Role

### A. Đối với Người Chủ quản (Human Approver)
* **Không phê duyệt chỉ dựa trên cảm tính:** Khi đọc tài liệu Agent trình duyệt, không chỉ đọc phần "sẽ làm gì", mà bắt buộc đọc phần:
  1. *Danh sách giả định (Assumptions).*
  2. *Những gì KHÔNG thuộc phạm vi (Out of Scope).*
  3. *Các trường hợp biên nguy hiểm (Risky Edge Cases).*
* **Yêu cầu phản chiếu:** Nếu thấy Agent trả lời quá nhanh và quá hoàn hảo, hãy yêu cầu: *"Hãy nêu ra 3 lý do tại sao phương án này có thể thất bại trong môi trường thực tế"*.

### B. Đối với Analyst (S1 - Intake & S2 - Spec)
* **Quy tắc Vàng:** *Không ghi chép đơn thuần; phải vạch lá tìm sâu.*
* Thực thi skill bóc tách giả định: Liệt kê tối thiểu các trường hợp biên về phân quyền, trạng thái đồng thời, mất mạng/timeout, và toàn vẹn dữ liệu.
* Cập nhật `context/glossary.md` ngay khi xuất hiện khái niệm nghiệp vụ mới.

### C. Đối với Architect (S3 - Technical Design)
* **Quy tắc Vàng:** *Không tin tưởng mù quáng vào spec của Analyst.*
* Rà soát Gap Analysis: Chỉ ra các điểm Analyst chưa tính đến về mặt kỹ thuật (race condition, memory, idempotency, rate limit).
* Đóng băng hợp đồng bằng `openapi.yaml`, schema DB và Architecture Decision Records (ADRs).

### D. Đối với Developer (S4 - Build)
* **Quy tắc Vàng:** *Code là hiện thân cuối cùng của sự hiểu biết; không code dựa trên phỏng đoán.*
* Áp dụng nguyên tắc Contract-First: Chỉ code dựa trên các tiêu chí AC đã được đánh số định danh (`AC-*`).
* Nếu phát hiện tài liệu thiết kế có điểm vô lý hoặc thiếu sót khi viết code, lập tức dừng lại, giơ cờ cảnh báo (*raise impediment*), không tự ý "sửa lén" logic.

### E. Đối với QA (S5 - Quality Assurance)
* **Quy tắc Vàng:** *QA là tuyến phòng thủ điểm mù cuối cùng trước khi bàn giao.*
* Không chỉ test Happy Path; tập trung thiết kế các kịch bản phá hoại (*destructive testing*), mutation testing, và kiểm tra tính toàn vẹn của dữ liệu ở trạng thái lỗi.
* Đối chiếu độc lập: Đọc song song cả Spec (S2), Thiết kế (S3) và Code thực tế (S4) để tìm ra độ lệch giữa ba bên.

---

> [!IMPORTANT]
> **Khẩu hiệu cốt lõi:**
> *"Sự ngầm hiểu là kẻ thù lớn nhất của chất lượng phần mềm. Nghi ngờ có phương pháp và minh bạch hóa mọi giả định là con đường duy nhất để loại bỏ điểm mù."*
