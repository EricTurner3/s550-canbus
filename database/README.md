# Adding to the database

The website is built from the `*database.md` files in this folder. This README is the template and the rules. For the
steps (fork, checks, pull request) see [CONTRIBUTING.md](../CONTRIBUTING.md).

## Which file

One file per module / firmware. The main focus is creating messages that the instrument cluster would be receiving. However if you have data for other modules (GWM, APIM, PCM, BodyCM.etc) feel free to document them. The website shows every file's notes for an ID side by side.

| File | Cluster |
|---|---|
| [database.md](database.md) | 2015-2017 analog (FR33) |
| [2018_digital_database.md](2018_digital_database.md) | 2018+ digital |

- If a relevant file exists already: edit it.
- It doesn't: copy the template below into `database/<name>_database.md`, e.g. `2020_lr3t_database.md`.
- Don't merge findings if they are for separate years / trims / modules unless you've confirmed they match.
- Please add any supporting log files under a subfolder in `/canbus_samples` as evidence of your discovery. These show up in the web UI's table automatically

## Template

````markdown
# <Module name> (<part number>)

**Label:** <short name shown on the site, e.g. 2020+ digital (LR3T)>

<What this module is and where the data came from.>

## Modules

| Module | Part number | Notes |
|---|---|---|
| IPC (cluster) | <LR3T-14C026-JE> | <bench / car, firmware version> |
| <APIM, GWM, ...> | <part number> | <anything else on the bus you tested with> |

## Sources

| Source | Vehicle | Bus | Notes |
|---|---|---|---|
| `canbus_samples/<you>/<car or bench>/keyon.txt` | <label for these samples on the site> | HS3 | <how it was captured> |

# 0x3B3 - <Message name>

**Sample:** `40 48 02 0A 10 05 00 02` (<what it shows>) · **Rate:** 100 ms · **Status:** Confirmed

| Byte | Signal | Values |
|---|---|---|
| 0 bits 7 - 4 | <signal> | `4` run, `0` off |
| 4 | <signal> | `raw * 0.5 - 40 = °C` |

<Notes. Say "byte 4" or "bytes 4 - 5" and the site colors the note to match.>

# Topics

## <Topic name>

<Anything that isn't one ID: timeouts, DTCs, how several IDs work together.>
````

The Modules and Sources tables are optional, but say what you tested on if you can.

## Rules

- **Layout:** the title with a `**Label:**`, then one `# 0xNNN - Name` section per ID (one ID per heading, no `##`
  inside it), then `# Topics` with a `## Name` per topic. A topic heading can name several IDs
  (`## 0x3A6 / 0x3A7 - Blind Spot`), those ID pages link to it.
- **Each ID section** starts with the `**Sample:** · **Rate:** · **Status:**` line. Status is required. Samples are
  1 - 8 hex bytes in backticks.
- **Byte tables** have a `Byte` column with a byte number on every row (`0`, `4 - 5`, `0 bits 7 - 4`).
- **Confirmed findings take precedence.** Tested it on a bench or in a car? Edit the section and set Status to
  `Confirmed`. Not tested (logs, firmware, a guess)? Leave confirmed lines alone and add a note:

  ```markdown
  > [!NOTE]
  > **Unconfirmed (from firmware):** byte 3 bit 3 looks like the valid bit.
  ```

`python build_web.py --check` tells you what's wrong, with file and line.

## Status values

Every ID's Status starts with one of these, detail can follow (`Confirmed (byte 4)`):

| Status | Use it when |
|---|---|
| **Confirmed** | Tested on a cluster, on the bench or in a car |
| **From logs** | Matched in a CAN log or a DBC, not tested yet |
| **From firmware** | Read out of the firmware, not tested yet |
| **Cluster sends** | The cluster transmits it. Never send it |
| **APIM sends** | The APIM transmits it. Never send it |

## Log samples (Sources)

Optional. Frames from your log show up on each ID's page next to the notes.

- Put logs in `canbus_samples/<you>/<car or bench>/`, e.g. `canbus_samples/<you>/2020_gt_car/`. One folder per car
  or bench rig, not per module: a log holds the whole bus.
- Keep them small. The site only uses the first frame of each ID, so a few seconds of key-on is plenty.
- Add a row to your file's `## Sources` table: the path in backticks (a file, a folder or `*.csv`) and a Vehicle
  label.

The simplest format is a text file, one frame per line:

```
0x3B3: 40 48 02 0A 10 05 00 02
0x42F: C0 00 7D 00 00 00 1F 40
```

Also read: candump (`(6.53) can0 3B3#4048020A10050002`), python-can CSV (`python -m can.logger`), `id,count,data`
CSV and Forscan freeze frame CSV (`ID (HEX)`, `Sample Data` columns).
