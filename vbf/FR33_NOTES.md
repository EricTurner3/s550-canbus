# FR33 IPC notes

The bench cluster: 2015 Mustang analog IPC on an SPC56 (Power Architecture, big-endian, VLE code). Only confirmed
findings go here. Leads from the KL3T / KR3T images stay in `KL3T_NOTES.md` / `KR3T_NOTES.md` until the FR33 image confirms them.

## Strategy F188 `FR33-14C026-AG`
| | |
|---|---|

| Range | `0x00008000-0x000FFFFF` (1,015,808 bytes). Load the file at **base `0x8000`** |
| Verified | 16 upload sections, each matching the CRC-16/CCITT-FALSE the bootloader returns on `37` (0 mismatches) |
| `0x8000` | app header: `FF×8  DEADBEEF DEADBEEF  FF×8  A55AA55A 0001 000C` |
| `0x10000` | VLE code |
| Not in the image | `0x0000-0x7FFF` (bootloader: `35` there → NRC 0x31) and anything at `0x100000` or above (NRC 0x31) |

Tooling: `VLE_IMAGE=fr33 python -I vledis.py <addr> <len>` (and `vlexref.py`). Small-data bases are set at
`0xDC46`/`0xDC54`: `r2 = 0x000FC418` (ROM constants, used heavily) and `r13 = 0x40003000` (barely used; RAM is mostly
addressed with `e_lis` absolutes).

## Diagnostic access

| Session | Security | 
|---|---|---|
| `10 03` extended (app) | `27 03/04` | 
| `10 03` extended (app) | `27 31/32` (needed by `2E 40 4C`) | 
| `10 02` programming (bootloader) | `27 01/02` only. Every other level → NRC 0x12. Wrong keys don't lock out | 


## App UDS tables

Same layout as the KL3T app, at different addresses:

| table | address | layout |
|---|---|---|
| SID → service index | `0xA4BF2` (indexed by SID − 0x10) | `10→0 11→1 14→2 19→3 22→4 23→5 27→6 2E→7 2F→8 31→9 34→10 35→11 36→12 37→13 3D→14 3E→15`, plus index 16 for SID 0x45 |
| service records | `0xA4C28`, 8 bytes × 18 | byte 5 = first record index (the next service's byte 5 = end) |
| shared record pool | `0xA4CB8`, 16 bytes × 110 | `+0` request length (0 = any), `+4` access mask, `+8` attr, `+12` handler |
| identifier pool | `0xA5398` | sessions `01 02 03`; security `01 02 03 04 31 32`; 2E ids `404C 4197 601E 601F DE00-DE05 FD35 FD36`; 2F ids from `61A4` |
| DID read table (0x22) | contains `0xA54AC` (`404C`), 16 bytes per record | `+0` DID, `+2` length, `+4` mask, `+12` handler |

The app has **`0x23`, `0x35` and `0x3D` (WriteMemoryByAddress)** services (pool records 10, 103, 106; handlers
`0x5EF18`, `0x5F9BE`, `0x5FA08`). Their address checks haven't been decoded yet.

**Access mask** (checker `0x61788`, state word `0x40009490`): the low nibble of the mask's top byte is tested against the
session bits (bit0 `10 01`, bit1 `10 02`, bit2 `10 03`), miss → NRC 0x7E. The high nibble is tested against the security
bits (bit1 `27 01`, bit2 `27 03`, bit3 `27 31`), miss → NRC 0x33.

**0x2E records 17-28** (pool `0xA4DC8`…):

| DID | length | mask | needs | handler |
|---|---|---|---|---|
| `404C` | 6 | `0x8C` | extended + **`27 31/32`** | `0x5EF3E` → `0x188F0` |
| `4197` | 5 | `0xFC` | extended | `0x5EF5C` |
| `601E` / `601F` | 5 / 6 | `0xFD` | default or extended | `0x5EF7C` / `0x5EF9C` |
| `DE00-DE05` | 11 | `0x4C` | extended + `27 03/04` | `0x5EFBC` … `0x5F066` |
| `FD35` / `FD36` | 4 / 5 | `0xFC` | extended | `0x5F088` / `0x5F0A8` |

## Main counter (DID `404C`)

Same design as the analog KR3T: total = **main counter + offset**, in 0.1 km.

| function | address | behaviour |
|---|---|---|
| read handler | `0x627F8` → `0x60538` | `0x347F4(0)`, 3 bytes big-endian |
| getter | `0x347F4(p)` | offset = NvM read `0x350D0` (status other than 1/2 → 0), ×64/103 when `p≠0`; main = `0x347A2(p)` (RAM `0x40008ABC` + sub-count `0x8E74A(2)`); returns `min(main + offset, 9,999,999)` |
| write worker | `0x188F0` | data length 3 → else NRC 0x13. `new` must be **greater than** `0x347F4(0)` → else NRC 0x31. Then `0x3471A(new)` |
| commit | `0x3471A` | NvM idle `0x8DFB0() == 1` → else returns with **no response**. `new < 0xF59236` → else NRC 0x31. Encode `0x346A6`; round-trip check `0x21C1C` → else NRC 0x13; encoded ≤ `0x1609375` → else NRC 0x31. Then NvM write `0x8DF52(0, &rec, 1)` and **offset = 0** via `0x35132(0, 0)` |

So `2E 40 4C` can only raise the total, and it needs level `0x31`.

**Main counter storage:**
- RAM `0x40008ABC` = whole km as **packed BCD** (decode `0x27970`, one digit per nibble, capped at `0x99999999`).
  For example 112,990 km = `00 11 29 90`.
- Sub-km = an accumulator at 5000 counts/km (`0x8E74A(2)` / `0x8E380(2, …)`).
- NvM record (encoder `0x346A6`): `{u32 BCD km, u16 sub-count}`, from a 0.1 km input.
- Boot `0x33FD0`: NvM read → RAM `0x40008ABC`.
- Increment `0x34142`: when the accumulator reaches 5000 it subtracts 5000, sets RAM = BCD(RAM + 1 km) (`0x27A9E`) and
  **writes RAM to NvM** (`0x8DF52(1, &ram, 1)`), capping at `0x1609375`. So whatever RAM holds is what gets saved at
  the next km.

## WriteMemoryByAddress `0x3D` (app)

Handler `0x5FA08` → worker `0x17926`. Pool record 106 has mask `0xFF` (any session, any security), and the service
entry allows every session. Checks, in order:

| check | rule | else |
|---|---|---|
| format | ALFID `0x14` (4-byte address, 1-byte size) or `0x24` (2-byte size) | 0x31 |
| length | request length = header + size | 0x13 |
| size | ≤ 255 | 0x31 |
| range | `0x40000000-0x4000BFFF` (RAM) → `0x1785C` byte copy, after `0x18846`, which always returns 1 | 0x31 |
| range | `0xFF000000-0xFF0003FF` → `0x178BC`, only while `0x40008B06` is 2 or 3 | 0x22 |

`0x23` ReadMemoryByAddress (handler `0x5EF18` → `0x1776C`) has the same shape: RAM from `0x40000000`, ≤ 255 bytes,
plus the `0xFF00xxxx` window.

**Consequence:** `3D 14 40 00 8A BC 04 <BCD km>` sets the main counter in RAM, up or down, with no security. The
getter `0x347F4` reads RAM on every call, and the increment `0x34142` saves RAM to NvM at the next km.
**Confirmed on the bench (18 Nov 2026):** `ipc_dtc_test.py odo set=<km>` changes the reading, up and down.
`s550_cluster.py` uses it to follow the game's odometer (`ODOMETER_SYNC`).

## Gauge motors and the needle sweep

The app drives the needles itself through the chip's stepper motor controller. Nothing in the app sweeps the needles at
key on: every caller of the sweep is the self test routine, an IOControl or the hidden self test menu.

| layer | address | |
|---|---|---|
| SMC (stepper motor controller) | `0xFFE60000` | coil duty registers `+0x20 … +0x36`: 12 coils = 6 motors. Stall detect blocks at `0xFFE61000 … 0xFFE63800` |
| coil writer | `0x8F7BA(motor, microstep)` | sine table `0xF2C18`, indexed by `microstep & 0x1FF` |
| profile engine (one per gauge) | `0x2B000` for gauge 2 | 3 phases: ramp start → peak, hold, ramp peak → end. Positions are fractions of full scale (`0xFFFF` = full) |
| start a profile | `0x2CF16` `0x2CFE2` `0x2B4D0` `0x2E592` (gauges 0 - 3) | `cfg = {u8 mode, u16 up ms, u16 down ms, u16 hold ms, ptr → {u16 start, peak, end}}`. Mode 4 ends by itself |
| sweep all 4 gauges | `0x187EC(up, hold, down)` | start 0, peak `0xFFFF`, end 0 |

**Routine `0x0202` (self test)**, `31 01 02 02`, needs `10 03` and no security (record mask `0xFC`). Routine IDs
`0202 0301 0304 2047 F001 FF00 FF01` at `0xA4BB0`. Start `0x1636C` → NRC `0x13` with any data after the ID, NRC `0x22`
when the gate `0x166FE` fails, NRC `0x24` while it's already running. The gate wants `0x40008B06 == 2`, `0x400081E9`
set, and either the speed signal invalid (`0x40007E38 & 7`) or speed `< 300` with `(0x400078F0 >> 13) & 3` = 2 or 3.
`0x40008B06` comes from table `0x9D2C0` on the key nibble (`0x40007A08 >> 12`): `4` → 2, `8` → 3, `2` → 4, else 4. Stop `31 02 02 02`
(`0x1643C`), results `31 03 02 02` (`0x16494`). Seven steps, table `0x9AC14`:

| step | function | does |
|---|---|---|
| 0 | `0x16776` | `0x6AECE(32, 1)` |
| 1 | `0x16798` | the needle sweep: **2000 ms up, 500 ms hold, 2000 ms down**, all four gauges, then waits 225 calls |
| 2 | `0x16760` | ends the sweep |
| 3 - 6 | `0x16834 0x168C4 0x168FC 0x16934` | output and display steps |

The bench run of `31 01 02 02` (22 Nov 2026) swept all four needles, and also turned the screen white, lit every lamp
and sounded a long chime.

The hidden test menu runs its own sweep through `0x187EC`: **3000 ms up, no hold, 3000 ms down**. The UI is a
statechart, with nodes at `0xAB39C` (714 pointers) and the current node in `0x400096C4`. Nodes `0x1A5 → 0x28F → 0x290 → 0x291`
are menu items 1 - 4 (`0x69A58(n)`, events 7 / 6 move down / up). Entering item 2 (action node `0x2A7` →
`0x6A788(0x73, 7)`) starts the sweep. Leaving it (`0x6A788(0x15, …)`) stops it.

The other callers of the gauge starters are UDS IOControls (`0x18174` / `0x181EA` sweep one gauge for 3000 ms, `0x18D7A`
parks one at a percentage). The motor init (`0x8E94C`, `0x8F5A8`) only sets up pins and the SMC.

**Sweep state per gauge (RAM, writable with `0x3D`):**

| gauge | needle (bench, 22 Nov 2026) | base |
|---|---|---|
| 0 | speed | `0x4000881E` |
| 1 | RPM | `0x40008866` |
| 2 | fuel | `0x40008778` |
| 3 | coolant temp | `0x400088AE` |

| offset | field |
|---|---|
| `+0` `+2` `+4` | up, hold, down (u16, ms / 100, as `0x2B4D0` stores them) |
| `+6` `+8` `+A` | start, peak, end (u16, `0xFFFF` = full scale) |
| `+C` | tick count |
| `+E` | mode: 0 the gauge's own input, 1 hold at `+6` (fuel: `0x0000` E, `0xFFFF` F, linear), 4 run the profile once then back to 0 |
| `+F` | phase (0 up, 1 hold, 2 down) |

## Bootloader (`10 02`)

- `10 02` resets into the bootloader. The display goes dark. Key off or a power cycle starts the app again.
- Identity DIDs: `F180` = `01 FR33-14C025-AB`, `F111` = `FR33-14F094-GA`, `F113` = `FR33-10849-GF`, `D100` = `02`,
  `F162` = `05`. `F181 F182 F186 F188 F110 F124 F125` → NRC 0x31.
- RequestUpload `35` checks in this order. Only the last check depends on the SBL:

| check | passes | fails with |
|---|---|---|
| format | ALFID `0x44` (4-byte address, 4-byte size) | 0x13 |
| data format | `0x00` | 0x31 |
| range | inside `0x8000-0xFFFFF` | 0x31 (`0x0`, RAM `0x4000xxxx`, `0x00FFC000`, `0x100000+`) |
| condition | SBL downloaded and activated | 0x22 |

## SBL `FR33-14C025-AB` (`vbf/FR33-14C025-AB.vbf`)

- Volvo-format VBF: `ecu_address 0x720`, one block of 984 bytes at file address `0x00000000`, `call = 0x40002000`.
  Block CRC = CRC-16/CCITT-FALSE (`5CED`, echoed by the bootloader's `37`).
- It's NXP's C90 flash driver, with no CAN/UDS code. A function table at +4: `0x242` unlock blocks, `0x1E2` lock,
  `0x2D8` erase (`MCR=ERS`, `EHV`), `0xF6` program (`MCR=PGM`, `EHV`), and `0x020` verify. Lock passwords
  `A1A11111 / B2B22222 / C3C33333`.
- Loading and activating it only writes RAM. The app boots normally after key off (tested twice).

## Reading the flash

`python ipc_dtc_test.py upload` (about 160 s). No erase and no download to flash.

```
10 02                                   -> 50 02 (wait ~1.5 s, bootloader starting)
27 01 / 27 02 <key>                     -> 67 02
34 00 44 00000000 000003D8              -> 74 20 0FFF
36 01 <984 SBL bytes>                   -> 76 01
37                                      -> 77 5CED
31 01 0301 40002000                     -> 71 01 0301 10
35 00 44 <addr> <size>                  -> 75 20 0FFF   (max block 0xFFF)
36 <seq> ...                            -> 76 <seq> <data>
37                                      -> 77 <CRC-16/CCITT-FALSE of the section>
```

Requests over 7 bytes need ISO-TP multi-frame. Big replies occasionally lose a frame; asking for the same `36 <seq>`
again returns the same block.

## Calibration `F124` `FR33-14C088-RJ` (graphics / text package)

Everything in this section is from the calibration file `vbf/FR33-14C088-RJ.vbf`, not the `F188` app.

| | |
|---|---|
| VBF | `sw_part_type = DATA`, `data_format_identifier 0x10`, one block at **`0x80000000`**, erase `0x80000000` + `0x00FFFFF0` |
| Unpack | `vbf_lzss.decode` (same LZSS as the KR3T), 4,022,088 → **16,777,200 bytes** (the header's byte count). Used data ends at `0xE1FDF4`, the rest is `FF` |
| `+0x00` | `F7B68974 3030E801`, then `FR33-14C088-RJ` in ASCII |
| `+0x20 - 0x47BA0` | 480-pixel-wide 8-bit greyscale test screens: grey ramps, plus a sample screen (Fuel History, compass `NW`, adaptive-cruise car with gap bars, `76 MPH`, odometer, gear `6`). The display is 480 px wide |
| `+0x49400 …` | string pointer tables and UTF-16BE strings (below) |
| the rest | images and fonts. No index in this file, and the app has no plain `0x80xxxxxx` pointers to them. The index is probably in the app's compressed RAM-init data (around app `0xF5100`). Not solved yet |

### Strings

- UTF-16BE, NUL-terminated. Each table is an array of 32-bit pointers (`0x80xxxxxx`) to strings, laid out as
  **n items × 18 languages**, one language after another: EN-US, FR, ES, PT-BR, EN-UK, DE, IT, FR-CA, ES-EU, TR, RU,
  NL, PL, SV, PT-PT, zh-TW, zh-CN, AR. A string that's the same in two languages is stored once, and both pointers point to it.
- The app lists the tables in 8-byte records at app `0xEC89C` (menus) and `0xECB4C` (156 message-center
  messages), plus `0xED380`, `0xEDA00` and `0xEDBBC`.

| pointer table | pointers | contents |
|---|---|---|
| `0x49400` | 4428 | menus and settings |
| `0x62A18` | 10063 | message-center messages |
| `0x973E0` | 162 | compass: `N NE E SE S SW W NW --` |
| `0x97794` | 487 | Gauge Mode units and states: `°C °F V inHg psi bar`, `Low / Normal / Warm / High`, `Volts` |
| `0x984E4` | 72 | cruise: `SET`, `MPH`, `km/h` |
| `0x98644` / `0x99D70` | 183 / 126 | tire pressure units, `Hold OK to Reset`, reset states |
| `0x99490` / `0x9AB00` | 343 / 128 | trip and fuel: `gal l Used avg`, `Avg MPG`, `L/100km`, `km to E` |
| `0x9B2DC` | 3550 | Track Apps screens |
| `0xA3280` / `0xA6078` | 739 / 630 | Oil Life, MyColor RGB, MyKey, languages, confirmation pop-ups |
| `0xA8A3C` | 1512 | screen titles |

### Menus (English)

| menu | items |
|---|---|
| main | Gauge Mode, Trip/Fuel, Track Apps™, Driver Assist, Settings |
| Gauge Mode | Air/Fuel Ratio, Boost/Vacuum, Cylinder Head Temp, Inlet Air Temp, Oil Pressure, Oil Temp, **Trans Oil Temp**, **Voltage** |
| Trip/Fuel | Trip 1, Trip 2, Fuel Economy, Fuel History (last 30 minutes), Average Speed, Distance to Empty |
| Track Apps | Accelerometer, Acceleration Timer (Automatic / Countdown Start; 0-30/60/100 MPH, 0-1/8, 0-1/4 Mile), Brake Performance (60-0, 100-0 MPH), Line Lock, Launch Control (RPM), View/Clear Results (All Time Best) |
| Driver Assist | AdvanceTrac, Active City Stop, Auto Engine Off, Blindspot, Collision Warning (Sensitivity), Cross Traffic Alert, Cruise Control (Adaptive / Normal), Hill Start Assist, Rear Park Aid, Seatbelts, Tire Monitor, View Camera (Guidelines, Zoom 1-5) |
| Settings | Vehicle (Alarm, Easy Entry/Exit, Lighting, Locks, Oil Life Reset, Park Lock Control, Remote Start, Tire Mobility Kit, Windows, Wiper Controls), MyColor (Gauge Color, Halo, Ambient Light, Set MyColor 1-3), MyKey, Display Setup (Distance, Temperature, Tire Pressure, Language) |

The 088 has no navigation strings, no digital-speedometer screen, and no compass calibration or zone menu.
`MPH` / `km/h` appear only next to cruise `SET`, in Average Speed, and in Track Apps.

The bench cluster reports `F124 = FR33-14C088-RF`. The file here is **RJ**, a later revision of the same calibration.

### As-built gates for these screens (CyanLabs Visteon L3 database, checked against the bench as-built)

| field | location | bench | effect |
|---|---|---|---|
| Avg Speed Display (ASD) | `720-01-01` digit 6, bit 2 | `0` disabled | hides Trip/Fuel → Average Speed |
| GPS / Magnetic compass | `720-01-01` digit 9 | `7` (GPS) | the compass letters come from `0x466` |
| CHT / IAT / Oil Pressure / Oil Temp | `720-06-01` digit 4 | `F` all on | |
| AFR, Battery Voltage, Boost/Vac | `720-06-01` digit 3 | `7` all on (Virtual Gauges off) | Voltage is enabled, but its CAN input isn't known yet |
| **Transmission Fluid Temp Display** | `720-06-01` digit 5 | `0` disabled (`8` = enabled) | hides Gauge Mode → Trans Oil Temp |
| **Digital Speedometer Feature (DSF)** | **`720-07-01`** digit 4, bit 0 | **no block 07** | not available on FR33 |

FR33 has as-built blocks `720-01 … 720-06` only. `DE06` doesn't answer, and the app's 0x2E table stops at `DE05`.
The 2019 KR3T app has `DE06`, so the digital speedometer bit came with later software. KR3T is a different
microcontroller (RH850), so its software can't go onto this cluster.

The 2016 GT350 cluster (service part `FR3Z-10849-CA`) does have block 07. Forum reports say GT350s read
`720-07-01 xxx1 …` (DSF on) and other cars `xxx0`. Owners of 2015-17 GT clusters say Forscan rejects 720-07 as an
invalid selection, which matches FR33. Same `FR3` design year as this cluster (`FR33-10849-GF`), so the GT350 is
likely the same hardware family with a different `F188` / `F124`. Not confirmed: we have neither its part numbers nor its VBFs.

### Message center (English, table `0x62A18`)

- **Doors and body:** Driver Door / Passenger Door / Rear Left / Rear Right Door Ajar, Door Ajar, Hood Ajar, Trunk Ajar,
  Convertible Top Deactivated / Not Secure, Child Lock fault, Vehicle Alarm, Switches Inhibited
- **Engine:** LOW Engine Oil Pressure, Engine Coolant Overtemperature, Oil Change Required, Change Engine Oil Soon,
  Engine Shuts Off in ^#^ Seconds (Press OK to Override), Engine Has Shut Off for Fuel Economy, Engine ON,
  Charging System Service Soon / Service Now, Battery State of Charge Low, Low Battery Features Temporarily Turned Off
- **Fluids:** Fuel Level Low, Check Fuel Fill Inlet, Washer Fluid Level Low, Brake Fluid Level Low
- **Brakes and chassis:** Check Brake System, Park Brake Engaged, Hill Start Assist Not Available, AdvanceTrac
  Service / Off / On / SPORT MODE, Traction Control Off / On, Hazards Activated Due to Spinout Detected, Steering
  Fault / Loss / Assist Fault / Lock Malfunction / Col. Lock, Drive Mode (Normal, Snow/Wet, Sport +, Track) and
  Steering Feel (Normal, Sport, Comfort) pop-ups and their "Selection Not Available" messages
- **Transmission:** not in Park, Warming Up, Overtemperature / Overheating Stop Safely, Too Hot Press Brake,
  Malfunction, Service Required, Limited Function, Adjusted, AdaptMode, IndicatMode Lockup On / Off, Neutral Tow
  Enabled / Disabled, Press Brake to Unlock Park, Park Unlocked
- **Tires:** Tire Pressure Low, Sensor Fault, Monitor Fault, Train (each) Tire, Training Complete, Tire Not Trained,
  Service Tire Mobility Kit, Tire Low
- **Start and keys:** Press Brake / Clutch to START, To Drive: Turn Key to ON / Press Brake and Start Button,
  No Key Detected, Cranking Time Exceeded, Restart Now or Key is needed, Run Power Active, Starting System Fault,
  Engine Start Pending, Pending Start Cancelled, Key Program Successful / Failure, Max Number of / Not Enough Keys
  Learned, Key Battery Low
- **Driver assist:** Collision Warning, Adaptive Cruise (Not Available, Malfunction, Shift Down, Speed too Low, Driver
  Resume Control, Sensor Blocked), Normal Cruise Active, Front Sensor Not Aligned, Active City Stop, Blindspot /
  Cross Traffic (System Fault, Not Available, Vehicle Coming from Left / Right), Rear Park Aid, Check Rear Park Aid,
  Occupant Sensor BLOCKED, Seatbelts / Rear Belt Monitor
- **MyKey:** MyKey Active, Speed Limited to ^#^, Check Speed, Near / at Top Speed, Buckle Up to Unmute Audio, Park
  Aid Cannot be Deactivated
- **Other:** Launch Control Not Available, Line Lock Not Available / Release, View/Clear Results While Stopped,
  MyColor Not Adjustable In Daytime, Memory ^#^ Saved / Recall Not Permitted, Transport / Factory Mode Contact Dealer,
  Dimming, See Manual

`^#^` is where the cluster inserts a number.
