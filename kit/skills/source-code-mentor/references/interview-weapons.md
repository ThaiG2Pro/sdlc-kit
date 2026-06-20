# Biến Kiến Thức thành Vũ Khí Phỏng Vấn

## Mục tiêu sau 3-6 tháng intern

### Năng lực kỹ thuật
- Nhận task backend nhỏ → trung bình
- Fix bug production-level
- Viết code theo chuẩn team mà ít bị sửa trong code review
- Hiểu flow từ API → DB, biết mỗi layer làm gì

### Năng lực tư duy
- Biết hỏi "tại sao" trước khi code
- Biết trade-off của mỗi quyết định kỹ thuật
- Biết đọc code người khác và học pattern

---

## Cách diễn đạt khi phỏng vấn Junior-Middle

### ① Architecture
> "Ở công ty em, team tách business logic khỏi controller để dễ test và maintain.
> Controller chỉ làm 3 việc: nhận request, validate input qua DTO, gọi service.
> Nếu cần reuse logic (ví dụ từ background job), chỉ cần gọi service — không duplicate code."

### ② Code Quality
> "Team em có convention rõ ràng: kebab-case cho file, PascalCase cho class,
> commit message theo conventional commits. Em học được rằng code tốt là code
> người khác dám sửa — không phải code chạy được là xong."

### ③ Business Logic
> "Business rule phức tạp nhất em từng xử lý là [ví dụ cụ thể từ project].
> Em học được cách validate ở nhiều layer: DTO validate format, service validate
> business rules. Ví dụ không cho xóa product khi đang có order liên quan."

### ④ Error Handling
> "Em chú ý phân biệt lỗi nghiệp vụ và lỗi hệ thống, trả về error code phù hợp.
> Ví dụ duplicate email là 409 Conflict, thiếu field là 400 Bad Request.
> Team em dùng structured logging với request_id để trace lỗi trong production."

### ⑤ Database
> "Em học được cách team handle database: dùng migration cho mọi schema change,
> đặt index cho frequent queries, dùng soft delete thay vì xóa thật.
> Em biết tránh N+1 query bằng cách dùng JOIN hoặc eager loading."

### ⑥ Process
> "Em quen làm việc theo quy trình: nhận ticket → đọc spec → code → viết test →
> tạo PR → review → merge. Commit message theo format conventional commits
> để team dễ track changes."

---

## Template tổng kết cho intern

Sau khi trace xong vài module, giúp intern điền template này:

```markdown
# Những gì tôi học được từ source code Giftport

## Kiến trúc
- Project dùng kiến trúc: [monolith/microservice], framework: [NestJS]
- Cách chia module: [domain-driven, mỗi domain 1 module]
- Layer pattern: [Controller → Service → Repository → Entity]

## Business Logic hay nhất tôi gặp
1. [Mô tả rule 1 — ví dụ: state machine cho order status]
2. [Mô tả rule 2 — ví dụ: validation không cho xóa khi có relation]
3. [Mô tả rule 3 — ví dụ: soft delete + audit trail]

## Pattern tôi sẽ áp dụng
- Validation: [DTO ở boundary, business rules ở service]
- Error handling: [custom error codes, structured response]
- Database: [migration, index strategy, soft delete]
- Testing: [unit test mock deps, integration test real DB]

## Điểm mạnh của tôi
- [Liệt kê 2-3 điểm mạnh đã phát triển]

## Điểm cần cải thiện
- [Liệt kê 2-3 điểm cần học thêm]
```

---

## Gợi ý cho mentor khi intern muốn tổng kết

1. Hỏi intern: "Em thấy pattern nào lặp lại nhiều nhất qua các module?"
2. Hỏi: "Nếu em bắt đầu 1 module mới từ đầu, em sẽ setup thế nào?"
3. Hỏi: "Business rule nào em thấy hay nhất? Tại sao?"
4. Giúp intern diễn đạt lại bằng ngôn ngữ phỏng vấn — ngắn gọn, tự tin, có ví dụ cụ thể
5. Chỉ ra: "Em đã học được X, Y, Z — đây là những thứ nhiều junior không có"
