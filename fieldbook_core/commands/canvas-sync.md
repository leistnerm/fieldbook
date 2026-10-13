---
description: Read Canvas coursework, quizzes, discussion deadlines and planner; preview deduplicated local updates
---
Input: $ARGUMENTS.

Read AGENTS.md and fieldbook.json. Require school setup and features.canvas.
Load the `canvas-school` skill, or read `fieldbook_core/skills/canvas-school/SKILL.md`.
Use canvas_pull for the chosen configured instance and scope. For a broad deadline
check, choose coursework with selected courses and an explicit planner date window.
Review identity warnings, separate date types and both discussion checkpoints.
Default to updating
linked records only; offer missing courses/assignments only when requested.
Announcements and calendar events are optional context, not automatic tasks or
meeting notes. Preview a local change plan before notebook_write. Never change
Canvas, submit work, read grades/rosters, or create people from course data.
