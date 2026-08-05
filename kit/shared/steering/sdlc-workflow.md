---
title: AI-Augmented SDLC Workflow
version: 2.4.0
scope: all-projects
inclusion: always
---

# AI-Augmented SDLC Workflow

🤖 AI owns the draft · 👤 Human owns the decision · 🔒 Spec locked before code · 🔴 Gate fail = STOP

## Input Sources (before S1)

Three combinable sources for the analyst's `proposal.md`:

| Source | Convention |
|---|---|
| **docs folder** | `docs/extra-docs/<ticket-id>-<slug>/` — BA attachments + intake package (Word/PDF/Figma exports, `intake.md`, `figma-urls.txt`). From the `intake` agent or dropped in by hand; no sub-structure required. |
| **Ticket tracker** | `sdlc feature <module> --ticket=1234` — AI fetches subject/description/attachments via the configured MCP. |
| **Direct chat** | No ticket, no docs — analyst asks the user. |

Folder rules: prefix with the ticket ID; kebab-case slug matching the eventual OpenSpec change name;
one folder per feature; **INPUT only** — S1 output lives in `openspec/changes/<change>/`, never `docs/`.

## Git isolation (R-SDLC-003)

**Mỗi pipeline mới PHẢI cô lập trên nhánh/worktree riêng — KHÔNG code trên nhánh protected
(`main`/`master`/…) hay nhánh của change cũ.** Orchestrator tự chạy bước này khi tạo change (mọi
type), điều khiển bởi `sdlc.config.json → git`; quy trình chi tiết ở `sdlc-orchestration-core`
§New Change Setup step 2. Naming mặc định `{type}/{ticket}-{slug}` (vd
`feature/71194-voucher-redeem`). Chỉ orchestrator được tạo nhánh/worktree; mọi git mutation khác bị
shell guard chặn — code chỉ do developer (S4) viết.

> ### 🔒 Bất biến: role là PLAYBOOK, không phải DANH TÍNH
> Nạp prompt của một role (orchestrator đọc `architect.md` để chạy S3 inline, hay tự xưng "tôi là
> architect") = mượn **checklist** của phase đó, KHÔNG phải trở thành actor có quyền của role đó.
> Quyền GHI do **host cấp danh tính**, không theo lời tự khai: Kiro lấy tên agent từ `argv[1]`; Claude
> lấy `agent_type` từ subagent do Task spawn (main session = không có). Mỗi danh tính có write-fence
> cố định — **chỉ `developer` có `src/**`**. Nên: mạo danh role chỉ-ghi-spec là vô hại (phase đó vốn
> không sinh code); mạo danh `developer` để ghi code thì guard tra danh tính THẬT, không thấy `src/**`
> trong fence → **chặn (exit 2)**. Mạo danh KHÔNG leo thang tới code. S4 là chỗ inline-driving cố tình
> "gãy": muốn ghi code phải là `developer` thật (Kiro `/agent swap → developer`; Claude: orchestrator
> **spawn** developer subagent).

## Lifecycle phases

| Phase | Role | Gate owner |
|---|---|---|
| S1 — Req Intake | Analyst | BA + Dev + QC |
| S2 — Func Spec | Analyst | BA + QC |
| 🔒 SPEC LOCK | Human | BA + Dev + QC |
| S3 — Design (sketch → full) | Architect | Dev + QC |
| S4 — Build | Developer | CI + Dev reviewer |
| S5 — QA | QA | QC Lead |
| S6 — Release | Developer | Dev + QC |

**Fast-track** (`bugfix`/`hotfix`: clear root cause, config/copy change, dependency bump, small
refactor with no behavior change) = **S4 → S5 (lite) → docs sync → merge**. Developer writes fix +
tests (coverage ≥ threshold); QA does retest + regression only. **Docs sync is MANDATORY**: API
behavior changed → `openapi.yaml`; business logic → spec deltas' AC; DB schema → `design.md`. Commit
docs separately (`docs(<scope>): <ticket-id> sync spec after fix`) from the fix
(`fix(<scope>): <ticket-id> <subject>`). ⚠ Scope grows mid-fix → escalate to the full flow.

## Spec zone (S1 ↔ S2)

Loop freely at cost 1× until the spec is 100% clear. No S3 without SPEC LOCK (BA + Dev + QC sign-off,
no "TBD"). S3 runs sketch first — gap found → back to S2/S1. After S2 the analyst runs a lightweight
risk scan (edge cases, missing error handling, security risks) into an `### Early Risk Flags` section;
Critical risks block SPEC LOCK. Catching risk here costs 1× instead of 25× at S5.

## Source of truth (R-SDLC-001)

**Immutable flow**: spec deltas → design (+ `openapi.yaml`) → code.

| Artifact | Owner | Rule |
|---|---|---|
| `proposal.md` + spec deltas | Analyst, S1/S2 | changes only via S1/S2 |
| `design.md` | Architect, S3 | changes only via S3 |
| `openapi.yaml` | Architect, S3 | never updated from code |
| Code | Developer, S4 | must follow design |

Never update `openapi.yaml`/`design.md` to "match" code — code diverging from design is a **gap**
(S4→S3, 5×). A requirement change after SPEC LOCK goes spec deltas → design → openapi → commit the
spec change → then implement.

## Cost escalation

| Loop | Cost | Signal |
|---|---|---|
| S1 ↔ S2 | 🟢 1× | expected, iterate freely |
| S3 sketch → S2 | 🟡 3× | sketch found a spec gap |
| S4 → S3 | 🟠 5× | design gap |
| S4 → S2 | 🟠 5–8× | S2 was weak |
| S5 → S4 | 🔴 15× | code bug — normal but expensive |
| S5 → S3 | 🔴 20× | S3 was weak |
| S5 → S2 | 💀 25× | S2 was very weak |
| S6 rollback | 💀 75× | S5 was weak |

## Gate checklists

- **SPEC LOCK** (R-SDLC-002, before S3) — 100% AC testable, no "TBD" · scope closed · BA+Dev+QC
  sign-off · Figma URL (or `Figma: N/A`) · Early Risk Flags reviewed, no unaddressed Critical.
- **S3** (before S4) — `design.md` complete · `openapi.yaml` committed if API (real YAML, not
  pseudo-code) · DB migrations documented · `tasks.md` with dependencies.
- **S4** (before merge) — CI green · PR approved · R-COV-001 coverage ≥ threshold · R-SEC-001 security
  scan PASS · R-SEC-003 input validation on new DTOs.
- **S5** (before release) — 0 Critical/High bugs open · all ACs verified.
- **S6** (before deploy) — migration reviewed · rollback plan documented · stable 30 min post-deploy.

QA tests, reports, classifies, does RCA, and calls GO/NO-GO — it never fixes code. Bug flow: S5 finds
bug → report → NO-GO → S4 fix → S5 retest → GO/NO-GO.
