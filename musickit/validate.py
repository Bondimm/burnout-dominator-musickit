"""Validate a MusicKit output ISO against its source: file systems parse, untouched files are byte-identical
and keep their LSNs, the song list/names/streams of the new image are consistent."""
import hashlib
import struct

from . import core, iso

from . import elfpatch

# PCSX2 patches (resources/patches.zip) for the supported versions, by game CRC: written EE addresses.
PNACH = {
    0x8C9576B4: {"Widescreen 16:9 (ElHecht and Arapapa)": [0x38B128, 0x43E8F0]},
    0x8C9576A1: {
        "Widescreen 16:9/21:9 (SuperType1/remco)": [0x1A2798, 0x1A27A0, 0x1F60FC, 0x22BE50, 0x22BE54, 0x1C91FB8,
                                                     0x1C91FF8, 0x1C91FE0, 0x1C92000, 0x1C91AA0, 0x1C91FF0, 0x3C5314,
                                                     0x1C91980, 0x1C91690, 0x1C91988, 0x1CADE10, 0x1C9BD40, 0x1C9BD48,
                                                     0x1C9BD50, 0x1C91A78, 0x1C91A70, 0x1C91F60, 0x441078, 0x1C919A8,
                                                     0x3DCEA8],
        "60 FPS Menus and Crashes": [0x2159AC, 0x2159A4, 0x209070],
        "Extra particles / falling car parts / progressive scan (Nehalem)": [0x2E30DC, 0x2847D8, 0x183F1C],
    },
}


def _hash_file(img, e):
    h = hashlib.sha1()
    img.f.seek(e.lsn * iso.SECTOR)
    left = e.size
    while left:
        b = img.f.read(min(left, 8 << 20))
        h.update(b)
        left -= len(b)
    return h.hexdigest()


def validate(src_path, out_path, log=print, hash_all=True):
    ok = True
    src = iso.IsoImage(src_path)
    out = iso.IsoImage(out_path)
    s0 = core.Disc(src_path)
    CHANGED = s0.changed_paths
    if not out.udf:
        log("FAIL: UDF bridge not readable: %s" % getattr(out, "udf_error", "?"))
        ok = False
    # pycdlib cross-check (independent ISO9660/UDF parser)
    try:
        import pycdlib
        p = pycdlib.PyCdlib()
        p.open(out_path)
        n = 0
        for root, dirs, files in p.walk(iso_path="/"):
            n += len(files)
        nu = 0
        if p.has_udf():
            for root, dirs, files in p.walk(udf_path="/"):
                nu += len(files)
        p.close()
        log("pycdlib: %d ISO9660 files, %d UDF files" % (n, nu))
        if n != len(src.entries) or (nu and nu != len(src.entries)):
            log("FAIL: file count differs from source (%d)" % len(src.entries))
            ok = False
    except ImportError:
        log("pycdlib not installed, skipped")
    except Exception as exc:
        log("FAIL: pycdlib could not parse the image: %s" % exc)
        ok = False
    # UDF and ISO9660 agree
    for k, e in out.entries.items():
        if e.udf_fe is None:
            continue
        d = out.read(e.udf_fe)
        ext = out._fe_extents(d)
        size = struct.unpack_from("<Q", d, 56)[0]
        if size != e.size or ext[0][0] + out.part_start != e.lsn:
            log("FAIL: UDF/ISO9660 mismatch for %s" % k)
            ok = False
        if bytes(iso.udf_fix_tag(d)) != d:
            log("FAIL: bad UDF descriptor CRC for %s" % k)
            ok = False
    same = moved = 0
    for k, e in src.entries.items():
        o = out.entries.get(k)
        if o is None:
            log("FAIL: %s missing" % k)
            ok = False
            continue
        if k in CHANGED:
            continue
        if o.lsn != e.lsn or o.size != e.size:
            log("FAIL: %s moved (%d -> %d)" % (k, e.lsn, o.lsn))
            moved += 1
            ok = False
        elif hash_all and _hash_file(src, e) != _hash_file(out, o):
            log("FAIL: %s content differs" % k)
            ok = False
        else:
            same += 1
    log("untouched files identical at original LSNs: %d/%d%s" % (same, len(src.entries) - len(CHANGED),
                                                                 "" if hash_all else " (LSN/size only)"))
    for k in sorted(CHANGED):
        log("changed %-34s lsn %8d -> %8d  size %10d -> %10d" % (k, src.entries[k].lsn, out.entries[k].lsn,
                                                                 src.entries[k].size, out.entries[k].size))
    d = core.Disc(out_path)
    log("version: %s" % d.region)
    log("songs: %d -> %d" % (s0.count, d.count))
    log("Song Manager rows: %s" % "/".join(map(str, elfpatch.read_rows(d.elf))))
    c_src, c_out = elfpatch.crc(s0.elf), elfpatch.crc(d.elf)
    log("PCSX2 game CRC: %08X -> %08X %s" % (c_src, c_out, "(unchanged)" if c_src == c_out else "CHANGED"))
    if c_src != c_out:
        ok = False
    ranges = elfpatch.touched_ranges(d.elf)
    if c_src not in PNACH:
        log("pnach: no PCSX2 patch list known for CRC %08X, overlap check skipped" % c_src)
    for name, addrs in PNACH.get(c_src, {}).items():
        clash = [a for a in addrs if any(lo <= a < hi for lo, hi in ranges)]
        log("pnach '%s': %s" % (name, "no overlap" if not clash else "OVERLAP at " + ", ".join(map(hex, clash))))
        if clash:
            ok = False
    log("note: the modified disc can never match the redump MD5 (expected for any modified image)")
    size = out.volume_sectors * iso.SECTOR
    log(("" if size <= core.DVD5_SECTORS * iso.SECTOR else "warning: ") + core.capacity_text(size))
    ok = check_songs(s0, d, log) and ok
    log("RESULT: %s" % ("OK" if ok else "FAILED"))
    return ok


def check_songs(s0, d, log=print):
    """Song list consistency of output disc `d` (built from `s0`): table, names, streams. Songs whose audio was
    kept (same segment UUID) must be byte-identical to the source; new / replaced songs must decode."""
    ok = True
    table = elfpatch.read_table(d.elf)
    if [t[:2] for t in table] != [(i, 0) for i in range(d.count)]:
        log("FAIL: song table entries do not match their positions")
        ok = False
    if not 1 <= d.count <= core.MAX_SONGS:
        log("FAIL: song count %d" % d.count)
        ok = False
    if d.patched and elfpatch.read_rows(d.elf) != [d.count] * 3:
        log("FAIL: Song Manager rows %s for %d songs" % (elfpatch.read_rows(d.elf), d.count))
        ok = False
    nseg = [len(h.segments) for h in d.headers]
    if nseg[0] < min(d.count, core.SPLIT) or (d.count > core.SPLIT and nseg[1] < d.count - core.SPLIT):
        log("FAIL: stream files have %s segments for %d songs" % (nseg, d.count))
        ok = False
    src_by_uuid = {}
    for s in s0.songs:
        src_by_uuid[s0.headers[s.rws_index].segments[s.segment].uuid] = s
    for s in d.songs:
        for l in d.langs:
            if not d.tables[l].get(core.sid("title", s.index)):
                log("FAIL: song %d has no title in %s" % (s.index + 1, l))
                ok = False
        seg = d.headers[s.rws_index].segments[s.segment] if s.segment < nseg[s.rws_index] else None
        if seg is None:
            continue
        o = src_by_uuid.get(seg.uuid)
        if o is not None and o.usable == s.usable and _seg_hash(s0, o) == _seg_hash(d, s):
            continue
        if o is not None and not seg.uuid.startswith(core.MARK):
            log("FAIL: song %d audio differs from the source song %d" % (s.index + 1, o.index + 1))
            ok = False
            continue
        pcm = d.decode_song(s.index)
        log("  #%d %s / %s / %s  %.1f s  peak %d  (new audio)" % (s.index + 1, s.artist, s.title, s.album,
                                                                 len(pcm) / 32000.0, int(abs(pcm.astype(int)).max())))
        if len(pcm) < 32000:
            log("FAIL: song %d is shorter than 1 s" % (s.index + 1))
            ok = False
    kept = sum(1 for s in d.songs if s.original)
    log("songs: %d total, %d original, %d added or replaced" % (d.count, kept, d.count - kept))
    return ok


def _seg_hash(disc, s):
    hdr = disc.headers[s.rws_index]
    seg = hdr.segments[s.segment]
    f, e = disc.img.open_file(core.RWS_FILES[s.rws_index])
    with f:
        f.seek(e.lsn * iso.SECTOR + hdr.segment_file_offset(seg))
        h = hashlib.sha1()
        left = seg.size
        while left:
            b = f.read(min(left, 8 << 20))
            if not b:
                break
            h.update(b)
            left -= len(b)
    return h.hexdigest()
