# FR33 IPC notes

The bench cluster: 2015 Mustang analog IPC on an SPC56 (Power Architecture, big-endian, VLE code). Only confirmed
findings go here. Leads from the KL3T / KR3T images stay in `FIRMWARE_NOTES.md` until the FR33 image confirms them.

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
