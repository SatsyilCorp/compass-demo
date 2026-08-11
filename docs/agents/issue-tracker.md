# Issue tracker: Local Markdown

Issues and PRDs for this repository live as markdown files in `.scratch/`.

## Conventions

- One feature per directory: `.scratch/<feature-slug>/`
- The PRD is `.scratch/<feature-slug>/PRD.md`
- Implementation issues are `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01`
- Triage state is recorded as a `Status:` line near the top of each issue file
- Comments and conversation history append under a `## Comments` heading

## Publishing work

When a skill publishes to the issue tracker, create a file under `.scratch/<feature-slug>/`, creating the directory when needed.

## Fetching work

Read the file at the referenced path. The user will normally provide the path or issue number directly.
