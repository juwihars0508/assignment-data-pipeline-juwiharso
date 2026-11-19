"""
Data Preparation & Pipeline Project
===================================

Pipeline ETL sederhana untuk dataset otomotif (automobileEDA_dirty_training.csv).

    Extract   : membaca CSV mentah dari data/raw/
    Transform : inspeksi -> cleaning -> transformasi (Min-Max Scaling & Encoding)
    Load      : menyimpan hasil ke data/processed/automobileEDA_processed.csv

Jalankan dari root project:

    python src/pipeline.py

Dataset mentah TIDAK pernah ditimpa. Script memverifikasi hal ini dengan
membandingkan hash MD5 file mentah sebelum dan sesudah pipeline dijalankan.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Konfigurasi
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = PROJECT_ROOT / "data" / "raw" / "automobileEDA_dirty_training.csv"
PROCESSED_PATH = PROJECT_ROOT / "data" / "processed" / "automobileEDA_processed.csv"

# Kolom kategorikal bertipe teks yang perlu diperiksa & diseragamkan.
CATEGORICAL_COLS = [
    "make", "aspiration", "num-of-doors", "body-style", "drive-wheels",
    "engine-location", "engine-type", "num-of-cylinders", "fuel-system",
    "horsepower-binned",
]

# Sinonim kategori yang perlu dipetakan ke satu label baku.
# 'awd' hanya muncul 1x (huruf kapital 'AWD'); taksonomi dataset hanya mengenal
# fwd / rwd / 4wd, dan AWD = penggerak semua roda -> digabung ke '4wd'.
CATEGORY_SYNONYMS = {
    "drive-wheels": {"awd": "4wd"},
}

# Angka yang ditulis sebagai kata -> integer.
WORD_TO_NUMBER = {
    "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "eight": 8, "twelve": 12,
}

# Format tanggal yang ditemukan di kolom transaction_date.
# Setiap format punya pola separator yang unik sehingga tidak ambigu.
DATE_PATTERNS = [
    (re.compile(r"^\d{4}-\d{2}-\d{2}$"), "%Y-%m-%d"),      # 2025-01-01
    (re.compile(r"^\d{2}/\d{2}/\d{4}$"), "%d/%m/%Y"),      # 02/01/2025 (DD/MM/YYYY)
    (re.compile(r"^\d{2}-\d{2}-\d{4}$"), "%m-%d-%Y"),      # 01-03-2025 (MM-DD-YYYY)
    (re.compile(r"^\d{2}-[A-Za-z]{3}-\d{4}$"), "%d-%b-%Y"),  # 04-Jan-2025
]

HP_BIN_ORDER = ["Low", "Medium", "High"]

# Transformasi
MINMAX_COLS = ["curb-weight", "engine-size", "horsepower", "peak-rpm", "city-mpg", "highway-mpg"]
ONEHOT_COLS = ["aspiration", "body-style", "drive-wheels", "engine-location", "engine-type", "fuel-system"]
ORDINAL_COL = "horsepower-binned"
FREQ_COL = "make"

TARGET_COL = "price"


# ---------------------------------------------------------------------------
# Utilitas tampilan
# ---------------------------------------------------------------------------
def section(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def sub(title: str) -> None:
    print(f"\n--- {title} ---")


def file_md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# 1. EXTRACT
# ---------------------------------------------------------------------------
def load_data(path: Path = RAW_PATH) -> pd.DataFrame:
    """Membaca dataset CSV mentah dari folder data/raw/."""
    section("[EXTRACT] Membaca dataset mentah")
    if not path.exists():
        raise FileNotFoundError(f"Dataset mentah tidak ditemukan: {path}")
    df = pd.read_csv(path)
    print(f"File   : {path.relative_to(PROJECT_ROOT)}")
    print(f"Ukuran : {df.shape[0]} baris x {df.shape[1]} kolom")
    return df


# ---------------------------------------------------------------------------
# 2. INSPECTION
# ---------------------------------------------------------------------------
def inspect_data(df: pd.DataFrame) -> dict:
    """Memeriksa kondisi awal dataset dan menampilkan hasilnya di terminal."""
    section("[TRANSFORM 1/3] Inspeksi kondisi awal dataset")

    sub("Lima baris pertama")
    print(df.head().to_string())

    sub("Jumlah baris dan kolom")
    print(f"{df.shape[0]} baris, {df.shape[1]} kolom")

    sub("Nama kolom")
    print(", ".join(df.columns))

    sub("Tipe data setiap kolom")
    print(df.dtypes.astype(str).to_string())

    sub("Jumlah missing values per kolom (hanya yang > 0)")
    missing = df.isna().sum()
    print(missing[missing > 0].to_string() if missing.any() else "Tidak ada missing values")
    print(f"Total missing values: {int(missing.sum())}")

    sub("Duplicate records")
    n_dup = int(df.duplicated().sum())
    print(f"Jumlah baris duplikat (identik di semua kolom): {n_dup}")
    if n_dup:
        dup_idx = df.index[df.duplicated(keep=False)].tolist()
        print(f"Indeks baris yang terlibat duplikasi: {dup_idx}")

    sub("Nilai unik kolom kategorikal")
    for col in CATEGORICAL_COLS:
        counts = df[col].value_counts(dropna=False)
        print(f"\n{col} ({counts.size} nilai unik):")
        print("  " + ", ".join(f"{k!r}: {v}" for k, v in counts.items()))

    sub("Inkonsistensi penulisan kategori (beda huruf besar/kecil atau spasi)")
    inconsistent = {}
    for col in CATEGORICAL_COLS:
        values = df[col].dropna().unique()
        normalized: dict[str, list[str]] = {}
        for v in values:
            normalized.setdefault(str(v).strip().lower(), []).append(v)
        variants = {k: v for k, v in normalized.items() if len(v) > 1}
        if variants:
            inconsistent[col] = variants
            print(f"{col}: " + "; ".join(f"{vs}" for vs in variants.values()))
    if not inconsistent:
        print("Tidak ditemukan")

    sub("Format tanggal pada transaction_date")
    def date_format(value):
        if pd.isna(value):
            return "missing"
        for pattern, fmt in DATE_PATTERNS:
            if pattern.match(value):
                return fmt
        return "tidak dikenali"
    print(df["transaction_date"].map(date_format).value_counts().to_string())

    sub("Kolom numerik yang tersimpan sebagai teks")
    for col in ["num-of-doors", "num-of-cylinders"]:
        print(f"{col}: {sorted(df[col].dropna().unique().tolist())}")

    sub("Rentang nilai kolom numerik (skala belum seragam)")
    print(df.describe().T[["min", "max", "mean"]].round(3).to_string())

    return {
        "rows": df.shape[0],
        "cols": df.shape[1],
        "missing": missing,
        "duplicates": n_dup,
        "inconsistent": inconsistent,
    }


# ---------------------------------------------------------------------------
# 3. CLEANING
# ---------------------------------------------------------------------------
def _standardize_categories(df: pd.DataFrame) -> pd.DataFrame:
    """Trim spasi, seragamkan huruf, dan petakan sinonim kategori."""
    for col in CATEGORICAL_COLS:
        df[col] = df[col].str.strip().str.lower()
        if col in CATEGORY_SYNONYMS:
            df[col] = df[col].replace(CATEGORY_SYNONYMS[col])
    # horsepower-binned memakai label Title Case (Low / Medium / High)
    df["horsepower-binned"] = df["horsepower-binned"].str.title()
    return df


def _parse_date(value) -> pd.Timestamp:
    if pd.isna(value):
        return pd.NaT
    value = str(value).strip()
    for pattern, fmt in DATE_PATTERNS:
        if pattern.match(value):
            return pd.to_datetime(value, format=fmt)
    return pd.NaT


def _impute_dates(dates: pd.Series) -> pd.Series:
    """
    transaction_date tercatat harian dan berurutan sesuai urutan baris
    (2025-01-01, 2025-01-02, ...). Tanggal kosong diisi dengan interpolasi
    linear dari baris sebelum & sesudahnya.
    """
    epoch = pd.Timestamp("1970-01-01")
    as_days = (dates - epoch).dt.total_seconds() / 86400  # NaT -> NaN
    filled = as_days.interpolate(method="linear", limit_area="inside").round()
    return epoch + pd.to_timedelta(filled, unit="D")


def _hp_bin_edges(df: pd.DataFrame) -> pd.DataFrame:
    """Rentang horsepower untuk tiap kategori horsepower-binned (dipelajari dari data)."""
    return df.groupby("horsepower-binned")["horsepower"].agg(["min", "max"]).reindex(HP_BIN_ORDER)


def _assign_hp_bin(hp: float, edges: pd.DataFrame) -> str | float:
    if pd.isna(hp):
        return np.nan
    if hp <= edges.loc["Low", "max"]:
        return "Low"
    if hp <= edges.loc["Medium", "max"]:
        return "Medium"
    return "High"


def _fill_make_from_specs(df: pd.DataFrame) -> pd.Series:
    """Cari merek dari baris lain yang spesifikasi teknisnya identik; jika tidak ada -> 'unknown'."""
    spec_cols = ["wheel-base", "length", "width", "height", "curb-weight",
                 "engine-type", "num-of-cylinders", "engine-size", "fuel-system"]
    make = df["make"].copy()
    for idx in make.index[make.isna()]:
        same_spec = (df[spec_cols] == df.loc[idx, spec_cols]).all(axis=1) & df["make"].notna()
        candidates = df.loc[same_spec, "make"]
        make.loc[idx] = candidates.mode().iat[0] if not candidates.empty else "unknown"
    return make


def clean_data(df_raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Membersihkan dataset berdasarkan temuan pada tahap inspeksi."""
    section("[TRANSFORM 2/3] Data cleaning")
    df = df_raw.copy()  # dataset mentah di memori tidak diubah
    log: list[str] = []

    rows_before = len(df)
    missing_before = df.isna().sum()

    # 3.1 Menyeragamkan penulisan kategori & menghapus spasi berlebih -----------
    before = df[CATEGORICAL_COLS].copy()
    df = _standardize_categories(df)
    changed = (before.fillna("<NA>") != df[CATEGORICAL_COLS].fillna("<NA>")).sum()
    for col, n in changed[changed > 0].items():
        log.append(f"Standarisasi kategori '{col}': {n} nilai diubah (trim spasi / huruf kecil / sinonim)")

    # 3.2 Menghapus duplicate records -----------------------------------------
    # Dilakukan SETELAH standarisasi teks agar duplikat yang hanya beda
    # penulisan (mis. 'BMW' vs 'bmw') juga terdeteksi.
    n_dup = int(df.duplicated().sum())
    df = df.drop_duplicates(keep="first")
    log.append(f"Hapus duplikat: {n_dup} baris identik dihapus (keep='first')")

    # 3.3 Memperbaiki tipe data ---------------------------------------------
    df["transaction_date"] = df["transaction_date"].map(_parse_date).astype("datetime64[ns]")
    log.append("transaction_date: string 4 format berbeda -> datetime64 (format ISO YYYY-MM-DD)")
    for col in ["num-of-doors", "num-of-cylinders"]:
        df[col] = df[col].map(WORD_TO_NUMBER).astype("Int64")
        log.append(f"{col}: teks angka ('four', 'six', ...) -> integer")

    # 3.4 Menangani missing values ------------------------------------------
    # a) price adalah variabel target -> baris tanpa harga DIHAPUS
    n_no_price = int(df[TARGET_COL].isna().sum())
    df = df.dropna(subset=[TARGET_COL])
    log.append(f"price: {n_no_price} baris tanpa harga dihapus (target tidak diimputasi)")

    # b) transaction_date -> interpolasi dari tanggal baris sebelum/sesudah
    n = int(df["transaction_date"].isna().sum())
    df["transaction_date"] = _impute_dates(df["transaction_date"])
    log.append(f"transaction_date: {n} tanggal kosong diisi dengan interpolasi urutan harian")

    # c) make -> lookup spesifikasi identik, fallback 'unknown'
    n = int(df["make"].isna().sum())
    df["make"] = _fill_make_from_specs(df)
    log.append(f"make: {n} nilai kosong diisi (lookup spesifikasi identik, fallback 'unknown')")

    # d) num-of-doors -> modus per body-style
    n = int(df["num-of-doors"].isna().sum())
    door_mode = df.groupby("body-style")["num-of-doors"].agg(lambda s: s.mode().iat[0])
    df["num-of-doors"] = df["num-of-doors"].fillna(df["body-style"].map(door_mode)).astype("Int64")
    log.append(f"num-of-doors: {n} nilai kosong diisi modus per body-style")

    # e) horsepower -> median per horsepower-binned
    n = int(df["horsepower"].isna().sum())
    hp_median = df.groupby("horsepower-binned")["horsepower"].transform("median")
    df["horsepower"] = df["horsepower"].fillna(hp_median)
    log.append(f"horsepower: {n} nilai kosong diisi median per horsepower-binned")

    # f) horsepower-binned -> diturunkan dari horsepower dengan rentang bin dari data
    n = int(df["horsepower-binned"].isna().sum())
    edges = _hp_bin_edges(df)
    mask = df["horsepower-binned"].isna()
    df.loc[mask, "horsepower-binned"] = df.loc[mask, "horsepower"].map(lambda v: _assign_hp_bin(v, edges))
    log.append(f"horsepower-binned: {n} nilai kosong diturunkan dari horsepower "
               f"(Low<={edges.loc['Low', 'max']:.0f}, Medium<={edges.loc['Medium', 'max']:.0f}, High>)")

    # g) stroke -> median keseluruhan
    n = int(df["stroke"].isna().sum())
    stroke_median = df["stroke"].median()
    df["stroke"] = df["stroke"].fillna(stroke_median)
    log.append(f"stroke: {n} nilai kosong (mesin rotary Mazda) diisi median = {stroke_median}")

    # 3.5 Pemeriksaan nilai tidak wajar ---------------------------------------
    sub("Pemeriksaan nilai tidak wajar")
    numeric = df.select_dtypes("number")
    negatives = (numeric < 0).sum()
    negatives = negatives.drop("symboling", errors="ignore")  # symboling memang -3..3
    print(f"Nilai negatif pada kolom non-symboling : {int(negatives.sum())}")
    print(f"symboling di luar rentang -3..3        : {int((~df['symboling'].between(-3, 3)).sum())}")
    print(f"Baris dengan diesel + gas != 1         : {int((df['diesel'] + df['gas'] != 1).sum())}")
    l100 = 235.215 / df["city-mpg"]
    print(f"city-L/100km tidak sesuai 235/city-mpg  : {int((~np.isclose(l100, df['city-L/100km'], rtol=1e-2)).sum())}")
    print("Outlier (metode IQR 1.5x) per kolom kontinu:")
    # kolom diskrit/biner tidak relevan untuk deteksi outlier IQR
    numeric = numeric.drop(columns=["symboling", "num-of-doors", "num-of-cylinders", "diesel", "gas"])
    q1, q3 = numeric.quantile(0.25), numeric.quantile(0.75)
    iqr = q3 - q1
    outliers = ((numeric < q1 - 1.5 * iqr) | (numeric > q3 + 1.5 * iqr)).sum()
    outliers = outliers[outliers > 0]
    print("  " + ", ".join(f"{c}: {v}" for c, v in outliers.items()))
    print("-> Outlier dipertahankan: nilainya masuk akal secara domain (mobil mewah/berperforma"
          " tinggi, mesin diesel ber-compression-ratio tinggi), bukan kesalahan input.")
    log.append("Nilai tidak wajar: tidak ditemukan nilai mustahil; outlier IQR dipertahankan")

    df = df.reset_index(drop=True)

    # Ringkasan ---------------------------------------------------------------
    missing_after = df.isna().sum()
    sub("Langkah cleaning yang dijalankan")
    for i, item in enumerate(log, 1):
        print(f"{i:>2}. {item}")

    sub("Ringkasan sebelum vs sesudah cleaning")
    print(f"Jumlah baris            : {rows_before} -> {len(df)} (berkurang {rows_before - len(df)})")
    print(f"Baris duplikat dihapus  : {n_dup}")
    print(f"Baris tanpa price dihapus: {n_no_price}")
    print(f"Total missing values    : {int(missing_before.sum())} -> {int(missing_after.sum())}")
    mv = pd.DataFrame({"sebelum": missing_before, "sesudah": missing_after}).fillna(0).astype(int)
    print(mv[mv["sebelum"] > 0].to_string())

    sub("Kolom yang mengalami perubahan")
    changed_cols = _changed_columns(df_raw, df)
    print(changed_cols.to_string(index=False))

    stats = {
        "rows_before": rows_before,
        "rows_after": len(df),
        "duplicates_removed": n_dup,
        "missing_before": int(missing_before.sum()),
        "missing_after": int(missing_after.sum()),
    }
    return df, stats


def _changed_columns(df_raw: pd.DataFrame, df_clean: pd.DataFrame) -> pd.DataFrame:
    """
    Bandingkan nilai per kolom antara data mentah (setelah membuang baris yang
    dihapus) dan data bersih. Baris dicocokkan lewat urutan setelah drop.
    """
    raw = df_raw.drop_duplicates(keep="first")
    raw = raw[raw[TARGET_COL].notna()].reset_index(drop=True)
    raw = raw.copy()
    rows = []
    for col in df_clean.columns:
        a = raw[col].astype(str)
        b = df_clean[col].astype(str)
        if col == "transaction_date":
            b = df_clean[col].dt.strftime("%Y-%m-%d")
        n = int((a != b).sum())
        dtype_change = str(df_raw[col].dtype) != str(df_clean[col].dtype)
        if n or dtype_change:
            rows.append({
                "kolom": col,
                "sel_berubah": n,
                "dtype_awal": str(df_raw[col].dtype),
                "dtype_akhir": str(df_clean[col].dtype),
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 4. TRANSFORMATION
# ---------------------------------------------------------------------------
def transform_data(df_clean: pd.DataFrame) -> pd.DataFrame:
    """Normalisasi Min-Max dan encoding kolom kategorikal."""
    section("[TRANSFORM 3/3] Data transformation")
    df = df_clean.copy()

    # 4.1 Min-Max Scaling ----------------------------------------------------
    # Kolom asli dipertahankan, hasil scaling disimpan di kolom baru <kolom>_minmax
    # supaya nilai sebelum & sesudah dapat dibandingkan langsung.
    sub("Min-Max Scaling: x' = (x - min) / (max - min)")
    for col in MINMAX_COLS:
        col_min, col_max = df[col].min(), df[col].max()
        df[f"{col}_minmax"] = (df[col] - col_min) / (col_max - col_min)
        print(f"{col:<12} min={col_min:<8g} max={col_max:<8g} -> {col}_minmax [0, 1]")
    print("\nContoh perbandingan (5 baris pertama):")
    compare = df[[c for col in MINMAX_COLS for c in (col, f"{col}_minmax")]].head()
    print(compare.round(4).to_string())

    # 4.2 Ordinal encoding: horsepower-binned --------------------------------
    sub("Ordinal Encoding: horsepower-binned (Low=0, Medium=1, High=2)")
    mapping = {label: i for i, label in enumerate(HP_BIN_ORDER)}
    df["horsepower-binned_ordinal"] = df[ORDINAL_COL].map(mapping).astype(int)
    sample = df[[ORDINAL_COL, "horsepower-binned_ordinal"]].drop_duplicates().sort_values("horsepower-binned_ordinal")
    print(sample.to_string(index=False))

    # 4.3 Frequency encoding: make -----------------------------------------
    sub("Frequency Encoding: make -> make_freq (proporsi kemunculan merek)")
    freq = df[FREQ_COL].value_counts(normalize=True)
    df["make_freq"] = df[FREQ_COL].map(freq)
    print(df[[FREQ_COL, "make_freq"]].drop_duplicates().sort_values("make_freq", ascending=False)
          .head(8).round(4).to_string(index=False))

    # 4.4 One-hot encoding kolom nominal --------------------------------------
    sub("One-Hot Encoding kolom nominal")
    before_onehot = df[ONEHOT_COLS].head(3).copy()
    df = pd.get_dummies(df, columns=ONEHOT_COLS, prefix=ONEHOT_COLS, dtype=int)
    for col in ONEHOT_COLS:
        new_cols = [c for c in df.columns if c.startswith(f"{col}_")]
        print(f"{col:<16} -> {len(new_cols)} kolom: {', '.join(new_cols)}")
    print("\nContoh body-style sebelum vs sesudah (3 baris pertama):")
    body_cols = [c for c in df.columns if c.startswith("body-style_")]
    print(pd.concat([before_onehot[["body-style"]], df[body_cols].head(3)], axis=1).to_string())

    # Kolom teks horsepower-binned sudah terwakili oleh versi ordinal
    df = df.drop(columns=[ORDINAL_COL])

    # Susun ulang: identitas -> numerik asli -> hasil transformasi
    front = ["transaction_date", "make", "make_freq"]
    df = df[front + [c for c in df.columns if c not in front]]

    sub("Ringkasan hasil transformasi")
    print(f"Ukuran akhir : {df.shape[0]} baris x {df.shape[1]} kolom")
    text_cols = df.select_dtypes(include=["object", "string"]).columns.tolist()
    print(f"Kolom teks tersisa : {text_cols} (dipertahankan sebagai label; versi numerik: make_freq)")
    print(f"Missing values     : {int(df.isna().sum().sum())}")
    return df


# ---------------------------------------------------------------------------
# 5. LOAD
# ---------------------------------------------------------------------------
def save_data(df: pd.DataFrame, path: Path = PROCESSED_PATH) -> Path:
    """Menyimpan processed dataset ke folder data/processed/."""
    section("[LOAD] Menyimpan processed dataset")
    path.parent.mkdir(parents=True, exist_ok=True)
    # lineterminator eksplisit agar file identik di Windows/macOS/Linux
    df.to_csv(path, index=False, date_format="%Y-%m-%d", lineterminator="\n")
    print(f"Tersimpan : {path.relative_to(PROJECT_ROOT)}")
    print(f"Ukuran    : {df.shape[0]} baris x {df.shape[1]} kolom")
    return path


# ---------------------------------------------------------------------------
# PIPELINE
# ---------------------------------------------------------------------------
def run_pipeline() -> pd.DataFrame:
    """Menjalankan seluruh tahapan ETL dari awal sampai akhir dalam satu eksekusi."""
    raw_hash_before = file_md5(RAW_PATH)

    df_raw = load_data(RAW_PATH)                  # Extract
    inspect_data(df_raw)                          # Transform - inspeksi
    df_clean, stats = clean_data(df_raw)          # Transform - cleaning
    df_processed = transform_data(df_clean)       # Transform - transformasi
    save_data(df_processed, PROCESSED_PATH)       # Load

    raw_hash_after = file_md5(RAW_PATH)
    section("SELESAI")
    print(f"Baris  : raw {stats['rows_before']} -> processed {len(df_processed)}")
    print(f"Kolom  : raw {df_raw.shape[1]} -> processed {df_processed.shape[1]}")
    print(f"Missing: {stats['missing_before']} -> {int(df_processed.isna().sum().sum())}")
    status = "TIDAK BERUBAH" if raw_hash_before == raw_hash_after else "BERUBAH (!)"
    print(f"Dataset mentah (MD5 {raw_hash_after}) : {status}")
    return df_processed


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 40)
    run_pipeline()
