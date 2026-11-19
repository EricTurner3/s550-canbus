# IPC Firmware (VBF) Reverse-Engineering Notes

Reading the IPC application firmware from Ford VBF flash files to cross-reference CAN behaviour
(primarily: which IDs the cluster subscribes to, and the service-required / wrench logic).

## Files

| VBF | Year / cluster | Compression | Section base | Decompressed size | Status |
|---|---|---|---|---|---|
| `KL3T-14C026-BD` | 2019 **digital** IPC | none (`data_format_identifier` absent/0x00) | 0x8000 | 0x1F8000 (as-is) | **fully readable** |
| `KR3T-14C026-AC` | 2019 **analog** (GT 401A) | **0x10 = compressed** | **loads at 0xC100** (erase 0xC000) | 0x3B3F00 (3,882,752) | **DECODED** (`vbf_lzss.py`), receive path mapped |

Chip: **SPC667221VLU** (ST SPC56 family, Power Architecture e200 core → **big-endian**). FR33-10849-GF
cluster board uses the same part. Flash map (from the chip RM): `0x0000-0x7FFF` primary bootloader,
`0x8000+` main application.

**The 2019 analog KR3T is a different platform:** its code is **Renesas RH850 (little-endian)**, RAM at
`0xFEDxxxxx`, gp = `0xFEDD9334`, tp = `0x00136048` (startup at `0x070F14`). So KR3T is not the same hardware
as the bench FR33 (SPC56). Its CAN behaviour is Ford-specified and the wrench text in the manual is the same for
2015 and 2019, but treat KR3T findings as strong leads for the FR33, not proof.

`python-vbf.py` (Jakka351 GUI unpacker) extracts raw blocks and verifies CRC16, but **does not
decompress** `0x10` sections — it writes the compressed bytes verbatim.

## Digital (KL3T) — RX subscription table [DONE]

CAN IDs are stored as **big-endian 16-bit halfwords**, hash-indexed, with `0xFFFF` = empty slot
(so IDs cluster but aren't sorted). The RX table is at **addr 0x117A00-0x117C00** (file off −0x8000).

**122 distinct subscribed IDs:**
```
001 010 018 028 048 04C 051 052 076 077 07A 081 082 084 086 090 101 102 108 109
14C 156 163 166 168 169 175 178 179 17C 17D 17E 188 18A 19B 1D6 202 203 204 20B
213 227 22A 262 263 274 277 279 27A 27E 281 282 2A1 2AC 2CF 2D9 2DE 303 304 30B
30C 312 349 361 38A 38D 3A8 3AA 3AB 3B1 3B2 3B3 3B4 3B5 3B8 3C3 3CD 3D0 3D8 3E1
3E5 3E6 3E7 400 404 408 40A 412 416 41F 420 421 422 424 42C 42D 42F 431 432 43E
440 443 444 445 44A 44E 452 466 46A 46B 470 471 4A2 4D0 59C 5C4 644 650 720 798
7A4 7DF
```

Relevant to the wrench / service-required logic (distinctive IDs, solidly in the dense cluster):
- **Present:** `0x179 0x431 0x3B3 0x43E 0x46A 0x168 0x263 0x4A2 0x178 0x42C 0x42D 0x421`.
- The three bench candidates from `TODO.md` (**`0x168 0x263 0x4A2`**) are all confirmed RX messages.
- `0x230` is ambiguous: a `02 30` BE16 hit sits in the table region, but that's a common byte pattern and it
  is **not** in the tight diverse cluster, so don't rely on it either way. (Note the analog FR33 uses `0x230`
  for gear where the digital uses `0x171` — `database.md` — so analog subscription may differ regardless.)

The 122-ID list above is the dense *core* of the table from a narrow window; the full hash table extends
further (canscan.py with the tightened anchors reports a larger set). Treat it as "these are definitely
subscribed", not "only these".

### Digital (KL3T) — receive path and the wrench [mapped 14 Nov 2026]

Code is **Power Architecture VLE**, read with `vledis.py`. Startup at `0x116EAC`: r1 = `0x4000FFD4`, r2 = `0x001751F8`
(ROM small data), **r13 = `0x4000A4D0`** (RAM small data). Same table layout as the analog cluster, big-endian:

- Hash keys `0x117A50` (167 slots, FFFF = empty), sorted list `0x117BA0` (38 entries, stored as **ID<<2**),
  handles `0x117BEC` (keys) / `0x117D3A` (list). **140 RX IDs, handles 0-139**: 0x179 = 109, 0x3B2 = 46, 0x3B3 = 45,
  0x14C = 119, 0x46A = 5. DLC per handle `0x117D88`, RX buffer pointers `0x117E18` (131 Com handles, `0x4000xxxx`).
- Unlike the analog cluster, each message has its own generated handler that unpacks bits into RAM variables and
  reloads a deadline counter (625 or 1250 ticks, about 5 s). A per-signal handler table sits at `0x164C54`
  (384 entries). A timeout callback per message sets its "lost" flag.

**The wrench** (`0x0A8A86`): ORs up to seven inputs into `0x40006E88` and drives telltale (3,4) through `0xA5CDE`. It
only evaluates when `0xB2E42(0) == 0`, `0xAE154() != 0` and RAM `0x40003BDE == 0`. Each input is "lost flag set → on;
else no-data flag set → skip; else service bit == 1 → on". Some are switched by vehicle configuration
(calls to `0x4E836(param, value)`):

| Input | Gate | Message | "Lost" clears only when | Service bit (must be 0) |
|---|---|---|---|---|
| 1 / 2 | config 13 == 1 / == 2 | `0x263` | (not read) | (struct `0x40007FD0`) |
| 3 | always | `0x14C` | **byte 3 bit 0 = 1** (handler `0x0D01DE`, reload 1250) | byte 2 bit 0 |
| 4 | always | `0x46A` | **byte 3 bit 3 = 1** (handler `0x0D4C8A`, reload 1250) | byte 5 bit 4 |
| 5 | always | `0x3B2` | any frame (handler `0x0CF81C`, reload 625) | byte 1 bit 2 |
| 6 | config 205 == 1 | `0x4A2` | | byte 2 bit 5 (LsdSrvcRqd) |
| 7 | config 245 == 1 | `0x46B` | | byte 7 bit 2 |

`0x179` is **not** a wrench input here (its handler `0x0D07C8` reads bytes 0, 4-5 and byte 2 bit 6, none feed it).
`0x168` / `0x169` service bits are unpacked (`0x0D7E28` / `0x0D7E48`) but nothing reads them. Compared with the
analog cluster, the digital adds **0x46A** and drops 0x179. The bench sends 0x46A as all zeros, so input 4 never
clears. That explains why the 0x14C-only probe (14 Nov 2026) still showed the wrench.

## Analog (KR3T) — compression [SOLVED]

Section is Volvo/Ford compressed (`data_format_identifier = 0x10`). The algorithm is **Haruhiko
Okumura's educational LZSS, BIT-PACKED** (not the ring-buffer `getc()` LZSS, and not LZHUF) — the same
code Volvo's "VBF CONVERT" uses, reproduced in `smartgauges/qvbf` (`lzss.cpp`). Parameters:

- **EI=10** → window **N=1024**, 10-bit offset   **EJ=4** → 4-bit length (match copies len+2 = 2..17 bytes)
- **P=1** → matches ≤1 byte are emitted as literals
- Bitstream **MSB-first**: flag bit **1 = literal** (next 8 bits); flag bit **0 = match** (10-bit offset,
  then 4-bit length). A match whose 10-bit offset field reads **0 = end-of-stream**.
- Window pre-filled with `' '` (0x20); output pointer `r` starts at 0; offset is an **absolute** window
  index, stored 1-based (decoder does `i -= 1`).

`vbf/vbf_lzss.py` implements it. `1,657,227 → 3,882,752` bytes, **exactly** the header's `Bytes:` count.
Output head is `a5 5a a5 5a …` and it contains the real part strings `KR3T-14C026-AC`, `KR3T-1A292-AA`,
`GR33-14C025`, `-10849`, `-14F094`.

Why earlier attempts failed: the tokens are **bit-granular** (9-bit literals / 15-bit matches packed
continuously), so every byte-aligned LZSS decoder desyncs. The near-random 7.88 bits/byte entropy is just
dense firmware content (compressed assets/fonts), not a Huffman layer. `consp/vbfdecode`,
`esaulenka/vbf_parser` and `jakka351/python-vbf` only unpack blocks; they do not decompress `0x10`.

```
python vbf_lzss.py <section_001_...C100...bin> out_C000.bin   # the file name says C000, it loads at 0xC100
python -I kr3t_com_extract.py && python -I make_can_notes.py      # receive config -> notes
```

## Analog (KR3T) — receive path and the wrench [DONE, 14 Nov 2026]

Read from the code with `rh850dis.py` (a small RH850 disassembler) and pulled out by `kr3t_com_extract.py` into
`KR3T-14C026-AC_com.json`. Addresses below are runtime addresses (load **0xC100**).

**Receive path** (frame → handle → buffer → monitors):

1. CanIf lookup `0x0129A0`: `slot = (id + 0x56) % 223`, linear probe in the key table `0x145434` (u16, FFFF =
   empty) → handle from `0x1456B4`. IDs not in the hash sit in a sorted LE32 list `0x1455F4` (handles `0x145872`).
   **172 RX IDs, handles 0-171**: 0-161 go through Com (sorted by ID descending), 162-171 are diagnostics
   (`0x7DF 0x720`) and a `0x2A7-0x2CF` block.
2. `0x128D6` sets a "received" bit per handle (`0xFEDD9528`, byte `0x145EE0[h]`, mask `0x145F8C[h]`). DLC per
   handle at `0x1458D4` (also the RX buffer length: `0x168` / `0x169` are 3 bytes, `0x3B3` 7).
3. Com task `0x0145A0` copies the frame to the RX buffer (`0x145980[h]`) and calls the handle's callback
   (`0x146720[h]`). Init values per handle at `0x146CBC[h]` (copied in by `0x0142F6` at start-up).
4. Each callback sets one or more **monitor flag bits** (`0xFEDD9582`), unconditionally ("message present") or
   only when a specific **frame bit is 1** ("signal asserted").
5. Two monitor loops time those flags:
   - **G2** `0x05356C`, 138 items (`0x1488D4` flag byte, `0x148960` mask, `0x1489EC` timeout u16): one per message,
     "message present". 123 × 500 ticks (5 s), **0x3A6 / 0x3A7 = 160 ticks (1.6 s)**, 13 at 0 = not monitored
     (`0x084 0x086 0x090 0x091 0x191 0x194 0x19B 0x1D6 0x1E6 0x30B 0x30C 0x440 0x466`).
   - **G1** `0x053392`, 159 items (`0x148794` / `0x148834`), fixed 500 ticks: one per frame bit.
   - Item state (`G2 0xFEDDBA08[i]`, `G1 0xFEDDB7C8[i]`): 5 at start-up (not received yet), 0 after a frame,
     bit 1 set after the timeout (3 if it never arrived).

Every monitor maps to its source except G1#1 and G2#15. Per ID, the notes file has the deadline, the
bit monitors and the firmware init bytes.

**The wrench** (`0x0483EC`, called per input by `0x0483A4`, result in `gp+6584`): six inputs at `0x1443C0`, each
`{state getter, value getter, value that requests}`. An input requests the wrench when its watchdog has timed
out (state & 6 == 2), or when the message is fine and the service bit equals 1. Which inputs count depends on a
config mode (`0x42BAA`) through `0x144408`, but the table is the same in all three modes:

| # | Active | Watchdog | Service bit |
|---|---|---|---|
| 0 | **yes** | G1#16 = `0x14C` received with **byte 3 bit 0 = 1** | `0x14C` byte 2 bit 0 |
| 1 | **yes** | G2#30 = `0x179` received | `0x179` byte 2 bit 3 (EngSrvcRqd) |
| 2 | no | G2#26 `0x169` | `0x169` byte 2 bit 3 |
| 3 | no | G2#25 `0x168` | `0x168` byte 2 bit 7 (GsmSrvcRqd) |
| 4 | **yes** | G2#93 = `0x3B2` received | `0x3B2` byte 1 bit 2 (the DBC's BodySrvcRqd position) |
| 5 | no | G2#49 `0x263` | `0x263` byte 0 bit 0 (AwdSrvcRqd) |

So three messages, as the manual says: **engine = 0x179, body = 0x3B2 (not 0x3B3), transmission = 0x14C**. That
is why `0x168` / `0x263` / `0x4A2` never moved it, and why zeros on every ID didn't either: 0x14C's watchdog
only counts frames with byte 3 bit 0 set. The bench sends 0x179 and 0x3B2 with their bits clear and doesn't
send 0x14C at all. Test: `python ipc_dtc_test.py probe 14C=0000000100000000@100`.

Also found on the way: a UDS DID table at `0x147E90` and a routine/IO table at `0x147640` — both fully
decoded in **"UDS diagnostic tables"** below (analog + digital).

## Analog (KR3T) — cruise control set speed [found 14 Nov 2026]

The workshop manual lists "Cruise control set speed display: GWM → HS-CAN3 → IPC". `0x202` byte 4-5 (`Veh_V_RqCcSet`)
and `0x165` byte 2 (`Veh_V_DsplyCcSet`) both showed nothing on the bench, and `0x165` isn't an RX ID here. The GWM
repacks the set speed into **`0x077` byte 4** on HS3.

**Signal getters.** Com has one small getter per signal at `0x052FB0 - 0x055F86` (`ld.bu X[gp]` → shift / mask →
`jmp [lp]`), sorted by CAN ID, each usually paired with a status getter on a `0xFEDDB7xx - 0xFEDDBAxx` byte (timeout /
invalid, `& 7 == 0` = OK). Signals that span bytes have their own getters at `0x04DA2C - 0x04DF00`
(`mov <RX buffer>, ep` + `sld.bu`). The ones that matter here:

| Getter | Signal |
|---|---|
| `0x054A92` | `0x42C` byte 0 bits 7 - 5, cruise status (the icon). `0x42C` has no 8 bit signal |
| `0x053BFA` / `0x053C02` | status / value of **`0x077` byte 4, cruise set speed** |
| `0x053C0A` / `0x053C12` | status / value of `0x077` byte 5 bit 1 |

**Cruise telltale** `0x01BFC8` ORs four parts into one state word:

- `0x01BEAE`: a 2.5 s timer (`gp+1496`, up to 250 ticks) and the `0x42C` cruise status, kept in `gp+1498`
- `0x01BF2A`: `0x077` byte 5 bit 1 = 1 with status OK → `0x40`; status `& 6 == 2` → `0x100`
- `0x01BF5A`: `0x077` byte 4. **1 - 253 is the set speed**, kept in `gp+1499`; `0xFE` / `0xFF` are invalid and kept as
  0; non-zero → `0x80`; timed out → `0x100`. The range matches the DBC's `Veh_V_DsplyCcSet` (0 - 253, no scale)
- `0x01BF9C`: `0x3D8` byte 4 bits 3 - 2 → `0x200`

**Display.** `0x01B5A6` picks what the cruise display item shows from the HMI state in `gp+1460` (bits 19 - 18). In
state `0x40000` it is `gp+1499` (read back by `0x01C004`), the set speed. In state `0x80000` it is `0x077` byte 4 read
directly (same `< 0xFE` check). Either way the value goes to `gp+1464` with a byte from `0x138910` (`01 00`), picked by
bit 0 of `0x036862()`, likely km/h / mph. The number is shown as sent, so send it in the cluster's display unit.

So the bench never showed it: the steering warning fix frame (`FF FF FF FF FF FF 00 FC`) has `FF`, "invalid", in
byte 4. Bench test: `python interactive_brute_force.py cruise77` (byte 4 swept on the fix frame, icon green).

## Tooling

- `vbf/canscan.py <bin> [base_hex] [be|le]` — scan an **uncompressed** image for the RX ID hash table
  (16-bit halfwords, `FFFF` padding) and list subscribed IDs. Auto-detects endianness. Good for the digital
  image; on the analog one it runs on into the handle table, so use `kr3t_com_extract.py` there.
- `vbf/vbf_lzss.py <section.bin> [out.bin]` — decompress a VBF `data_format_identifier=0x10` section
  (bit-packed Okumura LZSS, EI=10/EJ=4/P=1).
- `vbf/rh850dis.py <addr> <len>` — minimal RH850 disassembler for the analog image (load 0xC100).
- `vbf/vledis.py <addr> <len>` — minimal VLE disassembler for the digital image (base 0x8000). Tracks simple register
  constants (r13 / r2 included) and prints the absolute address of each load/store it can resolve. Calls preserve the
  callee-saved r14-r31, so stores made through a register set before an `e_bl` (e.g. the 0x404C writers) still resolve.
- `vbf/vlexref.py mem|ptr|call|fn ...` — whole-image xrefs for the digital image: loads/stores into an address
  range, r13/r2 pointer materialisation into a range, callers of a target, function start of an address.
- `vbf/kr3t_com_extract.py` — analog receive config → `KR3T-14C026-AC_com.json` (IDs, handles, DLC, init bytes,
  monitors and deadlines, wrench inputs).
- `vbf/make_can_notes.py` — `KR3T-14C026-AC_com.json` + `database.md` + DBC + freeze frame →
  `KR3T-14C026-AC_CAN_Notes.json`/`.md`. Keeps `required_bytes` / `notes` across re-runs.

## FR33 bootloader, SBL and flash dump

Moved to `FR33_NOTES.md` (FR33-only, confirmed findings).

## UDS diagnostic tables — DID read (0x22) + routine/IO (0x2F/0x31) [decoded 18 Nov 2026]

Both firmwares carry two parallel 16-byte-record tables that drive the UDS server. Same Vendor diag
stack, same record shape; **analog KR3T is little-endian (load 0xC100), digital KL3T is big-endian (base
0x8000)**. The digital KL3T is the SPC56/VLE platform — the closest proxy for the **bench FR33** — so trust
the *digital* addresses for bench work and the analog ones only as corroboration.

### Record layout (both tables)

| off | DID table | routine/IO table |
|---|---|---|
| +0 | `DID` (u16) | `rid` (u32, routine/IO identifier, e.g. `0x2F000`) |
| +2 | `len` (u16, bytes the read handler returns) | — |
| +4 | **access mask** (u32; significant byte `0x5F`/`0x7F`/`0x2F` analog, `0xFD`/`0xFF`/`0xF2` digital) | same |
| +8 | `attr` (`0x0F` analog / `0xF0` digital; read path uses 2 bits for a record flag) | `idx` (u16) + `id` (u16): selector into a fn table |
| +12 | `handler` ptr | `handler` ptr |

### Access mask (the "what level" answer)

A checker runs on `record+4` **before** the handler, AND-ing a sub-field of the mask against the live
session/security state word, and emits an NRC on mismatch (0x31 requestOutOfRange / 0x33
securityAccessDenied). The mask is a bit-field: **bits 6-4 = allowed sessions, bits 3-0 = allowed security
states** (decoded from the analog checker `0x50CF8`; see "Analog 0x2E WriteDataByIdentifier" below). Three
tiers gate the **same DIDs in both firmwares**:

| analog | digital | meaning |
|---|---|---|
| `0x5F` | `0xFD` | bulk — default + extended session, any security (readable in a plain `0x10 03`, no key) |
| `0x7F` | `0xFF` | all three sessions, any security (ID part numbers, `0xD100`) |
| `0x2F` | `0xF2` | **programming session only** (`F162` analog / `F162 F17C F180` digital) |

So almost every DID reads in a plain extended session with no key; the `0x2F`/`0xF2` tail needs a programming
session (`0x10 02`), which the bench is still blocked on — see [[ipc-security-access]]. Writes do exist: the
analog shared record pool `0x147640` carries a **0x2E WriteDataByIdentifier** block (records 17-32:
`404C 4197 601E 601F DE00-DE09 FD35 FD36`, including the main counter), documented under "Analog 0x2E" below. The
digital bit-field decode (`0xFD`/`0xFF`/`0xF2`) and whether digital exposes a 0x2E block are not yet checked —
treat the digital masks as the parallel values, presumed to encode the same tiers.

### Addresses

**Analog KR3T** (RH850, `rh850dis.py`): DID table `0x147E90` (~57 DIDs: `0x0202 404C 40B5 4190-4197
600E.. 61xx DE00-DE09 EE00-EE0F D100 D137 F110.. F15F F162`), routine/IO `0x147640` (11+ records).
Dispatchers `0x51418`/`0x52188` (read), `0x511FA` (routine); access-check `0x50CF8`; NRC emit `0x50E8A`;
state word `gp+8344`. The `0xEE00-0xEE0F` block = 16×250 B = the raw EEPROM/NVM mirror (where main counter
physically lives); reading it is key-free, writing it is a programming/NVM op, not a DID.

**Digital KL3T** (VLE, `vledis.py`): **DID table `0x11C710`, 102 records** `0x11C710-0x11CD60`; routine/IO
**`0x11BF60`, 14 records**. Dispatcher `~0x53A88`; access-check `0x52E08`; state word `0x40004746`. Masks:
95×`0xFD`, 4×`0xFF`, 3×`0xF2` (`F162 F17C F180`). DID set:
```
0202 2B05 404C 4190 4194-4197 6003 600E 600F 601A 601D 601E 601F 602C 602E 61A4 61A5 61A9 61B0-61B2
61B6 61B7 61CE 630F 6310 9A01 A48A D100 DE00-DE09 F110 F111 F113 F124 F125 F159 F15C F15E-F163 F166
F17C F180 F188 F18C F442 F47F FD03 FD04 FD09-FD15 FD22 FD25-FD2E FD51-FD68 FE00 FE03 FE40 FE61 FE70
```
Digital has no `0xEE0x` 250 B blocks; its NVM surfaces through the `FDxx`/`FExx` DIDs and `DE00-DE09`
config instead.

### Testing (bench, read + IO-control only)

Reuse `ipc_dtc_test.py` (0x720/0x728, `3E 80` keep-alive): `0x10 03`, then `0x22 <DID>` sweeps the whole
`0xFD` set key-free (add the level-0x03 key for the `0xF2` tail). The `0x11BF60` routine/IO table is the
useful bench primitive — `0x2F`/`0x31` to command gauges/telltales for test; invoke by the `rid` at +0
under its mask. All read/observe; no NVM/main counter writes.

### DID 0x404C — distance/main counter counter [digital, decoded 18 Nov 2026]

Digital KL3T read chain, fully traced: table entry `0x11C720` (`len=3`, mask `0xFD` = **readable in a
`0x10 03` session, no SecurityAccess**, handler `0x05540C`).

- Handler `0x05540C`: precondition check `0x55718` → NRC **0x22 conditionsNotCorrect** if not ready; else
  calls producer `0x47874` and sets response length 3.
- Producer `0x47874`: fetches a 32-bit value via getter `0xBDAE6(param=1)`, **divides by 10**, packs the
  quotient big-endian into 3 bytes. Getter "no-data" → returns `00 00 00`.
- Getter `0xBDAE6`: returns a **28-bit counter from RAM `0x40003D08`** (param 1; param 0 reads a sibling at
  `0x40003D04`). Invalid flag at `0x40003CF8` bit 3 → `0x7FFFFFFF` sentinel → bytes zeroed.
- `0x40003D08` is a field of a **checksum-validated NVM-backed struct** `0x40003D04..0x40003D1A` (validator
  `0xBD5E0` walks D04/D08/D14/D18/D1A through checksum `0xBC864`). Signature of a persisted main counter/distance
  store. `D04` = miles, `D08` = km (see write path below).
- **DID `0xFE61`** (handler `0x0553D4`) also reaches producer `0x47874`, so it returns the same km value.
- **No DID reads `param=0` (miles).** The `param=0` callers (`0x47776`, `0x4C40C`, `0x4C470`, `0x4C630`,
  `0x4C6AA`) are not reached from any of the 102 DID handlers within two call levels. They're the internal
  consumers (display / `0x430` TX).

**So `0x404C` = main counter in 0.1 km, 24-bit big-endian, read-only, key-free.** Bench check: the cluster's own
`0x430` reports `0x01B97E` = 112,990 km, so `22 40 4C` should return about `11 3D 2C`.

#### Write path — 0x179 byte 5 → 0x40003D08 [digital, traced 18 Nov 2026]

There is no DID write. The counter is only ever rebuilt from the distance pulse count in `0x179` byte 5:

| step | where | what |
|---|---|---|
| 1. RX | `0x0D07C8` (`0x179` handler) | RX buffer `0x40003350`; byte 5 → mirror `0x40008165`. `0xFF` = invalid → timeout monitor `0xCEE20` (reload 1250) |
| 2. Commit | `0x0D631E` (10 ms `0x179` task) | if status `0x40008166 == 0`: `0x40008164 = 0x40008165`. `0x0CD94C` writes the timeout default |
| 3. Delta | `0x0474A8` → `0x475D0` | when `0x40008164` changes, call `0xBD0AE(raw, flags)` |
| 4. Accumulate | `0x0BD0AE` | `delta = (raw − D18) & 0xFF` (flag bit1 → delta = raw; bit0 → 0); **`D20 += delta`** inside a critical section `0xBBD9E`/`0xBBDAE`; `D18 = raw`; re-stamp check bytes `D22`/`D1A` (`0xBC834`). If `D20 − D1C ≥ 49` → writer |
| 5. Rollover | `0x0BC91A` | if `D20 > 8047`: `D20 −= 8047`, **`D14 += 1`** (whole miles), re-stamp (`0xBC89C`), → writer |
| 6. **Writer** | **`0x0BD012`** | `D14` checked (`0xBC8F8`); if `D14 & 0x0FFFFFFF == 0x0FFFFFFF` (erased) → `D04 = D08 = 0x0FFFFFFF`. Else `x = max(D14−1, 0)·100 + D20·100/8047`; **`D04 = D08 = x`** (`0xBD07C`/`0xBD07E`), then **`0xBDA9E(&D08)`**: `x + (x·39 >> 6)` = ×1.609 (mi → km); re-stamp D04/D08 (`0xBC89C`); `D1C = D20` |

Other writer callers: `0xBD324`/`0xBD360` (restore from the NVM record at `0x400071A0`, `D14 = rec+8`),
`0xBCE64` (load path: rejects `D20 ≥ 8048` or `D14 > 1,000,001`), `0xBD64C`, `0xBD906`.

Units that fall out: **one `0x179` byte-5 count = one `D20` tick; 8047 ticks = 1 mile (0.2 m/tick)**. `D14` =
whole miles + 1, `D04` = 0.01 mi, `D08` = 0.01 km. `0xBDABE` is the reverse (×0.621, km → mi).

**Bench implication:** `s550_cluster.py` used `ODOMETER_COUNTS_PER_MILE = 8767` (measured from a log). The
firmware divisor is **8047**, so game miles read ~8% long. Corrected to 8047 on 18 Nov 2026. The counter is add-only
(delta of a rolling byte) and capped at 0xFF counts per change, so nothing reachable from CAN can lower it.

#### Method (repeatable for any DID)

1. **Table → handler → producer**: read the DID record (`0x11C710 + 16·i`, handler at +12) and follow the
   handler's calls (`vledis.py <handler> 80`) to the function that fills the response.
2. **Producer → storage**: follow the getter to the RAM address (here r13-relative, `-26568(r13)` =
   `0x40003D08`).
3. **Find writers, two ways.** `vlexref.py mem <lo> <hi>` lists resolved loads/stores. It found **only loads**
   for D04/D08, because the writer stores through a register (`se_stw r0, 0(r29)`). `vlexref.py ptr <lo> <hi>`
   lists every `e_add16i rX, r13, …` that builds a pointer into the range. The hit at `0xBD026`/`0xBD02A`
   (`r29 = D04`, `r30 = D08`) is the writer. Read code around each `ptr` hit.
4. **Callers both ways**: `vlexref.py call <fn>` up (who triggers the write), and along the struct's other
   fields (`D20`, `D14`) to find the input. Repeat `mem`/`ptr` on each new RAM address until it reaches a CAN
   RX buffer (`0x40003350` = `0x179`, handle 109).
5. **Decode the arithmetic.** Magic constants were the units: 8047 (mile / 0.2 m), 39/64 (0.609 → mi→km),
   25/103 (0.243 → km→mi), 1,000,001 (main counter max).

Tool caveat: both the `D04`/`D08` stores and the `0x40008164` commit use a callee-saved register set *before* an
`e_bl`, so the `mem` sweep only catches them because it preserves r14-r31 across calls. It still doesn't follow
branch targets, so `0xBD07C`/`0xBD07E` (reached after a jump) still need the `ptr` pass.

#### Analog KR3T comparison — same 0.2 m count, metric base [18 Nov 2026]

The constant 8047 appears nowhere in KR3T, as a 16- or 32-bit value. The analog firmware keeps the main counter in **km**:

- DID `0x404C` record `0x147EA0` (mask `0x5F`) → handler `0x051810` → `0x501EE` → getter **`0x32BE6(param 0)`**:
  reads an NVM block (`0x332B0` → manager `0x6BE94`, service `0x54`). `param≠0` applies `×64/103` (km → mi),
  then adds a sub-unit term `0x32BA8` and clamps to 9,999,999. Same 3-byte big-endian response as digital.
- `0x179` byte 5 = `gp+7377` (`0xFEDDB005`), read through getter `0x53E52`. Delta builders `0x323EA` / `0x326B2`
  return `(new − last) & 0xFF`, with `0xFF` = invalid.
- **`0x3270C`**: accumulator `+= delta`; at **≥ 5000** (`addi 0xEC78` = −5000) it subtracts 5000, increments
  the stored main counter `gp+4468` (`0x29F16`) and commits it (`0x6BE6C`, clamp `0x1609375`). `0x32444` is a
  second accumulator that rolls at 125,000 (= 25 × 5000).
- NVM writers: `0x332F8(slot, value)`. The callers are `0x32B22` (the `0x404C` write commit) and `0x20C66`
  (the `0x601F` write). Both are **0x2E WriteDataByIdentifier** handlers, documented below.

**Analog = 5000 counts/km, digital = 8047 counts/mi.** Both are 0.2 m per `0x179` byte-5 count
(5000 × 1.609344 = 8046.7). The sender's 8767 is wrong for both clusters.

TODO: live `22 40 4C` (expect ≈ `11 3D 2C`) and `22 FE 61`; check a known game distance with the corrected
`ODOMETER_COUNTS_PER_MILE = 8047`.

### Analog 0x2E WriteDataByIdentifier — tables, gating, 0x601F and 0x404C [KR3T, decoded 18 Nov 2026]

Static analysis of the **analog KR3T** only. The bench FR33 is analog (2015) using the same chipset, so treat this as a map of where to look on
digital, not as proof that the bench accepts these writes.

#### How a request is dispatched

1. SID → service index via the byte table at `tp+70871` (`0x50F52`): `10→0 11→1 14→2 19→3 22→4 23→5 27→6
   2E→7 2F→8 31→9 34→10 36→12 37→13 3D→14 3E→15`.
2. Service record = `0x147568 + 12·idx`. Byte 9 = first record index into `0x147640`; the next service's
   byte 9 = end; bytes 10-11 = offset of this service's identifiers in the pool `0x147D80`. The service record's
   own mask (`+4`) gates the whole SID: 0x2E is `0x5F`.
3. `0x50EBA` binary-searches the request's identifier bytes in the pool → record `0x147640 + 16·i`.
4. Record checks, in order: `+0` (u16) = **required total request length** incl. SID (`0` = any), compared to
   `gp+8436` → **NRC 0x13**; `+4` mask through `0x50CF8` → session miss / **NRC 0x33**; then the handler at `+12`.
   The handler gets a context: `[0]` → data after the DID, `[4]` = data length, `[8]`/`[12]` = response
   buffer/length. `+8` selects a pre-hook (`7` for most records, `0x107` for `404C`, `DE02-DE06`) that is
   **not decoded yet**.

#### Access mask (analog) — `0x50CF8`, state byte `gp+8344` (`0xFEDDB3CC`, reset value `0x11`)

| mask bits | meaning | values |
|---|---|---|
| 6-4 | allowed sessions (AND with state bits 6-4; miss → session NRC) | bit4 = default `10 01`, bit5 = programming `10 02`, bit6 = extended `10 03` |
| 3-0 | allowed security states (AND with state bits 3-0; miss → **NRC 0x33**) | bit0 = locked, bit1 = `27 01/02`, bit2 = **`27 03/04`**, bit3 = `27 31/32` |

Transitions come from `0x147464` (8-byte entries: if the current state is in the from-mask, set the new bits). Any
session change re-locks. The `27` key records carry the transition index in `+8` (`02`→4→bit1, `04`→5→bit2,
`32`→6→bit3). The seed requests `27 01` (mask `0x2F`) only work in **programming**; `27 03` and `27 31` (mask `0x4F`) work
in **extended**.

#### The 0x2E table (records 17-32)

| DID | req. length | mask | session | security | handler → worker |
|---|---|---|---|---|---|
| **`404C`** main counter | 6 (3 data) | `0x48` | extended | **`27 31/32` only** | `0x4F1E8` → `0x1F2D6` |
| `4197` | 5 (2) | `0x4F` | extended | none | `0x4F1FE` → `0x20EA2` |
| `601E` | 5 (2) | `0x5F` | default/extended | none | `0x4F216` → `0x20D90` |
| **`601F`** | 6 (3) | `0x5F` | default/extended | none | `0x4F22E` → `0x20C66` |
| `DE00-DE06`, `DE08-DE09` as-built | 11 (8) | `0x44` | extended | **`27 03/04`** (the solved key) | `0x4F246…` |
| `DE07` as-built | 13 (10) | `0x44` | extended | `27 03/04` | `0x4F30A` |
| `FD35` / `FD36` | 4 / 5 | `0x4F` | extended | none | `0x4F378` / `0x4F390` |

The 0x22 read side of `601F` is DID record `0x147F50` (len 3, mask `0x5F`, `0x4FC52` → `0x20CA6`).

#### DID 0x601F write — `2E 60 1F XX YY ZZ`

A raw 24-bit value in its own NVM block (block 1, through slot 1 of `tp+39748`). Nothing else in the firmware
reads that slot except the `601F` read and the write's own verify, so what it means is unknown.

| step | where | behaviour |
|---|---|---|
| gate | dispatcher | length must be 6 → else **NRC 0x13**; session default or extended, no key (`0x5F`) |
| params | `0x20C66` | data length must be 3 → else **NRC 0x13**. `value = XX<<16 \| YY<<8 \| ZZ`. **No range check, no request checksum** |
| write | `0x332F8(1, value)` | NvM write (`0x6BE6C`, op `0x16`) of block 1 = value, **then block 3 = 0** (same on every slot write) |
| verify | `0x20C50` → `0x20BE4`, every tick of `0x1EEEC` | read block 1 back (`0x332B0(1)` → `0x6BE94` op `0x54`). NvM result `0` → OK → **positive `6E 60 1F`**; result `4` (busy) → keep polling; anything else → force timeout. Counter `gp+1978` ≥ 500 ticks → **NRC 0x72 generalProgrammingFailure** |
| note | | the verify only checks that the read **completes**. It doesn't compare the value read back with the value written. Integrity is the NvM layer's own block CRC |

The handler sends no reply itself, so the response arrives only after the verify finishes. Expect the stack's
`7F 2E 78` (responsePending) if the NvM job outlasts P2. Not confirmed on the wire.

#### DID 0x404C write (main counter) — `2E 40 4C XX YY ZZ`

| step | where | behaviour |
|---|---|---|
| gate | dispatcher | length 6 → else **NRC 0x13**; **extended session + `27 31/32` unlocked** (mask `0x48`) → else **NRC 0x33** |
| params | `0x1F2D6` | data length 3 → else **NRC 0x13**; `new = XX<<16\|YY<<8\|ZZ`, units **0.1 km** (same scale as the read) |
| **forward-only** | `0x1F2D6` | `new` must be **strictly greater** than the current main counter from `0x32BE6(0)` (main + offset) → else **NRC 0x31** |
| NvM idle | `0x32B22` | `0x6BEC0(0)` must return 1 (block 0 job idle). Otherwise it returns **without sending any response** (tester times out) |
| range | `0x32B22` | `new < 0xF59236` (16,093,750 = 1,000,000 mi in 0.1 km) → else **NRC 0x31** |
| encode | `0x32AE6` | `km = new/10` (encoded via `0x29D32`), sub-km = `(new % 10)·5000/10` counts (5000 counts/km) |
| canonical | `0x25368` | per-field clamp of the encoded word must leave it unchanged → else **NRC 0x13**; word ≤ `0x1609375` → else **NRC 0x31** |
| commit | `0x6BE6C(0, &rec)` then `0x332F8(0, 0)` | writes the main main counter record, then **zeroes the offset block 0** (and block 3). The completion response hasn't been traced yet; there's no direct reply in the handler |

How the stored value fits together: `0x32BE6` returns `min(main + offset, 9,999,999)`, where main = `0x32BA8`
(km counter `gp+4468` + the 5000-count accumulator) and offset = NVM block 0. A `404C` write folds everything into main
and clears the offset. Because it's forward-only, **this DID can only raise the main counter**.

#### Getting `0x32BE6` to 0 — every writer of main and offset [traced 18 Nov 2026]

`0x32BE6(p)`: `offset` = NvM id 0 via `0x332B0(0)`. A result other than OK/busy leaves it **0** (stack word cleared
first). If `p≠0` it is scaled km→mi. Then it returns `min(main + offset, 9,999,999)`, all unsigned. A 0 needs
**main = 0 and offset = 0**, because neither term can be negative.

NvM addressing, from the code: writes go through `0x6BE6C(port, &rec, now)` (table `tp+850340`). Port 1 = main
counter (`0x3270C` commits there), port 0 = the `404C` commit, ports 3/4 = the two snapshots below. Port `0x16` = small
data records `{u32 value, u16 id, u16 flag}`: **id 0 = offset, id 1 = `601F`, id 2 = `601E`, id 3 = learn marker**
(slot→id table `tp+39748` = `0 1 4 4`). Reads go through `0x6BE94(op)`, where op `0x1C` = main, `0x1E`/`0x1F` = snapshots,
`0x54` = data records. `0x6BEC0(port)` returns 1 when the port is idle (pending mask `gp+17660`).

RAM: main `gp+4468` (`0xFEDDA4A8`). Snapshots `gp+4472`/`4480` and `gp+4476`/`4482` are copies of main + sub-count,
taken by `0x3276C`. `0x32C80(i,0)` → `0x3298C` returns **main − snapshot i** (table `0x13FB3C`). Flags are in `gp+4490`.

**Everything that writes main (`gp+4468`) or the offset (id 0):**

| writer | what it does | can it lower? |
|---|---|---|
| `0x3270C` | +1 km every 5000 counts of `0x179` byte 5 | no |
| `0x1F2D6` → `0x32B22` (`2E 40 4C`) | main = new (> current total), offset id 0 = **0** | no (forward-only) |
| `0x325FA` (boot) | main = NvM op `0x1C` read. **Read fails → main = 0 and sets `gp+4490` bit 2** | yes, on NvM failure only |
| **`0x32804`** (cyclic, via `0x328C8` ← `0x3290E`) | writes **zeros to ports 1-4** (main + both snapshots) and returns 4 → `gp+4490` bit 2, which latches until reset | **yes, the only zeroing code** |
| `0x33260` → `0x331C6` (PCM main counter learn, below) | offset id 0 = id 1 = `diff`, id 2 = 1 | no, adds only |
| NvM job callbacks `0x22xxx-0x29xxx` (e.g. `0x25C06`, `0x265F4`) | copy a finished NvM read back into RAM | no, restore only |
| `601E` / `4197` / `FD35` / `FD36` handlers | write id 2 / timers `0x186` `0x251` `0x252` via `0x743DE`. None touches main or id 0 | n/a |

**`0x32804` triggers** (any one of these):
1. `gp+4490` bit 2 is already set. That happens when the boot read of op `0x1C` returns something other than 0/1, or when
   a previous zeroing ran.
2. Port 1 idle and `0x6BE94(0x1C)` returns **2**. In this firmware's NvM codes 0 = OK and 4 = pending, so 2 is the
   invalid/blank-block status.
3. Any of ports 1-4 stays not-idle for **200** consecutive calls (counter `gp+4486`). This is a stuck-job watchdog.

It never clears the offset (id 0). On a blank part, though, id 0 reads back as failed → treated as **0**.

**PCM main counter learn — `0x33260` (cyclic, from `0x325CE`).** The external value is **RX `0x166` bytes 3-5**
(`OdoTripVerify_L_Actl`, 0.1 km, PCM), read through `0x53D16` → `0x4DE3C` (buffer `0xFEDDAE50`). The marker id 3 =
`0xAA55` means the learn window is open (`0x330C6`). Gates (`0x330FE`): `gp+6008` bit 5 set (`0x42F3C`, likely
ignition), `gp+4490 == 0`, and `gp+10033 & 7 == 0` / `gp+9963 & 7 == 0` (signal status), plus `0x33138`. `0x33166`
builds a 4-bit index:

| bits | meaning |
|---|---|
| 3-2 | ext ≤ 0.1 km → `00` (index forced to 0); 0.2-22.9 km → `01`; ≥ 23.0 km → `10`; `0xFFFFFF` → `11` |
| 1 | own (main − snapshot 0) ≥ 20.0 km |
| 0 | ext > own **and** ext − own ≥ 2.1 km. Out value = `ext − own` |

The action byte comes from `tp+39716[marker][index]`. Bit 2 = next marker (`0` / `0xAA55`), bit 1 = calls
`0x5516E(1)`, bit 0 = **write offset**.

- Window closed: index 0-3 (PCM reports ≤ 0.1 km) **opens** the window. Every other index leaves it closed.
- Window open: index 9 / 11 / 7 → **offset = ext − own, window closes**. Ext ≤ 0.1 km or invalid → stays open.
  Otherwise it closes without learning.

So a virgin cluster (main ≈ 0, snapshot 0) adopts the PCM's mileage as its offset. That is the replacement-IPC
learn. It can only add.

**What it takes to zero it:**

- **No UDS path lowers it.** `404C` is forward-only, the learn only adds, and the other 0x2E DIDs don't touch either
  term. A linear-sweep xref finds no other callers of `0x32804`/`0x328C8`, `0x332F8` or `0x331C6`, and no other
  stores to `gp+4468`. The `0x6BE6C` callers outside `0x32xxx`/`0x33xxx` weren't checked for port 1. The only firmware zeroing is
  `0x32804`, and that runs only on an NvM fault (block `0x1C` invalid or stuck).
- **Method = make the main counter NvM blocks invalid, then power-cycle.** Erase or corrupt the main-counter block
  (op `0x1C` / port 1) and the id-0 offset record in the cluster's data-flash/EEPROM image. At boot `0x325FA` gets a
  failed read → main = 0 and bit 2 set → `0x32804` writes zeros to ports 1-4 → the offset reads as failed → 0
  → **`0x32BE6` = 0**. This needs bench access to the NvM storage (or a 0x34/0x36 download, which is blocked behind
  the programming session).
- **Afterwards keep `0x166` at bytes 3-5 = `00 00 00` (or absent).** A 0 here opens the learn window (marker
  `0xAA55`). Any later PCM value ≥ 23.0 km would then be learned straight back in as the offset. `s550_cluster.py`
  doesn't send `0x166` today. While the window is open, an intentional `0x166` value is also the one way to
  **set** a chosen starting mileage on a zeroed cluster without touching `404C`.
- Still static-only. Not confirmed: the NvM status code 2 = invalid reading, and which data-flash addresses hold op
  `0x1C` / id 0 (the `0xEE00-0xEE0F` raw DID dump should show them; diff two dumps taken 1 km apart).

#### Digital KL3T equivalent — zero path, 404C write, PCM learn [traced 18 Nov 2026]

Same job, different design. **There is no main + offset split and no zeroing routine.** Analog → digital map:

| analog KR3T | digital KL3T | notes |
|---|---|---|
| getter `0x32BE6(p)` = main + offset | **getter `0xBDAE6(out, p)`** = `D08` (p=1, 0.01 km) / `D04` (p=0, 0.01 mi), 28-bit | no offset term. Returns 0 + `0x7FFFFFFF` when `0x40003CF8` bit 3 (invalid) is set |
| main `gp+4468` + NvM port 1 | `D14` (whole miles) + `D20` (0.2 m counts) → writer `0xBD012` → `D04`/`D08` | NVM = 5-slot ring (slot table `0x16D460`, writer `0xBC978`). Payload 4 B: `u16 miles>>7`, `miles & 0x7F`, slot\|0x80 |
| offset NvM id 0 | — | does not exist |
| set `0x32B22` (forward-only) | **set `0xBD906(x)`** (x = 0.01 km) | needs `D02 == 5` (else returns 2 = success with **no write**) and a valid ring record (`0xBCB94`). Requires `x ≥ D08`, miles ≤ 1,000,001. Writes 3 slots (≥ 2 must succeed), `D14` = miles + 1, `D20` = remainder |
| — | **initial set `0xBD760`** (no forward check) | only allowed while the current value is **< 16093 (160.93 km = 100 mi)**, and latches `CF8` bit 6 (one-shot). Called only from state 7 of the cyclic task `0x5265A` (task ptr `0x164580`) when `0x40002ED6` is set, with the value at `0x40002ED8`. **No code sets that flag**: `0x40002ED0-EDD` is only cleared (`0x525E0`). Dormant in this build |
| zeroing `0x32804` (NvM fault → 0) | — | **No digital code writes 0 to `D14`.** Its writers are `0xBC962` (+1), `0xBCFDC` / `0xBD354` (load/restore from record), `0xBD6D2` (init), `0xBDA62` (`0xBD906`) |
| blank NvM → main 0 | blank NvM → **invalid**, not 0 | init `0xBD64C` (ptr `0x163A08`): `D20 = 4024` (half-mile seed), `D02 = 5`, `D14` = ring record, or `0x0FFFFFFF` when `0xBCB94` finds none (that also sets `CF8` bit 3). Writer → `D04 = D08 = 0x0FFFFFFF`; the getter fails → `22 40 4C` = `00 00 00`. `0xBD906` then refuses (no valid record) and `0xBD760` refuses (current reads `0x7FFFFFFF`) |
| learn `0x33260` (window + marker) | **learn `0x47C18`** (from `0x47AD6`) | input = **`0x166` bytes 3-5** too (handle 116, buffer `0x40003210`, getter `0xB8074` → `0x400085CC` → `0x400085C8`). Diff = ext − own (own from `0x477D0`, minus reference `0x40000D40`). If diff < 1,610,000 → count `0x40000D38` += 1, total `0x40000D3C` += diff (≤ `0xFFFFFF`), then **`0xBD906`(own + diff·10)**. Adds only, through the forward-only setter. Float gates at 20.0 / 16.0 (`0xDE720`/`0xDE710`) not decoded |

**Digital `2E 40 4C` exists (corrects "no 0x2E on digital").** The shared pool `0x11BF60` has `0x2E` records 18-31,
the same set as analog minus `FD35/FD36`: ids `404C 4197 601E 601F DE00-DE09` (pool `0x11C624`). Record 18 = `404C`:
length 6, mask **`0x44`**, handler **`0x55352`**:

| step | where | behaviour |
|---|---|---|
| gate | `0x52E08` | mask byte: **high nibble = security, low nibble = session** (the reverse of analog). Sessions bit0 `10 01`, bit1 `10 02`, bit2 `10 03`, bit3 `10 60` (from pool `01 02 03 60`). Security bit0 locked, bit1 `27 01/02`, bit2 **`27 03/04`**, bit3 `27 61/62` (pool `01 02 03 04 61 62`). `0x44` = **extended + `27 03/04`** = the solved level-0x03 key, the same tier as the DE00 as-built writes (analog `404C` needs `27 31/32` instead). Session miss → NRC 0x7E, security miss → NRC 0x33 |
| pre | `0x55718` | same precondition as the read → else **NRC 0x22** |
| pre | `0xC0FD8` | `0x40003D94 != 0xFF` → else **NRC 0x33** (meaning of `D94` unknown) |
| value | `0x55352` | `x = (XX<<16\|YY<<8\|ZZ)·10`, then stub `0x478C8` adds 10 (+0.1 km) → `0xBD906(x)` |
| result | | `0xBD906` = 0 (below current / no valid record / > 1,000,001 mi) → **NRC 0x22**; otherwise positive. The positive reply also comes back when `D02 ≠ 5` and nothing was written |

**So the KL3T can't be zeroed the analog way.** The setters are forward-only, the initial-mileage setter is dormant,
and an erased ring gives an invalid main counter (`00 00 00` / likely dashes) that no DID can then write. The only route
to a real 0 is writing a **valid** ring record with miles = 0 into the NVM (all 5 slots, payload `00 00 00 8n`).
Even then init seeds `D20 = 4024`, so it reads 0.50 mi / 0.80 km (`22 40 4C` → `00 00 08`) until the
next accumulator commit. Static only. Not traced: whether driving with an erased ring ever writes a fresh record
(`0xBD1BA`/`0xBCDB8` ring writers, `0xBD360` restore), and the `D14` +1 offset between the record and RAM on reload.

**Digital service map, no `0x3D`.** SID → index table `0x11BE88` (indexed by SID − 0x10), 8-byte service records
at `0x11BEC0`: `10 11 14 19 22 23 27 2E 2F 31 34 36 37 3E` (plus one more at index 14). **There is no
WriteMemoryByAddress (`0x3D`)** on KL3T (analog has it, index 14), so RAM `D14`/`D20` can't be poked over UDS.
That leaves three ways to set an arbitrary value (down as well as up): the NVM ring on the bench, a
`0x34/0x36` download (programming session, still locked), or a firmware patch that removes the `x ≥ D08` compare in
`0xBD906`. **Up-only sets work today**: `10 03`, `27 03/04`, `2E 40 4C` with a value one tenth below the target (the
handler adds +0.1 km), and NRC 0x22 if the value is below the current reading.

#### Open items

- `+8` pre-hook dispatch (`7` vs `0x107`): the table at `tp+70664` didn't resolve to functions, so the reading is wrong somewhere.
- ~~What blocks 1/2/3 represent~~: id 1 (`601F`) = copy of the learned offset, id 2 (`601E`) = learn-done flag (set
  to 1), id 3 = learn-window marker (`0xAA55` = open). Every `0x332F8`/`0x33374` write sets id 3 = 0, which closes the window.
  See "Getting `0x32BE6` to 0".
- The `404C` completion path, and whether `27 31/32` uses the same key algorithm as level 0x03.
- ~~Repeat on digital KL3T~~: done. `0x11BF60` is the shared pool and has the 0x2E block (records 18-31). See
  "Digital KL3T equivalent".
