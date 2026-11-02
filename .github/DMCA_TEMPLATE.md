# Takedown playbook

Short checklist for dealing with copies that strip attribution or impersonate
the project. Not legal advice — for real disputes, consult a lawyer.

## What is a violation

- Copies that remove or hide the copyright/attribution (violates GNU GPL v3 §5
  and the additional terms in `NOTICE`).
- Copies that use the "Claude Code Manager" name or logo and present themselves
  as the original project (violates the name clause in `NOTICE`).
- Copies distributed without source under GPL (violates GPL §6).

A fork that keeps the notices, marks its changes with a date and uses a
different name is **allowed**. Do not report those.

## Evidence to collect first

1. URL of the copy and date/time you found it (screenshot with a clock).
2. Proof of the original: GitHub commit history, release tags and dates,
   `updates.json` timestamps, Wayback Machine snapshots of the site and the
   releases page.
3. The fingerprint from the copy, if visible in its logs or About screen
   (`ccm-on1felix-…`). It proves the build came from this repository.
4. Side-by-side diff of the stripped notices, if possible.

## Where to report

| Platform | How |
| --- | --- |
| GitHub | https://github.com/contact/dmca — DMCA form, "Repository" section |
| Netlify | abuse@netlify.com, subject "Copyright infringement" |
| Generic hosting | abuse address from the provider's site, same template |
| Search engines | Google DMCA removal form, Bing content removal |

## DMCA template

```
To: <abuse contact or platform form>
Subject: DMCA takedown notice — Claude Code Manager

1. Copyrighted work
   Claude Code Manager, source: https://github.com/on1felix/claude_code_manager
   Copyright (c) 2026 on1felix. Licensed under GNU GPL v3.0 or later with
   additional attribution terms (see NOTICE in the repository).

2. Infringing material
   <URL of the copy>
   The copy removes the copyright notices and the author attribution, and
   presents the work as its own, which violates GPL v3 §5 and the additional
   terms of the license.

3. Good faith statement
   I have a good faith belief that the use of the material described above is
   not authorized by the copyright owner, its agent, or the law.

4. Accuracy statement
   I swear, under penalty of perjury, that the information in this notice is
   accurate and that I am the copyright owner or authorized to act on behalf of
   the owner.

5. Contact
   Name: on1felix
   GitHub: https://github.com/on1felix
   Telegram: https://t.me/on1felix001
   Email: <your email>

Signature: /s/ on1felix
Date: <date>
```

## Monitoring (once a month)

- grep.app and GitHub code search for `ccm-on1felix-` and for unique strings
  from the interface.
- Search for the project name without "on1felix" nearby.
- Check the fork list of the repository and the releases feed.
- Save a new Wayback snapshot of the site and the releases page.

Watermark registry lives outside this repository on purpose.
