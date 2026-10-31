# Lessons for Drona, written outside the app

CandleCast's teacher, Drona, learns market topics into `knowledge.db` and uses what it has learned when it makes
its daily calls. Its queue is long, so topics can also be answered here, pushed to GitHub, and imported in one go.

## What to do

1. Open a list file, such as `level2/topics_001.md`. It holds up to 50 topics. Each has an id, a title, why it
   matters, and the subjects it sits under.
2. Answer every topic in it into an answers file, such as `level2/answers/answers_001.txt`. Answers are matched by
   topic id, so a file may hold any number of topics and its name doesn't matter.
3. Commit and push.

## Answer format

Write exactly this, one block per topic:

```
<topic id="4144">
<level>advanced</level>
<lesson>
# Title of the lesson

## Core idea
...
## How it works, step by step
...
## Formulas and numbers (worked example)
...
## India specifics
...
## Real examples and history
...
## Edge cases and common mistakes
...
## How traders, investors and quants use it
...
## Related concepts
...
</lesson>
<qa difficulty="hard"><q>A question</q><a>A complete, worked answer</a></qa>
<subtopic why="one line: why go deeper here">A narrower, deeper topic</subtopic>
<source url="https://example.com/page">Title of a page you actually used</source>
</topic>
```

- **`id`**: the topic's id from the list. Blocks with an unknown id are skipped.
- **`level`**: one of beginner, intermediate, advanced or expert.
- **The lesson**: Markdown, about 1,000 to 2,500 words, with the eight sections above. A lesson under 400 characters
  is rejected.
- **`qa`**: 6 to 10 blocks, mostly hard or expert. Use multi-step calculations, tricky edge cases and "why" questions.
  `difficulty` is medium, hard or expert.
- **`subtopic`**: 3 to 6 blocks. Each becomes a new, deeper topic in Drona's queue, so each should be narrow enough
  for one lesson.
- **`source`**: 2 or more. List only real pages you read; never invent a link.

### Content rules

- Explain in your own words, never copy a book's text, and include a worked example with numbers.
- Use India's current rules (SEBI, RBI, NSE, BSE) with dates. Check figures against sources, and say plainly when
  something is uncertain.
- Don't put `<topic>`, `<lesson>`, `<qa>`, `<q>`, `<a>`, `<subtopic>` or `<source>` inside the text itself: the
  importer reads those tags.
- **Never put API keys, passwords or personal data in these files: the repository is public.**

## Importing, on the laptop

```
git pull
.venv\Scripts\python -m app.lesson_import store lessons\level2\answers github
```

It stores every block from every `.txt` and `.md` file in the folder and prints one line per topic. A topic Drona
has already learned keeps its lesson. To store the answer over it, add `--replace`.

## Refreshing the list

A list is a snapshot of the topics pending when it was made (`index.md` gives the time). To make a new one, for
any depth:

```
.venv\Scripts\python -m app.lesson_import export 2 lessons\level2
```

That rewrites `topics_*.md` and `index.md`, and leaves `answers/` alone.
