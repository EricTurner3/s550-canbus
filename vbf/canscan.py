# Scan an UNCOMPRESSED IPC firmware image for the CAN RX subscription table and list the IDs it holds.
# The cluster stores subscribed CAN IDs as 16-bit halfwords in a hash-indexed table, 0xFFFF = empty slot
# (so IDs cluster densely but aren't sorted). This finds the densest such cluster and dumps its IDs.
#
# Endianness differs by cluster build: the 2019 DIGITAL (KL3T) image is BIG-endian; the 2019 ANALOG
# (KR3T) image is LITTLE-endian. This script auto-detects by whichever endianness yields the tightest
# cluster of the distinctive wrench IDs, or you can force it with a 3rd arg (be|le).
#
# It anchors on the wrench-ID cluster and then widens along the run of FFFF-or-valid-ID halfwords, so it
# won't latch onto a monotonic PDU/index array (which has valid IDs but no FFFF padding).
# SPC56 is a Power Architecture core; compressed sections (VBF data_format_identifier 0x10) must be
# decompressed first with vbf_lzss.py - see KR3T_NOTES.md.
#
#   python canscan.py <image.bin> [base_hex] [be|le]   base defaults 0x8000 (digital); analog erase base 0xC000
#
# Run with -I since the .bin is extracted/untrusted data.
import sys, struct

if len(sys.argv) < 2:
    print('usage: python canscan.py <image.bin> [base_hex] [be|le]'); sys.exit(1)
data = open(sys.argv[1], 'rb').read()
BASE = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x8000
FORCE = sys.argv[3].lower() if len(sys.argv) > 3 else None

# distinctive chassis / service-required IDs used to recognise the table. Deliberately excludes common
# byte-pattern values (0x200/0x202/0x204/0x415...) that occur all over code and would anchor on noise.
KNOWN = [0x230, 0x179, 0x431, 0x3B3, 0x46A, 0x168, 0x263, 0x4A2, 0x178, 0x42C, 0x42D, 0x43E,
         0x421, 0x156, 0x3E0, 0x430, 0x434, 0x3A8, 0x38D, 0x3B2]
WRENCH = {0x230, 0x179, 0x431, 0x3B3, 0x46A, 0x168, 0x263, 0x4A2, 0x178, 0x42C, 0x42D, 0x43E, 0x421}


def best_cluster(endian):
    """Return (distinct_wrench, anchor_start, anchor_end) for the densest wrench-ID window."""
    hits = []
    for idv in KNOWN:
        p = struct.pack(endian + 'H', idv); i = data.find(p)
        while i != -1:
            if i % 2 == 0:                       # table slots are halfword-aligned
                hits.append((i, idv))
            i = data.find(p, i + 1)
    hits.sort()
    best = (0, 0, 0); j = 0
    for i in range(len(hits)):
        while hits[i][0] - hits[j][0] > 0x400:
            j += 1
        d = len({h[1] for h in hits[j:i + 1]} & WRENCH)
        if d > best[0]:
            best = (d, hits[j][0], hits[i][0])
    return best


# pick endianness
cands = {'>': best_cluster('>'), '<': best_cluster('<')}
if FORCE in ('be', 'le'):
    endian = '>' if FORCE == 'be' else '<'
else:
    endian = '>' if cands['>'][0] >= cands['<'][0] else '<'
best = cands[endian]
if best[0] < 4:
    print('no RX table found (best {} distinct wrench IDs) - is this image uncompressed / right base?'.format(best[0]))
    sys.exit(0)


def hw(o):
    return struct.unpack_from(endian + 'H', data, o)[0]

def is_slot(v):
    return v == 0xFFFF or (0 < v <= 0x7FF)

# widen along the FFFF-or-valid-ID run around the anchor, tolerating short breaks of "other" values.
# This stops at sustained non-table data and (unlike a fixed ±window) won't swallow adjacent arrays.
s = best[1]
while s - 2 >= 0 and is_slot(hw(s - 2)):
    s -= 2
e = best[2]; bad = 0
while e + 2 <= len(data):
    if is_slot(hw(e)):
        e += 2; bad = 0
    else:
        bad += 1
        if bad > 3:
            break
        e += 2

slots = [hw(o) for o in range(s, e, 2)]
ff = sum(1 for v in slots if v == 0xFFFF)
ids = sorted({v for v in slots if 0 < v <= 0x7FF})
print('endianness: {}  (wrench-cluster: BE {}/13, LE {}/13)'.format(
    'BIG' if endian == '>' else 'LITTLE', cands['>'][0], cands['<'][0]))
print('RX table 0x{:X}..0x{:X} (addr): {} slots, {} FFFF, {} distinct subscribed IDs'.format(
    s + BASE, e + BASE, len(slots), ff, len(ids)))
for i in range(0, len(ids), 12):
    print('  ' + ' '.join(('*%03X*' % x if x in WRENCH else ' %03X ' % x) for x in ids[i:i + 12]))
print('(* = wrench / service-required related)')
print('wrench IDs present:', ' '.join('%03X' % x for x in sorted(WRENCH & set(ids))) or 'none')
print('wrench IDs absent :', ' '.join('%03X' % x for x in sorted(WRENCH - set(ids))) or 'none')
