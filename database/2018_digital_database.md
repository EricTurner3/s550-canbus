# 2018+ Digital Cluster (S550 refresh, 12.4" digital IPC)

**Label:** 2018+ digital · **Status:** Confirmed on a bench **2018 digital cluster** (part `MR3V-14C026-DC`, JR3T family) unless noted.
Contributed by [datechnerd / 2018-2023_S550_Digital_Cluster](https://github.com/datechnerd/2018-2023_S550_Digital_Cluster).
[database.md](database.md) is the **2015-2017 analog** cluster (FR33/GR3T); the digital refresh shares the same
HS3 bus and many IDs but differs on several. This file lists only what is **new or different** on the digital unit;
where an ID behaves the same (e.g. `0x156`, `0x3B5`, `0x42D`, `0x466` compass) the database.md entry applies.

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

## Modules

| Module | Part number | Notes |
|---|---|---|
| IPC (cluster) | MR3V-14C026-DC | datechnerd's bench, JR3T family |

# 0x3B2 - Boot / Activation (digital)

**Sample:** `40 00 00 0B 10 00 00 02` @ ~16 ms - **Status:** Confirmed

On the digital (JR3T) cluster `0x3B2` **alone** boots and keeps the cluster awake - `0x3B3` is **not** required
(the opposite of the analog FR33, which needs `0x3B3`). This confirms the `mustang.c` note that GR3T/JR3T use
`0x3B2` alone. Byte 0 upper nibble must be `4` (key on); any other value = key off and the display dies in ~2-10 s.
Byte 0 low nibble bit 0 = Trunk Ajar. Layout is Ford `BodyInfo_3` (door/lamp/turn bits per the analog `0x3B2`/`0x3B3`).

# 0x42F - Tachometer (digital)

**Sample:** `C0 00 7D 00 00 00 1F 40` (8000 rpm) - **Status:** Confirmed

Ford `EngAout_N_Dsply`, a 13-bit field in bytes 6-7, **rpm = raw x 2**.

| Bytes | Signal | Encoding |
|---|---|---|
| 6 - 7 | Tachometer | `raw = (b6 & 0x1F) << 8 OR b7`, rpm = raw x 2. So `b6 = (rpm/2 >> 8) & 0x1F`, `b7 = (rpm/2) & 0xFF` |

- Sweeps the needle cleanly 0 -> 8000 -> 0. The analog `0x204` RPM (bytes 3-4) does **nothing** on the digital cluster.
- Note `b6` bit 4 alone = raw bit 12 = 4096 -> x2 = 8192 rpm (redline), which is why setting byte 6 alone snaps to redline
  (an old "launch control" red herring).

# 0x171 - Gear / PRND S (digital automatic)

**Sample:** `14 60 00 00 00 00 00 00` (Drive) - **Status:** Confirmed

| Byte | Signal | Values |
|---|---|---|
| 0 | enable | `0x14` for P/N |
| 1 | Gear | `0x00` P, `0x20` R, `0x40` N, `0x60` D, `0x80` S |

Park = `14 00`, Reverse = `14 20`. (The analog manual gear readout is `0x230`.) Full DBC layout and the SelectShift gear
digit (byte 0 bit 0 on): [0x171](database.md#0x171---transmission-display-selectshift-gear-prnds) in database.md, confirmed on the analog.

# 0x470 - Trans oil temp (digital)

**Status:** Confirmed

A Gauge Mode / engine-data page readout, latches its last value. See [Gauge-mode readouts](#0x470--0x17e--0x432--0x43e---gauge-mode-readouts-digital).

| Byte | Signal | Values |
|---|---|---|
| 2 | Enable | set `0xFF` to enable |
| 3 | **Trans oil temp (TOT)** | C = raw - 60 |

# 0x17E - Manifold charge temp (digital)

**Status:** Confirmed

A Gauge Mode / engine-data page readout, latches its last value. See [Gauge-mode readouts](#0x470--0x17e--0x432--0x43e---gauge-mode-readouts-digital).

| Byte | Signal | Values |
|---|---|---|
| 1 | **Manifold charge temp (MCT)** | C = raw x 0.5 - 20 |

# 0x432 - Rear diff / axle oil temp (digital)

**Status:** Confirmed

A Gauge Mode / engine-data page readout, latches its last value. See [Gauge-mode readouts](#0x470--0x17e--0x432--0x43e---gauge-mode-readouts-digital).

| Byte | Signal | Values |
|---|---|---|
| 0 - 1 | **Rear diff / axle oil temp (DT)** | 9 bits, b0[7:0] + b1 bit 7. C = raw - 40 |
| 1 | Enable | **bit 6 (`0x40`)** |

# 0x43E - Oil pressure, AFR, vac / boost (digital)

**Status:** Confirmed

A Gauge Mode / engine-data page readout, latches its last value. See [Gauge-mode readouts](#0x470--0x17e--0x432--0x43e---gauge-mode-readouts-digital). The analog layout is [0x43E](database.md#0x43e---air-fuel-ratio-cylinder-head-temp-boost--vacuum) in database.md.

| Byte | Signal | Values |
|---|---|---|
| 3 | Air fuel ratio (AFR) | raw / 10 (same as analog) |
| 5 | **Vac / boost** | psi = `0.4628 x raw - 30.08`; vacuum shown in inHg. The digital drove this via byte 5 alone, the analog uses the 13-bit b5:b6 |
| 7 | **Eng oil pressure (EOP)** | 1 kPa / count |

# 0x3B3 byte 4 - Outside temperature (digital)

**Status:** Confirmed

On the digital cluster the outside-air temp reads from **`0x3B3` byte 4, C = raw x 0.5 - 40** (range -40..+80 C;
`FE`/`FF` ignored). `0x3B3 = 00 00 00 00 78 00 00 00` boots reading 68 F (20 C). Reads "--" while lost-comm DTCs are
active, blank with none + no source.

# 0x191 - Display units + distance-to-empty (digital)

**Status:** Confirmed

Byte 0 is a packed units field (**stored** - survives a key cycle, reset only by an IPC power cycle). Temperature and
distance units are separate: temp `0x10` = F, `04/08/40/80` = C. b0 `01`/`04` also pops "0 mi to E", so `0x191`
is the fuel-range / distance-to-empty frame. Distance-unit bits not fully mapped; send with care.

# 0x3B4 - TPMS telltale lamp (digital)

**Sample:** `00 00 00 00 00 00 00 00` (lamp off) - **Status:** Confirmed - layout from opendbc `ford_cgea1_2_ptcan_2011.dbc`

| Bits | Signal | Values |
|---|---|---|
| b0[7:4] | System status | `0` OK (lamp off), `2` sensor fault, `3` low (+ shows all four pressures), `5`/`6` train LF/RF |
| b0[3:2] | Telltale | `1` solid, `2` flashing |

All-zeros = lamp off. Pressures themselves are `0x3B5` as on the analog cluster.

# 0x38D - TrackApps menu gate (digital)

**Status:** Confirmed

**Presence-gated:** broadcasting `0x38D` at all - any payload, even all-zero, at ~50 ms - makes the **TrackApps** menu
entry appear; dropping it removes the entry.

# 0x081 - Steering-wheel / menu buttons (digital, byte 0 is a bitmask)

**Status:** Confirmed

Byte 0 is an 8-bit mask, **one physical button per bit** (the analog table in database.md lists the same 5-way). On the
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

# 0x430 - Ignition status (digital, cluster TX)

**Status:** Cluster sends

On the digital cluster `0x430` is a **cluster output**, byte 0 = `05` Run / `04` Off-Acc (echoes `0x3B2` ignition) -
not the odometer. The digital odometer is `0x179` byte 5 `OdoCount` (as the analog `0x179` distance-counter note describes).
Other digital cluster-TX detectors: `0x225` b3 = displayed speed (whole mph), `0x318` b5 bit7 = a popup is on screen.

# Topics

## 0x470 / 0x17E / 0x432 / 0x43E - Gauge-mode readouts (digital)

The digital cluster Gauge Mode / engine-data page adds readouts the analog does not. All latch their last value
(a hit in a fast sweep can show one step late). Confirmed on the bench by driving each byte and reading the screen:

| Readout | Frame / field | Scale |
|---|---|---|
| Engine oil temp (EOT) | `0x156` b1 `EngOil_Te_Actl` | C = raw - 60 (same as analog) |
| **Trans oil temp (TOT)** | `0x470` b3 (set b2 = `0xFF` to enable) | C = raw - 60 |
| **Eng oil pressure (EOP)** | `0x43E` b7 | 1 kPa / count |
| Air fuel ratio (AFR) | `0x43E` b3 | raw / 10 (same as analog) |
| **Vac / boost** | `0x43E` b5 | psi = `0.4628 x raw - 30.08`; vacuum shown in inHg (digital drove this via byte 5 alone; analog uses the 13-bit b5:b6 in database.md) |
| Inlet air temp (IAT) | `0x42D` b1[1:0]:b2 | raw x 0.25 - 128 C (same as analog) |
| **Manifold charge temp (MCT)** | `0x17E` b1 | C = raw x 0.5 - 20 |
| **Rear diff / axle oil temp (DT)** | `0x432` 9-bit b0[7:0] + b1.7; **enable = b1 bit6 (`0x40`)** | C = raw - 40 |
| Voltage | none - cluster measures its own 12 V supply | reads the bench PSU |

- Low oil-pressure warning telltale = `0x421` b2 (FF = warning, 0 = normal), consistent with the analog `0x421`.
- G-meter page (`0x76`) on the digital cluster would not take a dot from `0x76`, `0x92`, `0x77` or `0x416`; it appears
  computed internally from ABS + RCM data with live counters - still open on the digital unit.

## Fault / lamp suppression

The digital cluster latches more than the analog. Confirmed on the bench:

| Lamp / warning | Clear by |
|---|---|
| MIL + oil pressure | `0x421` zeros (b0[3:2] MIL, b2.2 oil) |
| Park-brake fault (moving in gear) | `0x213` = `FF FF 00 00 00 11 FF 41` |
| Blind-spot lamp | `0x3A6` and `0x3A7` = `00 40 02 00 00 00 00 00` |
| TPMS lamp | `0x3B4` zeros |
| ABS / TCS / red BRAKE | `0x416` lamp fields 0 (a healthy ABS also clears them) |
| Lost-comm U-codes | module-presence frames held at zeros: `0x076`->U0121 (ABS), `0x168`->U0103 (GSM), `0x223`->U0193 (DACM), `0x2E3`->U0253 (APIM); pair `0x2A1`+`0x3E6`->U0212 (SCCM) |
