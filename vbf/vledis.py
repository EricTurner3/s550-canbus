# Minimal Power Architecture VLE disassembler for the 2019 digital KL3T cluster (SPC56, big-endian, image at 0x8000).
# Common formats only, unknown encodings print as .hword/.word. sweep() follows simple register constants
# (e_lis / e_or2i / e_add16i / e_li / se_li / se_mr, r13 / r2 small-data bases) so loads and stores get an
# absolute effective address where one can be worked out.
# r1 = 0x4000FFD4, r2 = 0x001751F8 (ROM small data), r13 = 0x4000A4D0 (RAM small data), set at 0x116EAC.
#
#   python -I vledis.py <hex addr> <hex length>
#
# Run with -I since the .bin is extracted/untrusted data.
import os, sys
IMG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "KL3T-14C026-BD_unpacked",
                   "KL3T-14C026-BD.vbf_section_001_00008000_len_1F8000.bin")
BASE = 0x8000
R2, R13 = 0x001751F8, 0x4000A4D0
d = open(IMG, "rb").read()
def u16(a): o = a - BASE; return (d[o] << 8) | d[o + 1]
def u32(a): return (u16(a) << 16) | u16(a + 2)
def sx(v, b): return v - (1 << b) if v & (1 << (b - 1)) else v
def rr(n): return n if n < 8 else n + 16          # 4-bit se_ register field -> r0-r7, r24-r31
SE_RR = {0x01: "se_mr", 0x04: "se_add", 0x05: "se_mullw", 0x06: "se_sub", 0x07: "se_subf", 0x0C: "se_cmp",
         0x0D: "se_cmpl", 0x0E: "se_cmph", 0x0F: "se_cmphl", 0x40: "se_srw", 0x41: "se_sraw", 0x42: "se_slw",
         0x44: "se_or", 0x45: "se_andc", 0x46: "se_and.", 0x47: "se_and"}
SE_IMM = {0x60: "se_bclri", 0x62: "se_bgeni", 0x64: "se_bseti", 0x66: "se_btsti", 0x68: "se_srwi", 0x6A: "se_srawi",
          0x6C: "se_slwi"}
SE_ONE = {0x2: "se_not", 0x3: "se_neg", 0x8: "se_mflr", 0x9: "se_mtlr", 0xA: "se_mfctr", 0xB: "se_mtctr",
          0xC: "se_extzb", 0xD: "se_extsb", 0xE: "se_extzh", 0xF: "se_extsh"}
DFORM = {12: "e_lbz", 13: "e_stb", 14: "e_lha", 15: "e_stha?", 20: "e_lwz", 21: "e_stw", 22: "e_lhz", 23: "e_sth"}
I16A = {0x11: "e_add2i.", 0x12: "e_add2is", 0x13: "e_cmp16i", 0x14: "e_mull2i", 0x15: "e_cmpl16i", 0x16: "e_cmph16i",
        0x17: "e_cmphl16i"}
I16L = {0x18: "e_or2i", 0x19: "e_and2i.", 0x1A: "e_or2is", 0x1C: "e_lis", 0x1D: "e_and2is."}
X31 = {444: "or", 266: "add", 40: "subf", 0: "cmpw", 32: "cmplw", 87: "lbzx", 279: "lhzx", 23: "lwzx", 215: "stbx",
       407: "sthx", 151: "stwx", 339: "mfspr", 467: "mtspr", 24: "slw", 536: "srw", 28: "and", 60: "andc", 124: "nor",
       316: "xor", 235: "mullw", 459: "divwu", 491: "divw", 954: "extsb", 922: "extsh", 26: "cntlzw", 792: "sraw",
       824: "srawi", 83: "mfmsr", 146: "mtmsr", 163: "wrteei", 131: "wrtee", 15: "isel", 104: "neg"}

def dis(a):
    """-> (length, text, info). info: dict(kind, rd, ra, imm, ...) for sweep()'s constant tracking."""
    h = u16(a)
    if (h >> 12) not in (1, 3, 5, 7):
        top = h >> 12; b = h >> 8
        if h == 0x0004: return 2, "se_blr", dict(kind="ret")
        if h == 0x0005: return 2, "se_blrl", dict(kind="call")
        if h == 0x0006: return 2, "se_bctr", dict(kind="ret")
        if h == 0x0007: return 2, "se_bctrl", dict(kind="call")
        if b == 0x00 and (h >> 4) & 0xF in SE_ONE:
            n = SE_ONE[(h >> 4) & 0xF]; return 2, "%s r%d" % (n, rr(h & 0xF)), dict(kind="clob", rd=rr(h & 0xF))
        if b in SE_RR:
            ry, rx = rr((h >> 4) & 0xF), rr(h & 0xF)
            return 2, "%s r%d, r%d" % (SE_RR[b], rx, ry), dict(kind="mr" if b == 1 else "clob", rd=rx, rs=ry)
        if b in (0x02, 0x03):
            ry, rx = (h >> 4) & 0xF, h & 0xF
            return 2, ("se_mtar r%d, r%d" % (ry + 8, rr(rx))) if b == 2 else ("se_mfar r%d, r%d" % (rr(rx), ry + 8)), \
                dict(kind="clob", rd=(ry + 8) if b == 2 else rr(rx))
        if top == 2:
            k = (h >> 9) & 7; v = (h >> 4) & 0x1F; rx = rr(h & 0xF)
            n = {0: "se_addi", 1: "se_cmpli", 2: "se_subi", 3: "se_subi.", 5: "se_cmpi", 6: "se_bmaski", 7: "se_andi"}.get(k, "se_?")
            imm = v + 1 if k in (0, 1, 2, 3) else v
            return 2, "%s r%d, %d" % (n, rx, imm), dict(kind="addi" if k == 0 else "clob" if k in (2, 3, 6, 7) else "cmp", rd=rx, imm=imm)
        if (h & 0xF800) == 0x4800:
            rx = rr(h & 0xF); v = (h >> 4) & 0x7F; return 2, "se_li r%d, %d" % (rx, v), dict(kind="li", rd=rx, imm=v)
        if b & 0xFE in SE_IMM:
            rx = rr(h & 0xF); v = (h >> 4) & 0x1F
            return 2, "%s r%d, %d" % (SE_IMM[b & 0xFE], rx, v), dict(kind="cmp" if b & 0xFE == 0x66 else "clob", rd=rx)
        if top in (8, 9, 0xA, 0xB, 0xC, 0xD):
            sd = (h >> 8) & 0xF; rz = rr((h >> 4) & 0xF); rx = rr(h & 0xF)
            sz = {8: 1, 9: 1, 0xA: 2, 0xB: 2, 0xC: 4, 0xD: 4}[top]
            n = {8: "se_lbz", 9: "se_stb", 0xA: "se_lhz", 0xB: "se_sth", 0xC: "se_lwz", 0xD: "se_stw"}[top]
            return 2, "%s r%d, %d(r%d)" % (n, rz, sd * sz, rx), dict(kind="ld" if top in (8, 0xA, 0xC) else "st",
                                                                    rd=rz, ra=rx, imm=sd * sz, size=sz)
        if (h & 0xFE00) == 0xE800:
            bd = sx(h & 0xFF, 8) * 2
            return 2, "%s 0x%X" % ("se_bl" if h & 0x100 else "se_b", a + bd), dict(kind="call" if h & 0x100 else "jmp", tgt=a + bd)
        if (h & 0xF800) == 0xE000:
            bo = (h >> 10) & 1; bi = (h >> 8) & 3; bd = sx(h & 0xFF, 8) * 2
            return 2, "se_b%s 0x%X" % ((["ge", "le", "ne", "ns"] if bo == 0 else ["lt", "gt", "eq", "so"])[bi], a + bd), dict(kind="br", tgt=a + bd)
        return 2, ".hword 0x%04X" % h, dict(kind="?")
    w = u32(a); op = w >> 26; rd = (w >> 21) & 31; ra = (w >> 16) & 31
    if op in DFORM:
        imm = sx(w & 0xFFFF, 16); sz = 1 if op in (12, 13) else 2 if op in (14, 15, 22, 23) else 4
        return 4, "%s r%d, %d(r%d)" % (DFORM[op], rd, imm, ra), dict(kind="st" if op in (13, 15, 21, 23) else "ld",
                                                                   rd=rd, ra=ra, imm=imm, size=sz)
    if op == 7:
        imm = sx(w & 0xFFFF, 16); return 4, "e_add16i r%d, r%d, %d" % (rd, ra, imm), dict(kind="add16i", rd=rd, ra=ra, imm=imm)
    if op == 28:
        if not (w & 0x8000):
            li = sx((((w >> 11) & 0xF) << 16) | (((w >> 16) & 0x1F) << 11) | (w & 0x7FF), 20)
            return 4, "e_li r%d, %d" % (rd, li), dict(kind="li", rd=rd, imm=li)
        sub = (w >> 11) & 31
        if sub in I16L:
            ui = (((w >> 16) & 31) << 11) | (w & 0x7FF)
            return 4, "%s r%d, 0x%04X" % (I16L[sub], rd, ui), dict(kind=I16L[sub], rd=rd, imm=ui)
        if sub in I16A:
            si = sx((((w >> 21) & 31) << 11) | (w & 0x7FF), 16)
            return 4, "%s r%d, %d" % (I16A[sub], ra, si), dict(kind="add2i" if sub == 0x11 else "add2is" if sub == 0x12 else "cmp", rd=ra, imm=si)
        return 4, ".word 0x%08X" % w, dict(kind="?")
    if op == 29:
        sh, mb, me = (w >> 11) & 31, (w >> 6) & 31, (w >> 1) & 31
        return 4, "%s r%d, r%d, %d, %d, %d" % ("e_rlwinm" if w & 1 else "e_rlwimi", ra, rd, sh, mb, me), dict(kind="clob", rd=ra)
    if op == 30:
        if not (w >> 25) & 1:
            bd = sx((w >> 1) & 0xFFFFFF, 24) * 2
            return 4, "%s 0x%X" % ("e_bl" if w & 1 else "e_b", a + bd), dict(kind="call" if w & 1 else "jmp", tgt=a + bd)
        bo = (w >> 20) & 3; bi = (w >> 16) & 15; bd = sx((w >> 1) & 0x7FFF, 15) * 2
        cc = ["lt", "gt", "eq", "so"][bi & 3]
        return 4, "e_b%s%s cr%d, 0x%X" % ("" if bo == 1 else "n", cc, bi >> 2, a + bd), dict(kind="br", tgt=a + bd)
    if op == 6:
        xo4 = (w >> 12) & 0xF
        if xo4 in (8, 9, 0xA, 0xB, 0xC, 0xD, 0xE):
            f, scl, ui8 = (w >> 10) & 1, (w >> 8) & 3, w & 0xFF
            v = ui8 << (8 * scl)
            if f: v |= ~(0xFF << (8 * scl)) & 0xFFFFFFFF if scl else 0
            n = {8: "e_addi", 9: "e_addic", 0xA: "e_mulli/cmpli", 0xB: "e_subfic", 0xC: "e_andi", 0xD: "e_ori", 0xE: "e_xori"}[xo4]
            if xo4 in (0xC, 0xD, 0xE):   # logical SCI8: rS = bits 6-10, rA = bits 11-15
                return 4, "%s r%d, r%d, 0x%X" % (n, ra, rd, v), dict(kind="clob", rd=ra)
            return 4, "%s r%d, r%d, %d" % (n, rd, ra, sx(v, 32)), dict(kind="addi32" if xo4 == 8 else "clob", rd=rd, ra=ra, imm=sx(v, 32))
        xo8 = (w >> 8) & 0xFF; d8 = sx(w & 0xFF, 8)
        n = {0x00: "e_lbzu", 0x02: "e_lhzu", 0x04: "e_lwzu", 0x08: "e_lmw", 0x09: "e_stmw", 0x0B: "e_stwu", 0x09 << 0: "e_stmw"}.get(xo8, "e_d8.%02X" % xo8)
        return 4, "%s r%d, %d(r%d)" % (n, rd, d8, ra), dict(kind="clob", rd=rd)
    if op == 31:
        xo = (w >> 1) & 0x3FF; rb = (w >> 11) & 31
        n = X31.get(xo, "x31.%d" % xo)
        if xo == 444 and rd == rb: return 4, "mr r%d, r%d" % (ra, rd), dict(kind="mr", rd=ra, rs=rd)
        if xo in (339, 467):
            spr = ((rb << 5) | ra); return 4, "%s %s, r%d" % (n, {8: "lr", 9: "ctr", 1: "xer"}.get(spr, "spr%d" % spr), rd), dict(kind="clob", rd=rd)
        tgt = ra if xo in (444, 28, 60, 124, 316, 24, 536, 792, 824, 954, 922, 26) else rd
        return 4, "%s r%d, r%d, r%d" % (n, rd, ra, rb), dict(kind="clob", rd=tgt)
    return 4, ".word 0x%08X" % w, dict(kind="?")

def sweep(start, end, regs0=None):
    """Linear sweep with constant tracking. Yields (addr, len, text, info, ea) where ea is the absolute address of a
    load/store when known. Register knowledge is dropped at calls and branch targets are not followed."""
    regs = dict(regs0 or {}); a = start
    while a < end:
        try: L, s, info = dis(a)
        except IndexError: return
        k = info.get("kind"); ea = None
        base = lambda r: R13 if r == 13 else R2 if r == 2 else regs.get(r)
        if k == "e_lis": regs[info["rd"]] = info["imm"] << 16
        elif k == "e_or2i": regs[info["rd"]] = (regs[info["rd"]] | info["imm"]) if regs.get(info["rd"]) is not None else None
        elif k == "e_or2is": regs[info["rd"]] = (regs[info["rd"]] | (info["imm"] << 16)) if regs.get(info["rd"]) is not None else None
        elif k == "add16i":
            b = base(info["ra"]); regs[info["rd"]] = (b + info["imm"]) & 0xFFFFFFFF if b is not None else None
        elif k == "addi32":
            b = base(info["ra"]); regs[info["rd"]] = (b + info["imm"]) & 0xFFFFFFFF if b is not None else None
        elif k == "add2i":
            regs[info["rd"]] = (regs[info["rd"]] + info["imm"]) & 0xFFFFFFFF if regs.get(info["rd"]) is not None else None
        elif k == "add2is":
            regs[info["rd"]] = (regs[info["rd"]] + (info["imm"] << 16)) & 0xFFFFFFFF if regs.get(info["rd"]) is not None else None
        elif k == "li": regs[info["rd"]] = info["imm"] & 0xFFFFFFFF
        elif k == "addi":
            regs[info["rd"]] = (regs[info["rd"]] + info["imm"]) & 0xFFFFFFFF if regs.get(info["rd"]) is not None else None
        elif k == "mr": regs[info["rd"]] = regs.get(info["rs"])
        elif k in ("ld", "st"):
            b = base(info["ra"])
            if b is not None: ea = (b + info["imm"]) & 0xFFFFFFFF
            if k == "ld": regs[info["rd"]] = None
        elif k == "clob": regs[info.get("rd")] = None
        elif k in ("call", "ret", "jmp"): regs = {}
        yield a, L, s, info, ea
        a += L

def run(a, n):
    for addr, L, s, info, ea in sweep(a, a + n):
        raw = " ".join("%04X" % u16(addr + i) for i in range(0, L, 2))
        print("%06X  %-10s %-34s%s" % (addr, raw, s, ("  ; [0x%08X]" % ea) if ea is not None else ""))

if __name__ == "__main__":
    run(int(sys.argv[1], 16), int(sys.argv[2], 16))
