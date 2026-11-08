# Changelog

## [2.0.0] - 2026-11-07

A major version: the bench tools were rewritten with new command lines, `s550_cluster.py` now runs at the car's real
message rates, and `s550_data.py` has new fields with new defaults. Track Apps, the g meter, and the AFR, boost,
cylinder head temp and inlet air temp gauges work on the bench cluster for the first time.

### New message IDs

Confirmed on the bench cluster unless marked *from logs*. Full details are in [database.md](database.md).

| ID | What it does |
|---|---|
| `0x3B2` | **Unlocks Track Apps.** Sent alongside `0x3B3`. Also carries the turn signals (byte 4 bit `0x08` right, byte 6 bit `0x40` left) and trunk ajar (byte 0 `0x41`). Not in any of our logs, found in another project's 2016 Mustang firmware |
| `0x76` | **Track Apps Accelorometer** (the red dot). Byte 2 = `16 + lateral g * 8`, bytes 3 - 4 = `1024 + longitudinal g * 512`, ±1.5 g. Bytes 0 - 1 steering angle |
| `0x43E` | **AFR** (byte 3, `raw / 10`), **cylinder head temp** (byte 4, `raw - 60 = °C`), **boost / vacuum gauge** (bytes 5 - 6, `value * 0.1 - 206.9` kPa). Fills in the AFR, boost, CHT and IAT gauges with `0x42D` |
| `0x42D` | **Inlet air temp**, 10 bit, `raw * 0.25 - 128 = °C` |
| `0x421` | **Oil pressure** "Normal" (just sending it clears "Low"), **check engine light** (byte 0 `0x04` solid / `0x08` flashing), **engine shutdown messages** (byte 1, auto start-stop) |
| `0x3E0` / `0x3E3` / `0x3E6` | **Startup handshake.** The cluster asks the other modules to answer (`04 01` ... `04 11`) and waits 5 s for each. Replies are `00 01 04 xx 80` on `0x3E3`, except `04 07`, which is answered on `0x3E6` |
| `0x92` | Accelerometer (*from logs*): three 13 bit values `(m/s² + 40) * 100`, byte 6 checksum (bytes add up to `0x16`), byte 7 counter `+5`. Checked against every log |
| `0x179` | Byte 5 is the distance counter that drives the odometer (~8767 counts per mile). Bytes 6 - 7 likely fuel used |
| `0x3B5` | Tire pressures are 16 bit kPa per tire, not 8 bit |
| `0x40A` | VIN and vehicle config (*from logs*), multiplexed pages from the body control module. Pages `C1 04` / `C1 10` are its as-built blocks 726-12 / 726-13 |
| `0x167` | Bytes 5 - 6 manifold pressure (*from logs*). Doesn't drive the boost gauge, that's `0x43E` |
| `0x453` / `0x454` | Seat occupant sensor and airbag module serial numbers (*from logs*) |
| `0x77` `0x85` `0x91` `0x165` `0x200` `0x204` `0x217` `0x230` `0x331` `0x415` `0x422` `0x4B0` | Speed, yaw, steering angle, brake pedal, torque, accelerator pedal, wheel speeds, gear, outside temp, coolant and braking pressure, decoded *from logs* |
| Cluster transmits | 30+ IDs the cluster sends itself, now listed so nothing else sends them: `0x18B 0x19A 0x220 0x225 0x287 0x2F4 0x2FD 0x30A 0x313 0x315 0x316 0x317 0x318 0x346 0x348 0x350 0x353 0x3C8 0x3E0 0x3FB 0x430 0x434 0x45A 0x591`, plus power-up one-shots `0x087 0x123 0x190 0x193 0x195 0x1EE 0x1F2 0x1F8 0x1F9 0x1FA 0x1FB 0x1FC 0x363` |

Corrected:

- `0x3C8` (drive mode / MyColor) and `0x430` (odometer) are sent by the cluster itself, sending them causes bus errors.
- `0x178` bytes 5 & 7 have no visible effect, the old outside air temp guess is removed.
- `0x3B3` byte 4 is `0x10` while running in every log. Its turn signal bits don't light the arrows on the bench, `0x3B2` does.

### s550_cluster.py

- **Real message rates.** The schedule now matches the car: 100 Hz, 50 Hz, 10 Hz, 2.5 Hz and 1 Hz groups (was 0.16 - 6.4 s). One scheduler thread sends every message on its own deadline, and a status line prints frames sent / failed each second.
- **New senders:** `send_track_apps` (`0x3B2`, Track Apps and turn signals), `send_engine_gauges` (`0x43E`), `send_intake_temp` (`0x42D`), `send_engine_status` (`0x421`), `send_accelerometer` (`0x92`, live counter and checksum, replaces `send_misc_6`).
- **`send_steering` (`0x76`)** now drives the g meter from game acceleration and is scheduled (it wasn't before).
- **`send_warnings_1` (`0x179`)** runs the distance counter from game speed, so game miles add to the odometer. Set `ODOMETER_COUNTS_PER_MILE = 0` to turn this off.
- **`send_tire_pressure` (`0x3B5`)** sends 16 bit kPa from the new tire pressure fields instead of a fixed 30 psi.
- **Turn signals** now work, on `0x3B2`. `icon_left_signal` / `icon_right_signal` `1` is solid, `2` flashes.
- `0x3B3` byte 4 is `0x10` (was `0x18`, which set an unused turn signal bit).
- Fixed the `python-can` startup error: the bus is opened with `interface='slcan'` (was `bustype`).
- New `clamp()` helper, temperature senders clamp to the byte range.

### s550_data.py

- New fields: `icon_check_engine`, `value_afr`, `cylinder_head_temp`, `intake_temp`, `accel_lateral`, `accel_longitudinal`, `accel_vertical`, `tire_pressure_fl` / `_fr` / `_rr` / `_rl`.
- `value_boost` is now mapped: psi, negative is vacuum (gauge range 30 inHg to 20 psi).
- **Warm defaults** so gauges read normal in games that don't report them: oil 100 °C, coolant 110 °C (needle mid gauge), cylinder head 99 °C / 210 °F, inlet air 22 °C / 72 °F, tires 35 psi.
- `accel_*` are the g forces the driver feels (opposite the car's acceleration), which is what the g meter shows.

### Games

- **Forza Horizon 5:** acceleration is mapped to the Track Apps g meter (both axes inverted, tested in game).
- **ATS / ETS2:** acceleration mapped to the g meter (untested). Turn signals use the blinking lamp state (`blinkerLeftOn` / `blinkerRightOn`) instead of the stalk, so the arrows flash.

### interactive_brute_force.py (rewritten)

- Built on `s550_cluster.py`'s scheduler: the full set of cluster messages runs underneath, and the IDs under test are taken over so the cluster never sees them drop out.
- **Test presets** picked on the command line: `afr`, `cht`, `map`, `boost`, `iat`, `oil`, `accel`, `coolant`, `gx`, `gy`, `trackapps`, `trackapps3b2`, `config04`, `config10`.
- **Modes:** `sequential`, `incremental` and `bits` (flips one bit at a time).
- **Keys:** arrows / Enter navigate the cluster menus, space pauses, `+` / `-` step, `r` resets.
- **Options:**

  | Option | Does |
  |---|---|
  | `--gt`, `--gt-only`, `--gt-skip`, `--gt-all` | Send v-ivanyshyn's GT log frames for missing IDs, looping them so counters stay valid |
  | `--dummydata` | Steady chassis messages (`0x217 0x77 0x415 0x85 0x91 0x200 0x82 0x230`), every speed built from one value so Hill Start Assist stays quiet |
  | `--respond [VALUE]`, `--respond-tail`, `--respond-sweep` | Answer the cluster's `0x3E0` startup requests on `0x3E3` / `0x3E6`, prints whether each was accepted or timed out |
  | `--freeze` | Send the freeze frame from this cluster's car for IDs nothing else sends |
  | `--config`, `--vin`, `--config-page` | Send `0x40A` vehicle config pages |
  | `--nm IDS` | Fake "module alive" frames for a range of `0x5xx` IDs |

- **Listens to the cluster:** prints each new ID it sends, writes `cluster_tx.csv` (every ID and value seen) and `cluster_tx_changes.csv` (timeline of every change, with key presses).

### replay.py (rewritten)

- Paces frames off the log timestamps (it used to send as fast as possible), with `--speed` and `--loop`.
- Reads the python-can CSV logs in `/can` (`python replay.py longerdrive`) and v-ivanyshyn's text log format.
- `--only` / `--skip` (ID ranges allowed, e.g. `0x500-0x5FF`), `--set 0x178:7=0x14` to override a byte.
- Skips every ID the cluster sends itself unless `--include-ipc`, so replaying a car log doesn't put two senders on one ID.
- Keys: arrows / Enter navigate, space pauses.

### Added

- `other_refs/v-ivanyshyn_parse_can_logs` submodule: v-ivanyshyn's 2016 GT log (HS1 + HS3) and notes.
- `other_refs/2015GTPremium_FreezeFrame.csv`: one sample of every ID from this cluster's original car.
- `simhub_customserial.shsds`: experimental SimHub Custom Serial Device profile that sends the cluster messages straight to the CAN adapter (slcan). Doesn't keep the cluster working reliably yet, the Python scripts are the supported way to drive it.
- `CHANGELOG.md`.

### database.md

- Reformatted: legend, sources, an index of every ID with its status, and byte tables per ID instead of code blocks.
- Callout that `0x3B3` must be sent first and kept going, or the cluster stays off.
- New sections for everything above, plus the cluster's own transmits and the startup handshake.

### Other

- `requirements.txt`: `pywin32>=306` (was pinned to `==306`).

### Still open

- Startup faults remain: blind spot, cross traffic, steering assist and tire pressure monitor. Those modules' own messages aren't in any log we have.
- Blind spot and cross traffic are greyed out in Driver Assist, and Hill Start Assist can't be toggled.
- No fuel level: the cluster reads it from an analog sender, not CAN.

## [1.0.0]

Everything before this changelog: `s550_cluster.py` driving speed, RPM, temperatures, warning lights and menu
navigation from Forza Horizon 5 and ATS / ETS2, `interactive_brute_force.py`, `replay.py` and the first version of
`database.md`.
