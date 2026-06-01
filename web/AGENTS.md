<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

## Repository Rules

Before modifying files under `web/`, also read the repository root
`MASTER_DEVELOPMENT_GUIDE.md` and `AGENTS.md`.

Frontend work must follow the repository's simplified, review-only investment
posture. Do not add or restore live/paper execution toggles, broker/KIS order
controls, real-account mutation controls, or automatic execution UI unless a
dedicated approved execution task explicitly permits it.

When displaying layered score-flow feedback, treat `FeedbackSignal`,
`DecisionStateSnapshot`, and orchestrator outputs as review/audit data only.
Do not convert them into active allocation, rebalancing, or order submission
actions in the UI.
