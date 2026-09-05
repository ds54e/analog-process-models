# Security policy

## Supported release

Security and provenance maintenance targets the latest released line and
current `main`. APM v5.0.0 is the latest completed release, and `main` is its
current v6 development line. All released tags are immutable and
retained for reproducibility; fixes are normally made on `main` rather than by
moving a released tag or rewriting published history.

## Reporting privately

For a security vulnerability, accidentally exposed credential, or a
licensing/provenance concern that should not initially be public, use GitHub's
**Report a vulnerability** action on the repository Security tab. Private
Vulnerability Reporting is enabled for this public repository.

GitHub documents [Private Vulnerability Reporting](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting)
and sends the report privately to repository maintainers. If GitHub's private
reporting action is temporarily unavailable, open a minimal GitHub issue
asking the maintainers to establish a private channel.
Do not include exploit details, credentials, proprietary model content,
personal information, or other sensitive evidence in that public issue.

If a credential belongs to you, revoke or rotate it immediately; reporting it
to this project is not a substitute for revocation.

## What to include

Once a private channel exists, provide the affected version/commit and path,
the impact, minimal reproduction steps, and any suggested remediation. For a
licensing concern, include the upstream source, exact revision/file, and the
specific redistribution or notice issue.

Please allow maintainers time to verify and coordinate a fix before public
disclosure. This policy does not create a warranty, support SLA, or security
guarantee.
