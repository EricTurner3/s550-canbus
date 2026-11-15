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
`KR3T-14C026-AC_com.json`. Addresses below are runtime addresses (load 0xC100). An earlier pass assumed 0xC000,
so older notes quoting `0x145334` / `0x148906` / "288 RX IDs" / "125 timeouts" are 0x100 low and wrong on counts.

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

Also found on the way: a UDS DID table at `0x147E90` (`{DID, length, 0x5F, 0x0F, handler}`, Ford DIDs
`0x404C 0x4190-0x4197 0xFD70...`) and a routine/IO table at `0x147640`.

## Tooling

- `vbf/canscan.py <bin> [base_hex] [be|le]` — scan an **uncompressed** image for the RX ID hash table
  (16-bit halfwords, `FFFF` padding) and list subscribed IDs. Auto-detects endianness. Good for the digital
  image; on the analog one it runs on into the handle table, so use `kr3t_com_extract.py` there.
- `vbf/vbf_lzss.py <section.bin> [out.bin]` — decompress a VBF `data_format_identifier=0x10` section
  (bit-packed Okumura LZSS, EI=10/EJ=4/P=1).
- `vbf/rh850dis.py <addr> <len>` — minimal RH850 disassembler for the analog image (load 0xC100).
- `vbf/vledis.py <addr> <len>` — minimal VLE disassembler for the digital image (base 0x8000). Tracks simple register
  constants (r13 / r2 included) and prints the absolute address of each load/store it can resolve.
- `vbf/kr3t_com_extract.py` — analog receive config → `KR3T-14C026-AC_com.json` (IDs, handles, DLC, init bytes,
  monitors and deadlines, wrench inputs).
- `vbf/make_can_notes.py` — `KR3T-14C026-AC_com.json` + `database.md` + DBC + freeze frame →
  `KR3T-14C026-AC_CAN_Notes.json`/`.md`. Keeps `required_bytes` / `notes` across re-runs.
