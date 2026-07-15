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
  `Type=notify` to `Type=forking`. Bug 30347555 and PR 303 fixed a separate
  unbounded YUM retry path with the same portal symptom. Bug 33342595 reports
  the same systemd timeout signature at fleet scale.
- **Source code findings**:
  `ServiceManager.create_and_set_service_idem()` creates only the
  `MsftLinuxPatchAutoAssess` unit and defaults it to `Type=forking`.
  `ProcessHandler.stage_auto_assess_sh_safely()` generates a shell script that
  invokes `MsftLinuxPatchCore.py` synchronously, without daemonizing or
  backgrounding it. `Constants.AUTO_ASSESSMENT_MAXIMUM_DURATION` describes an
  expected one-hour operation window but is not an enforced wall-clock limit.
- **Fix validation**: A systemd 239 smoke test used a two-second
  `TimeoutStartSec`; the forking launcher returned in 32 ms, remained
  `active (running)` after the deadline, published a PID matching `MainPID`,
  and the complete service process was terminated on stop.

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
   demonstrated an unbounded YUM mitigation loop, but PR 303 added repeated
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

Keep `Type=forking`, but make the generated shell wrapper satisfy that
lifecycle contract. The wrapper starts Python in the background, writes its PID
to `/run/MsftLinuxPatchAutoAssess.pid`, verifies that the child launched, and
then exits. The generated unit declares the matching `PIDFile`, keeps
`KillMode=control-group`, removes the PID file after shutdown, and limits the
launcher startup phase to 30 seconds.

systemd can therefore complete service startup promptly while continuing to
track the Python assessment as the main process. Slow package operations are no
longer charged against `TimeoutStartSec`, and service stop operations still
terminate the complete assessment cgroup. The extension rewrites the launcher
with the latest contract when it starts Core, so upgrades replace wrappers
created by earlier extension versions.

No `RuntimeMaxSec` is added. Older supported systemd versions do not
consistently support that directive, and a forceful systemd runtime timeout can
terminate Core before it writes terminal assessment status. A future portable
application-level watchdog should enforce the operation deadline and write
terminal status before exiting.
