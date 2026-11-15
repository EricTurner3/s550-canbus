# Minimal RH850 (V850E3) disassembler, enough to read the analog KR3T cluster's CanIf / Com / monitor routines.
# Not exhaustive: the common formats only, anything else prints as .hword. The analog cluster is a Renesas RH850
# (little-endian, RAM at 0xFEDxxxxx); its decompressed image loads at 0xC100, the VBF block address (not the 0xC000
# erase base). gp = 0xFEDD9334, tp = 0x00136048 (startup code at 0x070F14).
#
#   python rh850dis.py <hex addr> <hex length>
#
# Run with -I since the .bin is extracted/untrusted data.
import os, sys
IMG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "KR3T-14C026-AC_unpacked", "KR3T-14C026-AC_decompressed_C000.bin")
BASE = 0xC100
d = open(IMG, "rb").read()
def u16(a): o = a - BASE; return d[o] | (d[o + 1] << 8)
def sx(v, b): return v - (1 << b) if v & (1 << (b - 1)) else v
R = ["r%d" % i for i in range(32)]; R[3] = "sp"; R[4] = "gp"; R[5] = "tp"; R[30] = "ep"; R[31] = "lp"
CC = ["bv", "bl", "be", "bnh", "bn", "br", "blt", "ble", "bnv", "bnl", "bne", "bh", "bp", "bsa", "bge", "bgt"]
F1 = {0: "mov", 1: "not", 2: "divh", 4: "satsubr", 5: "satsub", 6: "satadd", 7: "mulh", 8: "or", 9: "xor",
      10: "and", 11: "tst", 12: "subr", 13: "sub", 14: "add", 15: "cmp"}
F2 = {0x10: "mov", 0x11: "satadd", 0x12: "add", 0x13: "cmp", 0x14: "shr", 0x15: "sar", 0x16: "shl", 0x17: "mulh"}
F6 = {0x30: "addi", 0x31: "movea", 0x32: "movhi", 0x33: "satsubi", 0x34: "ori", 0x35: "xori", 0x36: "andi", 0x37: "mulhi"}

def dis(a):
    """Decode one instruction at address a -> (length in bytes, text)."""
    h = u16(a); r2 = h >> 11; op = (h >> 5) & 0x3F; r1 = h & 0x1F
    # prepare / 48-bit disp23 loads+stores (format XIV): 00000 1111 0x ...
    if h & 0xFFC0 == 0x0780:
        h2 = u16(a + 2); lo5 = h2 & 0x1F; reg3 = h2 >> 11
        if lo5 in (0x01, 0x03, 0x0B, 0x13, 0x1B):
            ext = {0x01: 0, 0x03: 2, 0x0B: 4, 0x13: 4, 0x1B: 6}[lo5]
            return 4 + ext, "prepare"
        h3 = u16(a + 4); hi = h & 0x20; rb = h & 0x1F
        def disp(nb):  # nb = number of low disp bits in h2 (7 for byte ops, 6 for half/word)
            # +0x8000 correction: verified on tp (TX ptr table 0x1452C4) and gp (RX buffers 0xFEDDB0xx)
            lowd = (h2 >> 4) & 0x7F if nb == 7 else ((h2 >> 5) & 0x3F) << 1
            return sx((h3 << 7) | lowd, 23) + 0x8000
        if h2 & 0xF == 0x5: return 6, "%s %d[%s], %s" % ("ld.bu" if hi else "ld.b", disp(7), R[rb], R[reg3])
        if h2 & 0xF == 0xD: return 6, "st.b %s, %d[%s]" % (R[reg3], disp(7), R[rb])
        if lo5 == 0x07: return 6, "%s %d[%s], %s" % ("ld.hu" if hi else "ld.h", disp(6), R[rb], R[reg3])
        if lo5 == 0x09: return 6, "ld.w %d[%s], %s" % (disp(6), R[rb], R[reg3])
        if lo5 == 0x0D: return 6, "st.h %s, %d[%s]" % (R[reg3], disp(6), R[rb])
        if lo5 == 0x0F: return 6, "st.w %s, %d[%s]" % (R[reg3], disp(6), R[rb])
        return 4, "fmtXIV? %04X %04X" % (h, h2)
    if op == 3 and r2 != 0:
        return 2, ("sld.hu %d[ep], %s" % ((h & 0xF) * 2, R[r2])) if h & 0x10 else ("sld.bu %d[ep], %s" % (h & 0xF, R[r2]))
    if h & 0xFFE0 == 0xC7E0 and (u16(a + 2) & 0x7FF) == 0x0160:
        return 4, "jarl [%s], %s" % (R[r1], R[u16(a + 2) >> 11])
    if op == 0x3F and (u16(a + 2) & 1):
        return 4, "ld.hu %d[%s], %s" % (sx(u16(a + 2) & ~1, 16), R[r1], R[r2])
    # 48-bit mov imm32 / jarl/jr disp32
    if r2 == 0 and op == 0x31:
        v = u16(a + 2) | (u16(a + 4) << 16); return 6, "mov 0x%X, %s" % (v, R[r1])
    if h & 0xFFE0 == 0x02E0:
        v = sx(u16(a + 2) | (u16(a + 4) << 16), 32); return 6, ("jarl 0x%X, %s" % (a + v, R[r1])) if r1 else "jr 0x%X" % (a + v)
    if h & 0xFFE0 == 0x06E0:
        v = u16(a + 2) | (u16(a + 4) << 16); return 6, "jmp 0x%X[%s]" % (v, R[r1])
    if op < 0x10:
        if op == 0 and r2 == 0 and r1 == 0: return 2, "nop"
        if op == 3 and r2 == 0: return 2, "jmp [%s]" % R[r1]
        if op == 2 and r2 == 0: return 2, "switch %s" % R[r1]
        if op == 4 and r2 == 0: return 2, "zxb %s" % R[r1]
        if op == 5 and r2 == 0: return 2, "sxb %s" % R[r1]
        if op == 6 and r2 == 0: return 2, "zxh %s" % R[r1]
        if op == 7 and r2 == 0: return 2, "sxh %s" % R[r1]
        if op == 0 and r2 == 0: return 2, "jmp?? %s" % R[r1]
        return 2, "%s %s, %s" % (F1.get(op, "op%x" % op), R[r1], R[r2])
    if op < 0x18:
        if op == 0x10 and r2 == 0: return 2, "callt/nop?"
        imm = sx(r1, 5) if op in (0x10, 0x11, 0x12, 0x13, 0x17) else r1
        return 2, "%s %d, %s" % (F2[op], imm, R[r2])
    top = (h >> 7) & 0xF
    if top == 0x6: return 2, "sld.b %d[ep], %s" % (h & 0x7F, R[r2])
    if top == 0x7: return 2, "sst.b %s, %d[ep]" % (R[r2], h & 0x7F)
    if top == 0x8: return 2, "sld.h %d[ep], %s" % ((h & 0x7F) * 2, R[r2])
    if top == 0x9: return 2, "sst.h %s, %d[ep]" % (R[r2], (h & 0x7F) * 2)
    if top == 0xA:
        return 2, ("sst.w %s, %d[ep]" if h & 1 else "sld.w %d[ep], %s") % ((R[r2], (h & 0x7E) * 2) if h & 1 else ((h & 0x7E) * 2, R[r2]))
    if top == 0xB:
        disp = sx((((h >> 11) & 0x1F) << 4 | ((h >> 4) & 7) << 1), 9)
        return 2, "%s 0x%X" % (CC[h & 0xF], a + disp)
    h2 = u16(a + 2)
    if op in F6:
        if op == 0x32 and r2 == 0: return 4, "dispose"
        return 4, "%s 0x%X, %s, %s" % (F6[op], h2, R[r1], R[r2])
    if op == 0x38: return 4, "ld.b %d[%s], %s" % (sx(h2, 16), R[r1], R[r2])
    if op == 0x39: return 4, ("ld.w %d[%s], %s" if h2 & 1 else "ld.h %d[%s], %s") % (sx(h2 & ~1, 16), R[r1], R[r2])
    if op == 0x3A: return 4, "st.b %s, %d[%s]" % (R[r2], sx(h2, 16), R[r1])
    if op == 0x3B: return 4, ("st.w %s, %d[%s]" if h2 & 1 else "st.h %s, %d[%s]") % (R[r2], sx(h2 & ~1, 16), R[r1])
    if op in (0x3C, 0x3D):
        if h2 & 1:
            return 4, ("ld.hu %d[%s], %s" if op == 0x3D else "ld.bu %d[%s], %s") % (sx(h2 & ~1, 16) if op == 0x3D else sx(((h2 & 0xFFFE) | ((h >> 5) & 1)), 16), R[r1], R[r2])
        disp = sx(((h & 0x3F) << 16) | h2, 22)
        return 4, ("jarl 0x%X, %s" % (a + disp, R[r2])) if r2 else "jr 0x%X" % (a + disp)
    if op == 0x3E:
        bit = (h >> 11) & 7; sub = h >> 14
        return 4, "%s %d, %d[%s]" % (["set1", "not1", "clr1", "tst1"][sub], bit, sx(h2, 16), R[r1])
    if op == 0x3F:
        sub = (h2 >> 5) & 0x3F; r3 = h2 >> 11
        if h2 == 0x0160 and r2 == 0 and r1 == 0: return 4, "di"
        if h2 == 0x8160 and r2 == 0x10 and r1 == 0: return 4, "ei"
        if h2 == 0x0144 and r1 == 0 and r2 == 0: return 4, "reti"
        if (h2 & 0x7FF) == 0x0120 and r1 == 0 and r2 == 0: return 4, "halt"
        if sub == 0x00: return 4, "setf %s, %s" % (CC[r1 & 0xF], R[r2])
        if sub == 0x01: return 4, "ldsr %s, sr%d" % (R[r1], r2)
        if sub == 0x02: return 4, "stsr sr%d, %s" % (r1, R[r2])
        if sub in (0x04, 0x05, 0x06): return 4, "%s %s, %s, %s" % (["shr", "sar", "shl"][sub - 4], R[r1], R[r2], R[r3])
        if sub == 0x18 or sub == 0x19: return 4, "cmov%s %s, %s, %s" % (CC[(h2 >> 1) & 0xF], R[r1], R[r2], R[r3])
        return 4, "ext.%02X %s,%s,%s (h2=%04X)" % (sub, R[r1], R[r2], R[r3], h2)
    if op == 0x19 or op == 0x18: return 4, "dispose/prepare? %04X %04X" % (h, h2)
    return 2, ".hword 0x%04X" % h

def run(a, n):
    end = a + n
    while a < end:
        L, s = dis(a)
        raw = " ".join("%04X" % u16(a + i) for i in range(0, L, 2))
        print("%06X  %-16s %s" % (a, raw, s)); a += L

if __name__ == "__main__":
    run(int(sys.argv[1], 16), int(sys.argv[2], 16))
