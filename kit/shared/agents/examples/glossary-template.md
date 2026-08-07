<!--
  Template for {CHANGE_DIR}/_glossary.md — the shared domain/technical glossary every agent adds
  to. These definitions are the canonical truth across all phases. cpp-guard checks this is a
  markdown table with >=1 data row (S2) and >=1 row whose Phase is S3 (S3), and warns once the
  file passes 6 KB or a definition passes 220 chars. IMPORTANT: keep "Phase" as the LAST column —
  cpp-guard reads the trailing cell as the phase.
-->

# Glossary — {change-name} (ticket {ticket_id})

| Term | Definition | Defined by | AC/BR ref | Phase |
|------|-----------|-----------|-----------|-------|
| {Domain term} | {exact, agreed definition — reused verbatim downstream} | analyst | AC-{ticket}-001 | S2 |
| {Business rule name} | {definition} | analyst | BR-{ticket}-001 | S2 |
| {Architecture pattern / service / lock strategy} | {definition} | architect | ADR-001 | S3 |

<!--
  A row earns its place only if the next phase CANNOT read the term off the spec/design — a word
  used in a non-obvious sense, or used inconsistently. Definition: ONE line, <=220 chars. If it
  needs a paragraph it is a design note; put it in design.md.

  When a term's meaning changes, EDIT ITS ROW IN PLACE. Do not add a second row and mark the old
  one [SUPERSEDED]/[HISTORICAL] — this file is re-read in full on every spawn for the rest of the
  change, so a term carrying both its dead and live meaning is paid for over and over. Git has the
  old wording. Delete a row only when the term leaves the spec entirely.

  - Defined by: analyst | architect | developer | qa
  - AC/BR ref: the AC/BR/ADR id this term anchors to, or "—" if none
  - Phase (LAST column, required): S1 | S2 | S3 | S4 | S5 | S6
-->
