# Intake — apply-voucher (Redmine #12345)

<!--
  This is a format sample for the INTAKE agent's `intake.md` — the analyst's primary S1 input.
  It is the index of one ticket package:

    docs/extra-docs/12345-apply-voucher/
      intake.md              ← THIS file (6 sections, all required)
      figma-urls.txt         ← one Figma URL per line
      figma/                 ← exported screens (referenced from §4 + each ui/*.md)
      attachments/           ← downloaded Redmine files
      ui/                    ← one <screen>.md per UI screen (see ui-screen-example.md)
        cart-voucher.md
        cart-voucher-applied.md

  Transcribe; never invent. Tag interpretations [INFERRED]; record every gap as MISSING — <reason>.
  The reference domain (voucher/commerce) is illustrative — reuse the STRUCTURE, not the content.
-->

## §1 Ticket

| Field | Value |
|-------|-------|
| Subject | Apply voucher code at cart |
| Type | Feature |
| Status | In Progress |
| Priority | Normal |
| Assignee | — |
| Redmine | https://redmine.example.com/issues/12345 |

## §2 Description

> *(verbatim from Redmine)*
> "Khách hàng nhập mã voucher ở màn giỏ hàng. Nếu hợp lệ thì áp dụng giảm giá và hiển thị số tiền
> được giảm; nếu sai/hết hạn thì báo lỗi ngay dưới ô nhập."

**[INFERRED] restatement:** At the cart screen the user enters a voucher code; a valid code applies a
discount and shows the discount amount; an invalid/expired code shows an inline error under the input.

## §3 Acceptance / notes

- Valid code → discount applied, cart total updates, discount line shown.
- Invalid or expired code → inline error, total unchanged.
- One voucher per cart (from journal comment #3).
- [INFERRED] Code is case-insensitive — design shows uppercase but not stated. → §6.

## §4 UI / Figma

| Screen | Purpose | Figma image | ui/ spec | States |
|--------|---------|-------------|----------|--------|
| Cart — voucher input | Enter + submit code | `figma/cart-voucher.png` | `ui/cart-voucher.md` | default, focus, error, loading |
| Cart — voucher applied | Show discount + remove | `figma/cart-voucher-applied.png` | `ui/cart-voucher-applied.md` | applied, removing |

Figma URLs (also in `figma-urls.txt`):
- https://figma.com/design/abc123/Cart?node-id=10-2

## §5 Attachments & docs

| File | What it is |
|------|-----------|
| `attachments/voucher-rules.pdf` | Business rules for voucher validity/stacking |
| `figma/cart-voucher.png` | Exported cart screen with the voucher input |

## §6 Open questions / gaps

- **[INFERRED]** Code case-insensitivity — confirm with PO.
- **MISSING — figma not reachable** for the error-toast variant; asked user to paste the frame.
- Max discount cap? Not in ticket or rules PDF.
