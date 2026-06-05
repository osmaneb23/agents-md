# Security Policy

## Supported Versions

Security fixes target the latest published `agent-context-md` release on PyPI and the `main` branch of this repository. Older releases may receive a fix only when the issue is severe and the patch is low risk.

## Reporting a Vulnerability

Do not open a public issue with exploit details, real secrets, private repository contents, or provider API keys.

Preferred reporting path:

1. Check whether GitHub private vulnerability reporting is available for this repository.
2. If it is unavailable, open a [security contact issue](https://github.com/osmaneb23/agents-md/issues/new?template=security_contact.md) with only a short non-sensitive summary.
3. Wait for a maintainer to move the discussion to a private channel before sharing reproduction details.

Helpful report details:

- affected `agent-context-md` version
- command or GitHub Action configuration involved
- minimal reproduction using synthetic files or fake tokens
- expected impact, including whether generated `AGENTS.md` output, local file scanning, package publishing, or the composite action is involved

## Scope

In scope:

- vulnerabilities in the `agents-md` CLI
- unsafe handling of local repository files
- GitHub Action behavior in `.github/actions/agents-md-lint`
- packaging, release, or Trusted Publishing configuration
- accidental disclosure of secrets through generated output, logs, or diagnostics

Out of scope:

- model-provider behavior in Anthropic, OpenAI, or Gemini services
- vulnerabilities in optional third-party SDKs, except where `agents-md` uses them unsafely
- generated `AGENTS.md` content in repositories not controlled by the reporter
- social engineering or testing against systems the reporter does not own

## Disclosure Expectations

Please give the maintainer a reasonable chance to investigate before public disclosure. The target response time is 7 days, with a target fix or mitigation within 30 days for confirmed vulnerabilities. Timelines may vary for low-impact issues or reports that need coordination with upstream providers.

`agents-md` has no telemetry. It scans local repository files and writes local Markdown output unless the user explicitly enables LLM synthesis with a provider API key.
