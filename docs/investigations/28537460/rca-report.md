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
  expected one-hour operation window but was not an enforced wall-clock limit.
- **Fix validation**: An accelerated systemd 239 smoke test used a five-second
  soft deadline and a four-second grace period. The foreground service wrote a
  terminal assessment error at the soft deadline. A process that ignored the
  soft signal was killed at the nine-second hard deadline. An accelerated
  recurring timer started two bounded runs 11 seconds apart, including after
  the first service run exited with timeout status.

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

Use `Type=simple` because the wrapper and Core are foreground processes, then
bound that foreground execution below the hourly timer interval. The generated
wrapper replaces itself with:

```text
timeout -s USR1 -k 4m 55m <python-core-command> -autoAssessmentOnly True
```

`exec` keeps systemd tracking the timeout supervisor directly. At 55 minutes,
GNU `timeout` sends `SIGUSR1` to the supervised process group. During automatic
assessment, Core converts that signal to a dedicated
`AutoAssessmentTimeoutError`, bypasses package-manager retries, and writes an
`Error` assessment status. The prior signal handler is restored after the
assessment so repeated Core invocations in the same process remain isolated.

If graceful handling is blocked, such as a process in an uninterruptible kernel
wait, GNU `timeout` sends `SIGKILL` after a further four minutes.
`KillMode=control-group` ensures systemd owns the complete process tree. The
hard upper bound is therefore 59 minutes, leaving one minute before the
unchanged `OnUnitActiveSec=1h` timer boundary. systemd does not overlap
instances of the same service, and the completed service can be activated by
the next timer event.

This design is selected instead of daemonizing because no daemon lifecycle is
needed: the work is periodic, finite, and should remain under systemd
supervision. It is selected instead of only increasing `TimeoutStartSec`
because that would continue treating the entire assessment as startup and
would not bound a real hang. `RuntimeMaxSec` is not used because systemd 219 is
in the supported range and does not provide that directive. The extension
already depends on GNU `timeout` for bootstrap checks, so the launcher does not
introduce a new package dependency.

Terminal status at the soft deadline is best-effort for interruptible
userspace hangs. The 59-minute cgroup kill is the authoritative safety
guarantee for uninterruptible work, where no in-process implementation can
guarantee an additional status write.
