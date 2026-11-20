# Decompress a Volvo/Ford VBF data_format_identifier=0x10 section (the "compressed" blocks).
#
# Algorithm: Haruhiko Okumura's educational LZSS (public domain), BIT-PACKED, as used by the
# Volvo "VBF CONVERT" tool and implemented in smartgauges/qvbf (lzss.cpp). Parameters:
#     EI=10 -> window N=1024, 10-bit offset        EJ=4 -> 4-bit length (match = len+2, i.e. 2..17)
#     P=1   -> matches of <=1 byte are emitted as literals
# Bitstream, MSB-first:  flag bit 1 => literal (next 8 bits);  flag bit 0 => match: 10-bit offset
# then 4-bit length. A match whose 10-bit offset field reads 0 is the end-of-stream terminator.
# The sliding window is pre-filled with ' ' (0x20); output pointer r starts at 0; offset is an
# absolute window index (decremented by 1, since the encoder stores it 1-based).
#
# This is NOT the ring-buffer getc() LZSS and NOT LZHUF: the tokens are bit-granular (9-bit
# literals / 15-bit matches), which is why byte-aligned LZSS decoders desync on these files.
#
#   python vbf_lzss.py <compressed_section.bin> [out.bin]
#
# Run with -I since the .bin is extracted/untrusted data. See KR3T_NOTES.md.
import sys

EI, EJ, P = 10, 4, 1
N = 1 << EI          # 1024
F = (1 << EJ) + P    # 17

def decode(cdata: bytes) -> bytearray:
    out = bytearray()
    buffer = bytearray([0x20]) * N
    for i in range(N - F, N):
        buffer[i] = 0
    nbits = len(cdata) * 8
    bitpos = 0

    def getbit(n):
        nonlocal bitpos
        x = 0
        for _ in range(n):
            if bitpos >= nbits:
                return None
            byte = cdata[bitpos >> 3]
            x = (x << 1) | ((byte >> (7 - (bitpos & 7))) & 1)
            bitpos += 1
        return x

    r = 0
    while True:
        c = getbit(1)
        if c is None:
            break
        if c:                                   # literal
            c = getbit(8)
            if c is None:
                break
            out.append(c); buffer[r] = c; r = (r + 1) & (N - 1)
        else:                                   # match
            i = getbit(EI)
            if i is None:
                break
            j = getbit(EJ)
            if j is None:
                break
            if i == 0:                          # end-of-stream terminator
                break
            i -= 1
            for k in range(j + 2):
                ch = buffer[(i + k) & (N - 1)]
                out.append(ch); buffer[r] = ch; r = (r + 1) & (N - 1)
    return out

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python vbf_lzss.py <compressed_section.bin> [out.bin]"); sys.exit(1)
    cdata = open(sys.argv[1], "rb").read()
    out = decode(cdata)
    outpath = sys.argv[2] if len(sys.argv) > 2 else sys.argv[1].rsplit(".", 1)[0] + "_decompressed.bin"
    open(outpath, "wb").write(out)
    print("decompressed {} -> {} bytes (0x{:X})".format(len(cdata), len(out), len(out)))
    print("wrote", outpath)
