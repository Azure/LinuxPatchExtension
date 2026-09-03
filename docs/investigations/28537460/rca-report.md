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

## Azure VM Validation

- **VM**: Azure RHEL 8.9, systemd 239, Linux Patch Extension 1.6.71.
- **Reproduction**: Wrapped `/usr/bin/yum` to delay its first invocation by
  120 seconds and forced auto-assessment to run.
- **Before the fix**: `systemctl start` failed after exactly 90 seconds.
  `systemctl show` reported `TimeoutStartUSec=1min 30s`, `Result=timeout`, and
  the journal recorded `start operation timed out. Terminating.`
- **Deployment**: Built the extension from this branch, copied the generated
  `MsftLinuxPatchCore.py` over the installed extension payload, and reran
  `ConfigurePatching` to regenerate the systemd unit.
- **After the fix**: The unit retained `Type=forking` and reported
  `TimeoutStartUSec=10min`. The delayed real assessment completed successfully:
  the assessment stopwatch reported 136 seconds and systemd reported
  `Result=success`.
- **Non-regression**: A subsequent platform-triggered on-demand assessment
  completed with status `Succeeded`.
- **Cleanup**: The `yum` wrapper was removed, the original executable was
  restored, and the auto-assessment timer was active after validation.

## Supported Distro Sanity Matrix

The same test was repeated on Azure VMs using Linux Patch Extension 1.6.71.
Each package-manager wrapper delayed only its first invocation by 120 seconds.

| Distribution | Delayed command | Before fix | After fix | Platform assessment |
| --- | --- | --- | --- | --- |
| Ubuntu 22.04.5 LTS | `apt-get` | Failed at 90s with `Result=timeout` | Service completed in 157s with `Result=success`; patch assessment completed | `Succeeded` |
| Ubuntu 24.04.4 LTS | `apt-get` | Failed at 90s with `Result=timeout` | Service completed in 136s with `Result=success`; patch assessment completed | `Succeeded` |
| SLES 15 SP5 | `zypper refresh` | Failed at 90s with `Result=timeout` | Service completed in 144s with `Result=success`; assessment stopwatch reported 133.1s | `Succeeded` |

All three regenerated units retained `Type=forking` and reported
`TimeoutStartUSec=10min`. After each run, the original package-manager
executable was restored and `MsftLinuxPatchAutoAssess.timer` was active.

On Ubuntu, the intentional delay occurred during the
`ubuntu-advantage-tools` prerequisite step before the assessment stopwatch
started. The full systemd service duration therefore captures the delayed
startup, while the logs separately confirm the subsequent patch assessment
completed successfully.

## Package-Manager Delay Commands

The validation delayed only the first package-manager invocation. A 120-second
delay reproduces the original 90-second failure while remaining below the
10-minute mitigation. A 660-second delay validates that the mitigation remains
bounded and terminates at 600 seconds.

> Use these commands only on disposable test VMs. Do not run package-manager
> commands between installing a wrapper and starting auto-assessment, because
> the first invocation consumes the one-time delay.

### Ubuntu: `apt-get`

The delayed command observed during validation was
`apt-get install ubuntu-advantage-tools -y`. Use `dpkg-divert` so the original
package-managed binary is preserved safely:

```bash
DELAY_SECONDS=120

sudo test ! -e /usr/bin/apt-get.distrib || {
    echo "apt-get diversion already exists; inspect before continuing."
    exit 1
}

sudo dpkg-divert --local --rename --add /usr/bin/apt-get

sudo tee /usr/bin/apt-get >/dev/null <<EOF
#!/usr/bin/env bash
MARKER=/var/tmp/lpe-28537460-apt-delay-used

if [ ! -e "\$MARKER" ]; then
    touch "\$MARKER"
    logger -t lpe-28537460-repro \
        "Delaying first apt-get invocation for ${DELAY_SECONDS} seconds"
    sleep ${DELAY_SECONDS}
fi

exec /usr/bin/apt-get.distrib "\$@"
EOF

sudo chmod 755 /usr/bin/apt-get
sudo rm -f /var/tmp/lpe-28537460-apt-delay-used
```

Cleanup:

```bash
sudo rm -f /usr/bin/apt-get
sudo dpkg-divert --local --rename --remove /usr/bin/apt-get
sudo rm -f /var/tmp/lpe-28537460-apt-delay-used
```

### RHEL 8: `yum`

The delayed command was `yum -q check-update`. On RHEL 8, `/usr/bin/yum`
normally resolves to `/usr/bin/dnf-3`, so the wrapper must invoke `dnf-3`
directly. Do not create a wrapper backup beside `yum`; rerunning that setup can
replace the backup with the wrapper and create recursive Bash processes.

```bash
DELAY_SECONDS=120

test "$(readlink -f /usr/bin/yum)" = "/usr/bin/dnf-3" || {
    echo "Unexpected yum target; inspect before continuing."
    exit 1
}

sudo rm -f /usr/bin/yum

sudo tee /usr/bin/yum >/dev/null <<EOF
#!/usr/bin/env bash
MARKER=/var/tmp/lpe-28537460-yum-delay-used

if [ ! -e "\$MARKER" ]; then
    touch "\$MARKER"
    logger -t lpe-28537460-repro \
        "Delaying first yum invocation for ${DELAY_SECONDS} seconds"
    sleep ${DELAY_SECONDS}
fi

exec /usr/bin/dnf-3 "\$@"
EOF

sudo chmod 755 /usr/bin/yum
sudo restorecon -v /usr/bin/yum
sudo rm -f /var/tmp/lpe-28537460-yum-delay-used
```

Cleanup:

```bash
sudo rm -f /usr/bin/yum
sudo ln -s dnf-3 /usr/bin/yum
sudo restorecon -v /usr/bin/yum
sudo rm -f /var/tmp/lpe-28537460-yum-delay-used
```

### SLES 15: `zypper`

The delayed command was `zypper refresh`. Preserve the original executable
once, and abort rather than overwrite the backup if setup is accidentally
repeated:

```bash
DELAY_SECONDS=120

sudo test ! -e /usr/bin/zypper.lpe28537460.original || {
    echo "Existing zypper backup found; inspect before continuing."
    exit 1
}

sudo mv /usr/bin/zypper /usr/bin/zypper.lpe28537460.original

sudo tee /usr/bin/zypper >/dev/null <<EOF
#!/usr/bin/env bash
MARKER=/var/tmp/lpe-28537460-zypper-delay-used

if [ ! -e "\$MARKER" ]; then
    touch "\$MARKER"
    logger -t lpe-28537460-repro \
        "Delaying first zypper invocation for ${DELAY_SECONDS} seconds"
    sleep ${DELAY_SECONDS}
fi

exec /usr/bin/zypper.lpe28537460.original "\$@"
EOF

sudo chmod 755 /usr/bin/zypper
sudo rm -f /var/tmp/lpe-28537460-zypper-delay-used
```

Cleanup:

```bash
sudo rm -f /usr/bin/zypper
sudo mv /usr/bin/zypper.lpe28537460.original /usr/bin/zypper
sudo rm -f /var/tmp/lpe-28537460-zypper-delay-used
```

For the 10-minute boundary test, set `DELAY_SECONDS=660` in the relevant setup
block. Before leaving each VM, verify the restored package manager and timer:

```bash
sudo systemctl start MsftLinuxPatchAutoAssess.timer
sudo systemctl is-active MsftLinuxPatchAutoAssess.timer
```

## Ten-Minute Timeout Boundary Validation

The fixed unit was retested on new Azure VMs in `westus2` with a 660-second
delay on the first package-manager invocation. This verifies that the service
does not remain indefinitely in `activating` after increasing the startup
timeout.

| Distribution | Delayed command | Configured timeout | Observed result |
| --- | --- | --- | --- |
| RHEL 8.9 | `yum -q check-update` | 10 minutes | Timed out at exactly 600s |
| Ubuntu 22.04.5 LTS | `apt-get install ubuntu-advantage-tools -y` | 10 minutes | Timed out at exactly 600s |
| Ubuntu 24.04.4 LTS | `apt-get install ubuntu-advantage-tools -y` | 10 minutes | Timed out at exactly 600s |
| SLES 15 SP5 | `zypper refresh` | 10 minutes | Timed out at exactly 600s |

All units contained `Type=forking` and `TimeoutStartSec=10min`. Each
`systemctl start` returned 1, and the final service state was
`ActiveState=failed`, `SubState=failed`, and `Result=timeout`. The journals
recorded `start operation timed out. Terminating.` at the 600-second boundary.

After each test, the original package-manager executable was restored and
`MsftLinuxPatchAutoAssess.timer` was active. Complete VM evidence, extracted
logs, archives, checksums, and the per-distribution report are stored locally
under:

`artifacts\28537460-timeout-validation-20260811`
