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
- [ ] **1. The service required frames we don't send**, zeros (quiet, 1 min).
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
