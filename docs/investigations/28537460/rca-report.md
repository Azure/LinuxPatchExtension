# RCA Report - Bug #28537460

## Summary

Linux auto-assessment can remain in progress when a valid assessment exceeds
systemd's default 90-second service start timeout. The initial mitigation keeps
the existing `Type=forking` lifecycle and extends the generated unit's bounded
startup window to 10 minutes.

## Evidence Collected

- **Bug metadata**: Bug 28537460 is a high-severity recurring issue affecting
  Azure and Arc Linux VMs across multiple distributions.
- **Historical patterns**: Bug 33342595 reports the same
  `MsftLinuxPatchAutoAssess.service` timeout signature. Bug 24467908 and PR 203
  introduced `Type=forking` after `Type=notify` caused service failures.
- **Runtime evidence**: GitHub issue 350 demonstrates systemd sending SIGTERM at
  approximately 90 seconds while package-manager work is still running.
- **Duration evidence**: A one-day sample of on-demand assessments had P99 near
  215 seconds and P99.9 near 256 seconds. A 10-minute timeout provides
  substantial margin while remaining bounded.
- **Source code findings**: `ServiceManager.create_service_unit_file()` does not
  emit `TimeoutStartSec`, so systemd applies its manager default. The extension
  permits auto-assessment operations to run for up to one hour.

## Root Cause

The generated `MsftLinuxPatchAutoAssess.service` uses `Type=forking`. systemd
therefore keeps the unit in its startup phase until it observes the expected
forking lifecycle. If assessment startup and package-manager work exceed the
default `TimeoutStartSec=90s`, systemd terminates the service cgroup before the
extension writes terminal assessment status. Azure Update Manager then retains
the stale `In Progress` state.

## Competing Hypotheses

1. **Package-manager work is always hung indefinitely**: Some historical cases
   involved unbounded package-manager retries, but the deterministic reproduction
   uses an intentionally slow command that eventually completes. The exact
   90-second termination is imposed by systemd rather than the package manager.
2. **The service lifecycle should immediately change to `Type=simple`**: This
   matches the foreground wrapper more closely and removes the startup gate, but
   email review identified cross-distribution and lifecycle regression testing
   as a prerequisite.
3. **The startup timeout is too short for valid assessments**: The observed
   duration distribution and exact systemd timeout support this as the safest
   first mitigation.

## Selected Fix

Keep `Type=forking` and add `TimeoutStartSec=10min` to the generated service
unit. This avoids changing the established lifecycle model while allowing
normal slow assessments to finish. The timeout remains bounded so a process
that never reaches the expected started state is still terminated.

The validation plan reproduces the 90-second failure on an Azure Linux VM,
copies the modified `ServiceManager.py` into the installed extension, regenerates
the service, and verifies that the same assessment runs beyond 90 seconds and
completes before 10 minutes.
