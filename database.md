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
  - **APIM sends**: same, for the bench APIM (SYNC). See [APIM (SYNC)](#apim-sync).
- Temperatures `raw - 60 = °C` unless noted.

## Sources

| Source | Vehicle | Bus | Notes |
|---|---|---|---|
| `/can/*.csv` | 2016 Mustang GT350, 6MT | HS1 (OBD port, through the gateway) | Missing 37 IDs the GT has (`0x156 0x166 0x171 0x179 0x331 0x3B5 0x421 0x42D 0x43E` ...), so replaying them on this GT cluster throws warnings |
| `other_refs/v-ivanyshyn_parse_can_logs` | 2016 Mustang GT, 6R80 | HS1 + HS3 merged | |
| `other_refs/2015GTPremium_FreezeFrame.csv` | 2015 Mustang GT Premium, 6MT | HS-CAN / HS-CAN2 | One sample per ID from this cluster's car |
| `/can/apim/*.csv` | Bench APIM (SYNC) | HS3 | `apim_capture.py` logs, APIM alone on the bench. See [APIM (SYNC)](#apim-sync) |
| `cluster_tx.csv` | Bench cluster (2015 analog, FR33) | HS3 | What the cluster transmits on its own, see [Cluster (IPC) Transmits](#cluster-ipc-transmits) |
| `mustang.c` ([ufnalski's project](https://github.com/ufnalski/ford_mustang_cluster_h503rb/blob/main/Core/Src/mustang.c)) | 2016 Mustang V6, automatic | | Source of `0x3B2` and the `0x76` g meter which enabled TrackApps |

The web viewer (`docs/`, built by `build_web.py`) takes the first sample of each ID from every source above that has a
log, and labels it with the Vehicle column.

The cluster is on HS3 (DLC pins 12 / 13). It only talks on HS3, so anything it waits for has to come back on HS3.

## Index

| ID | Name | Status | Sent by `s550_cluster.py` |
|---|---|---|---|
| `0x4C` | Airbag / seatbelt indicators | Confirmed | Yes |
| **`0x048`** | **APIM power mode (required to boot the APIM)** | Confirmed | Yes |
| `0x76` | Steering angle, Track Apps g meter | Confirmed | Yes |
| `0x77` | Vehicle speed / yaw, steering warning fix | Confirmed | Yes (`FF ...` by default) |
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
| `0x290` | APIM state | APIM sends | No |
| `0x2E3` | APIM status, clears the digital cluster's U0253 | APIM sends | No |
| `0x217` | Wheel speeds | From logs | `--dummydata` |
| `0x230` | Gear position | From logs | `--dummydata` |
| `0x331` | Climate / outside temp? | From logs | No |
| `0x38D` | Key / start messages, Track Apps | Confirmed | Yes |
| `0x3A6` / `0x3A7` | Blind spot / cross traffic (side detect L / R) | Confirmed | Yes |
| `0x3B2` | Track Apps, turn signals | Confirmed | Yes |
| **`0x3B3`** | **Cluster on (required, send first)**, doors, lights, parking brake | Confirmed | Yes |
| `0x3B4` | TPMS lamp, system status, per-tire status | Confirmed | Yes |
| `0x3B5` | Tire pressure | Confirmed | Yes |
| `0x3C3` | High beams, parking brake | Confirmed | Yes |
| `0x3C8` | Drive mode, MyColor | Cluster sends | No |
| `0x3E0` / `0x3E3` / `0x3E6` | Startup requests / replies | Confirmed | `--respond` |
| `0x40A` | VIN / vehicle config | From logs | `--config` |
| `0x415` | Vehicle speed / yaw | From logs | `--dummydata` |
| `0x416` | ABS / traction control icons | Confirmed | Yes |
| `0x421` | Oil pressure status, check engine | Confirmed | Yes |
| `0x422` | Coolant temp | From logs | No |
| `0x42C` | Occupant sensor blocked, cruise status, PCM present | Confirmed | Yes |
| `0x42D` | Inlet air temp | Confirmed | Yes |
| `0x430` | Odometer | Cluster sends | No |
| `0x466` | GPS compass / time (APIM) | Confirmed (compass) | Yes |
| `0x431` | Transmission warnings | Confirmed | Yes |
| `0x43E` | AFR, cylinder head temp, boost / vacuum | Confirmed | Yes |
| `0x453` | Seat occupant sensor serial | From logs | No |
| `0x454` | Airbag module serial | From logs | No |
| `0x4B0` | Braking pressure? | From logs | No |
| `0x5xx` | Module alive frames | From logs | Yes (`0x581 0x596 0x59E 0x5B3 0x5B5`) |

---

# Cluster (IPC) Transmits

**Status:** Cluster sends · captured on the bench with `interactive_brute_force.py` (`cluster_tx.csv`, `cluster_tx_changes.csv`)

Only `0x18B 0x350 0x3C8 0x3E0 0x430 0x434` show up in the HS1 logs (passed through the gateway), the rest are HS3 only. `replay.py` skips all of these unless `--include-ipc`.

8 Nov 2026 - `other_refs/VehicleCAN.dbcx` (powertrain bus view) tags 90 frames with `FrameGatewayNetwork`, the network the GWM copies them from. The 29 `HS3_CAN` ones are the cluster / APIM's outputs and match this list: `0x18B 0x225 0x2FD 0x30A 0x317 0x318 0x3C8 0x3E0 0x430 0x434 0x45A` (`0x318` = `IPC_Send_Signals_2`, `0x430` = `Cluster_Info1`, `0x434` = `Cluster_Info_3`), the rest are APIM / nav / trailer. So the cluster sits on HS3 behind the GWM. The DBC only describes traffic onto the powertrain bus, so it doesn't list what the GWM sends the cluster on HS3. That gateway-built traffic is the likely home of the missing steering / U0146 data.

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
- Lateral shows the force the driver feels: a hard right turn puts the dot on the left, so game lateral acceleration goes in with its sign flipped. Longitudinal follows the acceleration: speeding up moves the dot to accel (both tested in Forza).
- Every 2015 - 2017 log has `C0 00 80` in bytes 2 - 4 (`drive.csv` also `80` / `40` in byte 2, `00` in byte 4), off that scale. The old fixed frame `3E 83 C0 00 00 ..` pinned the dot in the top left corner.

# 0x77 - Vehicle Speed / Yaw

**Sample:** `18 3B 08 00 7F F7 E5 E5` (logs), `FF FF FF FF FF FF 00 FC` (steering warning fix, s550_cluster.py default) · **Status:** From logs

| Bytes | Signal | Encoding |
|---|---|---|
| 0 - 1 | Vehicle speed | 14 bit (mask byte 0 with `0x3F`), `MPH * 175`, same as `0x202` |
| 2 - 3 | Yaw rate / lateral accel | 12 bit, center `0x0800`. Tracks the left / right wheel speed difference in turns |
| 6 | Hill Start Assist Not Available | `0x_C` shows it, `0x_6` hides it (`s550_cluster.py` sends `0xE6`) |

- In the GT and GT350 logs byte 6's low nibble changes constantly (part of a value with byte 7, tracks the pedal), so replaying a log makes the warning come and go.
- 8 Nov 2026 - the Ford DBC (`ford_lincoln_base_pt.dbc`) names it `BrakeSnData_3`, sent by the ABS, and the 2015 - 2017 logs fit its layout (Motorola bit order). No counter or checksum

| Bits | Signal (DBC name) | Encoding |
|---|---|---|
| byte 0 - 1 | Speed (`VehOverGnd_V_Est`) | DBC: 16 bit, 0.01 kph per count (`MPH * 161`), not checked against the `MPH * 175` above |
| byte 2 bits 7 - 5 | Travel direction (`VehTrvlDir_D_Stat`) | 0 in every log |
| byte 2 bits 3 - 0, byte 3 | Yaw rate (`VehYawComp_W_Actl`) | 12 bit, `raw * 0.03663 - 75` deg/s, `0x800` = 0 |
| byte 5 bits 3 - 0, byte 6 bits 7 - 2 | Lateral accel (`VehLatComp_A_Actl`) | 10 bit, `raw * 0.035 - 17.9` m/s² |
| byte 6 bits 1 - 0, byte 7 | Longitudinal accel (`VehLongComp_A_Actl`) | 10 bit, `raw * 0.035 - 17.9` m/s², positive speeding up |

- So the Hill Start Assist message is really the longitudinal accel: `E6 02` is about 0 m/s², `EC 02` is -17.8 m/s² (implausible), which shows the warning.
- Bytes 4 - 5 high nibble are `7F F_` in every log and not in the DBC. The GT350 `start.csv` opens with `00 00 0F FE 7F FF FB FE` (every value at its max, likely "not ready yet") before the engine runs.
- The power steering module is one of its receivers in the DBC. With `--dummydata` at 40 mph it adds Steering Fault Service Now to the Steering Assist Fault the missing module already causes. Muting 0x77 removes it, muting 0x217 or 0x415 doesn't.

> [!TIP]
> **Two fixes for Steering Assist Fault / Steering Fault Service Now on a bench, either one is enough:**
> 1. Send `0x77` as **`FF FF FF FF FF FF 00 FC`** (no Forscan needed, `s550_cluster.py` does by default)
> 2. Disable EPAS in the cluster's as-built, see [IPC As-Built](#ipc-as-built-720)

- 10 Nov 2026 - `FF FF FF FF FF FF 00 FC` (reported by another builder) keeps both steering warnings away with EPAS
  still enabled in the as-built, confirmed with the `steer77` preset and driving in live_test.py. A real speed frame
  brings Steering Assist Fault and Steering Fault Service Now back at once, and with `0x77` following `0x202` while
  the speed changes the fault keeps coming back. No Hill Start Assist Not Available with it.
- Every ABS signal at its max reads as invalid / not ready. Likely the cluster only checks for the power steering
  module once `0x77` reports a valid moving speed, so any valid speed (whatever the scale) faults on a bench without
  one, and an invalid one skips the check. Whether U0420-82 still sets isn't tested
  (`ipc_dtc_test.py probe 077=1B5808007FF7E602@20 dummy` puts the real frame back over the default).
- `s550_cluster.py` now sends `0x77` in the base schedule (50 Hz): this frame while `steering_warning_fix` is 1 (the
  default, a switch in live_test.py), the real speed frame above at 0.

# 0x81 - Steering Wheel Buttons

**Sample:** `00 00 00 00 00 00 00 00` · **Status:** Confirmed

| Byte | Value | Button |
|---|---|---|
| 1 | `0x01` | Down |
| 1 | `0x02` | Left |
| 1 | `0x04` | Right |
| 1 | `0x08` | Up |
| 1 | `0x10` | OK |

# 0x82 - Power Steering Info (EPAS_INFO)

**Sample:** `83 00 14 34 AF 00 44 FF` · **Rate:** 50 Hz · **Status:** Confirmed (byte 6 mode), rest from the Ford DBC + logs

Sent by the power steering module. The Ford DBC (`ford_lincoln_base_pt.dbc`, `EPAS_INFO`, Motorola bit order) fits the 2015 - 2017 logs, no counter or checksum.

| Bits | Signal (DBC name) | Encoding / logs |
|---|---|---|
| byte 0 | Steering column torque (`SteeringColumnTorque`) | `raw * 0.0625 - 8` Nm, `0x80` = 0. -4.5 to +4.0 Nm in the GT350 logs, moves both ways as the wheel is turned |
| byte 1 bits 1 - 0 | Power steering failure (`EPAS_Failure`) | `0` in every log |
| byte 1 bit 2 | Driver steer active (`DrvSteActv_B_Stat`) | `0` in every log |
| byte 1 bits 7 - 3, byte 2 bits 7 - 6 | Park assist angle control status (`SAPPAngleControlStat1 - 6`) | `0` in every log |
| byte 2 bits 5 - 0, byte 3 bits 7 - 2 | Motor current (`SteMdule_I_Est`) | 12 bit, `raw * 0.05 - 64` A. -3.8 to +36 A in the GT350 logs. Bytes 1 - 2 `00 14` are the current's high bits |
| byte 3 bits 1 - 0 | Trailer hitch lamp / trailer aid request | `0` |
| byte 4 | Module voltage (`SteMdule_U_Meas`) | `raw * 0.05 + 6` V. ~11.8 V key on engine off (`6F` - `77`), ~14.7 V running (`AF`) |
| byte 5 | `DrvSte_Tq_Actl` | `00` in every log |
| byte 6 bits 7 - 5 | Module state (`SteMdule_D_Stat`) | `start.csv`: `0` key on engine off (every `run_*` log), `4` cranking, `0`, `1` ramping up, `2` assisting. `shutoff.csv`: `2` then `1` |
| byte 6 bits 3 - 2 | Steering mode | `0x40` normal, `0x44` sport, `0x48` comfort (confirmed, not in the DBC) |
| byte 7 | Trailer aid max speed (`Veh_V_RqMxTrlrAid`) | `FF` |

- The old "fuel consumption?" guess for bytes 2 - 3 was the motor current.
- Value names from `other_refs/VehicleCAN.dbcx`:
    - `EPAS_Failure`: `0` OK / no message, `1` Power Steering Assist Fault, `2` Service Power Steering, `3` Service Power Steering Now
    - `SteMdule_D_Stat`: `0` initializing, `1` limited assist, `2` full assist, `3` shutdown, `4` system failure, `5` / `6` EPAS failure 2 / 3
- The DBC lists only the GWM and IPMA as receivers of these, but its message comment says "IPC needs EPAS_Failure for msg to driver", so the cluster gets it through the GWM. Sweeping `EPAS_Failure` 0 - 3 and the state 0 - 7 with `--dummydata` changed nothing on screen, but Steering Assist Fault and Service Now were already showing (U0420-82 and the 0x77 speed). The 2018 project saw "Steering Loss - Stop Safely" with `FF` on 0x02D - 0x089, so the cluster may read something in that range. `epasfail` without `--dummydata` (Service Now not showing) also changed nothing at `2` / `3`, so on this 2015 cluster the warnings don't come from 0x82 directly. They follow U0420-82 and, for Service Now, the 0x77 speed. Fixed by disabling EPAS in the cluster's as-built, see [IPC As-Built](#ipc-as-built-720).
- `epasfail` / `epasstat` in `interactive_brute_force.py` sweep the failure and state fields to see if the cluster reads them for the steering warnings.

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
| 2 bit 7 | Steering power request (`StePw_B_Rq`) | `1` running, `0` in the `FF FF 00 00` boot frames |
| 4 | Checksum | `0xFF - (b0 + b1 + counter + b6 + b7)`, low 8 bits. Matches all 88,614 GT350 frames and all 7,002 in v-ivanyshyn's log. Drops by 1 as the counter goes up, jumps up 15 when it wraps F → 0, and stays put when the angle and counter move in opposite directions on the same frame |
| 5 (upper nibble) | Rolling counter | `+0x10` per frame, lower nibble always `0` |
| 6 - 7 | Learned steering center | Same scale as the angle, doesn't follow the wheel. `FF FE` at key on and until the car has driven ~1 minute (`drive.csv`), then steps between about -4° and -6°. `7C EA` GT350 parked, `7C 7F` v-ivanyshyn's GT |

- Ford DBC `SteeringPinion_Data` (0x7E) has the same layout, which `s550_cluster.pinion_frame` builds for both IDs. Bytes 2 (low 7 bits) - 3 there are a compensated angle, always `0` on 2015 - 2017.
- `0x3A8` (v-ivanyshyn's GT only, 20 ms) bytes 2 - 3 are the same angle minus 21873 (center ~`0x278F`). No counter or checksum, the other bytes are `00`.
- Sending this frame with a correct counter and checksum doesn't clear U0420-82. Disabling EPAS in the cluster's as-built does, see [IPC As-Built](#ipc-as-built-720).
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
| 6 | Forward Gear? | 0x00 on 15-17 manual. 0x10 in 15-17 auto until P/R. used in 2018+ |

- The two are equal when coasting / off throttle.
- 8 Nov 2026 - byte 6 is `0x00` in every GT350 (manual) log. In v-ivanyshyn's log (an automatic, see `0x230` byte 1) it is `0x10` the whole drive and drops to `0x00` at 68.25 s, the moment the shifter leaves D/N for R and P. Likely an "in a forward gear" flag for automatics, untested on the cluster.
- The 2018+ Ford DBC (`TorqueDataEngFlags`) has a drive mode in byte 6's high nibble, a counter in its low nibble and a checksum in byte 7. The 2015 - 2017 logs have no counter there, byte 7 is always `00`.

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
| 1 | Shifter (automatic, v-ivanyshyn's log) | `0x08` the whole drive (D), then `06` `04` `02` `04` `00` as it is shifted at the end (likely N, R, P). Untested |
| 4 | Oil or transmission temp? | `raw - 60 = °C`, ~14 °C at cold start, ~37 °C after the drive |

# 0x331 - Climate / Outside Temp?

**Sample:** `C0 29 A6 C5 02 9B 0C 02` · **Rate:** ~1 Hz · **Status:** From logs (v-ivanyshyn's GT log)

| Bytes | Signal | Encoding |
|---|---|---|
| 2 - 3 | Counter | +1 every second (not a temperature) |
| 4 - 5 | Outside air temp? | 10 bit (mask byte 4 with `0x03`), `raw * 0.25 - 128 = °C` (Ford's usual ambient scale). `0x029B` = 38.75 °C / 102 °F, constant through the log. Untested |
| 7 | | `4` / `2` with ambient light or headlights on / off (per v-ivanyshyn) |

- Bytes 0, 1, 6 constant in the log. Not in the GT350 logs, likely only on cars with automatic climate control.

# 0x38D - Key / Start Messages, Track Apps

**Sample:** `20 00 00 00 00 00 00 00` (v-ivanyshyn's GT log, running) · **Status:** Confirmed (byte 4, `interactive_brute_force.py keymsg`)

Ford DBC `Body_Info_6_FD1`, sent by the gateway. Sending `0x38D` at all (any payload) also shows Track Apps in the menu.

| Byte | Signal | Values |
|---|---|---|
| 0 | Admin key count (DBC `KeyAdmnTot_No_Cnt`, high nibble) | `0x20` = 2 keys in both logs |
| 4 | Key / start message (DBC `immoMsgTxt_D_Rq`, high nibble) | See below |

| Byte 4 | Message |
|---|---|
| `0x00` | None (v-ivanyshyn's GT log) |
| `0x10` | Press Brake to Start |
| `0x30` | No Key Detected |
| `0x40` | No Key Detected |
| `0x60` | Run Power Active |
| `0x70` | Starting System Fault |
| `0x80` | Key Program Successful |
| `0x90` | Key Program Failure |
| `0xA0` | Max Number of Keys |
| `0xB0` | Not Enough Keys Learned |
| `0xC0` | Press Clutch to Start |

- v-ivanyshyn saw byte 4 spike on engine start, which fits a start message showing briefly.
- Other message fields per the DBC, untested: byte 4 bits 3 - 0 perimeter alarm (`PrmtrAlrmEvnt_D_Stat`), byte 3 bits 1 - 0 steering lock (`SteWhlLckMsgTxt_D_Rq`), byte 5 bits 3 - 1 door latch (`DrLatchMsgTxt_D_Rq`), byte 5 bits 7 - 6 security (`SecurityMsgTxt_D_Rq`).

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
| 4 | Outside temp (APIM) | `raw * 0.5 - 40 = °C`, same as the [digital cluster](#0x3b3-byte-4---outside-temperature-digital). The bench APIM (SYNC 2) shows it (10 Nov 2026, `apimtemp`). The GT350 logs only have `10` (-32 °C / -26 °F, likely "no sensor": the GT350 has no outside temp, only the GT does), `18` with the right turn signal, `E0` / `E6` at shutdown. v-ivanyshyn's GT log and this car's freeze frame are `10` too, unexplained. `s550_cluster.py` sends `outside_temp` from `s550_data`, kept under `E0` |
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
| Right | 4 / `0x08` | Lamp lit (flashes). Shares the byte with outside temp, the bench sends it on `0x3B2` only |
| Right | 7 / `0x40` | Stalk active |
| Right | 7 / `0x80` | Lamp lit (flashes with byte 4 bit `0x08`) |

```
Hazards on   44 8A C6 0C 18 00 C0 82
Hazards off  44 88 C6 0C 10 00 80 02
```

# 0x3B4 - TPMS Lamp and Status

**Sample:** `40 11 11 FF 20 20 00 00` (freeze frame, no lamp, no message) · **Status:** Confirmed (`interactive_brute_force.py tpmslamp`, `tpmssys`, `tpmslf` / `rf` / `rr` / `lr`)

Ford DBC `Tire_Pressure_Status` (CGEA 1.2 2011). Not in the GT350 logs, v-ivanyshyn's GT log has `34 11 21 FF 20 20 00 00` (system 3 low, lamp solid, RR status 2). Without `0x3B4` the cluster shows the TPMS lamp and a fault, sending the freeze frame value clears both until the frame stops.

| Byte | Signal | Values |
|---|---|---|
| 0, bits 7 - 4 | System status (`Tire_Press_System_Stat2`) | `0x1_` Tire Pressure Monitor Fault, `0x2_` Tire Pressure Sensor Fault, `0x3_` Tire Pressure Low window (no tire highlighted), `0x4_` nothing (freeze frame) |
| 0, bits 3 - 2 | Lamp (`Tire_Press_Telltale`) | `0x40` off, `0x44` solid, `0x48` flashing, `0x4C` flashing |
| 1 | LF (high nibble) / RF (low nibble) status | `2` or `4` highlights that tire, same as byte 2 (`0x21` / `0x41` LF, `0x12` / `0x14` RF). `1` in both logs |
| 2 | RR (high nibble) / LR (low nibble) status | `2` or `4` highlights that tire in the Tire Pressure Low popup and the tire pressure gauge page (`0x21` / `0x41` RR, `0x12` / `0x14` LR). Every other value: nothing. Needs system status 3 (`0x34`): with system status 4 no value did anything. `1` in the freeze frame, RR `2` with a low RR in v-ivanyshyn's log |
| 3 | Inner rears (duallys) | `FF` = not fitted |
| 4, 5 | | `20 20` in both logs, not in the DBC |

- The lamp and system status are separate fields: the system messages show with the lamp bits at 0.

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

# 0x42C - Occupant Sensor Blocked, Cruise Status

**Sample:** `80 00 00 00 9C 60 00 00` (quiet) · **Rate:** 51 ms · **Status:** Confirmed (byte 0, `interactive_brute_force.py occupant` / `occupantbits`)

Logged values: GT350 `8C 00 00 00 9C 60 00 00` in every log (`84 ..` and `8C 04 ..` briefly in `start.csv`), freeze frame `8C 00 00 00 68 A0 00 00`, v-ivanyshyn's GT `8C 60 00 00 B2 20 00 00`. Replaying any of them shows Occupant Sensor Blocked on this cluster.

| Byte | Signal | Values |
|---|---|---|
| 0 | Cruise status (bits 7 - 5) | From a 2018 GWM bench (2018-2023_S550_Digital_Cluster): the GWM repacks the PCM's `CcStat_D_Actl` here, bit 4 set while the PCM's cruise frame is present, `0x80` with no cruise data. Not tested here |
| 0 | Occupant Sensor Blocked (bit 3, `0x08`) | `0x80` - `0x87` nothing. `0x88`, `0x8C`, `0x8F` show Occupant Sensor Blocked with the passenger icon, gone as soon as the frame stops |
| 1, 4, 5 | | Data in the logs, but flipping every bit of bytes 0 - 5 one at a time (from `80 00 00 00 9C 60 00 00`) changed nothing visible beyond bit 3 above |

- Sending `0x42C` at all stops the cluster's U0100 (lost communication with the PCM), found with `ipc_dtc_test.py scan`. With the PCM counted as present the cluster then logs U0401-82 (invalid data from the PCM, alive counter), likely `0x202`'s missing counter (`ipc_dtc_test.py probe ... 202roll`).

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
- 8 Nov 2026 - `other_refs/VehicleCAN.dbcx` names it `Cluster_Info1_FD1`: the cluster's menu settings sent out to the other modules. openpilot's Ford port reads `DrvSlipCtlMde_D_Rq` from it to tell if traction control is off. Untested on this cluster, layout from the DBC (Motorola bit order):

| Bits | Signal (DBC name) | Values |
|---|---|---|
| byte 0 bit 7 | `AccDeny_B_RqIpc` | 1 = adaptive cruise denied. This cluster flips `0x84` / `0x04` |
| byte 0 bit 6 | `MetricActv_B_Actl` | 1 = metric units |
| byte 0 bit 2 | `LscmbbStat_B_Actl` | low speed collision braking on / off |
| byte 0 bit 1 | `NtrlTowMdeEnbl_B_RqDrv` | neutral tow requested |
| bytes 1 - 3 | `OdometerMasterValue` | km |
| byte 4 bits 1 - 0 | `DrvSlipCtlMde_D_Rq` | traction / stability mode: 0 default, 1 - 3 "off" modes (likely the Track Apps / Sport ESC choices) |
| byte 4 bit 2 | `DrvSlipCtlMde_B_Rq2` | pressed |
| byte 5 bit 3 | `EngOilLife_B_RqReset` | oil life reset from the menu |
| byte 6 bit 7 | `BulbChkActv_B_Stat` | bulb check active (at power up) |
| byte 6 bits 6 - 5 | `HsaMde_D_Rq` | Hill Start Assist setting: 0 off, 1 automatic, 2 manual. Likely the byte 6 change after Enter |
| byte 6 bit 4 | `ParkDetect_Stat` | in park |
| byte 6 bits 3 - 2 | `ReducedGuard_D_Rq` | 1 off, 2 on |

- Watching `cluster_tx_changes.csv` while changing the traction mode and Hill Start Assist in the menu would confirm bytes 4 and 6.

# 0x431 - Transmission Warnings

**Sample:** `05 1B 40 04 0F 83 42 00` (no message) · **Rate:** ~1 Hz · **Status:** Confirmed (`interactive_brute_force.py trans` / `transwarm`)

Not in any DBC. Logged values: warm (`longerdrive.csv`) `05 1B 40 04 0F 83 42 00`, idle `05 1D 42 03 97 83 42 00`, freeze frame `05 1D 40 EB B7 83 46 00` (shows Transmission Warming Up). Leaving `0x431` out shows no transmission message.

Messages found by flipping one bit at a time (only one bit changed from the base each time):

| Base | Bit flipped | Frame | Message |
|---|---|---|---|
| warm | byte 3 bit 3 (`0x08`) | `05 1B 40 0C 0F 83 42 00` | Transmission Malfunction |
| warm | byte 3 bit 4 (`0x10`) | `05 1B 40 14 0F 83 42 00` | Transmission Service Required |
| freeze | none | `05 1D 40 EB B7 83 46 00` | Transmission Warming Up |
| freeze | byte 3 bit 0 (`0x01`) | `05 1D 40 EA B7 83 46 00` | Transmission Warming Up (unchanged) |
| freeze | byte 3 bit 2 (`0x04`) | `05 1D 40 EF B7 83 46 00` | Transmission Indicator Mode Lockup |
| freeze | byte 3 bit 3 (`0x08`) | `05 1D 40 E3 B7 83 46 00` | Transmission Adapt Mode |
| freeze | byte 4 bit 5 (`0x20`) | `05 1D 40 EB 97 83 46 00` | Transmission Overheat, Stop |
| freeze | byte 4 bit 7 (`0x80`) | `05 1D 40 EB 37 83 46 00` | Transmission Too Hot, Press Brake |

- Byte 3 looks like a message number rather than separate flags (`04` nothing, `0C` malfunction, `14` service, `EB` / `EA` warming up, `EF` lockup, `E3` adapt mode), not yet swept value by value.
- Byte 4's messages appeared from the freeze frame base only. The GT350's idle frame has byte 4 `0x97` (= freeze with bit 5 cleared), which is unlikely to mean overheat at idle, so byte 4 may depend on byte 3 or the other bytes. Untested: replay the idle frame.
- Every other bit of both frames: nothing visible. Byte 3 or byte 6 = `FF` shows Transmission Limited Function (2018-2023_S550_Digital_Cluster bench).

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

- `s550_cluster.py` sends `0x581 0x596 0x59E 0x5B3 0x5B5`. The cluster's own is `0x591`, the APIM's `0x5E2` (only while it's on, see [APIM (SYNC)](#apim-sync)).
- Faking all of `0x500 - 0x5FF` (`--nm`) changed nothing.
- 8 Nov 2026 - `other_refs/VehicleCAN.dbcx` names them AutoSar network management frames: `0x59E` GWM, `0x5B5` PSCM, `0x596` ABS. Byte 0 is the node ID, byte 1 the control byte. We already send `0x59E` and `0x5B5` and the cluster still sets U0146 (GWM) and U0420 (PSCM), so it wants more than these alive frames.

# IPC As-Built (720)

**Status:** Confirmed on the bench · Written with Forscan, read with UDS `22 DExx` on `0x720` (no security for reads, writes need Forscan's security access)

The cluster's configuration. Block `720-NN` is DID `DE00 + NN - 1`, line `-01` is its first 5 bytes, line `-02` the rest. Forscan shows a checksum byte after each line that the UDS read leaves out:

```
checksum = (0x07 + 0x20 + block + line + data bytes) & 0xFF      e.g. 720-01-02: 07+20+01+02+0C+1B+10 = 61
```

| Line | This cluster (FR33-10849-GF) | Bench | Field (Forscan) |
|---|---|---|---|
| `720-01-01` | `8C0B 1064 70` | same | |
| `720-01-02` | `0C1B 10` `61` | `0C19 10` `5F` | 2nd byte low nibble, bit 3 Easy Entry/Exit, bit 2 Electric Parking Brake, **bit 1 Electric Power Assist Steering**, bit 0 ESC. `B` → `9` = EPAS disabled |
| `720-06-01` | `6C7F 0000 98` `B1` | `6C7F 0000 88` `A1` | 5th byte bit 4 = **EPAS Button**, enabled → disabled |

- **Fixes Steering Assist Fault / Steering Fault Service Now** (9 Nov 2026). `0x77` = `FF FF FF FF FF FF 00 FC` fixes them too, without Forscan, see [0x77](#0x77---vehicle-speed--yaw). With EPAS disabled the cluster stops expecting the power steering module, so U0420-82 has nothing to fault. Both fields were changed together; which one does it on its own isn't tested.
- Every CAN fix tried before this (`0x82` `EPAS_Failure` sweep, `0x085` / `0x07E` counter + checksum, `0x3A8`) didn't clear U0420-82.
- `fake_forscan.py` lets Forscan connect to the bench cluster: it answers as the PCM and BCM so Forscan finds a car. The ELM327 has to be on the cluster's CAN directly (HS3, Forscan doesn't look for the IPC on the OBD port's HS1 pins).
- Other IDs from the same Forscan read: F113 `FR33-10849-GF` (part), F188 `FR33-14C026-AG` (strategy), F124 `FR33-14C088-RF` (calibration), F111 `FR33-14F094-GA`, F110 `DS-FR33-1A292-AD`, F18C serial `42262060`.

# APIM (SYNC)

**Status:** Confirmed on the bench (10 Nov 2026) · APIM alone on the bench bus (500k, no cluster), captured with
`apim_capture.py`. Logs: `can/apim/`

The APIM lives on HS3 with the cluster. It wakes up on any CAN traffic, but only stays on and boots with a valid power
mode in **`0x048`**. `s550_cluster.py` already sends it (`APIM_2`, `00 00 00 00 07 00 E0 00`), from
[EtoTen's stm32_can_sim](https://github.com/EtoTen/stm32_can_sim/blob/main/src/main.cpp), a SYNC bench simulator. So
`APIM_1 - 3` (`0x044 0x048 0x109`) are frames the car sends *to* the APIM, not frames it sends.

- Muting one at a time (`--mute`): without `0x048` it doesn't boot. `0x044` and `0x109` aren't needed to boot.
- **No diagnostics on HS3.** Booted (`0x290` `7F`), it doesn't answer `10 01` on any request ID `0x700 - 0x7F7` or
  `0x7DF`, nor `10 01` / `3E 00` / `22 F190` / `22 F188` / `22 0200` / `10 03` on `0x7D0` (`apim_capture.py --probe`),
  so Forscan doesn't find it on the bench.
- Bench unit is a **SYNC 2** APIM (the GT350 in the `/can` logs had SYNC 3).
- **Outside temp** comes from [`0x3B3` byte 4](#0x3b3---cluster-on-doors-lights-parking-brake) (`raw * 0.5 - 40 = °C`). The fixed `10` we used to send (copied from the GT350 logs, which has no outside temp) showed -26 °F.
- **Compass**: in a car the heading comes from the GPS antenna on the APIM's GPS cable, with ABS wheel speed / direction
  ([SYNC primer](https://www.mustang6g.com/forums/attachments/s550-mustang-sync-system-and-tech-a-primer-pdf.892066/)).
  The APIM's compass also needs the nav SD card, so it stays blank on the bench. [`0x466`](#0x466---gps-compass--time)
  from `s550_cluster.py` does show the bearing on the cluster. The bench APIM (no antenna) never sends `0x466` or the
  DBC's `APIMGPS_Data_Nav_1 - 3` (`0x462 - 0x464`).
- **Diagnostics are on HS1** (connector pins 53 / 54, HS3 is 19 / 20). On HS1 alone it doesn't boot (no `0x290`), but
  `10 01` on `0x7D0` gets `0x7D8` `06 50 01 00 32 01 F4 00` (probe `094903`, cluster on the bus too). Like the car:
  booted by HS3, reached by Forscan through the OBD port's HS1. HS1 alone (with `fake_forscan.py`) is enough to read
  and write its as-built, the screen stays off. Move it back to HS3 to use it.
- **The cluster doesn't need it.** `ipc_dtc_test.py clear dummy` leaves the same 5 codes with the APIM booted on the bus
  or unplugged (P0460-13, P1346-13, U0146, U0184, U0401-82). U0184 (lost comm radio) stays with the APIM there, so it's
  the audio module (ACM), not the APIM. This analog cluster never sets U0253 (APIM), so there's nothing to spoof.
- `0x109` per v-ivanyshyn (HS3): RPM `(b0<<8 + b1) / 4`, gear (`b2` 1 P, 17 R, 33 N, 49 D, 65 S), speed `(b4<<8 + b5) / 100`, `b6` 1 in reverse. Likely the APIM's speed / reverse input. `0x044` unknown.

## 0x048 - Power Mode

**Sample:** `00 00 00 00 07 00 E0 00` · **Rate:** 10 Hz (ours) · **Status:** Confirmed (byte 4)

| Byte | Value |
|---|---|
| 4 bits 4 - 0 | Power mode, see below |
| 4 bits 7 - 5 | Not part of the power mode: `27` (bit 5 + running) still boots. Unknown |
| 6 | `E0`, untested |
| 0 - 3, 5, 7 | `00`, untested |

Byte 4 swept `00 - 1F`, 30 s each (`interactive_brute_force.py apimpower`). Names are a guess from Ford's usual power
mode list, but they match what a car does: the radio comes on in accessory and drops out while cranking.

| Byte 4 | Name (guess) | APIM |
|---|---|---|
| `00` | Key out | not tested (the sweep stepped past it at once) |
| `01` `02` `03` | Key recently out / key approved / post accessory | Off |
| **`04`** | **Accessory** | **On** - `0x2E3` → `02` in 0.3 s, `0x290` → `7F` 5.5 s later |
| **`05`** | **Post ignition** | **On** (stays on from `04`, bit flip test: no change either way) |
| **`06`** | **Ignition on** | **On** |
| **`07`** | **Running** | **On** (what `s550_cluster.py` sends) |
| `08` | ? | Off, `0x290` → `01` within 0.5 s |
| `09` | Crank | Off |
| `0A - 1F` | - | Off (`17` off too, so bit 4 is part of the field) |

- Off → on takes 5 - 25 s (`0x290` `01` → `7F`), on → off under a second.
- In "off" the APIM keeps listening: `0x290` stays at 5 Hz with ~19 IDs, so a later valid power mode still boots it.

## 0x466 - GPS Compass / Time

**Sample:** `78 34 D4 28 12 A0 80 00` (15:13:53 UTC, 10 Nov 2026, north) · **Rate:** 1 Hz (ours) · **Status:** Compass confirmed on the cluster, the rest from the DBC

`0x466 compass: v = (b3 & 0x07) * 2 + (b4 >> 7)` (datechnerd, digital cluster) is `GPS_Compass_direction 26|4` of the
DBC's `APIMGPS_Data_Nav_2_FD1` (`0x463`), so the rest of that layout is assumed:

| Byte | Bits | Signal |
|---|---|---|
| 0 | 7 - 3 | UTC hours |
| 0 | 2 | GPS fault (`Gps_B_Falt`) |
| 1 | 7 - 2 | UTC minutes |
| 2 | 7 - 2 | UTC seconds |
| 3 | 7 - 3 | PDOP, `raw * 0.2` |
| 3 - 4 | b3 2 - 0, b4 7 | Compass: `0` N, `1` NE, `2` E, `3` SE, `4` S, `5` SW, `6` W, `7` NW |
| 4 | 6 | Inferred (not actual) position |
| 4 | 5 - 1 | Day - 1 |
| 5 | 7 - 4 | Month - 1 |
| 6 | 7 - 3 | Year - 2010 |

- `s550_cluster.py` `send_gps_nav` sends it from `compass_heading` (degrees, rounded to 8 directions) and the PC's UTC
  clock. The cluster shows the bearing. The bench APIM ignores it (its compass needs the nav SD card and GPS antenna).
  In a car with nav the APIM probably sends this itself.

## What the APIM sends

**First at wake up:** `0x5E2` `E2 00 FF FF FF FF FF FF` (its [module alive frame](#0x5xx---module-alive-frames)), then
~10 ms later once each: `0x086 0x090 0x091 0x101 0x103 0x104 0x105 0x191 0x194 0x19B 0x1A1 0x1A3 0x1D4 0x1D6 0x1D9
0x1DA 0x1DC 0x1DD 0x1DF 0x1EA 0x1ED 0x1F4 0x1F5 0x1F6 0x1F7 0x1FF 0x227 0x22E 0x22F` (mostly zeros: `0x104`
`FF 00 00 FF 00 80 FF 00`, `0x191` `3C 00 ...`, `0x1DA` `0C EF 07 FF ...`, `0x1DD` `FF FF F0 00 00 00 3F FF`,
`0x1F6` `80 03 FF FF FF FF 00 00`). Without a valid `0x048` it stops `0x5E2` after 5 s and stays in the listening state.

**5 Hz:** `0x290`. **1 Hz:** `0x192 0x215 0x222 0x229 0x2D0 0x2D1 0x2D2 0x2E0 0x2E3 0x2EE 0x320 0x321 0x34E 0x35B
0x362 0x3DA 0x3F0 0x3F1`, and `0x5E2` while on. **0.2 Hz once booted:** `0x2CB` `10 0A 61 71 00 01 03 40` (byte 1
`08 - 0B`).

| ID | Data | Notes |
|---|---|---|
| `0x290` | `01 00 ...` | **Byte 0 = APIM state:** `01` starting / off, `7F` booted, `4F` was on and lost `0x048` |
| `0x2E3` | `01 00 ...` | Byte 0 `01` starting / off, `02` on. Held at zeros it clears the digital cluster's U0253 (lost comm APIM), see [Fault / lamp suppression](#fault--lamp-suppression-digital-standalone--no-gwm). The analog cluster never sets U0253 |
| `0x2D0` | `77 04 10 07 00 ...` | Byte 1 `04` → `24` and byte 2 `10` / `20` change around boot |
| `0x229` | `00 00 03 00 00 ...` | Byte 1 counts `10 30 20 00` for a few seconds after boot |
| `0x103` `0x222` | `00 ...` | Short pulses after boot (`0x103` `01 01 ...` every 5 s, `0x222` `40` / `10`) |

---

# 2018+ Digital Cluster (S550 refresh, 12.4" digital IPC)

**Status:** Confirmed on a bench **2018 digital cluster** (part `MR3V-14C026-DC`, JR3T family) unless noted.
Contributed by [datechnerd / 2018-2023_S550_Digital_Cluster](https://github.com/datechnerd/2018-2023_S550_Digital_Cluster).
Everything above in this file is the **2015-2017 analog** cluster (FR33/GR3T); the digital refresh shares the same
HS3 bus and many IDs but differs on several. This section lists only what is **new or different** on the digital unit;
where an ID behaves the same (e.g. `0x156`, `0x3B5`, `0x42D`, `0x466` compass) the entry above applies.

Same conventions: HS3 (DLC 12/13), 500 kbps, big-endian, bytes 0-7, temps `raw - 60 = C` unless noted.

| ID | Name | vs analog |
|---|---|---|
| `0x3B2` | Boot/activate (alone) | digital boots on `0x3B2` alone; `0x3B3` not required |
| `0x42F` | Tachometer | **digital tach** - analog `0x204` RPM is dead here |
| `0x171` | Gear / PRND S | automatic selector (analog uses `0x230` for manual gear) |
| `0x470` | Trans oil temp (TOT) | new |
| `0x17E` | Manifold charge temp (MCT) | new |
| `0x432` | Rear diff / axle oil temp (DT) | new |
| `0x43E` | adds Eng oil pressure (b7) | analog has AFR/CHT/boost only |
| `0x3B3` | Outside temp = byte 4 | confirmed byte for digital |
| `0x191` | Display units + distance-to-empty | new |
| `0x3B4` | TPMS telltale lamp | new |
| `0x38D` | TrackApps menu gate (presence) | new |
| `0x081` | menu keys b1/b2 | adds menu/music/back/cobra |
| `0x430` | ignition status (cluster TX) | analog uses `0x430` as odometer; digital odometer is `0x179` |

## 0x3B2 - Boot / Activation (digital)

**Sample:** `40 00 00 0B 10 00 00 02` @ ~16 ms - **Status:** Confirmed

On the digital (JR3T) cluster `0x3B2` **alone** boots and keeps the cluster awake - `0x3B3` is **not** required
(the opposite of the analog FR33, which needs `0x3B3`). This confirms the `mustang.c` note that GR3T/JR3T use
`0x3B2` alone. Byte 0 upper nibble must be `4` (key on); any other value = key off and the display dies in ~2-10 s.
Byte 0 low nibble bit 0 = Trunk Ajar. Layout is Ford `BodyInfo_3` (door/lamp/turn bits per the analog `0x3B2`/`0x3B3`).

## 0x42F - Tachometer (digital)

**Sample:** `C0 00 7D 00 00 00 1F 40` (8000 rpm) - **Status:** Confirmed

Ford `EngAout_N_Dsply`, a 13-bit field in bytes 6-7, **rpm = raw x 2**.

| Bytes | Signal | Encoding |
|---|---|---|
| 6 - 7 | Tachometer | `raw = (b6 & 0x1F) << 8 OR b7`, rpm = raw x 2. So `b6 = (rpm/2 >> 8) & 0x1F`, `b7 = (rpm/2) & 0xFF` |

- Sweeps the needle cleanly 0 -> 8000 -> 0. The analog `0x204` RPM (bytes 3-4) does **nothing** on the digital cluster.
- Note `b6` bit 4 alone = raw bit 12 = 4096 -> x2 = 8192 rpm (redline), which is why setting byte 6 alone snaps to redline
  (an old "launch control" red herring).

## 0x171 - Gear / PRND S (digital automatic)

**Sample:** `14 60 00 00 00 00 00 00` (Drive) - **Status:** Confirmed

| Byte | Signal | Values |
|---|---|---|
| 0 | enable | `0x14` for P/N |
| 1 | Gear | `0x00` P, `0x20` R, `0x40` N, `0x60` D, `0x80` S |

Park = `14 00`, Reverse = `14 20`. (The analog manual gear readout is `0x230`.)

## 0x470 / 0x17E / 0x432 / 0x43E - Gauge-mode readouts (digital)

The digital cluster Gauge Mode / engine-data page adds readouts the analog does not. All latch their last value
(a hit in a fast sweep can show one step late). Confirmed on the bench by driving each byte and reading the screen:

| Readout | Frame / field | Scale |
|---|---|---|
| Engine oil temp (EOT) | `0x156` b1 `EngOil_Te_Actl` | C = raw - 60 (same as analog) |
| **Trans oil temp (TOT)** | `0x470` b3 (set b2 = `0xFF` to enable) | C = raw - 60 |
| **Eng oil pressure (EOP)** | `0x43E` b7 | 1 kPa / count |
| Air fuel ratio (AFR) | `0x43E` b3 | raw / 10 (same as analog) |
| **Vac / boost** | `0x43E` b5 | psi = `0.4628 x raw - 30.08`; vacuum shown in inHg (digital drove this via byte 5 alone; analog uses the 13-bit b5:b6 above) |
| Inlet air temp (IAT) | `0x42D` b1[1:0]:b2 | raw x 0.25 - 128 C (same as analog) |
| **Manifold charge temp (MCT)** | `0x17E` b1 | C = raw x 0.5 - 20 |
| **Rear diff / axle oil temp (DT)** | `0x432` 9-bit b0[7:0] + b1.7; **enable = b1 bit6 (`0x40`)** | C = raw - 40 |
| Voltage | none - cluster measures its own 12 V supply | reads the bench PSU |

- Low oil-pressure warning telltale = `0x421` b2 (FF = warning, 0 = normal), consistent with the analog `0x421`.
- G-meter page (`0x76`) on the digital cluster would not take a dot from `0x76`, `0x92`, `0x77` or `0x416`; it appears
  computed internally from ABS + RCM data with live counters - still open on the digital unit.

## 0x3B3 byte 4 - Outside temperature (digital)

**Status:** Confirmed

On the digital cluster the outside-air temp reads from **`0x3B3` byte 4, C = raw x 0.5 - 40** (range -40..+80 C;
`FE`/`FF` ignored). `0x3B3 = 00 00 00 00 78 00 00 00` boots reading 68 F (20 C). Reads "--" while lost-comm DTCs are
active, blank with none + no source.

## 0x191 - Display units + distance-to-empty (digital)

**Status:** Confirmed

Byte 0 is a packed units field (**stored** - survives a key cycle, reset only by an IPC power cycle). Temperature and
distance units are separate: temp `0x10` = F, `04/08/40/80` = C. b0 `01`/`04` also pops "0 mi to E", so `0x191`
is the fuel-range / distance-to-empty frame. Distance-unit bits not fully mapped; send with care.

## 0x3B4 - TPMS telltale lamp (digital)

**Sample:** `00 00 00 00 00 00 00 00` (lamp off) - **Status:** Confirmed - layout from opendbc `ford_cgea1_2_ptcan_2011.dbc`

| Bits | Signal | Values |
|---|---|---|
| b0[7:4] | System status | `0` OK (lamp off), `2` sensor fault, `3` low (+ shows all four pressures), `5`/`6` train LF/RF |
| b0[3:2] | Telltale | `1` solid, `2` flashing |

All-zeros = lamp off. Pressures themselves are `0x3B5` as on the analog cluster.

## 0x38D - TrackApps menu gate (digital)

**Status:** Confirmed

**Presence-gated:** broadcasting `0x38D` at all - any payload, even all-zero, at ~50 ms - makes the **TrackApps** menu
entry appear; dropping it removes the entry.

## 0x081 - Steering-wheel / menu buttons (digital, byte 0 is a bitmask)

Byte 0 is an 8-bit mask, **one physical button per bit** (the analog table above lists the same 5-way). On the
digital cluster:

| Byte | Bit | Effect |
|---|---|---|
| 0 | `0x01` | Down / info-page next |
| 0 | `0x08` | Up / info-page prev |
| 0 | `0x10` | OK/Select (enters submenu, toggles checkboxes; hold on info page = reset trip) |
| 0 | `0x02` `0x04` `0x40` `0x80` | **ignored by the digital menu** - these are the media/voice buttons (volume, skip/rewind, back, voice), handled by the audio/APIM modules, not the IPC. **Not** left/right arrows |
| 0 | `0x20` | "Steering Feel Selection Not Available" popup |
| 1 | `0x01` | MENU (open/close Settings) |
| 1 | `0x02` | Music/audio page |
| 1 | `0x40` | Back / Exit |
| 1 | `0x80` | "Damper Mode Selection Not Available" popup |
| 2 | `0x80` | Cobra menu |

The digital menu is 1-D: Up / Down / OK / Menu / Back only (no left/right), which is why byte 0 `0x02`/`0x04` do nothing
to it. On the S550 wheel the physical packs are media on the left spoke, menu+voice on the right (18+; believed flipped
on 15-17) - so the "ignored" bits are real buttons the IPC simply does not act on.

## Fault / lamp suppression (digital, standalone / no GWM)

The digital cluster latches more than the analog. Confirmed on the bench:

| Lamp / warning | Clear by |
|---|---|
| MIL + oil pressure | `0x421` zeros (b0[3:2] MIL, b2.2 oil) |
| Park-brake fault (moving in gear) | `0x213` = `FF FF 00 00 00 11 FF 41` |
| Blind-spot lamp | `0x3A6` and `0x3A7` = `00 40 02 00 00 00 00 00` |
| TPMS lamp | `0x3B4` zeros |
| ABS / TCS / red BRAKE | `0x416` lamp fields 0 (a healthy ABS also clears them) |
| Wrench + "See Manual" | `0x168` b2 bit7 = 0 |
| Lost-comm U-codes | module-presence frames held at zeros: `0x076`->U0121 (ABS), `0x168`->U0103 (GSM), `0x223`->U0193 (DACM), `0x2E3`->U0253 (APIM); pair `0x2A1`+`0x3E6`->U0212 (SCCM) |

- **Charge + wrench are latched by the cluster own U-code DTCs** and cannot be cleared by any status frame a 2015-17
  car sends. Workaround: UDS `14 FF FF FF` on `0x720` (IPC, default session, no security) every ~2 s clears them (and
  reveals outside temp); codes re-set in ~5 s, so a periodic clear keeps them suppressed. Real fix = emulate each lost
  module (the real GWM HS3 output clears U0100/U0420/U0232/U0233/U0256/U0557 by itself).

## 0x430 - Ignition status (digital, cluster TX)

On the digital cluster `0x430` is a **cluster output**, byte 0 = `05` Run / `04` Off-Acc (echoes `0x3B2` ignition) -
not the odometer. The digital odometer is `0x179` byte 5 `OdoCount` (as the analog `0x179` distance-counter note describes).
Other digital cluster-TX detectors: `0x225` b3 = displayed speed (whole mph), `0x318` b5 bit7 = a popup is on screen.
