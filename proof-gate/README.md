# Proof Gate

A Kiro Crew app: Proof Gate

## Installation

```bash
kirocrew app install /path/to/proof-gate
kirocrew app enable proof-gate
```

## Development

Edit agents, skills, and backend code. Changes to agents and skills
take effect on next agent invocation. Backend changes require restart.

## Structure

```
proof-gate/
├── app.json              ← manifest
├── assets/
│   └── icon.png          ← store icon; replace this placeholder
├── agents/               ← agent definitions
│   └── sample-agent.json
├── skills/               ← skill files
│   └── sample-skill/
│       └── SKILL.md
├── backend/              ← optional backend (--backend)
│   └── server.py
├── ui/                   ← optional UI frontend (--ui)
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       └── App.tsx
└── README.md
```
