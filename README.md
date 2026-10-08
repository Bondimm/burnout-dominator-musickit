# MusicKit for Burnout Dominator (PS2)

**Add your own songs to the EA Trax soundtrack of Burnout Dominator** — with their title, artist and album — and
get a new disc image that plays them in the game just like the original songs: in menus and races, in the Song
Manager, and in the "EA TRAX" now-playing pop-up. You can also **replace, rename, remove and reorder** any song,
the original ones included.

> **Unofficial fan-made tool.** Not affiliated with, endorsed or sponsored by Electronic Arts Inc. or Criterion
> Games. You need **your own copy** of the game. See [Legal](#legal) before you use or share anything.

- Works with your own disc image of **Burnout Dominator for PlayStation 2**:
  - Europe — `SLES-54681` (English) and `SLES-54627` (English, French, German, Spanish, Italian)
  - USA — `SLUS-21596`
- Your original image is **only read, never modified**; MusicKit writes a **new** `.iso`.
- Songs: MP3, FLAC, WAV, OGG, M4A … (anything ffmpeg can read), up to 94 songs in total.
- Add, replace, rename, remove and reorder songs — and reopen an image MusicKit made to keep editing it.
- Added songs get their own rows in the game's Song Manager (the original list has 36 rows).
- The new image keeps the game's PCSX2 CRC (`8C9C76B4` / `8C9576B4` Europe, `8C9576A1` USA), so **PCSX2 still
  recognises the game and applies its patches** (widescreen etc.).
- **Tested in PCSX2** with the Europe English version: added songs appear in the EA TRAX list after the original
  36, play in menus and races and show up in the EA TRAX pop-up.

---

## How it works — 5 steps

### Step 1 — Select your ISO
![Step 1 - select your ISO](docs/images/step1_select_iso.png)

### Step 2 — Add songs
![Step 2 - add songs](docs/images/step2_add_songs.png)

### Step 3 — Arrange the song list (optional)
![Step 3 - replace, rename, remove and reorder songs](docs/images/step3_song_list.png)

### Step 4 — Save a new ISO
![Step 4 - save the new ISO](docs/images/step4_save.png)

Before you save, MusicKit shows the size of the new image and how much more music still fits on a single-layer
DVD (4.7 GB) — calculated from *your* image. If it would not fit, you see a warning; you can still save it (see
[FAQ](#faq)).

### Step 5 — Play
Load the new `.iso` in PCSX2 (or burn it / run it on your PS2) and open **SETTINGS → EA TRAX**.

![Step 5 - your songs in the EA TRAX list](docs/images/step5_in_game.png)

![Step 5 - your songs in a race](docs/images/step5_in_race.png)

---

## Guides

Nothing is written until you click **Save new ISO** — every change below is only collected in the song list
(right side), which shows the soundtrack exactly as it will be on the new disc. **Undo all changes** goes back to
the song list of the opened image.

### Add songs
*Choose audio file…* (or drop files on the window), type title / artist / album, click **Add song**. New songs are
added at the end of the list; move them anywhere with ▲ / ▼. The original songs are written in CAPITALS — type
yours that way too if you want them to look the same in the game.

### Replace a song's audio
Click **Replace** next to any song (original or added) and choose another file. The song keeps its place, its
names and its Song Manager setting — rename it too with **Edit** if you like. **Play** previews the new audio
exactly as the game will play it.

### Rename a song (per language)
Click **Edit**: the three fields change title, artist and album for **all languages** at once. Open *English
text*, *French text*, *German text* … to set a different text for one language only (the 5-language Europe disc
has English, French, German, Spanish and Italian text). **Restore original names** undoes a rename of an original
song.

### Remove songs
Click **X** to remove a song — original songs too. At least one song must stay on the disc.

### Reorder songs
Use ▲ / ▼ to move a song. Moved songs are tagged *[was #N]* with their old position.

### Reopen a MusicKit ISO and keep editing
Select an image MusicKit made in step 1: its current song list is read back from the disc (added and replaced
songs are recognised). Change it like any other image and save another **new** `.iso`.

### Save games: removing or reordering songs
The game stores the Song Manager setting of positions **1–36** (on/off, menus/races) on the memory card **by
position**, not by song. Adding songs, replacing audio and renaming keep every setting where it is. **Removing or
moving songs** among positions 1–36 shifts those settings: a song that ends up at another position uses the
setting saved for that position. MusicKit shows a warning with the affected positions before you save.
**What to do:** after loading your save with the new image, open the Song Manager once, set those songs the way
you want and save your game.

---

## Requirements

| What | Details |
|---|---|
| Operating system | Windows 10 or 11 (64-bit), macOS 14 Sonoma or newer (Apple Silicon or Intel), or 64-bit Linux (x86_64 or aarch64, glibc 2.28+; tested on Ubuntu 22.04 / 24.04) |
| Python | 3.11 or newer — <https://www.python.org/downloads/> |
| Python packages | installed automatically by `setup.bat` / `setup.command` / `setup.sh` into a private `.venv`: numpy, numba, glfw, PyOpenGL, imgui-bundle, Pillow, soundfile, pyloudnorm, pycdlib, pytest (see [requirements.txt](requirements.txt)) |
| ffmpeg | downloaded automatically by `setup.bat` / `setup.command` / `setup.sh` (or install it yourself: Windows `winget install Gyan.FFmpeg`, macOS `brew install ffmpeg`, Linux your package manager, e.g. `sudo apt install ffmpeg`) |
| Graphics | any GPU with OpenGL 3.3 (for the MusicKit window) |
| Disk space | about 5 GB free for the new disc image (4.2–4.7 GB) plus ~1 GB for Python packages and ffmpeg |
| The game | your own disc image (.iso) of Burnout Dominator for PS2: Europe `SLES-54681` / `SLES-54627` or USA `SLUS-21596` |
| Internet | only once, during `setup.bat` / `setup.command` / `setup.sh` |

## Installation (Windows 10 / 11)

1. Install **Python 3.11 or newer** from <https://www.python.org/downloads/> (tick *"Add python.exe to PATH"*).
2. Download this repository (green **Code** button → *Download ZIP*) and unpack it, or `git clone` it.
3. Double-click **`setup.bat`** once. It creates a private Python environment in `.venv` and downloads
   **ffmpeg** into the `ffmpeg` folder (used to read MP3/FLAC/OGG/… files). Nothing is installed system-wide.
   - If the ffmpeg download fails, install it yourself (`winget install Gyan.FFmpeg`) or put `ffmpeg.exe` and
     `ffprobe.exe` into `ffmpeg\bin`.
4. Start **`MusicKit.bat`**.

## Installation (macOS)

For Apple Silicon (M1 and newer) and Intel Macs with macOS 14 Sonoma or newer.

1. Install **Python 3.11 or newer** from <https://www.python.org/downloads/macos/> (or with
   [Homebrew](https://brew.sh): `brew install python`).
2. Download this repository (green **Code** button → *Download ZIP*) and unpack it, or `git clone` it.
3. Double-click **`setup.command`** once. It opens a Terminal window, creates a private Python environment in
   `.venv` and downloads **ffmpeg** into the `ffmpeg` folder (an ffmpeg installed with Homebrew is used instead
   when present). Nothing is installed system-wide.
   - **First start:** macOS blocks scripts downloaded from the internet (*"cannot be opened because it is from an
     unidentified developer"* / *"Apple could not verify …"*). Right-click (Control-click) `setup.command` →
     **Open** → **Open**. On macOS 15 and newer, if there is no *Open* button: try to open it once, then go to
     *System Settings → Privacy & Security* and click **Open Anyway**. Or clear the download flag of the whole
     folder once in Terminal: `xattr -dr com.apple.quarantine ` followed by the folder (drag it into the Terminal
     window), then Return.
   - If the ffmpeg download fails, install ffmpeg with Homebrew: `brew install ffmpeg`, then run `setup.command`
     again.
   - If macOS says the file *"could not be executed because you do not have appropriate access privileges"*, the
     unpacking lost the permissions: run `chmod +x *.command *.sh` in Terminal inside the folder.
4. Start **`MusicKit.command`** and keep its Terminal window open while you use MusicKit. Settings and the log
   (`gui.log`) are kept in `~/Library/Application Support/musickit-dominator`.

## Installation (Linux)

For 64-bit Linux on x86_64 or aarch64 (glibc 2.28 or newer; Alpine / musl is not supported). Tested in CI on
Ubuntu 22.04 and 24.04 (x86_64); other distributions (Debian, Fedora, Arch, openSUSE, Mint, ...) should work the same way.

1. Install the system packages. Python 3.11 or newer, and on Debian / Ubuntu the separate `venv` package:
   - Debian / Ubuntu / Mint: `sudo apt install python3 python3-venv python3-pip libgl1 libegl1 libxkbcommon0 zenity`
   - Fedora: `sudo dnf install python3 python3-pip mesa-libGL mesa-libEGL libxkbcommon zenity`
   - Arch / Manjaro: `sudo pacman -S python python-pip mesa libglvnd libxkbcommon zenity`
   - Ubuntu 22.04 has Python 3.10 only: add Python 3.11+ first (deadsnakes PPA, or <https://www.python.org/downloads/>).
   - The window needs OpenGL 3.3 (Mesa or the GPU driver) and an X11 or Wayland session. **`zenity`** (or `kdialog`
     on KDE) is used for the file and folder dialogs; without it, the dialogs do not open. The GLFW and
     imgui-bundle wheels bring everything else. A sound player (`paplay`, `aplay` or `ffplay`) is used for previews.
2. Download this repository (green **Code** button → *Download ZIP*) and unpack it, or `git clone` it.
3. Open a terminal in the folder and run **`./setup.sh`** once. It creates a private Python environment in `.venv` and downloads **ffmpeg** into the `ffmpeg` folder (an ffmpeg installed with your package manager is used instead
   when present).
   Nothing is installed system-wide. If you get *"Permission denied"*, run `chmod +x *.sh` first.
   - If the ffmpeg download fails, install ffmpeg with your package manager (`sudo apt install ffmpeg`, `sudo dnf install ffmpeg`,
     `sudo pacman -S ffmpeg`), then run `./setup.sh` again.
4. Start **`./MusicKit.sh`** and keep the terminal open while you use MusicKit. Settings and the log (`gui.log`) are kept in
   `~/.config/musickit` (or `$XDG_CONFIG_HOME/musickit`).

The Windows version also runs under Wine, but use the native Linux version.

## Sound quality

The game streams its music as **PS2 ADPCM, stereo, 32 kHz** — every song is converted to that format:

| Your file | What happens |
|---|---|
| CD quality or better (44.1 / 48 / 96 kHz, 16/24-bit) | downsampled to 32 kHz (the best the game can play) |
| lower than 32 kHz (e.g. 22 kHz) | upsampled — it plays fine, but quality cannot get better than the source |
| mono | copied to both channels |
| more than 2 channels | mixed down to stereo |

Loudness is matched to the original EA Trax songs, so your songs are neither louder nor quieter than the rest
(you can turn this off under *Options*). Titles, artists and albums can be up to 60 characters; characters the
game's font does not have are replaced by the closest one (accents are kept).

## Command line (optional)

Everything the window does is also available from `musickit-cli.bat` (Windows) or `./musickit-cli.sh` (macOS / Linux,
in a terminal). Song numbers are positions in the pending list shown by `queue` (the same as `list` until you change
something).

| Task | Command |
|---|---|
| show the songs of an image | `list --iso "Burnout Dominator (Europe).iso"` |
| add a song | `add song.flac --title "My Song" --artist "My Band" --album "My Album"` |
| replace a song's audio | `replace 5 other.flac --iso "Burnout Dominator (Europe).iso"` |
| rename (all languages / one language) | `edit 7 --title "New Title" --artist "New Artist"` · `edit 7 --album-ge "Neues Album"` |
| remove a song from the disc | `remove-song 12` |
| move a song | `move 36 1` · `move 36 up` · `move 36 down` |
| show the pending list | `queue` |
| forget all pending changes | `reset` |
| save the new image | `build --iso "Burnout Dominator (Europe).iso" --out "Burnout Dominator (MusicKit).iso"` |
| check a new image | `validate "Burnout Dominator (Europe).iso" "Burnout Dominator (MusicKit).iso"` |

`remove` (without `-song`) removes a queued *new* song; `remove-song` removes a song from the disc.

`validate` re-reads the new image and checks it: the file system is consistent, every file MusicKit did not change
is byte-identical, the PCSX2 CRC is unchanged, the song list is consistent and new or replaced songs decode; it
also tells you whether the image fits on a single-layer DVD.

## FAQ

**PCSX2 says the dump is not in the redump database / the MD5 is red.** That is expected for *any* modified disc
image — it simply is not the original pressing anymore. It does not affect the game or PCSX2 patches: the game CRC
(shown in PCSX2's game properties) stays the same.

**Can I change the songs again later?** Yes. Open the image MusicKit made and add, replace, rename, remove or
reorder songs; MusicKit reads the current song list back from that image.

**Will my save game still work?** Yes. Adding songs, replacing audio and renaming keep every Song Manager setting
where it is; new songs default to *ALL* (menus and races). Removing or moving songs shifts the saved settings of
positions 1–36 — see [Save games](#save-games-removing-or-reordering-songs). The settings of songs after position 36
are not stored on the memory card (the game only has room for 36): they start as *ALL* again after you load your
save.

**How many songs can the disc have?** From 1 up to 94 songs in total.

**My songs don't show up.** Make sure you started the *new* `.iso`. Added songs are at the end of the Song Manager
list unless you moved them — scroll down past the original songs.

**Can I switch songs OFF?** Yes — Burnout Dominator lets you switch every song OFF in the Song Manager right away,
original and added songs alike, so MusicKit has no extra option for it (the Burnout Revenge MusicKit needs one).

**Why are some versions of "Girlfriend" switched off?** The game has four language versions of Avril Lavigne's
"Girlfriend" and switches two of them off by default, depending on your console's region. MusicKit keeps that
rule for those songs wherever you move them. If you give one of them new audio, it is no longer switched off.

**Why does MusicKit warn that my image is too big to burn?** A normal (single-layer) DVD holds 4.7 GB. With a lot
of added or long songs the new image can get bigger than that. It still works in emulators such as PCSX2, but it
cannot be burned to a normal DVD for a real PS2 — remove or shorten songs until the warning is gone if you want
to burn it. The 5-language Europe disc (`SLES-54627`) is already almost full: as soon as you add a song or give one
new audio, its image no longer fits on a single-layer DVD (renaming, removing and reordering still fit).

## Other Burnout MusicKits

- [Burnout Revenge MusicKit](https://github.com/Bondimm/burnout-revenge-musickit)
- [Burnout 3: Takedown MusicKit](https://github.com/Bondimm/burnout3-takedown-musickit)

## Legal

**Please read this before using or sharing anything made with MusicKit.**

- **Unofficial project.** MusicKit is an independent, non-commercial fan project. It is not affiliated with,
  authorised, endorsed or sponsored by Electronic Arts Inc., Criterion Games or Sony Interactive Entertainment.
- **Trademarks.** "Burnout", "Burnout Dominator", "EA", "EA Trax" and related names and logos are trademarks of
  Electronic Arts Inc.; "PlayStation" and "PS2" are trademarks of Sony Interactive Entertainment. They are used
  here only to describe which game this tool works with. All other trademarks belong to their owners.
- **No game content is included.** This repository contains only original source code and documentation, plus
  screenshots used to illustrate how the tool works. It does not contain or distribute any part of the game —
  no disc images, executables, music, textures or other data.
- **Bring your own game.** You need your own, legally obtained copy of Burnout Dominator and must create the disc
  image from it yourself. MusicKit does not bypass any copy protection; it only edits a copy of your own image.
- **Do not share modified disc images.** Disc images contain the game, which is copyrighted by Electronic Arts.
  Uploading or distributing them — modified or not — is not allowed.
- **Music rights.** Songs belong to their artists and labels. Only add music you are allowed to use, keep your
  modified image for personal use, and do not distribute images or files that contain other people's music.
- **No warranty.** The software is provided "as is", without warranty of any kind (see [LICENSE](LICENSE)).
  Use it at your own risk; keep a backup of your original image and your memory card saves.
- **Licence.** The source code is released under the MIT License. The licence applies only to the code in this
  repository and grants no rights to the game or its content.

If you are a rights holder and have a concern about this project, please open an issue and it will be addressed
promptly.
