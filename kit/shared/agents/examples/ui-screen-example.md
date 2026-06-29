# UI — Cart voucher input

<!--
  Format sample for one `ui/<screen>.md` inside a ticket package
  (docs/extra-docs/<ticket_id>-<slug>/ui/cart-voucher.md), written by the INTAKE agent.
  It is the DEVELOPER's frontend build target at S4 and feeds the analyst's S1/S2 ACs.
  Transcribe what the design shows — do not design anew. Tag guesses [INFERRED].
  Reference domain (voucher/commerce) is illustrative — reuse the STRUCTURE.
-->

## §Screen

- **Name:** Cart — voucher input
- **Purpose:** Let the user enter and submit a voucher code from the cart.
- **Route/entry:** `/cart` (voucher block sits below the line items). [INFERRED — route not in ticket]

## §Reference

- **Image:** `../figma/cart-voucher.png`
- **Figma:** https://figma.com/design/abc123/Cart?node-id=10-2

## §Layout (top → bottom)

1. Cart line items (existing, out of scope).
2. **Voucher block** — label "Mã giảm giá", text input, "Áp dụng" button (right of input).
3. Inline message slot (below input — error or success).
4. Order summary (subtotal, discount line, total).

## §Components

| Element | Type | Label | States |
|---------|------|-------|--------|
| Voucher input | text field | placeholder "Nhập mã" | default, focus, disabled (while loading), error (red border + message) |
| Apply button | primary button | "Áp dụng" | default, hover, disabled (empty input), loading (spinner) |
| Inline message | text | — | hidden, error (red), success (green) |

## §Data & fields

- **code** — string, 4–20 chars, alphanumeric. Trimmed. [INFERRED] case-insensitive (uppercased in design).
- Submit is disabled until `code` is non-empty.

## §Interactions

- Click **Áp dụng** (or Enter) → button → loading; call apply-voucher.
- **Success** → input clears, success message "Đã áp dụng — giảm {amount}", summary shows discount line, navigate to the *applied* state (`ui/cart-voucher-applied.md`).
- **Error** (invalid/expired) → inline error under input, total unchanged, input keeps the value for retry.
- Network failure → generic error "Thử lại sau"; total unchanged.

## §Open questions

- [INFERRED] Pressing Enter submits — confirm.
- Error copy for "expired" vs "invalid" — same message in design; PO to confirm if they differ.
