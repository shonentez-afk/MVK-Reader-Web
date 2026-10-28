# Stage 70 — MVKView configuration edit commits locally

Checked original IDR `_Unit128.pas` and `_Unit115.pas`: 10/10 instruction anchors.

`Tmvkform.tabConfigAlarmsDblClick` at 0x00849038 opens the editor and assigns CellList/CellIndex. `Tmvkeditform.FormShow` uses `TMvkAdvancedCell.GetIndexByID` at 0x008407CC to highlight the existing selection. `Tmvkeditform.bOkClick` at 0x00840318 reads selected ListBox index, resolves actual physical parameter ID by `TMvkAdvancedCell.GetID` at 0x008403C1, then calls `TMvkCellList.InputValue` at 0x008403D3. The latter, at 0x007CFA2C, checks protection and advanced cell type (0x0A), then at 0x007CFAC4 writes DWORD directly to `CellList.Data + 2*register_offset`. There is no network call in InputValue. Separate button handler `bConfigUploadClick` starts at 0x0084A5A8; **local edit != uploading configuration**. Upload transport not analyzed; no command sent to device.

Full local archive: `MVKVIEW_STAGE70_EDIT_COMMIT_20261028.zip`, with Russian report and static verification script. Next Stage71: statically trace bConfigUploadClick and command creation. Stable v0.3.40 untouched.