# Stage111Z31EC: Mode2 status regression (candidate)

Base EC `e073d165852cddc2b82f90b518ae945658ee6c30`. Latest source-code revision is `26fa280233b98a9f77bbf64e195cc2c57da3445b`; the later EC commits are documentation. CI #45324239390: Linux Core and Go RX/export pass; Windows Core reports 8 failures, 2947 passed, 15 skipped. Native QPA reports 6 failures at each DPI; new autonomous EXE is skipped. The prior EB CI #45307882905 is the last verified Windows EXE baseline.

Root cause in OriginalMeasureControls.render: the new elapsed-caption loop reused the local variable that meant Mode2 selected. The last iteration overwrote it with the VALUES writer request. When the capture was not active and no VALUES writer existed, waiting/error status fell through to idle. Seven of the eight Windows core failures match this behavior. The remaining failure is an old exact caption assertion that does not include the new timer. The candidate uses separate mode2_requested and write_requested variables; the test now checks the full caption including its clock and provenance. It adds an actual Qt waiting/error regression with neither writer requested.

This branch changes no Go receiver, DSP, original writer flags, archive verification, command authorizations, or base production branch. All tests use synthetic/local data. PR #14 (VALUES trigger prefix) remains separate. The new workflow checks the full Windows core suite and the affected native Windows QPA paths at both scale factors. Results are pending until the actual CI receipt. It is not a new accepted numbered stage or an EXE release.

## Remaining comparison priorities

The original recovery atlas v32 is the reference, not an assertion of runtime parity. Review storage Range/Units initialization per TCP epoch and RX latch/VALUES reset separately from PARAM freshness; review reconnect writer close and FIFO semantics, and PageStatus source-register chart scaling. Do not enable instrument commands or copy suspected races from the original. User data and private original files remain local.
