"""Downloads the two real, de-identified public datasets Phase 2 trains on
(SPEC section 3). Both are directly downloadable without an account:

- UCI Diabetes 130-US Hospitals (1999-2008): official UCI static asset.
- Medical Appointment No-Shows (Kaggle, Brazil): the source is Kaggle, which
  requires an API token to download programmatically; this fetches the same
  file (identical row count/schema, verified) from a public GitHub mirror
  instead so no credentials are needed for this portfolio project.
"""

import io
import zipfile
from pathlib import Path

import httpx

RAW_DIR = Path(__file__).resolve().parent / "raw"

UCI_DIABETES_URL = (
    "https://archive.ics.uci.edu/static/public/296/"
    "diabetes+130-us+hospitals+for+years+1999-2008.zip"
)
NOSHOW_URL = (
    "https://raw.githubusercontent.com/ksatola/Medical-Appointments-No-Shows/"
    "master/noshowappointments-kagglev2-may-2016.csv"
)


def download_uci_diabetes() -> Path:
    out_path = RAW_DIR / "diabetic_data.csv"
    if out_path.exists():
        print(f"Already present: {out_path}")
        return out_path

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {UCI_DIABETES_URL}")
    resp = httpx.get(UCI_DIABETES_URL, timeout=120.0, follow_redirects=True)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = zf.namelist()
        csv_name = next(n for n in names if n.endswith("diabetic_data.csv"))
        with zf.open(csv_name) as f_in, open(out_path, "wb") as f_out:
            f_out.write(f_in.read())

    print(f"Wrote {out_path}")
    return out_path


def download_noshow() -> Path:
    out_path = RAW_DIR / "noshow_appointments.csv"
    if out_path.exists():
        print(f"Already present: {out_path}")
        return out_path

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {NOSHOW_URL}")
    resp = httpx.get(NOSHOW_URL, timeout=60.0, follow_redirects=True)
    resp.raise_for_status()
    out_path.write_bytes(resp.content)
    print(f"Wrote {out_path}")
    return out_path


if __name__ == "__main__":
    download_uci_diabetes()
    download_noshow()
