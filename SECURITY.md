# Security Policy

## Scope

Zissa Wiki is a template made of plain markdown files and folders, plus one small standard-library Python tool (`scripts/wiki.py`) and the hooks that call it. It has **no backend, no database, no embeddings, and no network services**, and the tool never contacts a model or the internet. The operational logic lives in `AGENTS.md`, which your AI agent reads at runtime on your own machine.

Because of this, the usual software attack surface is very small. The realistic concerns are:

- **Prompt content in `AGENTS.md` or page templates** that could cause an LLM agent to behave in unintended ways (for example, instructions that lead it to modify or delete `raw/` source files, which it should never do).
- **`wiki.py apply` writing model output to disk.** It accepts only `wiki/**.md`, `index.md` (replaced) and `log.md` (appended), and refuses any other path, including ones that climb out with `..`. A way around that restriction is in scope.
- **Secrets accidentally committed** into the template (none should ever be — this repo holds no credentials).

## Reporting a vulnerability

If you find an issue that fits the above — or anything else you believe is a security concern in the template — please report it privately rather than opening a public issue:

- Use GitHub's **[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)** ("Report a vulnerability" under the Security tab), or
- Email **paulo.deassis@orpheusinstituut.be**

Please include what you found, how to reproduce it, and the impact you have in mind. I'll acknowledge within a reasonable time and credit you in any fix unless you'd prefer otherwise.

## A note for forkers

Your own working wiki will contain your sources and notes. Treat your fork's `raw/` and `wiki/` folders with the same care you'd give any private research material — review what you commit before making a fork public.
