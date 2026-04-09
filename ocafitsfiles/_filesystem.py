"""OCA FITS file system library.

Provides utilities for working with OCA FITS files:
- Root directory detection
- Filename parsing (basename, suffix, metadata)
- Path reconstruction from basename+suffix
- Calibration dependency traversal
- Observation dictionary building

No external dependencies - stdlib only.
"""
import re
import datetime
from pathlib import Path
from itertools import chain
from typing import Optional, Tuple, List, Dict, Any


# ---------------------------------------------------------------------------
# Root directory detection
# ---------------------------------------------------------------------------

ROOT_SCHEMAS: Dict[str, Path] = {
    'CAMK': Path('/work/vela/oca/fits'),
    'OCM':  Path('/data/fits'),
    'Mik':  Path('/Users/Shared/oca_data/fits'),
}


def detect_fits_root() -> Tuple[Optional[str], Optional[Path]]:
    """Detect FITS root directory. Returns (schema_name, path) or (None, None)."""
    for schema, path in ROOT_SCHEMAS.items():
        if path.is_dir():
            return schema, path
    return None, None


# ---------------------------------------------------------------------------
# OCA Julian date
# ---------------------------------------------------------------------------

def oca_night(dt) -> int:
    """Calculate OCA night number from a datetime or date.

    OCA night number = int(JD) % 10000, where JD changes at noon UT.

    datetime.datetime:
        Uses actual UT time.
        Verified with astropy:
          2026-02-23T13:49:43Z -> JD 2461095.076 -> night 1095
          2026-02-22T01:00:00Z -> JD 2461093.54  -> night 1093
          2026-02-23T01:00:00Z -> JD 2461094.54  -> night 1094

    datetime.date:
        Interpreted as "the night that STARTS on the evening of that date"
        (equivalent to 18:00 UT of that date).

        date(2026-02-22) -> 1094  (night starting evening of Feb 22)
        date(2026-02-23) -> 1095  (tonight)
    """
    if isinstance(dt, datetime.datetime):
        # JD epoch: ordinal 1 (Jan 1, year 1) = JD 1721425.5
        # Verified: 2026-02-23T13:49:43Z -> JD 2461095.076 (astropy)
        jd = dt.toordinal() + 1721424.5 + (
            dt.hour * 3600 + dt.minute * 60 + dt.second
        ) / 86400.0
        return int(jd) % 10000
    else:
        # date as "night starting on evening of that date" = JD at 18:00 UT = ordinal + 1721424.5 + 0.75
        # int(ordinal + 1721425.25) = ordinal + 1721425
        return (dt.toordinal() + 1721425) % 10000


# Keep old name as alias for compatibility
ocm_julian_date = oca_night


def ensure_oca_julian(dt) -> int:
    """Convert to OCA night number (int(JD) % 10000).

    Accepts:
        int / str of int  - returned as-is (% 10000)
        'YYYY-MM-DD'      - treated as midnight UT (see oca_night warning about date semantics)
        datetime.datetime - uses actual time for correct night assignment
    """
    try:
        return int(dt) % 10000
    except (ValueError, TypeError):
        try:
            if 'T' in str(dt) or ' ' in str(dt).strip():
                return oca_night(datetime.datetime.fromisoformat(str(dt)))
            return oca_night(datetime.date.fromisoformat(str(dt)))
        except Exception:
            raise ValueError(f'Invalid date: {dt}')


def night_set(nights: list[int | str] | None) -> set[int] | None:
    """Build a set of OCA night numbers from user-supplied values.

    Each element is passed through :func:`ensure_oca_julian`, so the caller
    can freely mix raw integers, string integers, and ISO dates.

    Returns ``None`` when *nights* is ``None`` or empty (meaning "no filter").
    """
    if not nights:
        return None
    return {ensure_oca_julian(n) for n in nights}


# ---------------------------------------------------------------------------
# Filename parsing
# ---------------------------------------------------------------------------

# basename pattern: e.g. zb08c_0571_24540
_BASENAME_RE = re.compile(
    r'(?P<base>\w{5}.\d{4}_\d{5})(?:_(?P<suff>\w+))?\.(?P<ext>fits|fz)'
)

# full metadata pattern
_META_RE = re.compile(
    r'(?P<telescope>\w{4})(?P<instr>.)_(?P<night>\d{4})_(?P<count>\d{5})(?:_(?P<suffix>.*))?\.fits$'
)


def parse_filename(name: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract (basename, suffix) from a FITS filename or path.

    Returns (None, None) if not an OCA FITS file.

    Examples:
        zb08c_0571_24540.fits       -> ('zb08c_0571_24540', None)
        zb08c_0571_24540_zdf.fits   -> ('zb08c_0571_24540', 'zdf')
        zb08c_0571_24540_master_z.fits -> ('zb08c_0571_24540', 'master_z')
    """
    name = Path(name).name
    m = _BASENAME_RE.match(name)
    if m:
        return m.group('base'), m.group('suff') or None
    return None, None


def parse_metadata(name: str) -> Optional[Dict[str, str]]:
    """Extract full metadata dict from filename.

    Returns dict with keys: telescope, instr, night, count, suffix (may be None).
    Returns None if not an OCA FITS file.
    """
    name = Path(name).name
    m = _META_RE.match(name)
    if m:
        return m.groupdict()
    return None


# ---------------------------------------------------------------------------
# Path reconstruction
# ---------------------------------------------------------------------------

def processed_dir(basename: str, suffix: Optional[str], root: Path) -> Optional[Path]:
    """Return the canonical processed directory for a given basename+suffix.

    This is the authoritative location - use this instead of following symlinks.

    Examples:
        ('zb08c_0571_24540', 'zdf')        -> {root}/zb08/processed-ofp/science/0571/zb08c_0571_24540/
        ('zb08c_0571_24540', 'master_z')   -> {root}/zb08/processed-ofp/zeros/zb08c_0571_24540/
        ('zb08c_0571_24540', 'master_d')   -> {root}/zb08/processed-ofp/darks/zb08c_0571_24540/
        ('zb08c_0571_24540', 'master_f_V') -> {root}/zb08/processed-ofp/flats/V/zb08c_0571_24540/
        ('zb08c_0571_24540', None)         -> same as zdf if dir exists, else None
    """
    tel   = basename[:4]
    night = basename[6:10]
    base  = root / tel / 'processed-ofp'

    match suffix:
        case None:
            d = base / 'science' / night / basename
            return d if d.is_dir() else None
        case 'zdf':
            return base / 'science' / night / basename
        case 'master_z':
            return base / 'zeros' / basename
        case 'master_d':
            return base / 'darks' / basename
        case _ if suffix.startswith('master_f_'):
            fltr = suffix[len('master_f_'):]
            return base / 'flats' / fltr / basename
        case _:
            return None


def canonical_path(basename: str, suffix: Optional[str], root: Path) -> Optional[Path]:
    """Return the canonical file path for a given basename+suffix.

    For raw files (suffix=None) returns path in /raw/{night}/.
    For processed files returns path in appropriate processed-ofp subdir.
    """
    tel   = basename[:4]
    night = basename[6:10]
    fname = f'{basename}.fits' if suffix is None else f'{basename}_{suffix}.fits'

    if suffix is None:
        return root / tel / 'raw' / night / fname

    d = processed_dir(basename, suffix, root)
    if d is None:
        return None
    return d / fname


# ---------------------------------------------------------------------------
# Calibration dependency traversal
# ---------------------------------------------------------------------------

def _file_class(suffix: Optional[str]) -> str:
    """Map suffix to file class name."""
    if suffix is None:                        return 'raw'
    if suffix == 'zdf':                       return 'zdf'
    if suffix == 'master_z':                  return 'master_zero'
    if suffix == 'master_d':                  return 'master_dark'
    if suffix.startswith('master_f_'):        return 'master_flat'
    return 'unknown'


def iter_calib_files(
    basename: str,
    suffix: Optional[str],
    root: Path,
    *,
    master_zero: bool = False,
    master_dark: bool = False,
    master_flat: bool = False,
    raw_zero: bool = False,
    raw_dark: bool = False,
    raw_flat: bool = False,
    _level: int = 0,
) -> List[Tuple[Path, int, str, str, Optional[str]]]:
    """Recursively collect calibration files for a given observation.

    Returns list of (canonical_path, level, file_class, basename, suffix) tuples.
    May contain duplicates - deduplication is caller's responsibility (key: basename+suffix).

    Calibration dependency tree:
        ZDF / raw
        ├── master_flat ──► master_dark ──► master_zero ──► raw_zero
        │                │               └── raw_dark
        │                └── raw_flat
        ├── master_dark ──► master_zero ──► raw_zero
        │               └── raw_dark
        └── master_zero ──► raw_zero

    Recursion enters a node only if the requested file types can be found inside it:
        master_zero  → enter if: raw_zero requested
        master_dark  → enter if: master_zero, raw_zero, or raw_dark requested
        master_flat  → enter if: master_dark, master_zero, raw_zero, raw_dark, or raw_flat requested
    """
    results = []
    pdir = processed_dir(basename, suffix, root)
    if pdir is None or not pdir.is_dir():
        return results

    for f in chain(pdir.glob('*.fits'), pdir.glob('*.fz')):
        fb, fs = parse_filename(f.name)
        if fb is None:  # non-OCA file (e.g. shutter map)
            continue
        if fb == basename and fs == suffix:  # skip self
            continue

        if fs is None:  # raw file (symlink in processed dir)
            cpath = canonical_path(fb, None, root)  # reconstruct /raw/{night}/ path
            if suffix == 'master_z' and raw_zero:
                results.append((cpath, _level + 1, 'raw_zero', fb, None))
            elif suffix == 'master_d' and raw_dark:
                results.append((cpath, _level + 1, 'raw_dark', fb, None))
            elif suffix and suffix.startswith('master_f_') and raw_flat:
                results.append((cpath, _level + 1, 'raw_flat', fb, None))
            elif suffix == 'zdf' and fb == basename:
                pass  # expected symlink to raw science file in science dir
        else:
            kwargs = dict(master_zero=master_zero, master_dark=master_dark, master_flat=master_flat,
                          raw_zero=raw_zero, raw_dark=raw_dark, raw_flat=raw_flat)

            if fs == 'master_z':
                need_inside = raw_zero
                if master_zero:
                    results.append((canonical_path(fb, fs, root), _level + 1, 'master_zero', fb, fs))
                if need_inside:
                    results += iter_calib_files(fb, fs, root, **kwargs, _level=_level + 1)

            elif fs == 'master_d':
                need_inside = master_zero or raw_zero or raw_dark
                if master_dark:
                    results.append((canonical_path(fb, fs, root), _level + 1, 'master_dark', fb, fs))
                if need_inside:
                    results += iter_calib_files(fb, fs, root, **kwargs, _level=_level + 1)

            elif fs.startswith('master_f_'):
                need_inside = master_dark or master_zero or raw_zero or raw_dark or raw_flat
                if master_flat:
                    results.append((canonical_path(fb, fs, root), _level + 1, 'master_flat', fb, fs))
                if need_inside:
                    results += iter_calib_files(fb, fs, root, **kwargs, _level=_level + 1)

    return results


# ---------------------------------------------------------------------------
# Observation dictionary
# ---------------------------------------------------------------------------

def observation_dict(basename: str, root: Path) -> Optional[Dict[str, Any]]:
    """Build observation dictionary for a given basename.

    'files' contains only files belonging to this observation (same basename):
    raw file, ZDF, and any master calibration files produced from this observation.
    source_filenames lists direct (non-recursive) dependencies by filename only.
    Raw files have empty source_filenames.

    See README.md for full structure documentation.
    """
    meta = parse_metadata(basename + '.fits')
    if meta is None:
        return None

    obs: Dict[str, Any] = {
        'obs_name':   basename,
        'telescope':  meta['telescope'],
        'instrument': meta['instr'],
        'night':      meta['night'],
        'files':      [],
    }

    def _stat(path: Optional[Path]) -> Dict[str, Any]:
        if path and path.exists():
            st = path.stat()
            return {
                'filesize': st.st_size,
                'mtime':    datetime.datetime.fromtimestamp(
                                st.st_mtime, tz=datetime.timezone.utc
                            ).strftime('%Y-%m-%dT%H:%M:%S'),
            }
        return {'filesize': None, 'mtime': None}

    def _source_filenames(fb: str, fs: Optional[str]) -> List[str]:
        sources = []
        pdir = processed_dir(fb, fs, root)
        if not (pdir and pdir.is_dir()):
            return sources
        for sf in chain(pdir.glob('*.fits'), pdir.glob('*.fz')):
            sfb, sfs = parse_filename(sf.name)
            if sfb == fb and sfs == fs:
                continue
            sfname = f'{sfb}.fits' if sfs is None else f'{sfb}_{sfs}.fits'
            sources.append(sfname)
        return sorted(sources)

    def _file_entry(fb: str, fs: Optional[str]) -> Dict[str, Any]:
        fname = f'{fb}.fits' if fs is None else f'{fb}_{fs}.fits'
        path  = canonical_path(fb, fs, root)
        return {
            'filename':         fname,
            'file_class':       _file_class(fs),
            'path':             str(path) if path else None,
            **_stat(path),
            'source_filenames': _source_filenames(fb, fs) if fs is not None else [],
        }

    # Raw file
    raw = canonical_path(basename, None, root)
    if raw and raw.exists():
        obs['files'].append(_file_entry(basename, None))

    # ZDF file
    zdf_d = processed_dir(basename, 'zdf', root)
    if zdf_d and zdf_d.is_dir():
        if (zdf_d / f'{basename}_zdf.fits').exists():
            obs['files'].append(_file_entry(basename, 'zdf'))

    # Master files with same basename (this obs may be a calib observation)
    tel = basename[:4]
    base_processed = root / tel / 'processed-ofp'
    candidates = [
        ('master_z', base_processed / 'zeros' / basename / f'{basename}_master_z.fits'),
        ('master_d', base_processed / 'darks' / basename / f'{basename}_master_d.fits'),
    ]
    flats_dir = base_processed / 'flats'
    if flats_dir.is_dir():
        for fltr_dir in flats_dir.iterdir():
            sf = f'master_f_{fltr_dir.name}'
            candidates.append((sf, fltr_dir / basename / f'{basename}_{sf}.fits'))

    for suffix, path in candidates:
        if path.exists():
            obs['files'].append(_file_entry(basename, suffix))

    return obs

