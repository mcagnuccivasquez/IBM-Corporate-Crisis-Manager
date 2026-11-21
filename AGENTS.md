# AGENTS.md — start here (for any teammate and any AI assistant)

This repo is a **group project**: a multi-agent *Corporate Crisis Manager* for the fictional company ACME (IBM Use Case 2).
If you are an AI assistant (Claude Code, Claude.ai, ChatGPT, Gemini, Copilot, IBM Bob…), you are helping **one teammate** in **one work session**. Follow this file.

## 1. Read order (load only what you need; tokens are limited)
1. `STATUS.md`: current state, who is working on what. **Always.**
2. `PROJECT.md`: goal, architecture, shared contract, risk method, KB registry. **Once per chat.**
3. `agents/<the agent you're working on>.md`: **only that one.** (A2 covers 2a/2b/2c.)
4. Knowledge-base files or source code: only when the task needs them.

Do not load other agents' specs unless the task is about the interface between two agents.

## 2. Session protocol

### ▶ Start trigger
When the user says something like **"Hey I'm <name> and I will start my work session"** (any wording or language with that intent):
1. Ask what they will work on (agent/task, GitHub issue number) if they didn't say.
2. Make sure the repo is up to date: run `git pull` if you have a shell, or ask the user to.
3. Read `STATUS.md`. **Warn** if someone else is listed under "Working now" on the same agent or files.
4. Create `sessions/YYYY-MM-DD_<name>_<topic>.md` from `sessions/_TEMPLATE.md`. Fill the header (name, date, start time, tool/LLM, goal).
5. Add the person to "Working now" in `STATUS.md`.

### ● During the session
- Append **one line per meaningful action** to the session file's *Log*: files created or changed, decisions, prompt changes, test runs and results, blockers. Not every chat message.
- Anything that changes **PROJECT.md §4–§8 (contract, risk method, report structure, KB registry)** or another agent's interface: **don't apply it silently.** Write it under *Needs director review* and tell the user to bring it to the director chat.

### ■ End trigger
When the user says something like **"Ok, now I'm finishing my session"**:
1. Complete the session file: *Summary, Done, Not done / blockers, Next steps, Files touched, Needs director review*.
2. Update `STATUS.md`: the agent status table, remove the person from "Working now", add one line to "Recent sessions" (keep the last 10).
3. Propose a commit message: `[A1] <what changed> (session: <name>)`. Commit and push **only after the user confirms**, ideally on a branch `<name>/<topic>` with a pull request.
4. Remind the user to post one line in the group chat ("Done with A1 extraction; PR #12; next: verification rules").

### If your tool can't write files (web chat LLMs)
At the end, output the **full session file** and the **exact STATUS.md edits** as markdown blocks so the teammate can paste and commit them.

## 3. Rules for every chat
- The agent specs in `agents/` are the requirements. If code and spec disagree, raise it; don't silently change the spec.
- File ownership is listed in each agent spec. If you edit a file owned by another agent, note it in the session log and tell its owner.
- Never commit secrets (`.env`, API keys). Each teammate uses their own key.
- The system we build only **drafts and recommends**. It never sends real statements, notifications, or recalls.
- Writing LLM code with Claude Code? Load the `claude-api` skill first.
