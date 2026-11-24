# CLAUDE.md

Instructions for AI assistants working in this repo. The project documents research on the Ford S550 Mustang CAN
bus: what each message means, how it was found, and how sure we are. People's rules are in
[CONTRIBUTING.md](CONTRIBUTING.md), and they apply to you too.

## Layout

- `database/`: the CAN database, one `*_database.md` per module / firmware. Format, Status values and which file to
  edit: [database/README.md](database/README.md). `database/README.md` is not part of the database.
- `canbus_samples/<contributor>/`: CAN logs referenced by each database file's `## Sources` table.
- `build_web.py` builds the site in `docs/` from `database/` and the logs. `docs/data.js` is generated, don't commit it.

## Rules

- **Never set a Status to `Confirmed` yourself.** Only the person you work with can confirm, after testing on a
  bench or in a car, and only when they tell you they did. Findings you derive from logs, firmware or a DBC are
  `From logs` / `From firmware`, or a `> [!NOTE]` labelled unconfirmed.
- **Confirmed lines take precedence.** Don't change or remove them based on a log or firmware reading. Add a note
  that says it disagrees.
- **Edit the file for the module being worked on.** Never put one module's or year's findings in another's file
  unless the person confirmed they match. New module, new file, following the template in `database/README.md`.
- **One `# 0xNNN - Name` section per ID.** Notes about several IDs together go in a `##` topic under `# Topics`.
- **Don't commit firmware, dumps, security keys / seed-key constants or proprietary documents**, and don't write
  them into notes. Describe what was learned, not how to unlock a module. `uds_security.py` is gitignored for this
  reason, keep it that way.
- **Run the checks before you say you're done:**

  ```
  python build_web.py --check
  python test_web.py
  ```

  Both have to pass. Report failures as they are, don't work around a check.
- Match the existing writing: short, plain sentences, hex in backticks (`0x3B3`, `40 48 02 0A`), bytes numbered
  0 - 7, dates written like `14 Nov 2026`.
- For a pull request, say which parts you wrote and what the person checked by hand.
