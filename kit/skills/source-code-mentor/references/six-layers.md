# 6 Lớp Năng Lực — Chi tiết & Câu hỏi Socratic

Khi intern hỏi về bất kỳ module/luồng nào, hướng dẫn họ khám phá qua 6 lớp này.
Không cần đi hết 6 lớp trong 1 session — chọn lớp phù hợp với câu hỏi của intern.

---

## ① Architecture Mindset — Cách tổ chức hệ thống

### Intern cần trả lời được:
- Tại sao project chia module như vậy? Boundary ở đâu?
- Controller làm gì, KHÔNG làm gì?
- Service có business rule thật hay chỉ gọi repo?
- Domain logic nằm đâu?

### Câu hỏi Socratic:
- "Nhìn vào controller này, em thấy nó có chứa logic nghiệp vụ không? Tại sao?"
- "Nếu em cần thêm 1 rule mới, em sẽ đặt ở đâu? Vì sao?"
- "Module này có gọi sang module khác không? Nếu có, tại sao lại cần?"
- "Nếu 2 module cùng cần 1 logic, em sẽ đặt ở đâu? shared/ hay tạo module mới?"
- "Controller này có inject bao nhiêu service? Nhiều quá có vấn đề gì không?"

### Pattern cần chỉ ra trong Giftport:
- Thin controller: controller chỉ nhận request → validate → gọi service → trả response
- Service owns business logic: mọi rule nghiệp vụ nằm trong service
- Repository encapsulates DB: service không viết raw query
- Module boundary: mỗi domain (order, product, campaign...) là 1 module độc lập

### Khi phỏng vấn, intern nói được:
> "Ở công ty cũ, bọn em tách business logic khỏi controller để dễ test và maintain.
> Controller chỉ làm 3 việc: nhận request, validate input qua DTO, gọi service."

---

## ② Professionalism — Chuẩn code & kỷ luật team

### Intern cần quan sát:
- Naming convention: biến, function, class, file
- File dài bao nhiêu là chấp nhận được?
- Comment ở đâu, viết gì?
- Code có đọc lại sau 6 tháng vẫn hiểu không?

### Câu hỏi Socratic:
- "Nhìn tên function này, em có hiểu nó làm gì mà không cần đọc body không?"
- "File này dài X dòng — em thấy có nên tách không? Tách theo tiêu chí gì?"
- "Nếu em là người mới join team, đọc file này em có hiểu flow không?"
- "Tên biến `data` hay `result` — em thấy có vấn đề gì không?"
- "File này có comment không? Tại sao có (hoặc không có)?"

### Pattern cần chỉ ra trong Giftport:
- kebab-case cho file names: `order-api.service.ts`
- PascalCase cho class: `OrderService`, `CreateOrderDto`
- camelCase cho function/variable: `calculateTotal`, `orderItems`
- UPPER_SNAKE_CASE cho constants/enums: `ORDER_STATUS`, `MAX_RETRY`
- Mỗi file 1 class/component chính
- Tên file = tên class (lowercase + kebab)

### Insight quan trọng:
> 📌 Junior xịn ≠ code chạy được
> 📌 Junior xịn = code người khác dám sửa
> "Code cho người khác đọc, không phải cho compiler"

---

## ③ Business Logic — Thứ trường ĐH không dạy (💎 vàng)

### Intern cần khám phá:
- Validation nằm ở đâu? Tại sao ở đó?
- Rule phức tạp xử lý kiểu gì?
- Edge case được handle ra sao?
- State machine, soft delete, audit log

### Câu hỏi Socratic:
- "Validation này nằm ở DTO, không phải service — em nghĩ tại sao?"
- "Nếu user gửi quantity = 0, chuyện gì xảy ra? Code handle chưa?"
- "Tại sao dùng soft delete thay vì xóa thật? Trade-off là gì?"
- "Order có status PENDING → CONFIRMED → SHIPPED. Nếu ai đó cố chuyển từ SHIPPED về PENDING thì sao?"
- "Tại sao không cho xóa product khi đang có order liên quan?"
- "Audit log ghi lại gì? Ai cần đọc nó? Tại sao quan trọng?"

### Pattern cần chỉ ra trong Giftport:
- DTO validation ở boundary (controller level) — fail fast, không để lọt vào service
- Service validation cho business rules — kiểm tra quan hệ giữa entities
- State machine qua enum: `OrderStatus`, `SubOrderStatus`
- Soft delete qua `deleted_at` column — không mất data, có thể audit
- Audit trail cho mọi thay đổi quan trọng

### Đây chính là thứ giúp intern lên middle:
> Business logic thật = thứ trường ĐH không dạy.
> Intern nào nắm được cách team xử lý edge case, state machine, validation layers
> → đã vượt xa phần lớn junior khác.

---

## ④ Error Handling & Reliability

### Intern cần xem kỹ:
- Error handling có thống nhất không?
- Custom exception hay dùng built-in?
- Log level nào, log cái gì?
- Lỗi cho dev hay cho user?

### Câu hỏi Socratic:
- "Exception này throw ở service — ai sẽ catch? User thấy gì?"
- "Log dòng này ghi gì? Nếu production lỗi, thông tin này đủ debug không?"
- "Lỗi nghiệp vụ vs lỗi hệ thống — code phân biệt thế nào?"
- "HTTP 400 vs 422 vs 409 — khi nào dùng cái nào?"
- "Nếu database timeout, user thấy gì? Code handle chưa?"
- "Error response có format thống nhất không? `{ errors: [...] }` hay mỗi chỗ 1 kiểu?"

### Pattern cần chỉ ra trong Giftport:
- Custom error codes per domain: `OrderErrorCode`, `ProductErrorCode`
- Structured error response: `{ errors: [{ code, message, field }], meta }`
- JSON structured logging với `request_id` — trace được request nào gây lỗi
- Phân biệt: validation error (400) vs business rule violation (409/422) vs server error (500)
- KHÔNG log password, token, PII

### Khi phỏng vấn:
> "Em chú ý phân biệt lỗi nghiệp vụ và lỗi hệ thống, trả về error code phù hợp.
> Ví dụ duplicate email là 409 Conflict, thiếu field là 400 Bad Request."

---

## ⑤ Database Patterns

### Intern cần quan sát:
- Query viết ở đâu? Repository hay service?
- Có tránh N+1 query không?
- Index dùng thế nào?
- Migration / versioning DB ra sao?

### Câu hỏi Socratic:
- "Query này dùng JOIN hay query riêng rồi merge? Tại sao chọn cách đó?"
- "Nếu table này có 1 triệu record, query này có chậm không? Cần index gì?"
- "Migration này có `down()` không? Tại sao cần?"
- "Tại sao dùng UUID thay vì auto-increment ID?"
- "Column `created_at`, `updated_at`, `deleted_at` — tại sao mọi table đều có?"
- "Index `idx_orders_status_created_at` — tại sao index 2 column cùng lúc?"

### Pattern cần chỉ ra trong Giftport:
- Repository pattern: mọi query nằm trong `*.repository.ts`, service không viết raw SQL
- TypeORM entities với base fields: `id` (UUID), `created_at`, `updated_at`, `deleted_at`
- Migration files: timestamp prefix, có cả `up()` và `down()`
- Naming: `snake_case` cho tables/columns, `idx_{table}_{columns}` cho indexes
- Composite indexes cho frequent query patterns

### Đây là điểm nhiều junior yếu:
> Rất nhiều junior chỉ biết viết query chạy được, không biết query có scale không.
> Học từ code công ty: cách đặt index, cách tránh N+1, cách viết migration an toàn
> → vượt lên phần lớn junior khác.

---

## ⑥ Process & Product Thinking

### Intern cần học:
- Code gắn với ticket thế nào?
- Commit message nói lên điều gì?
- PR được review kỹ ra sao?

### Câu hỏi Socratic:
- "Commit message này theo format gì? Em đọc được gì từ nó?"
- "Nếu em review PR này, em sẽ hỏi gì?"
- "Tại sao commit message có `Refs: GIFT-123`? Nó giúp gì?"
- "File test nằm cạnh file code — em thấy tiện hay bất tiện? Tại sao?"
- "Nếu em nhận task 'thêm field mới vào product', em sẽ làm theo thứ tự nào?"

### Pattern cần chỉ ra trong Giftport:
- Conventional commits: `feat(product): add brand management API`
- Commit gắn ticket: `Refs: GIFT-123`
- Test file cạnh source: `order.service.ts` → `order.service.spec.ts`
- Migration đi kèm feature — không deploy code trước DB change

### Insight quan trọng:
> Bạn đang học: "Làm phần mềm cho doanh nghiệp, không phải làm bài tập."
> Code không tồn tại một mình — nó gắn với ticket, review, deploy, monitor.
