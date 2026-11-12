# TODO

## Wrench / See Manual (the last warning on the bench)

No DTC is behind it any more. What has been tried is in database.md under [0x46A](database.md#0x46a---gwm-present).
The only time it moved: with all 28 bench GWM frames held at once it went out for ~4 s.

For every run: note the clock time whenever the wrench goes out, even briefly. Each log line is printed at the
**end** of its 14 s test. Exit with Ctrl+C, not by closing the window (key off sequence).

- [ ] **0. New default, nothing else.** `0x223` (radio present) went in after the last bench run and hasn't been on the
      cluster yet. Expect no faults at all after the clear.
      ```
      python ipc_dtc_test.py clear dummy
      ```
      Does the wrench blink off right after `clear: ok`? If it does, it follows a code, not a signal.
- [ ] **1. `0x46A` the way a real GWM fills it** (~2 min). A TCS lamp may come on, on the 2018 cluster some of these
      bits are traction control.
      ```
      python ipc_dtc_test.py sweep 46A dummy 0000000800000000 0000008000000000 0000000000100000 0000000000002000 0000008000102000 0000000800102000 FFFFFFFFFFFFFFFF
      ```
- [ ] **2. The GWM frames in groups of 7** (~1.5 min), to find the group that made the wrench blink.
      ```
      python ipc_dtc_test.py scan dummy batch=7 file=other_refs/GWM_HS3_2018_KeyOn.csv
      ```
      If one group does it, rerun with `batch=1` and that group's ID range (e.g. `... batch=1 270-2FF file=...`).
- [ ] **3. Frames we already send** (~7 min each), if 1 and 2 find nothing. One ID at a time not sent, then as zeros.
      Other lamps flicker, only the wrench matters.
      ```
      python ipc_dtc_test.py watch off dummy
      python ipc_dtc_test.py watch zeros dummy
      ```

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
