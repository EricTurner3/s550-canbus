# TODO

## Wrench / See Manual (the last warning on the bench)

No DTC is behind it. Per the workshop manual it defaults on when the transmission, engine or body service required
message is missing for 5 s, and one missing is enough. The lead and everything tried are in database.md under
[Wrench / See Manual](database.md#wrench--see-manual-powertrain-malfunction-rtt).

Per the manual it should go out as soon as all three messages arrive, so watch it mid-run first. If it stays, pull
the cluster's power for 10 s with the candidates still running. Exit with Ctrl+C, not by closing the window (key off
sequence).

- [x] No faults with the 2.6.0 heartbeat (Forscan, 12 Nov 2026), the wrench stays
- [x] `0x46A` value sweep, the GWM frames in groups of 7, `watch off` / `watch zeros`: nothing
- [x] **1. The service required frames we don't send**, zeros (quiet, 1 min). **No change** (13 Nov 2026).
      `0x168 0x263 0x4A2` are confirmed RX messages in the 2019 digital firmware (`vbf/FIRMWARE_NOTES.md`),
      but sending them didn't move the wrench. It also returns instantly on a power cycle mid-run, so it's a
      default-on state, not a latched fault.
      ```
      python ipc_dtc_test.py probe dummy 168 263 4A2
      ```
- [ ] **2. Every unsent ID at once**, zeros once a second (~1,700 frames/s, every other warning lights up, only the
      wrench matters). `@2000` if the gauges drop out, still inside the 5 s timeout.
      ```
      python ipc_dtc_test.py probe dummy 000-6FF@1000
      ```
      If the wrench goes out: halve the range (`000-37F@1000`, `380-6FF@1000` ...) until the frames are found. It may
      need two of them together, so when neither half does it, keep one half and split the other.
- [ ] **3. If it stays on with everything present** a bit is set in a frame we send. Step 2 again with `0x179` and
      `0x230` as zeros on top (`... 000-6FF@1000 179 230`), then `0x3B3` byte 1 bit by bit.
- [ ] Ask the two builders with the same wrench which frames they send, and anyone with a BCM on a bench for its HS3
      / HS1 frames (body service required, and the `07 01` request on `0x3E0`)

## Firmware RE (next steps for the wrench)

Now that bench step 1 failed, go to the firmware. Full state in `vbf/FIRMWARE_NOTES.md`; scanner `vbf/canscan.py`.

- [ ] **Bench step 2 still untried** — every unsent ID at once (`probe dummy 000-6FF@1000`), then bisect. Cheapest
      thing left that doesn't need more RE; worth running before the firmware dig.
- [ ] **COM timeout table in the digital image** (`KL3T...section_001_00008000...bin`). The wrench is "service-
      required message missing 5 s → default on", so find the COM per-message RX timeout table: a parallel array,
      same hash index as the RX ID table at ~0x117A00, holding each PDU's timeout value (look for `0x1F4`=500ms /
      `0x5`=5 units near the service IDs 0x179/0x431/0x3B3) and a timeout-action/callback. That's the mechanism.
- [ ] **Decompress the analog KR3T VBF** (`KR3T-14C026-AC`, closest to our FR33). Section is Volvo-compressed
      (`data_format_identifier 0x10`); the unpacker doesn't decode it. Canonical Okumura LZSS desyncs → likely
      chunked. Next: find the chunk framing in the raw bytes, decode per chunk, then `canscan.py <bin> C000`.
- [ ] **(Optional) UDS strategy dump of our own cluster** — blocked: `RequestUpload` needs programming session
      (0x10 02) + L1 security (`0x01`, a different generator than the solved 0x03). Capturing L1 pairs safely is
      the hard part (the Forscan op that unlocks L1 is a reflash = brick risk). See `uds_security.py` (gitignored)
      and memory `ipc-security-access`. Try `memread ... session=03 sec=03` first — if 0x23 reads flash under the
      key we already have, L1 is moot.

## Smaller things

- [ ] Occupant Sensor Blocked is sent as `18` now (was `88`): check `warning_occupant_sensor_pass` still shows it
      (live_test.py)
- [ ] `icon_cruise_control` 1 / 2 in live_test.py: green / grey SET icon
- [ ] Which ID in `0x14D - 0x194` shows "Collision detection unavailable" (U0405-56) at zeros:
      `python ipc_dtc_test.py scan dummy batch=8 14D-194`, watch for the message
- [ ] `0x42C` byte 2: which bits turn the battery icon off (`sweep 42C dummy bits=1000FF009C600000`, 16 min, or just
      the 8 bits of byte 2)
- [ ] "Press Clutch to Start" (`0x38D` byte 4 `C0`) during the 1.5 s key off lead-in, cosmetic
- [ ] The `dtc_*.txt` logs in the repo root: keep, move or add to .gitignore
