# KL3T (2019 digital IPC) Firmware Reverse-Engineering Notes

Reading the IPC application firmware from Ford VBF flash files to cross-reference CAN behaviour
(primarily: which IDs the cluster subscribes to, and the service-required / wrench logic).
Analog KR3T findings are in `KR3T_NOTES.md`, confirmed FR33 findings in `FR33_NOTES.md`.

## File

| VBF | Year / cluster | Compression | Section base | Decompressed size | Status |
|---|---|---|---|---|---|
| `KL3T-14C026-BD` | 2019 **digital** IPC | none (`data_format_identifier` absent/0x00) | 0x8000 | 0x1F8000 (as-is) | **fully readable** |

Chip: **SPC667221VLU** (ST SPC56 family, Power Architecture e200 core → **big-endian**). FR33-10849-GF
cluster board uses the same part, so KL3T is the closest proxy for the bench FR33. Flash map (from the chip RM):
`0x0000-0x7FFF` primary bootloader, `0x8000+` main application.

## RX subscription table [DONE]

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

## Receive path and the wrench [mapped 14 Nov 2026]

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
analog cluster (`KR3T_NOTES.md`), the digital adds **0x46A** and drops 0x179. The bench sends 0x46A as all zeros, so
input 4 never clears. That explains why the 0x14C-only probe (14 Nov 2026) still showed the wrench.

## Tooling

- `vbf/canscan.py <bin> [base_hex] [be|le]` — scan an **uncompressed** image for the RX ID hash table
  (16-bit halfwords, `FFFF` padding) and list subscribed IDs. Auto-detects endianness.
- `vbf/vledis.py <addr> <len>` — minimal VLE disassembler for the digital image (base 0x8000). Tracks simple register
  constants (r13 / r2 included) and prints the absolute address of each load/store it can resolve. Calls preserve the
  callee-saved r14-r31, so stores made through a register set before an `e_bl` (e.g. the 0x404C writers) still resolve.
- `vbf/vlexref.py mem|ptr|call|fn ...` — whole-image xrefs for the digital image: loads/stores into an address
  range, r13/r2 pointer materialisation into a range, callers of a target, function start of an address.

## UDS diagnostic tables — DID read (0x22) + routine/IO (0x2F/0x31) [decoded 18 Nov 2026]

Both firmwares carry two parallel 16-byte-record tables that drive the UDS server. Same Vendor diag
stack, same record shape; **analog KR3T is little-endian (load 0xC100), digital KL3T is big-endian (base
0x8000)**. The digital KL3T is the SPC56/VLE platform — the closest proxy for the **bench FR33** — so trust
the *digital* addresses for bench work and the analog ones (`KR3T_NOTES.md`) only as corroboration.

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
session/security state word, and emits an NRC on mismatch. Three tiers gate the **same DIDs in both firmwares**:

| analog | digital | meaning |
|---|---|---|
| `0x5F` | `0xFD` | bulk — default + extended session, any security (readable in a plain `0x10 03`, no key) |
| `0x7F` | `0xFF` | all three sessions, any security (ID part numbers, `0xD100`) |
| `0x2F` | `0xF2` | **programming session only** (`F162` analog / `F162 F17C F180` digital) |

So almost every DID reads in a plain extended session with no key; the `0x2F`/`0xF2` tail needs a programming
session (`0x10 02`), which the bench is still blocked on — see [[ipc-security-access]]. The digital checker
`0x52E08` uses **high nibble = security, low nibble = session** (the reverse of analog); the bit assignments are in
"Digital `2E 40 4C`" below.

### Addresses

**DID table `0x11C710`, 102 records** `0x11C710-0x11CD60`; routine/IO **`0x11BF60`, 14 records**. Dispatcher
`~0x53A88`; access-check `0x52E08`; state word `0x40004746`. Masks: 95×`0xFD`, 4×`0xFF`, 3×`0xF2`
(`F162 F17C F180`). DID set:
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

### DID 0x404C — distance/main counter counter [decoded 18 Nov 2026]

Read chain, fully traced: table entry `0x11C720` (`len=3`, mask `0xFD` = **readable in a
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

#### Write path — 0x179 byte 5 → 0x40003D08 [traced 18 Nov 2026]

The counter is only ever rebuilt from the distance pulse count in `0x179` byte 5 (the `2E 40 4C` setter below can
only raise it):

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
The analog KR3T counts the same 0.2 m per tick but rolls a km every 5000 (`KR3T_NOTES.md`).

TODO: live `22 40 4C` (expect ≈ `11 3D 2C`) and `22 FE 61`; check a known game distance with the corrected
`ODOMETER_COUNTS_PER_MILE = 8047`.

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

### Zero path, 404C write, PCM learn — compared with analog [traced 18 Nov 2026]

Same job as the analog KR3T, different design (analog side in `KR3T_NOTES.md`, "Getting `0x32BE6` to 0").
**There is no main + offset split and no zeroing routine.** Analog → digital map:

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

**Digital `2E 40 4C` exists.** The shared pool `0x11BF60` has `0x2E` records 18-31, the same set as analog minus
`FD35/FD36`: ids `404C 4197 601E 601F DE00-DE09` (pool `0x11C624`). Record 18 = `404C`: length 6, mask **`0x44`**,
handler **`0x55352`**:

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
