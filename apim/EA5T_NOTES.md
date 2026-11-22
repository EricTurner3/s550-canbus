# EA5T-14D544-BA - Sync Gen2 APIM software (V3.10.16180)

Notes from the Ford Sync Gen2 USB update in `apim/EA5T-14D544-BA/` (git-ignored, Ford's files). Only confirmed
findings are recorded here; open questions are in their own section at the end.

The bench APIM: F188 strategy **EM5T-14D205-AD**, F113 ES7T-14D212-DA, FD02 software `4.32.14073_PRODUCT`.
It answers UDS on 0x7D0 / 0x7D8 on the same 500k bus as the IPC (`ipc_dtc_test.py <mode> ecu=7D0`).

## Tools (this folder)

| Script | What it does |
|---|---|
| `sec_unpack.py` | `.sec` (or the zip holding it) -> raw `.img`; `split` -> boot sections + one file per partition |
| `exfat_extract.py` | exFAT partition image -> list / files (read only) |
| `imgfs_extract.py` | Windows CE IMGFS partition -> list / files, XPR decompression, modules as sections |

```
python sec_unpack.py EA5T-14D544-BA/SyncMyRide/EA5T-14D544-BA.zip EA5T-14D544-BA_unpacked/EA5T-14D544-BA.img trim
python sec_unpack.py split EA5T-14D544-BA_unpacked/EA5T-14D544-BA.img
python exfat_extract.py EA5T-14D544-BA_unpacked/parts/p2_exfat.bin [out dir]
python imgfs_extract.py EA5T-14D544-BA_unpacked/parts/p1_imgfs.bin [out dir]
```

Everything they write goes under `EA5T-14D544-BA_unpacked/` (git-ignored). Run them with `venv\Scripts\python.exe`.

## Package

`autoinstall.lst` lists, per installed version, which items to install. `[SYNCGen2_3.10.16180]` installs the
14D546 helper CABs plus the zips; `[SYNCGen2_4.30 .. 4.32.14122]` (the bench unit's 4.32.14073 is in it) installs
only the six CABs (popups, AEB update helper, ADB uldr).

| File | Contents |
|---|---|
| `EA5T-14D544-BA.zip` | one file, `EA5T-14D544-BA.sec`, 2 104 594 708 bytes: the whole flash image |
| `EA5T-14F497-AE.zip` | Nuance voices / Gracenote (FRC, SPM) |
| `EA5T-14F657-AG.zip` | nav map engine (`NavMapPlugin*.dll`, resources) |
| `EA5T-14F496-PA.zip` | Mustang welcome / goodbye animations (`Mustang_Wel_Anim.mp4` ...) |
| `EA5T-14D546-BE.zip` | TDI nav core, SyncServices, VehicleHealthReport swf |
| `*.cab` | installer helpers only (popups, SafeMode, uldr, ESN fix). No vehicle firmware |

## Container (.sec)

Signed, **not encrypted**.

| Offset | Contents |
|---|---|
| 0x00 | magic `0D400D40` `01C000C0` `0D400D40`, u32 0x80 header size |
| 0x10 | u32 image size 0x7D706400, u32 0x7D70A2C0, u32 file size 0x7D719114, u32 signature size 0xEDD2 |
| 0x24 | u32 0xEE54 = first block header |
| 0x30 | 16-byte id `F0B8611A AC1BF342 989443EB 7D0828A1` |
| 0x80 | PKCS#7 SignedData, Ford "Sync Dynamic Code Signing Gen2 A5" (Ford Internal SYNCGEN2 Issuing CA) |
| 0xEE54 | 251 blocks: 0x40-byte header (id, u32 0x40, u32 index, u32 count 0xFB, u32 block size 0x800000, u32 image size) + data |

The blocks' data back to back is the flash image (`sec_unpack.py`). Everything after 0x5A000000 is FF.

## Flash image (.img)

Header at 0: u32 `400DB1B1`, u32 count 5 @0x2C, section table @0x60 (0x30 bytes each: u32 `C001C000`, id, 0,
size, load address ...). Data back to back from 0x4000:

| id | Image offset | Size | Load | Contents |
|---|---|---|---|---|
| 0 | 0x4000 | 0x1000 | - | |
| 1 | 0x5000 | 0x20000 | 0x8FF00000 | step loader (`stepldr.pdb`, `IPL: Launch %s...`), ARM, ROMHDR `ECEC` at +0x40 |
| 8 | 0x25000 | 0x80000 | 0x80040000 | eboot |
| 7 | 0xA5000 | 0x1000000 | 0x80100000 | NK (kernel XIP: nk.exe, coredll, filesys, gwes, ...) |
| 6 | 0x10A5000 | 0x7C661400 | - | storage, see below |

**Storage** is 4 KB sectors, each followed by an 8-byte tag: u32 logical sector, u32 flags (`FFFBFFFD` /
`FFFBFFFF`); an all-FF tag = unused. 363 668 records in the data, 123 380 in use. Logical sector 0 is an MBR
(55AA, partitions in **4 KB** sectors), sector 1 starts with `MSFLSH50`.

| Part | Type | Sectors | Size | Stored | Contents |
|---|---|---|---|---|---|
| p0 | 0x23 | 0x80 + 0x680 | 6.5 MB | 1302 | BINFS: boot-time modules (`iso15765r.dll`, `ipc.dll`, `ipc_ilprot.dll`, `ipcmp.dll`, `veim.dll`, `imgfs.dll`, `exfat.dll`, `wdg.dll` ...) |
| p1 | 0x25 | 0x700 + 0x8200 | 130 MB | 16803 | IMGFS: the OS and native apps, 500 files (498 modules) |
| p2 | 0x04 | 0x8900 + 0x50000 | 1.25 GB | 104937 | exFAT: HMI (Flash .swf), voices, fonts, animations, 4888 files / 391.5 MB |
| p3 | 0x04 | 0x58900 + 0x23880 | 568 MB | 330 | exFAT, empty (user data) |

## IMGFS

Header: GUID `F8AC2C9D-E3D4-2B4D-BD30-916ED84F31DC`, entry size 0x34 @0x1C, first directory block 0x1000 @0x24,
chunk 0x1000 @0x28, compression `XPR` @0x2C.

- Directory block: u32 `2F5314CE`, u32 next block (0 = last), then 0x34-byte entries.
- `FFFFFEFE` file / module: +08 first section entry, +0C u16 name length, +14 name entry (names over 24 chars:
  raw UTF-16 in the data area instead), +18 size, +1C attributes (0x2000 = ROM module), +20 FILETIME,
  +2C run table, +30 run table bytes.
- `FFFFFEFB` name: UTF-16 from +04.
- `FFFFFEFD` / `FFFFF6FD` module section (S000, S001 ...): +08 next section, +10 name, +18 size, +1C run table, +20 run table bytes.
- Run table: (u16 stored size, u16 size, u32 offset) per 4 KB chunk. Stored < size = **XPRESS plain LZ77**
  (MS-XCA 2.4). Checked: VNIGeneralSvc.dll decompresses to readable log strings and C++ symbols.

Modules come out as e32/o32 header + sections (not rebuilt PE files). Sections back to back are enough for strings.

## Vehicle network side (from IMGFS strings)

Native modules involved: `VNIGeneralSvc.dll` (257 KB), `VNISending.dll` (107 KB), `VNIDiagSvc.dll`,
`VNIClimateSvc.dll`, `VNIButtonSvc.dll`, `VNIAudioSvc.dll`, `VNIRadioSvc.dll`, `VNIBEVSvc.dll`, `VNILib.dll`,
`canio.dll`, `veim.dll`, `EVM.dll` / `EVMService.dll` (event bus), `FEClimate.dll`.

- **Receive:** each VNI service registers signal filters (`CVNISignalFilterList::SetFilters` -> `SetSignalFilters`)
  and reads values (`ReadSignals`), over `IPC_IOCTL_RECV`. Values are republished on the EVM event bus.
  No CAN IDs or Ford signal names for the receive side are in the Windows CE code.
- **Transmit:** `VNISending.dll` exports one function per outgoing signal, named after Ford signal groups
  (`HMI_Send_Signals_7::SetHMIMode(HMI_HMIMode_St)`, `MFD_Request_Signals4::Disp_VehUnitTempUsrSel`,
  `VS_Request_Signals_1::VS_SetESPMode_Rq`, `CGEA13_Climate_Requests::Drv_Set_Temp`, `Nav_Send_Signals_2`,
  `APIM_TripDisplay_1::ChrgPtDistLeft_L_Dsply` ...).
- `VNIGeneralSvc.dll` threads: Vehicle, VehHS, GPS, General, MessageCenter, MessageCenter Extended, Park,
  Personal, VehSettings, DisplayTP, VehPower, Timer, Multi-Contour Seats, FBMP.
- Vehicle values it logs: `EVM_VEHICLE_VehV` (speed, km/h), `EVM_DRVRTSR_Vehicle_Speed_St`,
  `EVM_VEHICLE_VehYaw` (`Yaw_W_Actl`), `EVM_VEHICLE_OUTSIDE_AIR_TEMP` (C and F), PRNDL (with a
  `PRNDLHysteresis` registry value). Elsewhere: `EVM_GEAR_St`, `EVM_VEHPOWER_POWERMODE`,
  `EVM_VEHICLE_DAY_NIGHT_STATUS`, `EVM_VEHSETTINGS_Disp_Miles_Kilometers_St` / `_Disp_Temperature_St`,
  EV power flow (`EVM_BEV_*`).
- **Speed source is configurable**: `DIAG_OID_VEHSPEED_NETWORK` = I-CAN (default), MS-CAN 0x3A or MS-CAN 0x425.
- **Cluster text**: `VNISending` sends `NavigationSymbolInfo_St`, `StreetName_St`, `CurrentStreetName_St`,
  `Destination_Info_St` only if the vehicle "contains nav screen cluster", and `MediaInformation_St`,
  `BTCallerIdentification_St` only with a "dual screen cluster" (`VehicleHasDualScreenCluster`).
- Config is read from inbound diagnostics (`DIAG_OID_*`: TRAILER_BACKUP_ASSIST, MYKEY_SETTINGS,
  ILLUMINATION_TYPE, PARKASSIST, PDC_ARCHITECTURE, MULTI_CONTOURED_SEATS, CGEA_VERSION, STEERING_WHEEL ...),
  i.e. the as-built (DE00-DE03).

## HMI (p2 exFAT)

Flash screens under `8inchSkins/<Ford|Lincoln>/Sync/Apps/`: AppConsole, BezelDiagnostics, BezelTest, Climate,
DriverAssist, EmergencyAssist, Ev (PowerFlow, ChargeSettings), GenericApp, Home, Info (SyncApps, SiriusTravelLink,
WhereAmI ...), Media, Menu (Vehicle: AmbientLighting, ElectronicStabilityControl, MyKey, VehicleHealthReport ...),
Nav, Phone, PowerModing, Provisioning, Vui. No .exe / .dll on this volume.

## APIM diagnostics (bench, 20 Nov 2026)

`ipc_dtc_test.py dids ecu=7D0 session=03`: 51 DIDs answer (log `dtc_dids_20261120_211943.txt`). Identity
(F110 DS-ET4T-14D212-AB, F111 ES7T-14F130-BA, F113, F188, F190 VIN), FD02/FD03 software versions,
8033 EA5T-14D544-AB, 8060 installed package list (EA5T-14D546-ATC, BT4T-14F500-AE, EA5T-14F657-AC,
EA5T-14F497-AB, EA5T-14F496-AB, EA5T-14D546-DB, EA5T-14D546-BB, DA5T-14F496-PA002), DE00-DE03 as-built,
F1D0 / F1D1 = 00:26:B4:85:4C:D8 / D9 (stored reversed in F1D0). None of them is live vehicle data.

## Open questions

- The CAN ID -> signal mapping is not in this package. The receive path goes through `ipc.dll` /
  `iso15765r.dll` to a vehicle-side processor; F188 EM5T-14D205-AD (not 14D544) is likely that processor's
  firmware. Not confirmed.
- Signal IDs used in `SetSignalFilters` are numeric; mapping them to the names above needs disassembly (ARM,
  modules need rebuilding from e32/o32 into PE first).
- Whether `Info/SyncApps` is AppLink (phone app text on the screen), and so a route for showing telemetry.
- Which S550 frames feed `VehV`, `VehYaw`, outside temp and PRNDL. Try with `apim_capture.py` and the heartbeat.
