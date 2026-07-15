# RCA Report - Work Item #38811250

## Summary

LinuxPatchExtension package-manager failures expose generic text and a long command in the customer-visible status error, while the actual package-manager output remains only in logs. The status handler truncates each error detail to 128 characters, so the current ordering removes the information customers need to diagnose the failure.

## Evidence Collected

- **Work item metadata**: Feature #38811250 requests meaningful portal errors without exceeding status-file limits.
- **Historical patterns**: Bug #24277199 and PR #10835391 removed verbose WindowsPatchExtension stack traces because they displaced useful status data. Bugs #34942475, #36476274, and #38467368 show recurring LPE customer-error classification and fidelity issues.
- **Source code findings**: `StatusHandler.__ensure_error_message_restriction_compliance` limits each message to 128 characters. APT, YUM, TDNF, DNF5, and Zypper package-manager invocation paths report the command but do not include a bounded, customer-facing output summary.

## Root Cause

Package-manager failures are serialized as free-form strings whose least actionable fields appear first. The generic `Customer environment error` prefix and full command consume the 128-character detail budget before any package-manager output can be shown. Whole-file truncation is not the primary cause because the per-error limit is applied when each detail is created.

## Competing Hypotheses

1. **The 128 KB status-file truncation removes the error details**: Rejected. Error messages are reduced to 128 characters before whole-file patch-list truncation runs.
2. **The package-manager error construction loses diagnostic priority**: Confirmed. The status message includes generic remediation text and the command, while stdout/stderr is only logged internally.

## Selected Fix

Add a shared package-manager error formatter that reports the package manager and exit code, selects the most actionable output line, redacts common credential patterns, and enforces the existing 128-character limit. Keep the full command and output in extension logs and preserve the existing exception text for compatibility.
