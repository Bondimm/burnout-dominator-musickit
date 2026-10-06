"""Patches the Burnout Dominator executable (Europe SLES_546.81 or USA SLUS_215.96) so the EA Trax playlist can
hold more (or fewer) than 36 songs.

Facts (Europe addresses; other builds are located by signature):
- song table: 36 entries x 12 bytes {u32 song id, u32 0, u32 flags (7 = all, 1/4 = menus or races only, 0 = off,
  8 = "not heard yet")} (0x3CF160); playlist struct (0x3CF310): +0x04 song count (36), +0x4c table pointer.
- song i streams from tracks\\EATrax0.rws segment i (i < 22) or tracks\\EATrax1.rws segment i-22.
- the profile (0x491540, saved on the memory card) holds one flag byte per original song (36 bytes); code copies
  it into the table (table_copy, profile_apply on profile load) and writes it back when a song is toggled
  (toggle) or played to the end (song_finished). Those must stay below index 36.
- the Song Manager list (trax_list) is built with a fixed number of rows (36): patched to the song count.
- at start-up the game switches two of the four "Girlfriend" versions (songs 5-8) off depending on the console
  territory (table_init: four stores into the table). Those stores follow the songs when they move, and go to an
  unused slot after the table when the song is removed or gets new audio.

The table moves into the 16 KB hole between the two PT_LOAD segments (the unused .sndata section); segment 1 is
extended over it and the rest of the file shifts by the hole size.

PCSX2 identifies games by the XOR of all 32-bit words of the boot ELF (ElfObject::GetCRC) and picks patches /
widescreen pnach files by it. A compensation word is appended after the last byte of the file (never loaded) so the
patched ELF keeps the original CRC.
"""
import struct

ORIGINAL_SONGS = 36
# Shuffle mode keeps its play order as one byte per song at music manager +0xE (filled at 0x2C3790, read at
# 0x2C3894). From 95 songs on that array reaches the playlist's song count at manager +0x6C, which can lead to an
# out-of-range song index in shuffle mode. (51+ songs already touch the shuffle position/count at +0x40/+0x44:
# harmless, shuffle just picks again.) So 94 songs at most.
MAX_SONGS = 94
_DETECT_MAX = 100
KNOWN = {0x8C9C76B4: "Europe SLES-54681", 0x8C9576A1: "USA SLUS-21596"}

# Signature groups: Europe function windows containing the patch sites (located in other builds by masked search).
EU_GROUPS = {
    "table_init": (0x2C25E0, 0x2C261C),     # territory default-off stores (Girlfriend versions)
    "table_copy": (0x2C2698, 0x2C26D0),     # profile flags -> table
    "profile_apply": (0x29DBD0, 0x29DC48),  # profile load: apply flags to every song
    "toggle": (0x2C3688, 0x2C370C),         # Song Manager toggle
    "song_finished": (0x2C2960, 0x2C29C0),  # song played to the end
    "trax_list": (0x19A800, 0x19A99C),      # Song Manager list: number of rows
}

# (EU vaddr, group, template, meaning). Template: int word, None = keep the original word, or a callable(ctx).
CODE_PATCHES = [
    (0x2C2698, "table_copy", lambda c: 0x3C020000 | c["tbl_hi"], "lui v0,%hi(table)"),
    (0x2C26A0, "table_copy", lambda c: 0x24420000 | c["tbl_lo"], "addiu v0,v0,%lo(table)"),
    (0x2C25F4, "table_init", lambda c: 0x3C020000 | c["tbl_hi"], "lui v0,%hi(table)"),
    (0x2C25FC, "table_init", lambda c: 0x24420000 | c["tbl_lo"], "addiu v0,v0,%lo(table)"),
    (0x2C2610, "table_init", lambda c: 0x24420000 | c["tbl_lo"], "addiu v0,v0,%lo(table)"),
    (0x29DC30, "profile_apply", 0x24020024, "addiu v0,zero,36  (was lw v0,4(sp) = song count)"),
    (0x2C36E4, "toggle", 0x2D230024, "sltiu v1,t1,36  (was lbu v1,0x54(a2))"),
    (0x2C2980, "song_finished", None, "lw a2,0xc4(s0)"),
    (0x2C2984, "song_finished", 0x2403FFF7, "addiu v1,zero,-9"),
    (0x2C2988, "song_finished", 0x8CC20008, "lw v0,8(a2)"),
    (0x2C298C, "song_finished", 0x00431024, "and v0,v0,v1"),
    (0x2C2990, "song_finished", 0xACC20008, "sw v0,8(a2)"),
    (0x2C2994, "song_finished", 0x8E0300D8, "lw v1,0xd8(s0)"),
    (0x2C2998, "song_finished", 0x2C620024, "sltiu v0,v1,36"),
    (0x2C299C, "song_finished", 0x0002180A, "movz v1,zero,v0"),
    (0x2C29A0, "song_finished", 0x00651821, "addu v1,v1,a1  (a1 = %hi(profile))"),
    (0x2C29A4, "song_finished", lambda c: 0x90620000 | c["prof_lo"], "lbu v0,%lo(profile)(v1)"),
    (0x2C29A8, "song_finished", 0x0200202D, "daddu a0,s0,zero"),
    (0x2C29AC, "song_finished", None, "andi v0,v0,0xf7"),
    (0x2C29B0, "song_finished", None, "jal <stop stream>"),
    (0x2C29B4, "song_finished", lambda c: 0xA0620000 | c["prof_lo"], "sb v0,%lo(profile)(v1)"),
]
# Words that depend on the song list (rewritten by patch / set_table / extend): Song Manager rows ...
ROW_SITES = [(0x19A80C, 0x24070000, "addiu a3,zero,rows"), (0x19A824, 0x24060000, "addiu a2,zero,rows"),
             (0x19A994, 0x2A220000, "slti v0,s1,rows")]
# ... and the four default-off stores "sw v1,8+12*position(v0)" of the original songs 7, 4 (territory 3), 6, 5.
DEFAULT_OFF_SITES = [(0x2C2600, 7), (0x2C2608, 4), (0x2C2614, 6), (0x2C2618, 5)]
_VARIABLE = {a for a, _, _ in ROW_SITES} | {a for a, _ in DEFAULT_OFF_SITES}
SINK = MAX_SONGS + 1       # unused table slot (inside the old .sndata hole) for default-off stores without a song
EU_PROFILE_SITES = (0x2C269C, 0x2C26A4)   # lui v1,%hi(profile) / addiu a2,v1,%lo(profile) in table_copy
EU_TABLE_SITES = (0x2C2698, 0x2C26A0)


def crc(data):
    """PCSX2 game CRC: XOR of every little-endian 32-bit word of the ELF file."""
    import numpy as np
    n = len(data) // 4 * 4
    return int(np.bitwise_xor.reduce(np.frombuffer(bytes(data[:n]), dtype="<u4"))) if n else 0


def hi16(a):
    return ((a + 0x8000) >> 16) & 0xFFFF


def _addr(hi, lo):
    lo &= 0xFFFF
    return ((hi & 0xFFFF) << 16) + (lo - 0x10000 if lo & 0x8000 else lo)


class Elf:
    def __init__(self, data):
        self.d = bytearray(data)
        if self.d[:4] != b"\x7fELF":
            raise ValueError("not an ELF file")
        self.phoff = struct.unpack_from("<I", self.d, 0x1C)[0]
        self.phnum = struct.unpack_from("<H", self.d, 0x2C)[0]
        self.shoff = struct.unpack_from("<I", self.d, 0x20)[0]
        self.shnum = struct.unpack_from("<H", self.d, 0x30)[0]

    def phdrs(self):
        return [list(struct.unpack_from("<8I", self.d, self.phoff + 32 * i)) for i in range(self.phnum)]

    def set_phdr(self, i, ph):
        struct.pack_into("<8I", self.d, self.phoff + 32 * i, *ph)

    def sections(self):
        return [list(struct.unpack_from("<10I", self.d, self.shoff + 40 * i)) for i in range(self.shnum)]

    def file_offset(self, va):
        for ph in self.phdrs():
            if ph[0] == 1 and ph[2] <= va < ph[2] + ph[4]:
                return ph[1] + va - ph[2]
        raise KeyError(hex(va))

    def r32(self, va):
        return struct.unpack_from("<I", self.d, self.file_offset(va))[0]

    def w32(self, va, v):
        struct.pack_into("<I", self.d, self.file_offset(va), v)

    def content_end(self):
        end = self.shoff + self.shnum * 40
        for sh in self.sections():
            if sh[1] != 8:
                end = max(end, sh[4] + sh[5])
        for ph in self.phdrs():
            end = max(end, ph[1] + ph[4])
        return end


def _find_group(e, sig, seg):
    """sig = [[value, mask], ...]; returns the vaddrs where (word & mask) == value for the whole window."""
    import numpy as np
    base_va, off, size = seg[2], seg[1], seg[4]
    text = np.frombuffer(bytes(e.d[off:off + size - size % 4]), dtype="<u4")
    vals = np.array([v for v, m in sig], dtype=np.uint32)
    masks = np.array([m for v, m in sig], dtype=np.uint32)
    cand = np.nonzero((text & masks[0]) == vals[0])[0]
    n = len(sig)
    hits = [int(i) for i in cand if i + n <= len(text) and np.array_equal(text[i:i + n] & masks, vals)]
    return [base_va + 4 * i for i in hits]


class Layout:
    """Addresses of everything MusicKit touches, for a given executable."""

    def __init__(self, data):
        e = Elf(data)
        self.elf = e
        ph = e.phdrs()
        if len(ph) < 2 or ph[0][0] != 1 or ph[1][0] != 1:
            raise ValueError("unexpected ELF layout")
        self.seg1, self.seg2 = ph[0], ph[1]
        self.patched = self.seg1[2] + self.seg1[4] == self.seg2[2]
        self.hole_end = self.seg2[2]
        sndata = [s for s in e.sections() if s[5] == 0x4000 and self.seg2[2] - 0x4008 <= s[3] < self.seg2[2]]
        if self.patched:
            self.hole_start = sndata[0][3] - 8 if sndata else None
        else:
            self.hole_start = self.seg1[2] + self.seg1[4]
        self.table_new = sndata[0][3] if sndata else (self.hole_start + 15) & ~15
        if not self.patched and self.hole_end - self.table_new < (SINK + 1) * 12:
            raise ValueError("no room for the song table in this executable")
        # code sites
        self.delta = {}
        for g, (a, b) in EU_GROUPS.items():
            hits = _find_group(e, EU_SIGNATURES[g], self.seg1) if EU_SIGNATURES else []
            if self.patched and not hits and PATCHED_SIGNATURES:
                hits = _find_group(e, PATCHED_SIGNATURES[g], self.seg1)
            if len(hits) != 1:
                raise ValueError("code signature %s found %d times (unsupported executable)" % (g, len(hits)))
            self.delta[g] = hits[0] - a
        dc = self.delta["table_copy"]
        self.prof_lo = e.r32(EU_PROFILE_SITES[1] + dc) & 0xFFFF
        self.profile = _addr(e.r32(EU_PROFILE_SITES[0] + dc), self.prof_lo)
        tbl = _addr(e.r32(EU_TABLE_SITES[0] + dc), e.r32(EU_TABLE_SITES[1] + dc))
        if not self.patched:
            self.table_old = tbl
        else:
            self.table_old = None
            if tbl != self.table_new:
                raise ValueError("relocated song table not where expected")
        self.playlist = self._find_playlist(e, tbl)

    def _find_playlist(self, e, table):
        s = self.seg1
        d = bytes(e.d[s[1]:s[1] + s[4]])
        key = struct.pack("<I", table)
        hits = []
        i = d.find(key)
        while i >= 0:
            if i % 4 == 0 and i >= 0x4C:
                base = i - 0x4C
                z, n = struct.unpack_from("<II", d, base)
                if z == 0 and 1 <= n <= _DETECT_MAX:
                    hits.append(s[2] + base)
            i = d.find(key, i + 1)
        if len(hits) != 1:
            raise ValueError("playlist structure not found (%d candidates)" % len(hits))
        return hits[0]

    def ctx(self):
        return {"tbl_hi": hi16(self.table_new), "tbl_lo": self.table_new & 0xFFFF, "prof_lo": self.prof_lo}

    def sites(self):
        """[(vaddr, EU vaddr, template, meaning)] for this build."""
        return [(eu + self.delta[g], eu, t, m) for eu, g, t, m in CODE_PATCHES]

    def row_sites(self):
        return [(eu + self.delta["trax_list"], base) for eu, base, _ in ROW_SITES]

    def default_off_sites(self):
        return [(eu + self.delta["table_init"], song) for eu, song in DEFAULT_OFF_SITES]


def is_patched(data):
    e = Elf(data)
    ph = e.phdrs()
    return ph[0][2] + ph[0][4] == ph[1][2]


def read_song_count(data):
    lay = Layout(data)
    return lay.elf.r32(lay.playlist + 4)


def read_table(data):
    """Song table entries [(song id, 0, flags)] for the current song count (original or relocated table)."""
    lay = Layout(data)
    e = lay.elf
    n = e.r32(lay.playlist + 4)
    ptr = e.r32(lay.playlist + 0x4C)
    return [struct.unpack_from("<3I", e.d, e.file_offset(ptr + 12 * i)) for i in range(n)]


def read_rows(data):
    """Rows of the Song Manager list (36 in the original game)."""
    lay = Layout(data)
    return [lay.elf.r32(va) & 0xFFFF for va, _ in lay.row_sites()]


def read_default_off(data):
    """{original song (4..7): its current position, or None} for the start-up default-off stores."""
    lay = Layout(data)
    out = {}
    for va, song in lay.default_off_sites():
        pos = ((lay.elf.r32(va) & 0xFFFF) - 8) // 12
        out[song] = pos if pos < SINK else None
    return out


def set_table(data, flags, default_off=None):
    """Return a copy whose song table is entry i = (i, 0, flags[i]) for every song (1..MAX_SONGS songs, same
    PCSX2 CRC). An original executable is patched first. Songs are identified by their position only: the
    profile flag bytes 0..35 (memory card) apply to table entries 0..35, later entries keep the flags written here.
    default_off: {original song 4..7: its new position or None}; None keeps the current positions."""
    total = len(flags)
    if not 1 <= total <= MAX_SONGS:
        raise ValueError("between 1 and %d songs are supported (got %d)" % (MAX_SONGS, total))
    target_crc = crc(data)
    if default_off is None:
        default_off = read_default_off(data)
    if not is_patched(data):
        data = patch(data, ORIGINAL_SONGS)
    lay = Layout(data)
    e = lay.elf
    old = e.r32(lay.playlist + 4)
    for i in range(max(total, old, ORIGINAL_SONGS)):
        if i < total:
            entry = (i, 0, flags[i])
        elif i < ORIGINAL_SONGS:      # the profile loader still writes flags into entries 0..35
            entry = (i, 0, 7)
        else:
            entry = (0, 0, 0)
        o = e.file_offset(lay.table_new + 12 * i)
        e.d[o:o + 12] = struct.pack("<3I", *entry)
    e.w32(lay.playlist + 4, total)
    _write_variable(lay, total, default_off)
    appended = len(e.d) > e.content_end()
    return _fix_crc(e.d, target_crc, appended)


def _write_variable(lay, total, default_off):
    e = lay.elf
    for va, base in lay.row_sites():
        e.w32(va, base | total)
    for va, song in lay.default_off_sites():
        pos = default_off.get(song)
        if pos is None or not 0 <= pos < total:
            pos = SINK
        e.w32(va, (e.r32(va) & 0xFFFF0000) | (8 + 12 * pos))


def _fix_crc(data, target, appended):
    """Make crc(data) == target via a compensation word after the ELF content (appended if needed)."""
    out = bytearray(data)
    if len(out) % 4:
        out += b"\0" * (4 - len(out) % 4)
    if not appended:
        out += b"\0\0\0\0"
    struct.pack_into("<I", out, len(out) - 4, 0)
    struct.pack_into("<I", out, len(out) - 4, crc(out) ^ target)
    assert crc(out) == target
    return bytes(out)


def patch(data, total_songs, new_flags=7):
    """Return a patched copy of an original executable holding `total_songs` table entries (same PCSX2 CRC)."""
    if total_songs > MAX_SONGS:
        raise ValueError("at most %d songs fit" % MAX_SONGS)
    lay = Layout(data)
    if lay.patched:
        raise ValueError("executable already patched")
    default_off = read_default_off(data)
    e = lay.elf
    target_crc = crc(data)
    if e.r32(lay.playlist + 4) != ORIGINAL_SONGS or e.r32(lay.playlist + 0x4C) != lay.table_old:
        raise ValueError("playlist data does not match an original Burnout Dominator executable")
    for i in range(ORIGINAL_SONGS):
        if struct.unpack("<3I", e.d[e.file_offset(lay.table_old + 12 * i):][:12])[:2] != (i, 0):
            raise ValueError("song table does not match")
    seg1, seg2 = lay.seg1, lay.seg2
    hole = bytearray(lay.hole_end - lay.hole_start)
    for i in range(max(total_songs, ORIGINAL_SONGS)):
        if i < ORIGINAL_SONGS:
            o0 = e.file_offset(lay.table_old + 12 * i)
            entry = e.d[o0:o0 + 12]
        else:
            entry = struct.pack("<3I", i, 0, new_flags)
        o = lay.table_new - lay.hole_start + 12 * i
        hole[o:o + 12] = entry
    seg1_end_file = seg1[1] + seg1[4]
    seg2_off = seg2[1]
    shift = (seg1_end_file + len(hole)) - seg2_off
    out = bytearray(e.d[:seg1_end_file]) + hole + e.d[seg2_off:]
    ne = Elf(out)
    ph = e.phdrs()
    s1 = list(seg1)
    s1[4] += len(hole)
    s1[5] += len(hole)
    ne.set_phdr(0, s1)
    for i in range(1, len(ph)):
        if ph[i][1] >= seg2_off:
            ph[i][1] += shift
        ne.set_phdr(i, ph[i])
    if ne.shoff >= seg2_off:
        ne.shoff += shift
        struct.pack_into("<I", ne.d, 0x20, ne.shoff)
    for i in range(ne.shnum):
        o = ne.shoff + 40 * i
        sh = list(struct.unpack_from("<10I", ne.d, o))
        if sh[5] == 0x4000 and lay.hole_start <= sh[3] < lay.hole_end:   # .sndata now inside segment 1
            sh[4] = s1[1] + sh[3] - s1[2]
        elif sh[4] >= seg2_off:
            sh[4] += shift
        struct.pack_into("<10I", ne.d, o, *sh)
    ne.w32(lay.playlist + 4, total_songs)
    ne.w32(lay.playlist + 0x4C, lay.table_new)
    c = lay.ctx()
    for va, eu, tmpl, _ in lay.sites():
        if tmpl is None:
            continue
        ne.w32(va, tmpl(c) if callable(tmpl) else tmpl)
    lay.elf = ne
    _write_variable(lay, total_songs, default_off)
    return _fix_crc(ne.d, target_crc, appended=False)


def extend(data, total_songs, new_flags=7):
    """Grow the song table of an executable already patched by MusicKit (keeps its PCSX2 CRC)."""
    lay = Layout(data)
    if not lay.patched:
        raise ValueError("executable is not MusicKit-patched")
    e = lay.elf
    target_crc = crc(data)
    old = e.r32(lay.playlist + 4)
    if total_songs < old:
        raise ValueError("cannot remove songs from an already patched disc; rebuild from the original ISO")
    if total_songs > MAX_SONGS:
        raise ValueError("at most %d songs fit" % MAX_SONGS)
    default_off = read_default_off(data)
    for i in range(old, total_songs):
        o = e.file_offset(lay.table_new + 12 * i)
        e.d[o:o + 12] = struct.pack("<3I", i, 0, new_flags)
    e.w32(lay.playlist + 4, total_songs)
    _write_variable(lay, total_songs, default_off)
    appended = len(e.d) > e.content_end()
    return _fix_crc(e.d, target_crc, appended)


def touched_ranges(data):
    """Virtual address ranges MusicKit writes (for conflict checks against PCSX2 pnach patches)."""
    lay = Layout(data)
    r = [(va, va + 4) for va, _, t, _ in lay.sites() if t is not None]
    r += [(va, va + 4) for va, _ in lay.row_sites()] + [(va, va + 4) for va, _ in lay.default_off_sites()]
    r += [(lay.playlist + 4, lay.playlist + 8), (lay.playlist + 0x4C, lay.playlist + 0x50),
          (lay.hole_start, lay.hole_end)]
    return r


# Signatures of the EU groups ([value, mask] per word), generated from SLES_546.81 by gen_signatures() into
# signatures.json: "original" for unpatched executables, "patched" to find the groups again in MusicKit output.
def _mask_of(w):
    op = w >> 26
    if op in (0x02, 0x03):                 # j / jal: targets differ between builds
        return 0xFC000000
    if op in (0x0F, 0x09, 0x0D):           # lui / addiu / ori: address halves differ
        return 0xFFFF0000
    return 0xFFFFFFFF


def gen_signatures(eu_data, path=None):
    import json
    import os
    global EU_SIGNATURES, PATCHED_SIGNATURES
    e = Elf(eu_data)

    def sig(w, va, m=None):
        m = _mask_of(w) if m is None else m
        if va in _VARIABLE:                # immediates that depend on the song list
            m &= 0xFFFF0000
        return [w & m, m]
    orig = {g: [sig(e.r32(va), va) for va in range(a, b, 4)] for g, (a, b) in EU_GROUPS.items()}
    EU_SIGNATURES, PATCHED_SIGNATURES = orig, {}
    pe = Elf(patch(eu_data, ORIGINAL_SONGS + 1))
    var = {eu for eu, g, t, m in CODE_PATCHES if callable(t)}
    patched = {g: [sig(pe.r32(va), va, 0xFFFF0000 if va in var else None) for va in range(a, b, 4)]
               for g, (a, b) in EU_GROUPS.items()}
    PATCHED_SIGNATURES = patched
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "signatures.json")
    with open(path, "w") as f:
        json.dump({"original": orig, "patched": patched}, f)
    return path


def _load_signatures():
    import json
    import os
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "signatures.json")
    if os.path.exists(p):
        with open(p) as f:
            j = json.load(f)
        return j["original"], j["patched"]
    return {}, {}


EU_SIGNATURES, PATCHED_SIGNATURES = _load_signatures()
