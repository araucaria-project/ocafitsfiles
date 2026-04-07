"""OCA FITS file system library.

Provides utilities for working with OCA FITS files:
- Root directory detection
- Filename parsing (basename, suffix, metadata)
- Path reconstruction from basename+suffix
- Calibration dependency traversal
- Observation dictionary building
- Download script generation

No external dependencies - stdlib only.
"""

# Re-export everything from the filesystem module (backward compatibility)
from ocafitsfiles._filesystem import (       # noqa: F401
    ROOT_SCHEMAS,
    detect_fits_root,
    oca_night,
    ocm_julian_date,
    ensure_oca_julian,
    night_set,
    parse_filename,
    parse_metadata,
    processed_dir,
    canonical_path,
    iter_calib_files,
    observation_dict,
)

# Download script generation
from ocafitsfiles._download import (         # noqa: F401
    DEFAULT_API_ENDPOINT,
    DEFAULT_AUTH_ENDPOINT,
    TEMPLATE_VERSION,
    fetch_user_token,
    render_download_script,
)

__all__ = [
    # filesystem
    "ROOT_SCHEMAS",
    "detect_fits_root",
    "oca_night",
    "ocm_julian_date",
    "ensure_oca_julian",
    "night_set",
    "parse_filename",
    "parse_metadata",
    "processed_dir",
    "canonical_path",
    "iter_calib_files",
    "observation_dict",
    # download
    "DEFAULT_API_ENDPOINT",
    "DEFAULT_AUTH_ENDPOINT",
    "TEMPLATE_VERSION",
    "fetch_user_token",
    "render_download_script",
]
