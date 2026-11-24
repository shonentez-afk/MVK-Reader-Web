# Atlas v18 — receiver, register memory and PARAM ordering

24.11.2026. Pinned production revision Stage111Z31EB: `dd020c4a8c1cd9d80440031730b7c4ee28bf8cef`. Documentation-only analysis; no production code, protocol, main or device operation changed. This public summary omits private original instruction addresses, register-family CSV and original reconstructed source.

## Candidate review

All original v15 641 entries and v16/v17 materials retained. Local v18 adds a focused review of 222 original candidate IDs (117 Data, 43 Storage, 62 Thread). The private source package, IDP SHA and SQLite were checked again, including 133/133 reconstructed source checksums.

| 117 Data candidates | Count |
|---|---:|
| Receiver route established statically, guarded | 40 |
| Local rebinding followed by text read | 1 |
| Initial nil overwritten on normal construction path | 9 |
| Advanced descriptor condition open | 7 |
| Receiver route not resolved | 60 |
| Total | 117 |

49 named call-sites examined. Eleven factory families produce 71 CellList objects; their pointer bindings and shared register contents are distinct layers of evidence. Direct routes, generic methods and dynamic receivers must not be conflated. No unresolved route is automatically excluded. Prior v17 decisions remain in the historical catalog; the new layer is not a replacement statistic. Storage and Thread rows are classified by lifecycle/epoch guards, allocation, Freeze and writer/Task contracts, not claimed as proven runtime def-use. Eight additional evidence cards.

## Concrete public Stage111 order question

On the pinned revision:

- [monitor.go](https://github.com/shonentez-afk/MVK-Reader-Web/blob/dd020c4a8c1cd9d80440031730b7c4ee28bf8cef/tools/research/native_tcp10230_stage108_live_recording_r6_1/source/monitor.go#L530-L554): updates all blocks of the PARAM frame before invoking the live VALUES writer.
- [source_live_values.go](https://github.com/shonentez-afk/MVK-Reader-Web/blob/dd020c4a8c1cd9d80440031730b7c4ee28bf8cef/tools/research/native_tcp10230_stage108_live_recording_r6_1/source/source_live_values.go#L216-L232): onParam finds the trigger, rejects duplicate triggers, invokes ordered raw tick.
- [source_live_page_status_banks.go](https://github.com/shonentez-afk/MVK-Reader-Web/blob/dd020c4a8c1cd9d80440031730b7c4ee28bf8cef/tools/research/native_tcp10230_stage108_live_recording_r6_1/source/source_live_page_status_banks.go#L43-L50): sourceLiveRawDWORD reads the current image. Thus ordering of the image itself matters, independently of output column ordering.

The private source-derived model evaluates the trigger after its own block's update, rather than after all subsequent blocks. There is a conditional discrepancy in row content when a later block of the same frame changes a selected register. The real device frame sequences, duplicate-trigger grammar and effects of inter-thread timing are not yet attested.

Eight deterministic synthetic model checks passed. Three demonstrated model differences: update after trigger, updates on both sides of trigger, and multiple triggers. These are model tests, **not execution of either original Win32 or production Go**. Final images can agree while captured row values differ.

Next working-branch test package (verify current HEAD before changing anything):
1. Seed a selected SPEC value with 1, then trigger followed by update to 2 within one accepted PARAM. Compare trigger-prefix row and final image independently.
2. Check update-before-trigger and both-sides ordering; preserve normal one-block behavior and latched masks.
3. Verify Freeze/inactive writer paths, duplicate-trigger grammar and acceptance independently, TACH freshness bounded by trigger prefix. Do not blindly enable multiple triggers without evidence of valid frame grammar.
4. Check Stop/writer finalization, session/epoch and partial-input behavior. Do not change production in the architecture PR.

## Artifacts and limitations

Private archive `MVK_ALIAS_V18_PRIVATE_HANDOFF.zip` contains v17 (including original v15 CSV and v16 material) plus the v18 HTML, 222-row overlay, family table, evidence JSON, audit, build and QA scripts, handoff. 34 structural and Chromium checks passed, no JS errors (page.set_content; file:// not tested). No private files were uploaded to GitHub. Actual hardware/Win32 SAME-RX, dynamic VMT, Advanced descriptor cases and unresolved receiver routes remain open.

See [v17](STAGE111_ALIAS_ORDER_REVIEW_V17_RU.md) and [handoff](ANALYSIS_HANDOFF_RU.md).
