# Hướng dẫn Trace Code — Không bị ngộp

## Sai lầm thường gặp của intern

❌ Đọc từ file đầu → file cuối
❌ Cố hiểu 100% mọi dòng code
❌ Đọc mà không có câu hỏi trong đầu

Kết quả: ngộp, chán, không nhớ gì.

---

## 4 Bước Trace Code đúng cách

### Bước 1: Chọn 1 luồng nghiệp vụ cụ thể

Không đọc cả module — chọn 1 flow duy nhất:

**Luồng dễ (bắt đầu từ đây):**
- CRUD product (create/read/update/delete)
- Get list with pagination
- Get detail by ID

**Luồng trung bình:**
- Create order (có validation, tính toán)
- Update inventory (có check constraint)
- Campaign management (có state machine)

**Luồng nâng cao:**
- Order → SubOrder → Delivery flow
- Webhook integration
- Cross-module operations

Gợi ý cho intern: "Em chọn 1 luồng mà em hay dùng khi test API — trace luồng đó trước."

### Bước 2: Trace theo luồng

```
API endpoint → Controller → Service → Repository → DB
```

Ở mỗi layer, chỉ cần hiểu **layer này chịu trách nhiệm gì**:

| Layer | Trách nhiệm | File pattern |
|-------|-------------|-------------|
| Controller | Nhận request, validate input (DTO), gọi service, trả response | `{domain}.controller.ts` |
| Service | Business logic, orchestration, gọi repo | `{domain}.service.ts` |
| Repository | Database access, query logic | `{domain}.repository.ts` |
| Entity | Data model, column definitions, relations | `entities/{name}.entity.ts` |
| DTO | Input validation rules | `dto/{action}-{domain}.dto.ts` |
| Enum | Domain constants, status values | `enums/{name}.enum.ts` |

**Cách trace trong Giftport:**
1. Tìm endpoint trong controller: `@Post()`, `@Get(':id')`, etc.
2. Xem controller gọi service method nào
3. Đọc service method đó — đây là nơi có business logic
4. Xem service gọi repository method nào
5. Đọc entity để hiểu data model

Không cần nhớ từng dòng — chỉ cần hiểu flow.

### Bước 3: Tự hỏi "TẠI SAO?"

Đây là bước quan trọng nhất. Với mỗi quyết định trong code, hỏi:

**Về architecture:**
- Tại sao validate ở DTO thay vì service?
- Tại sao tách service thành 2 file (service + api-service)?
- Tại sao module này import module khác?

**Về business logic:**
- Tại sao không cho update field này?
- Tại sao check condition này trước khi save?
- Tại sao dùng transaction ở đây?

**Về database:**
- Tại sao column này nullable?
- Tại sao có index trên column này?
- Tại sao dùng soft delete?

> 💡 Câu hỏi "tại sao" = kinh nghiệm của senior.
> Senior không giỏi hơn junior vì biết nhiều syntax hơn —
> mà vì đã gặp đủ vấn đề để biết "tại sao nên làm thế này".

### Bước 4: Ghi lại "Pattern của team"

Sau khi trace xong 1 luồng, tổng kết lại:

**Template ghi chú:**
```markdown
## Pattern Notes: [Tên luồng]

### Flow
[Mô tả ngắn flow từ API → DB]

### Patterns tôi học được
- Controller pattern: [mô tả]
- Service pattern: [mô tả]
- Validation pattern: [mô tả]
- Error handling pattern: [mô tả]

### Câu hỏi còn lại
- [Những gì chưa hiểu, cần hỏi senior]

### Có thể nói khi phỏng vấn
- [Cách diễn đạt kinh nghiệm này]
```

> Intern đang **copy mindset**, không phải copy code.
> Sau 5-10 luồng, em sẽ thấy pattern lặp lại — đó chính là "cách team làm việc".

---

## Thứ tự gợi ý cho intern mới

Nếu intern không biết bắt đầu từ đâu, gợi ý theo thứ tự:

1. **Product module** — CRUD đơn giản, dễ hiểu flow
2. **Supplier module** — tương tự product nhưng có thêm relations
3. **Inventory module** — bắt đầu có business rules (stock check)
4. **Campaign module** — có state machine, validation phức tạp
5. **Order module** — flow phức tạp nhất, nhiều sub-entities

Mỗi module trace 1-2 luồng là đủ. Không cần đọc hết.
