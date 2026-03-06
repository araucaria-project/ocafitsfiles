# ocafitsfiles

Python library for working with OCA FITS file system structure.

## Installation

```bash
pip install ocafitsfiles
# or from git:
pip install git+https://github.com/YOUR_ORG/ocafitsfiles.git
```

## File System Schema

OCA FITS files are stored under a root directory (autodetected or specified). Known schemas:

| Schema | Root path |
|--------|-----------|
| CAMK   | `/work/vela/oca/fits` |
| OCM    | `/data/fits` |
| Mik    | `/Users/Shared/oca_data/fits` |

Directory structure under root:

```
{root}/
  {telescope}/                          e.g. zb08
    raw/
      {night}/                          4-digit OCA Julian night, e.g. 1075
        {basename}.fits                 e.g. zb08c_1075_66218.fits
    processed-ofp/
      science/
        {night}/
          {basename}/
            {basename}_zdf.fits         calibrated science file
            {basename}_master_z.fits    symlink to used master zero
            {basename}_master_d.fits    symlink to used master dark
            {basename}_master_f_{F}.fits symlink to used master flat
      zeros/
        {basename}/
          {basename}_master_z.fits      master zero file
          {basename}_????.fits          symlinks to raw zero files used
      darks/
        {basename}/
          {basename}_master_d.fits
          {basename}_master_z.fits      symlink to used master zero
          {basename}_????.fits          symlinks to raw dark files used
      flats/
        {filter}/                       e.g. V, B, r, g, i, z, Ic
          {basename}/
            {basename}_master_f_{F}.fits
            {basename}_master_d.fits    symlink
            {basename}_master_z.fits    symlink
            {basename}_????.fits        symlinks to raw flat files used
```

**Note on symlinks**: Processed directories contain symlinks to files in other directories.
Always use `canonical_path()` to get authoritative paths — never follow symlinks for path construction.

### OCA Julian Night

A 4-digit integer counting days since 2023-02-23. Use `ensure_oca_julian()` to convert from ISO date.

### Filename Convention

```
{telescope}{instr}_{night}_{count}[_{suffix}].fits

Examples:
  zb08c_1075_66218.fits           raw science file
  zb08c_1075_66218_zdf.fits       calibrated (zero-dark-flat) science file
  zb08c_1075_52446_master_z.fits  master zero
  zb08c_1064_85720_master_d.fits  master dark
  zb08c_1075_49661_master_f_V.fits master flat, filter V
```

`basename` = `{telescope}{instr}_{night}_{count}` (e.g. `zb08c_1075_66218`), uniquely identifies an observation.
`basename + suffix` uniquely identifies a file.

## Calibration Dependency Tree

```
ZDF / raw science
├── master_flat ──► master_dark ──► master_zero ──► raw_zero
│                │               └── raw_dark
│                └── raw_flat
├── master_dark ──► master_zero ──► raw_zero
│               └── raw_dark
└── master_zero ──► raw_zero
```

## API Reference

### Root detection

```python
schema, root = detect_fits_root()
# ('CAMK', PosixPath('/work/vela/oca/fits'))
```

### Filename parsing

```python
parse_filename('zb08c_1075_66218_zdf.fits')
# → ('zb08c_1075_66218', 'zdf')

parse_filename('/full/path/zb08c_1075_49661_master_f_V.fits')
# → ('zb08c_1075_49661', 'master_f_V')

parse_metadata('zb08c_1075_66218.fits')
# → {'telescope': 'zb08', 'instr': 'c', 'night': '1075', 'count': '66218', 'suffix': None}
```

### Path construction

```python
canonical_path('zb08c_1075_66218', 'zdf', root)
# → PosixPath('/work/vela/oca/fits/zb08/processed-ofp/science/1075/zb08c_1075_66218/zb08c_1075_66218_zdf.fits')

canonical_path('zb08c_1075_66218', None, root)
# → PosixPath('/work/vela/oca/fits/zb08/raw/1075/zb08c_1075_66218.fits')

processed_dir('zb08c_1075_49661', 'master_f_V', root)
# → PosixPath('/work/vela/oca/fits/zb08/processed-ofp/flats/V/zb08c_1075_49661')
```

### Calibration traversal

```python
# Returns list of (path, level, file_class, basename, suffix)
files = iter_calib_files(
    'zb08c_1075_66218', 'zdf', root,
    master_zero=True, master_dark=True, master_flat=True,
    raw_zero=False, raw_dark=False, raw_flat=False,
)
# Note: may contain duplicates (same master used by flat and dark).
# Deduplication is caller's responsibility (key: basename+suffix).
```

`file_class` values: `raw`, `zdf`, `master_zero`, `master_dark`, `master_flat`, `unknown`

### Observation dictionary

```python
obs = observation_dict('zb08c_1075_66218', root)
```

Returns:
```json
{
  "obs_name": "zb08c_1075_66218",
  "telescope": "zb08",
  "instrument": "c",
  "night": "1075",
  "files": [
    {
      "filename": "zb08c_1075_66218.fits",
      "file_class": "raw",
      "path": "/work/vela/oca/fits/zb08/raw/1075/zb08c_1075_66218.fits",
      "filesize": 8398080,
      "mtime": "2026-02-04T03:54:19",
      "source_filenames": []
    },
    {
      "filename": "zb08c_1075_66218_zdf.fits",
      "file_class": "zdf",
      "path": "...processed-ofp/science/1075/zb08c_1075_66218/zb08c_1075_66218_zdf.fits",
      "filesize": 16790400,
      "mtime": "2026-02-04T19:02:34",
      "source_filenames": [
        "zb08c_1075_66218.fits",
        "zb08c_1064_85720_master_d.fits",
        "zb08c_1075_49661_master_f_V.fits",
        "zb08c_1075_52446_master_z.fits"
      ]
    }
  ]
}
```

`files` contains only files belonging to this observation (same basename).
For calibration observations (master_z, master_d, master_f_*), `files` will also include the master file.
`source_filenames` lists direct (non-recursive) dependencies by filename only.
Raw files have empty `source_filenames`.

## Download Script Generation

Library provides reusable logic to render a self-sufficient POSIX `sh` script
for list/check/download workflows. Concrete CLIs or web apps should call this
API and handle their own input/output.

### Public symbols

- `render_download_script(...)`
- `TEMPLATE_VERSION`
- `DEFAULT_API_ENDPOINT` (defaults to `https://api.ocadb.space/api/v1/observations`)

### Render API

```python
from ocafitsfiles import render_download_script

script = render_download_script(
    data_block="""\
zb08c_0908_71833.fits |science|54.0
# commented rows are ignored by -l/-c/-d/-D
""",
    api_token="<bearer token>",
    # optional:
    # api_endpoint="https://api.ocadb.space/api/v1/observations",
    # expires_in=604800,  # 7 days (S3-compatible max)
    # dl_timeout=300,
)
```

Parameters:

- `data_block`: embedded table text; first whitespace-separated column is the key/filename
- `api_token`: bearer token embedded into generated script
- `api_endpoint`: base API URL; script calls `/by-filename/{key}/plainurl?expires_in=...`
- `expires_in`: presigned URL validity in seconds (default `604800`)
- `dl_timeout`: curl/wget transfer timeout in seconds (default `300`)

### Generated script behavior

The generated script supports:

- `-l` list active keys (first column)
- `-L` print full embedded table
- `-c` check object availability
- `-d [DIR]` download missing files to `DIR`
- `-D [DIR]` download with overwrite

Implementation notes:

- Presigned URL API response may be returned as a quoted string; template strips surrounding quotes.
- Check mode uses a minimal range GET (`bytes=0-0`) instead of HEAD for better compatibility with some S3-compatible backends.
- Script prints a final summary (`ok/fail/skip`) and exits non-zero if failures occurred in check/download modes.

### Quick local template testing

Without a separate CLI project, you can iterate locally via module runner:

```bash
cat my_data_block.txt | python -m ocafitsfiles.download_script \
  --token '<TOKEN>' \
  --endpoint 'https://api.ocadb.space/api/v1/observations' \
  --expires-in 604800 \
  --dl-timeout 300 > out.sh

sh out.sh -l
sh out.sh -c
```

This runner is intended for development/testing convenience inside this library repo.
