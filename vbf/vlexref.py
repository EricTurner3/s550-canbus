# Whole-image cross-references for the digital KL3T image, built on vledis.sweep() (one linear pass, ~1 min).
#
#   python -I vlexref.py mem  <lo> <hi>       loads/stores whose resolved address is in [lo, hi)
#   python -I vlexref.py ptr  <lo> <hi>       e_add16i/e_addi off r13/r2 that leave a pointer into [lo, hi)
#   python -I vlexref.py call <tgt> [<tgt>..]  e_bl/se_bl/e_b/se_b to any target
#   python -I vlexref.py fn   <addr>           nearest function start (se_mflr r0) at or before addr
#
# Same limits as sweep(): no branch-target merging, so a store reached only by a jump can still be missed. Run
# `ptr` as well as `mem` and read the code around each pointer hit.
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # -I drops the script dir; the .bin is in a subdir
import vledis as v

def fn_start(a):
    while v.u16(a) != 0x0080: a -= 2
    return a

def main(mode, args):
    if mode == "fn":
        print("%06X" % fn_start(int(args[0], 16))); return
    lo, hi = (int(args[0], 16), int(args[1], 16)) if mode in ("mem", "ptr") else (0, 0)
    tg = {int(x, 16) for x in args} if mode == "call" else set()
    for addr, L, s, info, ea in v.sweep(v.BASE, v.BASE + len(v.d)):
        k = info.get("kind")
        if mode == "mem" and ea is not None and lo <= ea < hi:
            print("%06X  %-34s %s [0x%08X]" % (addr, s, "ST" if k == "st" else "LD", ea))
        elif mode == "ptr" and k in ("add16i", "addi32") and info["ra"] in (2, 13):
            t = ((v.R13 if info["ra"] == 13 else v.R2) + info["imm"]) & 0xFFFFFFFF
            if lo <= t < hi: print("%06X  %-34s -> r%d = 0x%08X" % (addr, s, info["rd"], t))
        elif mode == "call" and k in ("call", "jmp") and info.get("tgt") in tg:
            print("%06X  %s   (in fn ~%06X)" % (addr, s, fn_start(addr)))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
