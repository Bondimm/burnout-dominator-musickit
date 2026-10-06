"""MusicKit tests. Run from the repository folder: .venv\\Scripts\\python -m pytest tests

Format tests use your own disc images when MUSICKIT_ISO (Europe ISO, SLES-54681), MUSICKIT_USA_ISO (USA ISO) or
MUSICKIT_MULTI_ISO (Europe 5-language ISO, SLES-54627) are set; they only read. Without them those tests are
skipped. MUSICKIT_FULL_TEST=1 also builds complete images (~4.2 GB each) in the temp folder.
"""
import io
import os
import struct
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from musickit import adpcm, core, elfpatch, iso, rws, strtable  # noqa: E402

ISO = os.environ.get("MUSICKIT_ISO", "")  # path to your own Burnout Dominator ISO; tests that need it are skipped otherwise
USA_ISO = os.environ.get("MUSICKIT_USA_ISO", "")
MULTI_ISO = os.environ.get("MUSICKIT_MULTI_ISO", "")


def _skip(path):
    if not path or not os.path.exists(path):
        import pytest
        pytest.skip("missing " + (path or "disc image"))


def test_adpcm_roundtrip_exact():
    rng = np.random.default_rng(1)
    t = np.arange(32000) / 32000.0
    x = (np.sin(2 * np.pi * 440 * t) * 12000 + rng.normal(0, 300, len(t))).astype(np.int16)
    enc = adpcm.encode(x)
    assert len(enc) == (len(x) + 27) // 28 * 16
    y = adpcm.decode(enc)[: len(x)]
    snr = 10 * np.log10((x.astype(float) ** 2).sum() / ((x - y.astype(float)) ** 2).sum())
    assert snr > 30
    # re-encoding decoded ADPCM is lossless (encoder finds the same frames)
    assert np.array_equal(adpcm.decode(adpcm.encode(y)), adpcm.decode(enc)[: len(adpcm.decode(adpcm.encode(y)))])


def _rws_head(img, path):
    f, e = img.open_file(path)
    with f:
        return f.read(0x4000)


def test_rws_header_rebuild_identical():
    _skip(ISO)
    img = iso.IsoImage(ISO)
    for name, n in (("/TRACKS/EATRAX0.RWS", 22), ("/TRACKS/EATRAX1.RWS", 14)):
        head = _rws_head(img, name)
        h = rws.read_header(io.BytesIO(head))
        assert len(h.segments) == n and h.block_size == 0x2000 and h.channels == 2
        assert h.build() == head[:h.data_offset + 12]
        assert [s.name for s in h.segments][:1] == ["%02d" % (0 if n == 22 else 22)]


def test_rws_segment_reencode_lossless():
    _skip(ISO)
    d = core.Disc(ISO)
    s = d.songs[-1]
    pcm = d.decode_song(s.index)
    pay2, us2 = rws.encode_segment(pcm)
    seg = d.headers[s.rws_index].segments[s.segment]
    assert us2 == seg.usable and len(pay2) == seg.size
    assert np.array_equal(rws.decode_segment(pay2, us2), pcm)


def test_string_hash_and_table():
    _skip(ISO)
    img = iso.IsoImage(ISO)
    data = img.read_file("/LANGUAGE/STRINGS/MAINUK.BIN")
    t = strtable.StringTable(data)
    assert t.build() == data
    assert t.get("EATraxArtist_17") == "LCD SOUNDSYSTEM"
    assert t.get("EATraxSongTitle_17") == "US V. THEM"
    assert t.get("EATraxSongTitle_35") == "LOST ANGELES" and t.get("EATraxSongTitle_36") is None
    t.set("EATraxSongTitle_36", "Test")
    t2 = strtable.StringTable(t.build())
    assert t2.get("EATraxSongTitle_36") == "Test" and t2.get("EATraxSongTitle_0") == "NINE"
    assert core.sid("album", 3) == "EATraxAlbum_3"


def test_sanitize():
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 '-éü")
    assert strtable.sanitize("Café Motörhead", allowed) == "Café Motorhead"
    assert strtable.sanitize("Don’t", allowed) == "Don't"


def _elf_versions():
    out = []
    for path, crc in ((ISO, 0x8C9C76B4), (USA_ISO, 0x8C9576A1), (MULTI_ISO, 0x8C9576B4)):
        if path and os.path.exists(path):
            d = core.Disc(path)
            out.append((d.region, d.elf, crc, 0x3CF310, 0x404080, 0x491540))
    return out


def _vers():
    vers = _elf_versions()
    if not vers:
        import pytest
        pytest.skip("no executable")
    return vers


def test_elf_patch():
    for name, d, crc, playlist, table, profile in _vers():
        assert elfpatch.crc(d) == crc
        lay = elfpatch.Layout(d)
        assert (lay.playlist, lay.table_new, lay.profile, lay.table_old) == (playlist, table, profile, 0x3CF160), name
        assert set(lay.delta.values()) == {0}, name
        assert elfpatch.read_rows(d) == [36, 36, 36]
        assert elfpatch.read_default_off(d) == {4: 4, 5: 5, 6: 6, 7: 7}
        out = elfpatch.patch(d, 45)
        assert elfpatch.crc(out) == crc, name            # PCSX2 CRC kept
        e = elfpatch.Elf(out)
        assert elfpatch.read_song_count(out) == 45 and elfpatch.is_patched(out)
        assert elfpatch.read_rows(out) == [45, 45, 45] and elfpatch.read_default_off(out) == {4: 4, 5: 5, 6: 6, 7: 7}
        assert e.r32(playlist + 0x4C) == table
        assert struct.unpack("<3I", out[e.file_offset(table + 12 * 44):][:12]) == (44, 0, 7)
        assert struct.unpack("<3I", out[e.file_offset(table + 12 * 5):][:12]) == (5, 0, 15)
        c = lay.ctx()
        for va, eu, t, _ in lay.sites():
            if t is not None:
                assert e.r32(va) == (t(c) if callable(t) else t), (name, hex(va))
        o = elfpatch.Elf(d)
        a, b = o.phdrs()[1], e.phdrs()[1]
        assert d[a[1]:a[1] + a[4]] == out[b[1]:b[1] + b[4]]   # second segment moved but unchanged
        s = o.phdrs()[0]   # in the code segment only the listed words changed
        allowed = {va for va, _, t, _ in lay.sites() if t is not None} | {va for va, _ in lay.row_sites()}
        diff = {s[2] + i for i in range(0, s[4], 4) if o.r32(s[2] + i) != e.r32(s[2] + i)}
        assert diff <= allowed | set(range(playlist, playlist + 0x50, 4)), name
        out2 = elfpatch.extend(out, 47)
        assert elfpatch.read_song_count(out2) == 47 and elfpatch.crc(out2) == crc and len(out2) == len(out)
        assert elfpatch.read_rows(out2) == [47, 47, 47]


def test_default_off_follows_songs():
    """The start-up stores that switch two Girlfriend versions off follow those songs (or go to an unused slot)."""
    for name, d, crc, playlist, table, profile in _vers():
        out = elfpatch.set_table(d, [7] * 50, {4: 3, 5: 40, 6: None, 7: 7})
        assert elfpatch.read_default_off(out) == {4: 3, 5: 40, 6: None, 7: 7} and elfpatch.crc(out) == crc
        lay = elfpatch.Layout(out)
        offs = sorted(lay.elf.r32(va) & 0xFFFF for va, _ in lay.default_off_sites())
        assert offs == [8 + 12 * 3, 8 + 12 * 7, 8 + 12 * 40, 8 + 12 * elfpatch.SINK]
        assert table + offs[-1] + 4 <= lay.hole_end        # the unused slot is inside the relocated hole
        again = elfpatch.set_table(out, [7] * 20)           # positions past the end are dropped
        assert elfpatch.read_default_off(again) == {4: 3, 5: None, 6: None, 7: 7}


def test_udf_tag_crc():
    _skip(ISO)
    img = iso.IsoImage(ISO)
    for lsn in (256, img.pd_lsns[0], img.entries["/SLES_546.81"].udf_fe):
        d = img.read(lsn)
        assert bytes(iso.udf_fix_tag(d)) == d


def test_build_iso_end_to_end():
    """Full build into a temp folder (writes ~4.2 GB) - only with MUSICKIT_FULL_TEST=1."""
    if not os.environ.get("MUSICKIT_FULL_TEST"):
        import pytest
        pytest.skip("set MUSICKIT_FULL_TEST=1")
    _skip(ISO)
    from musickit import validate
    sys.path.insert(0, HERE)
    import make_test_songs
    tmp = tempfile.mkdtemp()
    make_test_songs.main(tmp)
    out = os.path.join(tmp, "test.iso")
    d = core.Disc(ISO)
    song = core.NewSong(os.path.join(tmp, "test_chords_44k_24bit.flac"), "Chord Test", "MusicKit", "Demo")
    rep = d.build([song], out)
    assert rep["total_songs"] == 37
    assert validate.validate(ISO, out, log=lambda *a: None)
    o = core.Disc(out)
    assert o.count == 37 and o.patched and elfpatch.read_rows(o.elf) == [37, 37, 37]
    assert o.songs[36].title == "Chord Test" and not o.songs[36].original
    o.img.f.close()
    os.remove(out)


# ---------------------------------------------------------------- song management (replace/edit/remove/move)
def _isos():
    out = [p for p in (ISO, USA_ISO) if p and os.path.exists(p)]
    if not out:
        import pytest
        pytest.skip("set MUSICKIT_ISO and/or MUSICKIT_USA_ISO")
    return out


def _ffmpeg():
    from musickit import audio
    try:
        audio.AudioInfo(os.path.join(HERE, "data", "test_chords_22k_mono.wav"))
    except Exception:
        import pytest
        pytest.skip("ffmpeg not found")


def _check_reps(d, items, reps):
    """Song list consistency of the files build_list writes for `items`: executable table + count + CRC, the
    strings of every language and the stream segment of every position."""
    total = len(items)
    elf = reps[d.elf_path]
    assert elfpatch.crc(elf) == d.crc and elfpatch.read_song_count(elf) == total
    assert elfpatch.read_rows(elf) == [total] * 3
    assert elfpatch.read_default_off(elf) == d.new_default_off(items)
    table = elfpatch.read_table(elf)
    for k, it in enumerate(items):
        assert table[k][:2] == (k, 0)
        assert table[k][2] == (7 if isinstance(it, core.NewSong) else d.songs[it.src].flags)
    for l in d.langs:
        t = strtable.StringTable(reps["/LANGUAGE/STRINGS/MAIN%s.BIN" % l])
        for k, it in enumerate(items):
            for f in core.FIELDS:
                want = it.text(l, f) if isinstance(it, core.NewSong) else it.text(d, l, f)
                assert t.get(core.sid(f, k)) == (want or (" " if f != "title" else "Untitled")), (l, k, f)
    for ri, path in enumerate(core.RWS_FILES):
        lo, hi = (0, min(core.SPLIT, total)) if ri == 0 else (core.SPLIT, total)
        if path not in reps:          # unchanged file: same songs at the same place, or not used at all
            assert hi <= lo or all(isinstance(items[k], core.SongRef) and items[k].src == k and not items[k].audio
                                   for k in range(lo, hi))
            continue
        parts = reps[path].parts
        h = rws.RwsHeader(parts[0])
        assert len(h.segments) == hi - lo and len(parts) == 1 + hi - lo
        for j, seg in enumerate(h.segments):
            it = items[lo + j]
            assert seg.name == "%02d" % (lo + j)
            assert seg.offset == sum(s.size for s in h.segments[:j])
            if isinstance(it, core.SongRef) and not it.audio:
                s = d.songs[it.src]
                src_seg = d.headers[s.rws_index].segments[s.segment]
                e = d.img.entries[core.RWS_FILES[s.rws_index]]
                assert parts[1 + j] == (d.path, e.lsn * iso.SECTOR + d.headers[s.rws_index].segment_file_offset(src_seg),
                                        src_seg.size)
                assert seg.usable == src_seg.usable and seg.uuid == src_seg.uuid
            else:
                assert seg.uuid.startswith(core.MARK) and len(parts[1 + j]) == seg.size


def test_disc_reads_original_list():
    for p in _isos():
        d = core.Disc(p)
        assert d.count == 36 and not d.patched and all(s.original for s in d.songs)
        assert d.songs[0].title == "NINE" and d.songs[17].artist == "LCD SOUNDSYSTEM"
        assert [s.rws_index for s in d.songs].count(0) == 22
        assert all(s.flags == 15 for s in d.songs) and d.default_off == {4: 4, 5: 5, 6: 6, 7: 7}
        assert 120 < d.songs[5].duration < 600


def test_remove_move_edit_consistency():
    for p in _isos():
        d = core.Disc(p)
        items = d.current_list()
        assert d.is_unchanged(items) and d.save_warning(items) is None
        items.pop(2)                                   # remove an original song in EATRAX0
        items.insert(0, items.pop(-1))                 # move the last song (in EATRAX1) to the top
        items[24], items[25] = items[25], items[24]    # swap two songs in EATRAX1
        items[5].title = "Edited Title"                # rename for every language
        items[5].names = {d.langs[-1]: {"artist": "Edited Artist"}}
        reps, rep = d.replacements(items, normalize=False)
        _check_reps(d, items, reps)
        assert rep["total_songs"] == 35 and rep["removed"] == 1
        assert d.save_shift(items)[:3] == [1, 2, 3] and d.save_warning(items)
        assert elfpatch.read_default_off(reps[d.elf_path]) == {4: 4, 5: 5, 6: 6, 7: 7}   # 1 removed + 1 moved up
        t = strtable.StringTable(reps["/LANGUAGE/STRINGS/MAIN%s.BIN" % d.langs[-1]])
        assert t.get("EATraxSongTitle_5") == "Edited Title" and t.get("EATraxArtist_5") == "Edited Artist"
        assert t.get("EATraxSongTitle_35") == d.songs[35].names[d.langs[-1]]["title"]   # original ids stay


def test_default_off_with_song_changes():
    _ffmpeg()
    for p in _isos():
        d = core.Disc(p)
        items = d.current_list()
        items.pop(4)                                   # remove Girlfriend (English)
        items[4].audio = os.path.join(HERE, "data", "test_chords_22k_mono.wav")   # new audio for song 6
        items.append(items.pop(5))                     # move song 7 to the end
        assert d.new_default_off(items) == {4: None, 5: None, 6: 34, 7: 5}
        reps, _ = d.replacements(items, normalize=False)
        _check_reps(d, items, reps)


def test_edit_only_keeps_streams_and_saves():
    for p in _isos():
        d = core.Disc(p)
        items = d.current_list()
        items[0].names = {l: {"title": "Neu %s" % l} for l in d.langs}
        reps, rep = d.replacements(items, normalize=False)
        _check_reps(d, items, reps)
        assert not any(k in reps for k in core.RWS_FILES)   # streams untouched
        assert d.save_shift(items) == [] and d.save_warning(items) is None


def test_minimum_one_song_and_limits():
    import pytest
    for p in _isos():
        d = core.Disc(p)
        items = [core.SongRef(30)]
        reps, rep = d.replacements(items, normalize=False)
        _check_reps(d, items, reps)
        assert core.RWS_FILES[1] not in reps and len(d.save_shift(items)) == 36
        with pytest.raises(ValueError):
            d.replacements([], normalize=False)
        with pytest.raises(ValueError):
            d.replacements([core.SongRef(0)] * (core.MAX_SONGS + 1), normalize=False)
        assert core.MAX_SONGS == elfpatch.MAX_SONGS == 94
        with pytest.raises(ValueError):
            elfpatch.set_table(d.elf, [7] * 95)


def test_replace_audio_keeps_slot():
    _ffmpeg()
    for p in _isos():
        d = core.Disc(p)
        items = d.current_list()
        items[10].audio = os.path.join(HERE, "data", "test_chords_22k_mono.wav")     # in EATRAX0
        items[30].audio = os.path.join(HERE, "data", "test_chords_44k_24bit.flac")   # in EATRAX1
        items.append(core.NewSong(os.path.join(HERE, "data", "test_chords_22k_mono.wav"), "New", "MusicKit", ""))
        reps, rep = d.replacements(items, normalize=False)
        _check_reps(d, items, reps)
        assert d.save_shift(items) == []
        assert [s["index"] for s in rep["songs"]] == [10, 30, 36] and rep["songs"][0]["replaced"]
        h = rws.RwsHeader(reps[core.RWS_FILES[0]].parts[0])
        pcm = rws.decode_segment(reps[core.RWS_FILES[0]].parts[11], h.segments[10].usable)
        assert abs(len(pcm) / 32000.0 - 20.0) < 0.1


def test_size_plan_and_dvd_capacity():
    """Projected image size from the planned layout (no encoding) and the single-layer DVD check."""
    for p in _isos():
        d = core.Disc(p)
        src = d.img.volume_sectors * iso.SECTOR
        same = d.size_plan(d.current_list())
        assert same["bytes"] == src and same["fits"] and "fits on a single-layer DVD" in same["text"] and "more minutes" in same["text"]
        pcm = (np.sin(np.arange(32000 * 3) / 7.0) * 8000).astype(np.int16)
        payload, usable = rws.encode_segment(np.stack([pcm, pcm], 1), d.headers[0].block_size)
        assert d.encoded_size(3.0) == (len(payload), usable)
        items = d.current_list() + [core.NewSong("fake%d.flac" % k, "Song %d" % k, "Band", "") for k in range(10)]
        small = d.size_plan(items, estimate={k: 200.0 for k in range(d.count, len(items))})
        audio_bytes = 10 * d.encoded_size(200.0)[0]
        rws1 = d.img.entries[core.RWS_FILES[1]].size     # the grown EATRAX1.RWS is written after the volume end
        assert small["fits"] and audio_bytes + rws1 <= small["bytes"] - src <= audio_bytes + rws1 + (8 << 20)
        big = d.size_plan(items, estimate={k: 1500.0 for k in range(d.count, len(items))})   # 10 x 25 min
        assert not big["fits"] and big["bytes"] > core.DVD5_SECTORS * iso.SECTOR
        assert "larger than a single-layer DVD (4.7 GB)" in big["text"] and "%.2f GB" % (big["bytes"] / 1e9) in big["text"]
        fewer = d.current_list()
        del fewer[30:]                     # shorter stream file: rewritten in place (only the executable may move)
        assert d.size_plan(fewer)["bytes"] - src <= d.img.entries[d.elf_path].size + (1 << 20)
        moved = d.current_list()
        del moved[5:15]                    # songs move from EATRAX1 into EATRAX0: that file grows and is appended
        assert d.size_plan(moved)["bytes"] > src
    assert "about 0 more minutes" in core.capacity_text(core.DVD5_SECTORS * iso.SECTOR)


def test_size_plan_multi_language_disc():
    """The 5-language Europe disc has only ~38 MiB left on a DVD5: a few added songs trigger the warning."""
    _skip(MULTI_ISO)
    d = core.Disc(MULTI_ISO)
    assert d.langs == ("UK", "FR", "GE", "SP", "IT") and d.count == 36
    same = d.size_plan(d.current_list())
    assert same["fits"] and same["room_bytes"] < 40 << 20
    assert same["music_room_bytes"] == 0 and "about 0 more minutes" in same["text"]
    items = d.current_list() + [core.NewSong("fake%d.flac" % k, "Song %d" % k, "Band", "") for k in range(3)]
    plan = d.size_plan(items, estimate={k: 240.0 for k in range(d.count, len(items))})
    assert not plan["fits"] and "larger than a single-layer DVD" in plan["text"]


def test_set_table_shrink_and_grow():
    for name, d, crc, playlist, table, profile in _vers():
        for n in (1, 22, 35, 36, 60, elfpatch.MAX_SONGS):
            flags = [(i % 7) + 1 for i in range(n)]
            out = elfpatch.set_table(d, flags)
            assert elfpatch.crc(out) == crc and elfpatch.read_song_count(out) == n, (name, n)
            assert [t[2] for t in elfpatch.read_table(out)] == flags and elfpatch.read_rows(out) == [n] * 3
            again = elfpatch.set_table(out, flags[:max(1, n // 2)] + [7])     # re-patch a patched executable
            assert elfpatch.crc(again) == crc and len(again) == len(out)
            e = elfpatch.Elf(again)
            for i in range(36):    # entries 0..35 stay valid for the memory card profile loader
                assert struct.unpack("<3I", again[e.file_offset(table + 12 * i):][:12])[:2] == (i, 0)


def test_manage_end_to_end():
    """Remove an original, replace one, rename one, add one, reopen the output and rename again (writes 2 images
    of ~4 GB per ISO, one at a time) - only with MUSICKIT_FULL_TEST=1."""
    if not os.environ.get("MUSICKIT_FULL_TEST"):
        import pytest
        pytest.skip("set MUSICKIT_FULL_TEST=1")
    _ffmpeg()
    from musickit import validate
    flac = os.path.join(HERE, "data", "test_chords_44k_24bit.flac")
    wav = os.path.join(HERE, "data", "test_chords_22k_mono.wav")
    quiet = lambda *a: None   # noqa: E731
    for p in _isos():
        tmp = tempfile.mkdtemp()
        out1, out2 = os.path.join(tmp, "step1.iso"), os.path.join(tmp, "step2.iso")
        d = core.Disc(p)
        names = [s.title for s in d.songs]
        items = d.current_list()
        items.pop(1)                                   # remove original #2
        items[8].audio = flac                          # replace (now #9, was #10)
        items[2].title = "Renamed Once"                # rename (now #3, was #4)
        items.append(core.NewSong(wav, "Added Song", "MusicKit", "Demo"))
        plan = d.size_plan(items)
        d.build_list(items, out1)
        assert abs(os.path.getsize(out1) - plan["bytes"]) <= 64 << 10, (os.path.getsize(out1), plan["bytes"])
        assert validate.validate(p, out1, log=quiet)
        r = core.Disc(out1)                            # read back the modified image
        assert r.count == 36 and r.patched and r.crc == d.crc and elfpatch.read_rows(r.elf) == [36] * 3
        assert [s.title for s in r.songs[:2]] == [names[0], names[2]]
        assert r.songs[2].title == "Renamed Once" and r.songs[35].title == "Added Song"
        assert [s.original for s in r.songs] == [True] * 8 + [False] + [True] * 26 + [False]
        assert r.default_off == {4: 3, 5: 4, 6: 5, 7: 6}
        assert abs(r.songs[8].duration - 30.0) < 0.1
        items2 = r.current_list()                      # edit again + move + add on the modified image
        items2[2].title = "Renamed Twice"
        items2.insert(0, items2.pop(35))
        items2.append(core.NewSong(flac, "Added Later", "MusicKit", ""))
        r.build_list(items2, out2)
        assert validate.validate(out1, out2, log=quiet)
        r2 = core.Disc(out2)
        assert r2.count == 37 and r2.crc == d.crc and elfpatch.read_rows(r2.elf) == [37] * 3
        assert [s.title for s in r2.songs[:2]] == ["Added Song", names[0]]
        assert r2.songs[3].title == "Renamed Twice" and r2.songs[36].title == "Added Later"
        assert sum(not s.original for s in r2.songs) == 3
        assert r2.default_off == {4: 4, 5: 5, 6: 6, 7: 7}
        r.img.f.close()
        r2.img.f.close()
        os.remove(out1)
        os.remove(out2)


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
