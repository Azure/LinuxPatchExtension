# RCA Report - Bug #28537460

## Summary

Linux auto-assessment can remain in progress when an assessment runs for more
than systemd's default 90-second start timeout. The generated systemd unit
declares a daemonizing service even though its shell wrapper keeps the Python
assessment in the foreground.

## Evidence Collected

- **Bug metadata**: Bug 28537460 is a high-severity recurring Linux guest
  patching issue. The deterministic reproduction records
  `MsftLinuxPatchAutoAssess.service` timing out and receiving SIGTERM after
  approximately 90 seconds.
- **Historical patterns**: Bug 24467908 and PR 203 changed this unit from
  `Type=notify` to `Type=forking`. Bug 30347555 and PR 286 fixed a separate
  unbounded YUM retry path with the same portal symptom. Bug 33342595 reports
  the same systemd timeout signature at fleet scale.
- **Source code findings**:
  `ServiceManager.create_and_set_service_idem()` creates only the
  `MsftLinuxPatchAutoAssess` unit and defaults it to `Type=forking`.
  `ProcessHandler.stage_auto_assess_sh_safely()` generates a shell script that
  invokes `MsftLinuxPatchCore.py` synchronously, without daemonizing or
  backgrounding it. Auto-assessment execution is allowed to take up to one hour
  by `Constants.AUTO_ASSESSMENT_MAXIMUM_DURATION`.

## Root Cause

`Type=forking` tells systemd that the process started by `ExecStart` will fork
and that its parent will exit after initialization. The generated
`MsftLinuxPatchAutoAssess.sh` wrapper does neither: bash executes the Python
assessment as a foreground command and remains tied to that operation.

systemd therefore keeps the unit in its starting state. If assessment work,
such as package metadata refresh, takes longer than the default
`TimeoutStartSec=90s`, systemd treats startup as failed and terminates the
service cgroup. That interruption occurs before Core writes terminal assessment
status, leaving the control plane with a stale in-progress state.

## Competing Hypotheses

1. **The package manager is stuck indefinitely**: Historical Bug 30347555
   demonstrated an unbounded YUM mitigation loop, but PR 286 added repeated
   error detection and a retry ceiling. Package-manager latency can expose the
   90-second service timeout, but normal slow work should not cause systemd to
   kill an assessment whose configured operation window is one hour.
2. **PR 299 caused the timeout through service-file permissions**: The timing
   correlates with increased reports, but PR 299 changed generated file modes
   rather than service lifecycle or timeout directives. A readable, non-
   executable unit file is valid systemd configuration, so this does not
   explain the exact start-timeout behavior.
3. **The systemd lifecycle contract is incorrect**: The source directly shows
   a foreground wrapper paired with `Type=forking`, and the deterministic
   timeout matches systemd's default start deadline. This is the selected root
   cause.

## Selected Fix

Change the generated service's default type from `forking` to `simple`.
`Type=simple` considers the service started after launching the foreground
process, so the 90-second startup deadline no longer terminates valid long-
running assessment work. The process remains tracked by systemd for stop and
failure handling.

No 30-minute `RuntimeMaxSec` is added. The repository explicitly permits
auto-assessment to take up to one hour, and older supported systemd versions
do not consistently support that directive. Existing operation-level duration
and package-manager retry controls remain the appropriate runtime safeguards.
