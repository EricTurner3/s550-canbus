# TODO

## Wrench / See Manual (the last warning on the bench)

No DTC is behind it. Per the workshop manual it defaults on when the transmission, engine or body service required
message is missing for 5 s, and one missing is enough. The lead and everything tried are in database.md under
[Wrench / See Manual](database/database.md#wrench--see-manual-powertrain-malfunction-rtt).

Per the manual it should go out as soon as all three messages arrive, so watch it mid-run first. If it stays, pull
the cluster's power for 10 s with the candidates still running. Exit with Ctrl+C, not by closing the window (key off
sequence).

- [x] No faults with the 2.6.0 heartbeat (Forscan, 12 Nov 2026), the wrench stays
- [x] `0x46A` value sweep, the GWM frames in groups of 7, `watch off` / `watch zeros`: nothing
- [x] **1. The service required frames we don't send**, zeros (quiet, 1 min). **No change** (13 Nov 2026).
      `0x168 0x263 0x4A2` are confirmed RX messages in the 2019 digital firmware (`vbf/KL3T_NOTES.md`),
      but sending them didn't move the wrench. It also returns instantly on a power cycle mid-run, so it's a
      default-on state, not a latched fault.
      ```
      python ipc_dtc_test.py probe dummy 168 263 4A2
      ```
- [x] **2. Every unsent ID at once**, zeros (`probe dummy 000-6FF@1000`): no change
- [x] **3. `0x14C` with byte 3 bit 0 set** (analog firmware): wrench still back ~5 s after power up (14 Nov 2026)
- [x] **4. `0x14C` + `0x46A` with byte 3 bit 3 set: wrench OFF, stays off through a power pull (14 Nov 2026). SOLVED.**
      ```
      python ipc_dtc_test.py probe 14C=0000000100000000@100 46A=0000000800000000@100
      ```
- [x] Both in the `s550_cluster.py` heartbeat (14 Nov 2026): `send_trans_service` (`0x14C`, `00 00 00 01 ...`) and
      `send_gwm_present` (`0x46A` byte 3 `08`), 10 Hz.
- [ ] Run the plain heartbeat (no probe): wrench off from power up, U0146 still away (`ipc_dtc_test.py read`), nothing
      new on the display.
- [ ] Ask the two builders with the same wrench which frames they send, and anyone with a BCM on a bench for its HS3
      / HS1 frames (body service required, and the `07 01` request on `0x3E0`)

## Firmware RE

Full state in `vbf/KR3T_NOTES.md` (analog) and `vbf/KL3T_NOTES.md` (digital); FR33 in `vbf/FR33_NOTES.md`.

- [x] **Decompress the analog KR3T VBF**: bit-packed Okumura LZSS (`vbf/vbf_lzss.py`), image loads at 0xC100.
- [x] **Analog receive path + wrench (14 Nov 2026).** RH850 code, read with `vbf/rh850dis.py`, pulled out by
      `vbf/kr3t_com_extract.py`: 172 RX IDs with handle, DLC, init bytes, message-missing deadline (5 s, `0x3A6`
      `0x3A7` 1.6 s, 13 unmonitored) and the frame bits each watches, plus the wrench inputs (`0x14C` / `0x179` /
      `0x3B2`). Notes: `vbf/KR3T-14C026-AC_CAN_Notes.{md,json}` via `vbf/make_can_notes.py`.
- [x] **Digital wrench mapped (14 Nov 2026)** with `vbf/vledis.py`: routine `0x0A8A86`, inputs `0x14C` / `0x46A` /
      `0x3B2` always, `0x263` / `0x4A2` / `0x46B` by config. See KL3T_NOTES.md.
- [ ] What config params 13 / 205 / 245 are (`0x4E836`), and their values on the FR33 (as-built?).
- [ ] Richer `sample_bytes` in the notes from `canbus_samples/EricTurner3/2016_gt350_car/*.csv` (`build_web.py` already takes the first sample per ID);
      only the freeze frame is used now.
- [x] **UDS strategy dump of our own cluster (FR33)**: done 18 Nov 2026, `vbf/FR33-14C026-AG.bin` (see `vbf/FR33_NOTES.md`)
- [ ] Odometer sync on the road: drive 1 km after a sync and confirm the value survives a power cycle (NvM commit at
      `0x34142`). Find a SimHub property for the car's odometer, if any game exposes one.
- [ ] Map the rest of the FR33 image (wrench / warnings, the PCM learn on `0x166`) and move confirmed items into
      `FR33_NOTES.md`.

## Needle sweep (FR33 routine 0202)

The FR33 app only sweeps from its self test (routine `0202`, also white screen, every lamp, chime) and the hidden test
menu (`vbf/FR33_NOTES.md`, Gauge motors). `s550_cluster.py` (`SWEEP_MODE = 'cluster'`) writes that sweep profile into
each gauge's RAM with `0x3D` at key on, so the cluster sweeps all four needles itself.

- [x] `selftest`: all four needles sweep, plus white screen, lamps and a long chime (22 Nov 2026)
- [x] `SWEEP_MODE = 'cluster'`: all four needles sweep at key on, nothing else on the display (22 Nov 2026)
- [x] Which base is which gauge: 0 speed, 1 RPM, 2 fuel, 3 coolant temp. Fuel `0x0000` E, `0xFFFF` F
- [ ] `FUEL_SYNC` in a game (ATS `fuel` / `fuelCapacity`, SimHub `FuelPercent`) and the `live_test.py` slider

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
