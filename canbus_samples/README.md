# CAN log samples

CAN logs referenced by the `## Sources` tables in [database/](../database/). The website shows the first frame of each
ID from every source next to that ID's notes. How to add yours (folders, file formats, Sources row):
[database/README.md, Log samples](../database/README.md#log-samples-sources).

```
canbus_samples/
  <contributor>/        anything unique, e.g. a GitHub username. Only add files to your own
    <capture setup>/    one car or one bench rig, with every module that was on its bus
```

Logs aren't split by module: a log holds everything on the bus while it was recorded. The modules' part numbers are
in the Sources row of the `*database.md`, if known.

| Folder | What's in it |
|---|---|
| [EricTurner3/](EricTurner3/) | The repo owner's logs |
| `EricTurner3/2016_gt350_car/` | 2016 GT350, 6MT, HS1 at the OBD port (python-can, slcan, 500k). `replay.py <name>` finds these by name |
| `EricTurner3/2015_gt_premium_car/` | The bench cluster's original car (2015 GT Premium, FR33-10890-AA): freeze frame (`interactive_brute_force.py --freeze` sends it) and a key on, engine off CANtact log at the gateway |
| `EricTurner3/bench_cluster/` | The bench cluster (FR33) alone: `cluster_tx.csv` / `cluster_tx_changes.csv`, what it sends on its own, written by `interactive_brute_force.py` |
| `EricTurner3/bench_apim/` | The bench APIM (SYNC 2, FR3T-14F239-CE) alone on HS3, written by `apim_capture.py` |
