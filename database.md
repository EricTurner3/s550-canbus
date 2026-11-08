# Ford S550 Mustang CAN Database

Vehicles: 2015 Mustang GT Premium (6-speed manual, this cluster's car, FR33-10890-AA) · 2016 Mustang GT350 (6-speed manual, the `/can` logs)

> [IMPORTANT]
> **`0x3B3` must be sent first and kept going.** It wakes the cluster: without it the cluster stays off and ignores
> every other message. Byte 0's upper nibble has to be `4` (e.g. `40 48 02 0A 10 05 00 02`). If it stops, the
> cluster goes back to sleep shortly after. See [0x3B3](#0x3b3---cluster-on-doors-lights-parking-brake).

## Conventions

- Bytes are numbered 0 - 7. Values are hex, multi-byte values are big-endian.
- **Status** on each ID:
  - **Confirmed**: tested on the bench cluster.
  - **From logs**: found by correlating logs against known signals, not tested on the cluster yet.
  - **Cluster sends**: the cluster transmits it itself. Never send it, two senders on one ID cause bus errors.
- Temperatures `raw - 60 = °C` unless noted.

## Sources

| Source | Bus | Notes |
|---|---|---|
| `/can/*.csv` | HS1 (OBD port, through the gateway) | 2016 GT350. Missing 37 IDs the GT has (`0x156 0x166 0x171 0x179 0x331 0x3B5 0x421 0x42D 0x43E` ...), so replaying them on this GT cluster throws warnings |
| `other_refs/v-ivanyshyn_parse_can_logs` | HS1 + HS3 merged | 2016 GT 5.0, 6R80 automatic |
| `other_refs/2015GTPremium_FreezeFrame.csv` | HS-CAN / HS-CAN2 | One sample per ID from this cluster's car |
| `mustang.c` ([ufnalski's project](https://github.com/ufnalski/ford_mustang_cluster_h503rb/blob/main/Core/Src/mustang.c)) | | 2016 Mustang base V6 automatic. Source of `0x3B2` and the `0x76` g meter which enabled TrackApps |

The cluster is on HS3 (DLC pins 12 / 13). It only talks on HS3, so anything it waits for has to come back on HS3.

## Index

| ID | Name | Status | Sent by `s550_cluster.py` |
|---|---|---|---|
| `0x4C` | Airbag / seatbelt indicators | Confirmed | Yes |
| `0x76` | Steering angle, Track Apps g meter | Confirmed | Yes |
| `0x77` | Vehicle speed / yaw | From logs | `--dummydata` |
| `0x81` | Steering wheel buttons | Confirmed | Yes (menu keys) |
| `0x82` | Steering mode | Confirmed | `--dummydata` |
| `0x83` | Clockspring | Confirmed | No |
| `0x85` | Steering wheel angle | From logs | `--dummydata` |
| `0x91` | Yaw rate | From logs | `--dummydata` |
| `0x92` | Accelerometer | From logs | Yes |
| `0x156` | Coolant & oil temp | Confirmed | Yes |
| `0x165` | Brake pedal | From logs | No |
| `0x167` | Engine state / torque / MAP | From logs | Yes |
| `0x178` | Launch control / ABS indicators | Confirmed | Yes |
| `0x179` | Warning suppression, distance counter | Confirmed | Yes |
| `0x200` | Engine torque | From logs | `--dummydata` |
| `0x202` | Speed gauge | Confirmed | Yes |
| `0x204` | RPM gauge, pedal | Confirmed | Yes |
| `0x217` | Wheel speeds | From logs | `--dummydata` |
| `0x230` | Gear position | From logs | `--dummydata` |
| `0x331` | Climate / outside temp? | From logs | No |
| `0x3B2` | Track Apps, turn signals | Confirmed | Yes |
| **`0x3B3`** | **Cluster on (required, send first)**, doors, lights, parking brake | Confirmed | Yes |
| `0x3B5` | Tire pressure | Confirmed | Yes |
| `0x3C3` | High beams, parking brake | Confirmed | Yes |
| `0x3C8` | Drive mode, MyColor | Cluster sends | No |
| `0x3E0` / `0x3E3` / `0x3E6` | Startup requests / replies | Confirmed | `--respond` |
| `0x40A` | VIN / vehicle config | From logs | `--config` |
| `0x415` | Vehicle speed / yaw | From logs | `--dummydata` |
| `0x416` | ABS / traction control icons | Confirmed | Yes |
| `0x421` | Oil pressure status, check engine | Confirmed | Yes |
| `0x422` | Coolant temp | From logs | No |
| `0x42D` | Inlet air temp | Confirmed | Yes |
| `0x430` | Odometer | Cluster sends | No |
| `0x431` | Transmission warnings | Confirmed | No |
| `0x43E` | AFR, cylinder head temp, boost / vacuum | Confirmed | Yes |
| `0x453` | Seat occupant sensor serial | From logs | No |
| `0x454` | Airbag module serial | From logs | No |
| `0x4B0` | Braking pressure? | From logs | No |
| `0x5xx` | Module alive frames | From logs | Yes (`0x581 0x596 0x59E 0x5B3 0x5B5`) |

---

# Cluster (IPC) Transmits

**Status:** Cluster sends · captured on the bench with `interactive_brute_force.py` (`cluster_tx.csv`, `cluster_tx_changes.csv`)

Only `0x18B 0x350 0x3C8 0x3E0 0x430 0x434` show up in the HS1 logs (passed through the gateway), the rest are HS3 only. `replay.py` skips all of these unless `--include-ipc`.

**Once at power up** (all zeros unless noted), possibly wake up / enable requests to other modules:
`0x087` `0x123` `0x190` (`00 00 00 00 FF 00 00 00`) `0x193` `0x195` `0x1EE` `0x1F2` `0x1F8` `0x1F9` `0x1FA` `0x1FB` `0x1FC` `0x363` (`00 3C 00 ...`)

**~1 Hz**

| ID | Data | Notes |
|---|---|---|
| `0x18B` | `00 00 00 1E 00 00 00 00` | GT350 log: `00 00 0A 0A ...` |
| `0x19A` | `00 00 00 02 40 00 00 00` | |
| `0x220` | `10 01 00 00 00 00 00 00` | Changes to `08 01 ...` in step with `0x2F4`. Same payload twice, left / right blind spot sensors? (the service manual says the cluster sends them an enable request) |
| `0x2F4` | `10 01 00 00 00 00 00 00` | See `0x220` |
| `0x225` | `20 81 00 00 00 00 00 00` | Byte 2 `0x80` for the first 5 s after power up |
| `0x2FD` | `0C 00 C2 00 00 00 00 00` | |
| `0x313` | `00 ...` | v-ivanyshyn: byte 5 grows with speed, odometer? |
| `0x316` | `00 ...` | |
| `0x317` | `03 FE 00 00 00 00 00 00` | |
| `0x318` | `00 ...` | v-ivanyshyn: bytes 5 & 6 slowly decrease during a drive, fuel in tank? |
| `0x350` | `00 ...` | Byte 0 `0x40` at times (also in `start.csv`) |
| `0x353` | `00 00 00 00 00 05 10 13` | Bytes 4 & 5 `0x03E7` (999) once, then 5 → 0. Distance to empty? (no fuel sender on the bench, the cluster shows Fuel Level Low) |
| `0x3C8` | | MyColor / drive mode, see [0x3C8](#0x3c8---drive-mode-mycolor) |
| `0x3E0` | `00 00 00 00 80 00 00 00` | Startup requests, see [0x3E0](#0x3e0--0x3e3--0x3e6---startup-requests-and-replies) |
| `0x3FB` | `00 ...` | |
| `0x45A` | `00 ...` | |
| `0x591` | `91 00 FF FF FF FF FF FF` | The cluster's own "module alive" frame, same pattern as the other `0x5xx` |

**~5 - 13 Hz**

| ID | Data | Notes |
|---|---|---|
| `0x287` | `00 ...` | |
| `0x30A` | `D7 00 00 00 00 00 00 00` | |
| `0x315` | | Bytes 6 & 7 `0x08xx`, change every frame. v-ivanyshyn: follows the pedal with some delay |
| `0x346` | `00 00 00 03 03 00 C0 00` | |
| `0x348` | `00 ...` | |
| `0x430` | | Odometer, see [0x430](#0x430---odometer) |
| `0x434` | `40 00 10 00 28 FF F0 00` | |

# 0x3E0 / 0x3E3 / 0x3E6 - Startup Requests and Replies

**Status:** Confirmed · `interactive_brute_force.py --respond`

About 0.8 s after start the cluster asks the other modules on HS3 to answer, one request at a time on `0x3E0`. Each module answers on its own ID. Idle frames on all of these are `00 00 00 00 80 00 00 00`.

| Frame | Layout |
|---|---|
| Request (`0x3E0`) | `04 xx 00 00 84 00 00 00`, `xx` = `01 03 04 05 07 0D 10 11` in that order |
| Reply | `00 01 04 xx 80 00 00 00` on the module's ID. Byte 1 `0x01` = OK / present |

| Request | Answered on | Notes |
|---|---|---|
| `04 01` `04 03` `04 04` `04 05` `04 0D` `04 10` `04 11` | `0x3E3` | HS3 only (v-ivanyshyn's GT log, freeze frame `00 01 04 11 80 01 64 00`). `0x3E3` takes all of them on the bench |
| `04 07` | `0x3E6` | `start.csv`: answered 7 ms after the request, then held. Power steering module? A one off STEERING FAILURE showed while sweeping its byte 1 |

- In a car each request is held ~40 - 60 ms. Unanswered, the cluster repeats it every ~1 - 2 s and gives up after 5 s, then sends `07 01` (never seen in a car).
- Byte 1 `0x02 - 0x07` time out for every request except `04 0D`, which takes anything.
- Other IDs in the same family: `0x3DF` `0x3E2` (idle frames), `0x3EB` `02 04 14 00 00 20 ..` (different layout), freeze frame `0x3E1` `80 00 00 07 01 80 00 00`, `0x3DA` `01 64 00 ..` (GT log all zeros).
- Answering every request doesn't clear the startup faults (blind spot, cross traffic, steering assist, tire pressure monitor). Those modules' own messages aren't in any log.

---

# 0x4C - Airbag / Seatbelt Indicators

**Sample:** `10 AF FF 00 00 00 00 00` · **Status:** Confirmed

| Byte | Signal | Values |
|---|---|---|
| 0 | Airbag indicator | `0x0_` off, `0x4_` on, `0x8_` flashing |
| 1 | Seatbelt icon | `0x00` no icon, `0xAF` both undone, `0x5F` both on, `0x6F` driver only on, `0x9F` passenger only on |

# 0x76 - Steering Angle, Track Apps G Meter

**Sample:** `3E 80 C0 00 80 00 00 00` · **Rate:** 50 Hz · **Status:** Confirmed

| Bytes | Signal | Encoding |
|---|---|---|
| 0 - 1 | Steering angle | `0x3E80` most common (center). Follows lateral g in turns (r ~0.6 against `0x92`) |
| 2 | G meter x, lateral | `16 + g * 8`, ±1.5 g. `0x1C` full right, `0x10` center, `0x04` full left |
| 3 - 4 | G meter y, longitudinal | `1024 + g * 512`, ±1.5 g. `0x0700` full accel, `0x0400` center, `0x0100` full brake |
| 5 - 7 | | `00` |

- The g meter is the red dot on the Track Apps accelerometer screen. Encoding from `mustang.c` (commented "tested for JR3T"), confirmed on this cluster with the `gx` / `gy` presets.
- The dot shows the force the driver feels: a hard right turn puts it on the left. Game acceleration goes in with its sign flipped (tested in Forza, both axes).
- Every 2015 - 2017 log has `C0 00 80` in bytes 2 - 4 (`drive.csv` also `80` / `40` in byte 2, `00` in byte 4), off that scale. The old fixed frame `3E 83 C0 00 00 ..` pinned the dot in the top left corner.

# 0x77 - Vehicle Speed / Yaw

**Sample:** `18 3B 08 00 7F F7 E5 E5` · **Status:** From logs

| Bytes | Signal | Encoding |
|---|---|---|
| 0 - 1 | Vehicle speed | 14 bit (mask byte 0 with `0x3F`), `MPH * 175`, same as `0x202` |
| 2 - 3 | Yaw rate / lateral accel | 12 bit, center `0x0800`. Tracks the left / right wheel speed difference in turns |
| 6 | Hill Start Assist Not Available | `0x_C` shows it, `0x_6` hides it (`s550_cluster.py` sends `0xE6`) |

- In the GT and GT350 logs byte 6's low nibble changes constantly (part of a value with byte 7, tracks the pedal), so replaying a log makes the warning come and go.

# 0x81 - Steering Wheel Buttons

**Sample:** `00 00 00 00 00 00 00 00` · **Status:** Confirmed

| Byte | Value | Button |
|---|---|---|
| 1 | `0x01` | Down |
| 1 | `0x02` | Left |
| 1 | `0x04` | Right |
| 1 | `0x08` | Up |
| 1 | `0x10` | OK |

# 0x82 - Steering Mode

**Sample:** `82 00 14 40 7E 00 64 FF` · **Status:** Confirmed (byte 6)

| Bytes | Signal | Values |
|---|---|---|
| 2 - 3 | Fuel consumption? | |
| 6 | Steering mode | `0x40` normal, `0x44` sport, `0x48` comfort |

# 0x83 - Clockspring

**Sample:** `00 E0 80 00 00 00 00 00` · **Status:** Confirmed

| Byte 0 | Byte 4 | Meaning |
|---|---|---|
| `00` | `00` | High beams off |
| `40` | `08` | Flash high beams |
| `00` | `10` | High beam switch activated |
| `80` | `00` | High beams on |

- Byte 0 also follows the turn signal lever (`10` left, `20` right, added to the above, e.g. `50` = left + flash), but this doesn't light the turn signal indicators.

# 0x85 - Steering Wheel Angle

**Sample:** `79 E0 80 00 61 30 7C C6` · **Status:** From logs

| Bytes | Signal | Encoding |
|---|---|---|
| 0 - 1 | Steering wheel angle | Unsigned with offset, center ~`0x7CD3` (31955). ~27350 - 36520 seen driving (±4600). Likely 0.1° per bit (±460°, about lock to lock). Increases with yaw |
| 5 (upper nibble) | Rolling counter | `+0x10` per frame |

- Confirm the direction by turning the wheel left while parked.

# 0x91 - Yaw Rate

**Sample:** `7E F3 7F 3D 63 6B F0 00` · **Status:** From logs

| Bytes | Signal | Encoding |
|---|---|---|
| 0 | Heartbeat? | Toggles `7E` / `7F` about once a second in every log |
| 2 - 3 | Yaw rate | 16 bit, ~`0x7F3D` going straight. Correlates with the wheel speed difference and `0x85` |

# 0x92 - Accelerometer

**Sample:** `6F B0 6F E8 73 5C DB F6` · **Rate:** 100 Hz (GT350) · **Status:** From logs

Doesn't move the Track Apps g meter dot (that's `0x76`), but the car sends it and `s550_cluster.py` does too.

| Bytes | Signal | Encoding |
|---|---|---|
| 0 - 1 | Lateral | 13 bit, `(m/s² + 40) * 100`. `0x6FB0` = 0.16 at rest. Which side is positive isn't confirmed |
| 2 - 3 | Longitudinal | Same, positive speeding up. `0x6FE8` = 0.72 at rest |
| 4 - 5 | Vertical | Same, `0x735C` = 9.56 at rest (gravity), 9.6 - 9.7 in every log |
| 0, 2, 4 (top 3 bits) | Valid | `0b011` (`0x6_`). `0b001` with `0x1FFF` (41.9) for ~1 s at key on in `start.csv` |
| 6 | Checksum | All 8 bytes add up to `0x16` (15,640 of 15,640 frames, GT350 and GT) |
| 7 | Counter | `+5` every frame |

Checked against every log (`0x202` speed, `0x91` yaw):

| Check | Result |
|---|---|
| Longitudinal vs change in speed | `longerdrive` r = 0.96, slope 1.00 (scale exact) · `drive` 0.72 · v-ivanyshyn 0.90 |
| Reverse (`reverse.csv`) | Sign flips (r = -0.61, slope -0.98), so the axis is the car's, not the direction of travel |
| Lateral vs speed × yaw rate | `longerdrive` 0.93 · `longerdrive2` 0.90 · `drive` 0.87 |
| Re-encoding `longerdrive` | All 15,037 frames reproduced byte for byte |

- Ranges: `longerdrive` -2.8 to 4.8 lateral, -3.2 to 3.9 longitudinal. v-ivanyshyn -5.2 to 6.7 longitudinal.

# 0x156 - Coolant & Oil Temp Gauge

**Sample:** `9E 99 00 00 03 00 00 00` · **Status:** Confirmed

| Byte | Signal | Encoding |
|---|---|---|
| 0 | Coolant temp (needle under the RPM gauge) | `raw - 60 = °C` (`0xA0` = 100 °C / 212 °F). Needle starts moving ~`0x80`, sits mid gauge from ~`0xA6` (106 °C) to `0xC0` (132 °C), then ramps up quickly and can trigger the overheat warning |
| 1 | Oil temp (Gauge Mode > Oil Temp) | `raw - 60 = °C`. Moves from `0x60` (36 °C), caps around `0xDA` (158 °C) |
| 4 | Overheat | `0x03` normal, `0x08` overheat message and max needle (a high byte 0 also triggers it) |

- The mid gauge hold is likely intended, Ford buffers the coolant needle across the normal range.
- Never in the GT350 logs, the car seems to send coolant temp on `0x422` byte 3 instead.

# 0x165 - Brake Pedal

**Sample:** `20 40 00 00 00 00 00 00` · **Status:** From logs

| Byte | Released | Pressed |
|---|---|---|
| 0 | `0x20` | `0x10` |
| 4 | `0x00` | `0x10` (average -2.5 mph/s while set in `longerdrive.csv`) |

- Also visible in `lights.csv` at 80 - 92 s (brake pumped for the brake lights) and in `0x242` byte 2 (`0xA0` / `0x20`).

# 0x167 - Engine State / Torque / Manifold Pressure

**Sample:** `72 7F 4B 00 00 1A ED 00` · **Rate:** 100 Hz · **Status:** From logs

| Bytes | Signal | Encoding |
|---|---|---|
| 0 | Engine state | `0x00` off, `0x20` starting, `0x72` running |
| 1 - 2 | Torque | `(((b1 - 128) << 8) + b2) / 4` per v-ivanyshyn. Byte 1 is `0x7F - 0x83` in the GT350 logs |
| 5 - 6 | Manifold absolute pressure | 0.2 kPa per bit. Atmospheric ~`0x1B3A`, vacuum kPa = `(0x1B3A - raw) / 5` |

| MAP reading | Raw | Vacuum |
|---|---|---|
| Cranking (atmospheric) | `0x1B3F` | 0 |
| Idle | `0x19F0` | ~66 kPa / 19.5 inHg (~35 kPa absolute) |
| Decel / coasting | `0x199F` | ~82 kPa / 24 inHg |
| Heavy pedal | `0x1B05` | ~10 kPa |

- Same behavior in the GT350 and GT logs. Pressure, not airflow: at a fixed pedal the value drops as rpm rises. Frozen once the engine is off.
- v-ivanyshyn's formula `(((b5 - 25) << 8) + b6 - 128) / 5` has the right scale, absolute kPa depends on altitude. Absolute kPa ≈ `(raw - 0x1940) / 5` if the GT350 logs were near sea level.
- Doesn't drive the cluster's boost / vacuum gauge, that's `0x43E` bytes 5 & 6.

# 0x178 - Launch Control / ABS Indicators

**Sample:** `00 00 02 00 0E 88 C6 86` · **Status:** Confirmed

| Byte | Value | Meaning |
|---|---|---|
| 0 | `0x2_` | Launch control icon |
| 0 | `0x8_` | RPM icon, launch control fault |
| 0 | `0xA_` | Launch control icon flashing |

- Bytes 5 & 7 track temperature in the GT350 logs, but sweeping them changed nothing on the cluster (outside temp and inlet air temp included, the IAT gauge is `0x42D`).

# 0x179 - Warning Suppression, Distance Counter

**Sample:** `00 00 00 00 96 00 02 C8` · **Status:** Confirmed

| Byte | Signal | Notes |
|---|---|---|
| 4 | | `0x4E` constant in the GT log |
| 5 | Distance counter | 8 bit, wraps at 256. ~8767 counts per mile (~0.18 m per count), using the `0x202` speed scale. Still when stopped |
| 6 - 7 | Second counter | Wraps at 3000 (max `0xBB6`). Runs at idle and faster with rpm / load (corr 0.78 with rpm × load), likely fuel used. Units unknown |

- Sending this frame turns off warnings like fuel service inlet, change oil soon and oil change required. Which bit does which isn't known.
- The distance counter drives the odometer. Replaying the GT log made it count up by tenths and the cluster saved it. Mileage only goes up, the trip meters can be reset from the menu to track game distance.
- Not in the GT350 logs (HS1).

# 0x200 - Engine Torque

**Sample:** `00 00 7F 9D 81 5A 00 00` · **Status:** From logs

| Bytes | Signal | Encoding |
|---|---|---|
| 2 - 3 | Actual / delivered torque? | Signed, offset `0x8000` |
| 4 - 5 | Requested torque? | Signed, offset `0x8000`. Rises with the pedal (corr 0.91 with `0x204` pedal) |

- The two are equal when coasting / off throttle.

# 0x202 - Speed Gauge

**Sample:** `00 FA 10 00 60 00 00 00` · **Status:** Confirmed

| Bytes | Signal | Encoding |
|---|---|---|
| 4 | | Upper nibble must be `6` or the gauge doesn't work |
| 6 - 7 | Speed | `MPH * 175` |

# 0x204 - RPM Gauge

**Sample:** `C0 00 7D 01 4B 00 00 00` · **Status:** Confirmed (RPM), from logs (pedal)

| Bytes | Signal | Encoding |
|---|---|---|
| 0 - 1 | Accelerator pedal | 10 bit (mask byte 0 with `0x03`). `0x000` off throttle, max seen `0x2C0` (704), possibly 0.1% per bit |
| 3 - 4 | RPM | Half the actual RPM, gauge 0 - 4000. 5000 RPM → 2500 (`09 C4`) |

# 0x217 - Wheel Speeds

**Sample:** `13 D0 13 CC 13 C8 13 D0` · **Status:** From logs

| Bytes | Signal | Encoding |
|---|---|---|
| 0 - 1 | Wheel 1 (FL?) | 13 bit (mask the high byte with `0x1F`), low 2 bits always 0. raw ≈ `MPH * 144` |
| 2 - 3 | Wheel 2 (FR?) | Same |
| 4 - 5 | Wheel 3 (RL?) | Same |
| 6 - 7 | Wheel 4 (RR?) | Same |

- Order is likely FL, FR, RL, RR: when `0x85` steering is above center, wheels 2 & 4 run faster than 1 & 3.
- Wheel speeds that don't agree with vehicle speed (`0x202` / `0x77` / `0x415`) make Hill Start Assist Not Available flash.

# 0x230 - Gear Position

**Sample:** `30 1C 00 00 55 00 00 00` · **Status:** From logs

| Byte | Signal | Values |
|---|---|---|
| 0 (upper nibble) | Current gear (manual) | `0x1_` 1st (RPM/MPH ~168), `0x2_` 2nd (~115), `0x3_` 3rd (~83), `0x4_` 4th (~64), `0x5_` 5th (~50), `0xF_` neutral / clutch in / unknown |
| 1 | Reverse | `0x1C` not in reverse, `0x02` reverse (`reverse.csv`) |
| 4 | Oil or transmission temp? | `raw - 60 = °C`, ~14 °C at cold start, ~37 °C after the drive |

# 0x331 - Climate / Outside Temp?

**Sample:** `C0 29 A6 C5 02 9B 0C 02` · **Rate:** ~1 Hz · **Status:** From logs (v-ivanyshyn's GT log)

| Bytes | Signal | Encoding |
|---|---|---|
| 2 - 3 | Counter | +1 every second (not a temperature) |
| 4 - 5 | Outside air temp? | 10 bit (mask byte 4 with `0x03`), `raw * 0.25 - 128 = °C` (Ford's usual ambient scale). `0x029B` = 38.75 °C / 102 °F, constant through the log. Untested |
| 7 | | `4` / `2` with ambient light or headlights on / off (per v-ivanyshyn) |

- Bytes 0, 1, 6 constant in the log. Not in the GT350 logs, likely only on cars with automatic climate control.

# 0x3B2 - Track Apps, Turn Signals

**Sample:** `40 00 00 12 10 00 00 02` · **Status:** Confirmed

Sending this alongside `0x3B3` makes Track Apps show on this 2015 cluster (FR33). From `mustang.c`, built on a 2016 Mustang, so it's a 2015 - 2017 message, but it isn't in any of our logs or the freeze frame.

| Byte | Signal | Values |
|---|---|---|
| 0 | Activate | `0x40`. `0x41` shows Trunk Ajar (same as `0x3B3`). Other values don't turn the cluster off, `0x3B3` keeps it on |
| 3 | Backlight (`mustang.c`) | `0x0B` night, `0x10` day |
| 4 | Track Apps / right turn | Bit `0x10` Track Apps (`mustang.c`), bit `0x08` right turn signal (confirmed, `40 00 00 12 18 00 00 02`) |
| 5 | Cluster backlight (`mustang.c`) | `0` day, `5` night |
| 6 | Left turn | Bit `0x40` (`mustang.c`) |
| 7 | | `0x02` |

- `mustang.c` splits its code by cluster part number prefix: FR33 (this cluster) gets `0x3B3` then `0x3B2`, GR3T / JR3T get `0x3B2` alone (byte 0 `0x40` activates them).
- Bit `0x08` in `0x3B3` byte 4 does nothing, the turn signals only work here. `s550_cluster.py` sends them on `0x3B2` and `0x3B3` byte 4 as `0x10` like the logs.

# 0x3B3 - Cluster On, Doors, Lights, Parking Brake

**Sample:** `40 88 00 12 10 00 80 02` · **Status:** Confirmed

> [!IMPORTANT]
> **The cluster's wake-up message.** Without it the cluster doesn't boot and ignores everything else, and it goes back
> to sleep shortly after it stops. Send it first and keep it going (`s550_cluster.py` sends it at 2.5 Hz).
> Byte 0's upper nibble must be `4`, anything else turns the cluster off.

| Byte | Signal | Values |
|---|---|---|
| 0 | Cluster on / headlamps | Upper nibble must be `4` or the cluster turns off. `40` headlamps off, `44` on, `41` trunk ajar |
| 1 | Light mode | `48` DRL, `88` night, `4A` hazard |
| 3 | Backlight | `0x00` off, `0x0A` on (MyColor), `0x10` on (white), `0x0_` dims / `0x9_` brightens. In the logs the dash dimmer, `0x01 - 0x0C` (`run_light_dim_up` / `_down`) |
| 6 | Parking brake | `0x80` / `0xC0` on, `0x00` off |
| 7 | Doors | First digit `0` closed, `1` passenger ajar, `2` driver ajar, `3` both. Second digit `2` closed, `A` hood ajar. `02` all closed, `32` both doors open, `2A` driver + hood |

- `40 48` = running, doors closed, lights off. `41 48` = running, trunk ajar.
- Flipping every other bit one at a time changed nothing visible (`trackapps` preset).

Turn signals in the logs (`run_left_turn` / `run_right_turn` / `run_hazards`), OR'd into the bytes above. On the bench they don't light the arrows, use `0x3B2`:

| Side | Byte / bit | Meaning |
|---|---|---|
| Left | 1 / `0x02` | Lamp lit (flashes) |
| Left | 1 / `0x01` | Stalk active (held while signaling) |
| Left | 6 / `0x40` | Lamp lit (flashes with byte 1 bit `0x02`) |
| Right | 4 / `0x08` | Lamp lit (flashes) |
| Right | 7 / `0x40` | Stalk active |
| Right | 7 / `0x80` | Lamp lit (flashes with byte 4 bit `0x08`) |

```
Hazards on   44 8A C6 0C 18 00 C0 82
Hazards off  44 88 C6 0C 10 00 80 02
```

# 0x3B5 - Tire Pressure

**Sample:** `00 CE 00 CE 00 CE 00 CE` · **Status:** Confirmed · Credit [v-ivanyshyn](https://github.com/v-ivanyshyn/parse_can_logs/blob/master/Ford%20CAN%20IDs%20Summary.md)

| Bytes | Tire | Encoding |
|---|---|---|
| 0 - 1 | Front left | 16 bit kPa (`0x00CE` = 206 kPa shows 30 psi) |
| 2 - 3 | Front right | Same |
| 4 - 5 | Rear right | Same |
| 6 - 7 | Rear left | Same |

| Source | Frame | psi |
|---|---|---|
| Freeze frame (this cluster's car) | `00 FE 01 01 00 F2 00 EE` | 37 37 35 35 |
| v-ivanyshyn's GT | `00 C1 00 BA 00 85 00 C6` | 28 27 19 29 (the 19 psi tire is likely why `--gt` showed Tire Low) |

# 0x3C3 - High Beams, Parking Brake

**Sample:** `40 00 10 00 00 00 80 00` · **Status:** Confirmed

| Byte | Signal | Values |
|---|---|---|
| 0 | High beams | `0x_C` off, `0x_E` on. Upper nibble `4` / `5` unknown |
| 1 | Dimming? | Upper nibble `0 4 8 C`, lower `C D 8` |
| 2 | Parking brake | `0x0_` off, `0x1_` on |
| 3 | | Parking brake on / brake fluid level low warning |
| 6 | | `0x00` / `0x80`, unknown |

# 0x3C8 - Drive Mode, MyColor

**Sample:** `55 32 00 01 53 20 00 00` (GT log), `05 11 70 00 11 15 3C 00` (this cluster) · **Rate:** ~1 Hz · **Status:** Cluster sends

The cluster is the source of the MyColor / drive mode settings. Don't send it.

| Bytes | Signal | Values |
|---|---|---|
| 0, 4, 5 | MyColor RGB | per v-ivanyshyn |
| 2 | Drive mode | `0` normal, `1` sport, `2` snow, `3` track (per v-ivanyshyn). `0x70` from this cluster on the bench |

# 0x40A - VIN / Vehicle Config

**Sample:** `C1 00 31 46 41 36 50 38` · **Rate:** one page every 0.2 s · **Status:** From logs · `interactive_brute_force.py --config` (`--vin` for the VIN pages)

Sent by the body control module (BCM), it's the vehicle config the other modules check their features against. Multiplexed, byte 1 is the page.

| Page | Contents |
|---|---|
| `C1 00` | VIN characters 1 - 6, ASCII in bytes 2 - 7 |
| `C1 01` | VIN characters 7 - 12 |
| `C1 02` | VIN characters 13 - 17, byte 7 `FF` |
| `C1 04` | BCM as-built block 726-12 |
| `C1 10` | BCM as-built block 726-13 |
| `C0 00` | Bytes 3 - 6, 32 bit counter, 10 counts a second |

- Car order: `C1 02`, `C1 04`, `C1 10`, `C0 00`, `C1 00`, `C1 01`, each page every 1.2 s.
- The as-built pages leave out each as-built line's last byte, which is a checksum:
  ```
  726-12-01 0163 0827 5528 + 726-12-02 C102  ->  C1 04 01 63 08 27 55 C1
  726-13-01 4088 2024 80CD + 726-13-02 0042  ->  C1 10 40 88 20 24 80 00  (matches the freeze frame)
  ```

| Car | `C1 04` | `C1 10` | VIN positions 6 - 7, 10 |
|---|---|---|---|
| This cluster's car (2015 GT Premium, manual) | `01 63 08 27 55 C1` | `40 88 20 24 80 00` | `CF` / `F` (GT 5.0, 2015) |
| GT350 logs (manual) | `01 75 08 44 55 C2` | `40 88 20 24 80 00` | `JZ` / `G` (GT350 5.2, 2016) |
| v-ivanyshyn's GT (6R80 auto) | `01 3B 08 27 55 C1` | `40 88 20 25 00 00` | `CF` / `G` (GT 5.0, 2016) |

- The two manuals share `C1 10`, the auto differs in bytes 5 & 6 (`24 80` / `25 00`), transmission type? `C1 04` differs on all three. The VIN doesn't carry the transmission.

# 0x415 - Vehicle Speed / Yaw

**Sample:** `17 FF EC DB 07 FD 07 FD` · **Status:** From logs

| Bytes | Signal | Encoding |
|---|---|---|
| 0 - 1 | Vehicle speed | 14 bit (mask byte 0 with `0x3F`), `MPH * 175`, same as `0x202` |
| 4 - 5, 6 - 7 | Yaw rate / lateral accel | 12 bit, center `0x0800`, usually identical |

# 0x416 - ABS / Traction Control Icons

**Sample:** `50 00 FE 00 01 00 00 00` · **Status:** Confirmed

| Byte | Signal | Values |
|---|---|---|
| 1 | Warnings | `0x2_` Check Brake System, `0x4_` AdvanceTrac System Warning |
| 5 | Traction control | `0x00` off, `0x02` solid, `0x0F` flashing, `0x80` TC off, `0x18` ATC off |
| 6 | ABS | `0x0_` off, `0x4_` solid, `0x8_` slow flash, `0xD_` fast flash |

- In v-ivanyshyn's GT log bytes 0 and 2 change every frame (rolling counter, e.g. `50 00 FE` / `51 00 FD`). `s550_cluster.py` sends it frozen.

# 0x421 - Oil Pressure Status, Check Engine Light, Engine Shutdown Messages

**Sample:** `00 00 50 00 00 00 4D 00` · **Rate:** ~5 Hz · **Status:** Confirmed

| Byte | Signal | Values |
|---|---|---|
| 0 | Check engine light | `0x04` solid, `0x08` flashing. `0x01`, `0x02`, `0x10` and up no change |
| 1 | Engine shutdown messages | `0x01` "Engine shutoff in 30s", `0x02` "Engine has shut off for fuel economy" (auto start-stop) |
| 2 | Flags? | `0x50` / `0x58` in the GT log |
| 6 | | Moves `0x3D - 0x70` during the drive, unknown |

- Sending this at all changes Gauge Mode > Oil Pressure from "Low" (with a warning) to "Normal", missing `0x421` is treated as a fault. Flipping each of the 64 bits never changed it off Normal.
- The GT has an oil pressure switch, not a sender, so there's no radial gauge, only the status text.
- Not in the GT350 logs.

# 0x422 - Coolant Temp

**Sample:** `00 00 00 9A 38 40 FE 00` · **Status:** From logs

| Byte | Signal | Encoding |
|---|---|---|
| 3 | Coolant temp | `raw - 60 = °C` like `0x156`. `0x4B` (15 °C) at cold start, rising every few seconds to ~`0x9C` (96 °C). Frozen while the engine is off |

# 0x42D - Inlet Air Temp

**Sample:** `00 02 91 00 00 00 F0 00` · **Rate:** ~2 Hz · **Status:** Confirmed

| Bytes | Signal | Encoding |
|---|---|---|
| 1 - 2 | Inlet air temp | 10 bit (mask byte 1 with `0x03`), `raw * 0.25 - 128 = °C` (same scale as `0x331`) |

| Raw | °C | °F |
|---|---|---|
| `0x17C` | -33 | -27 |
| `0x19C` | -25 | -13 |
| `0x1BC` | -17 | 1 |
| `0x214` | 5 | 41 |
| `0x291` | 36.25 | 97 |

- Radial gauge 0 - 240 °F (raw ~`0x1B9 - 0x3CE`), the text readout also shows negatives.
- Falls from `0xB3` to `0x87` over v-ivanyshyn's drive as the heat soaked intake cools. Not in the GT350 logs.

# 0x430 - Odometer

**Sample:** `37 01 B9 AA C0 5E 37 5C` · **Rate:** ~10 Hz · **Status:** Cluster sends

| Bytes | Signal | Encoding |
|---|---|---|
| 1 - 3 | Odometer | km |

- The cluster is the odometer's source. This cluster sends `84 01 B9 7E 00 00 04 00` (`0x01B97E` = 112,990 km / 70,209 mi). Sending it from another device puts two senders on one ID.
- It doesn't take arbitrary values, a mileage not close to what's stored shows `-------`.
- Bench changes: byte 0 `0x84` / `0x04`, byte 6 `0x24` / `0x64` / `0xA4` / `0xE4` (byte 6 changed right after an Enter press in the menu).

# 0x431 - Transmission Warnings

**Sample:** `05 1D 40 EB B7 83 46 00` · **Status:** Confirmed

Controls these warning messages: Transmission Adaptive Mode, Transmission Indicator Mode, Transmission Warming Up, Transmission Adjusted.

# 0x43E - Air Fuel Ratio, Cylinder Head Temp, Boost / Vacuum

**Sample:** `00 93 10 8B 9D 31 30 00` · **Rate:** ~13 Hz · **Status:** Confirmed

With `0x43E` and `0x42D` sent, the AFR, boost / vacuum, cylinder head temp and inlet air temp gauges are populated, without them they're blank. Replaying the GT log shows ~14 AFR and ~207 °F head temp.

| Bytes | Signal | Encoding |
|---|---|---|
| 1 | | `0x93` constant (147 = 14.7 stoichiometric) |
| 3 | Air fuel ratio | `raw / 10`. `0x8A - 0x90` (13.8 - 14.4) idle, `0x74 - 0x7C` (11.6 - 12.4) wide open throttle, `0xB9` (18.5) decel |
| 4 | Cylinder head temp | `raw - 60 = °C`. Gauge 140 - 340 °F (60 - 171 °C, raw `0x78 - 0xE7`). `0x9D` (97 °C / 207 °F) in the GT log, drifting down to `0x9B` over the drive |
| 5 - 6 | Boost / vacuum | 13 bit, `(b5 << 8 \| b6) >> 3` (byte 6 low 3 bits always 0). Gauge kPa = `value * 0.1 - 206.9`, negative is vacuum. Zero is raw `0x40A8` |

Boost / vacuum gauge is 30 inHg vacuum (raw ~`0x20E8`) to 0, then 0 to 20 psi (raw ~`0x6BB8`) on the same needle. inHg = `-kPa / 3.386`, psi = `kPa / 6.895`. Readings on the cluster, all within 0.1 of the formula:

| Raw | Reading |
|---|---|
| `0x2700` | 24.3 inHg |
| `0x3000` | 15.8 inHg |
| `0x3130` | 14.6 inHg |
| `0x3C00` | 4.4 inHg |
| `0x4300` | 1.1 psi |
| `0x4600` | 2.5 psi |
| `0x5400` | 9.0 psi |

- Tracks `0x167` MAP (corr 0.94). Only `0x2A00 - 0x4200` in the GT log (NA engine, vacuum side).
- v-ivanyshyn reads it as engine load %, `(b5 << 8 | b6) / 72 - 140`.
- Not in the GT350 logs.

# 0x453 - Seat Occupant Sensor Serial Number

**Sample:** `30 39 4E 37 20 70 42 15` · **Status:** From logs

| Bytes | Signal | Encoding |
|---|---|---|
| 0 - 3 | First 4 characters | ASCII (`"09N7"`) |
| 4 - 7 | Last 8 digits | BCD (`20 70 42 15` → `"20704215"`). The 4 characters in between aren't sent |

- The occupant classification sensor's serial (DID F18C in the as-built, node 765, part 603B16). GT350 logs: `33 39 53 45 20 70 53 48` (`"39SE"` .. `"20705348"`), same layout.
- Likely for the airbag module to check its paired seat sensor, not something the cluster checks.

# 0x454 - Airbag Module Serial Number

**Sample:** `37 30 30 32 35 37 38 32` · **Status:** From logs

| Bytes | Signal | Encoding |
|---|---|---|
| 0 - 7 | First 8 characters | ASCII (`"70025782"`) |

- The restraints control module's serial (DID F18C, node 737). GT350 logs: `"70117912"`.
- No other module's serial (blind spot 7C4 / 7C6, power steering 730, ABS 760 ...) shows up in any log or the freeze frame.

# 0x4B0 - Braking Pressure?

**Sample:** `95 00 80 00 D0 00 00 F2` · **Rate:** ~50 Hz · **Status:** From logs (v-ivanyshyn's GT log), untested

| Byte | Signal | Encoding |
|---|---|---|
| 4 | Rolling counter | Upper nibble `+0x10` every frame |
| 5 - 6 | Braking pressure | per v-ivanyshyn |
| 7 | Checksum | Counts down by 1 as byte 4 counts up (`00`/`FF`, `10`/`FE`, `20`/`FD`) |

- Not in the GT350 logs.

# 0x5xx - Module Alive Frames

**Sample:** `81 00 FF FF FF FF FF FF` · **Rate:** ~1 Hz · **Status:** From logs

| Byte | Value |
|---|---|
| 0 | Low byte of the ID (`0x581` → `81`) |
| 1 | `00` |
| 2 - 7 | `FF` |

- `s550_cluster.py` sends `0x581 0x596 0x59E 0x5B3 0x5B5`. The cluster's own is `0x591`.
- Faking all of `0x500 - 0x5FF` (`--nm`) changed nothing.
