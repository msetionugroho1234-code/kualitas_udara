"""
cleaning.py
Pembersihan data kualitas udara + perhitungan ISPU (Indeks Standar Pencemar Udara).

Jalankan sendiri:   python cleaning.py
Hasil disimpan ke folder data/:
  - air_quality_clean.csv        data per jam yang sudah bersih
  - ispu_harian.csv              nilai ISPU & kategori kualitas udara per hari
  - laporan_pembersihan.json     ringkasan sebelum/sesudah pembersihan
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
RAW_FILE = DATA_DIR / "air_quality_train.csv"
CLEAN_FILE = DATA_DIR / "air_quality_clean.csv"
ISPU_FILE = DATA_DIR / "ispu_harian.csv"
REPORT_FILE = DATA_DIR / "laporan_pembersihan.json"

# ----------------------------------------------------------------------------
# Pengaturan
# ----------------------------------------------------------------------------
KOLOM_DIHAPUS = [
    "Eth-Benzene (ug/m3)",
    "MP-Xylene (ug/m3)",
    "Xylene (ug/m3)",
    "WD (degree)",
    "SR (W/mt2)",
    "RF (mm)",
]

POLUTAN = [
    "PM2.5 (ug/m3)", "PM10 (ug/m3)", "NO (ug/m3)", "NO2 (ug/m3)", "NOx (ppb)",
    "NH3 (ug/m3)", "SO2 (ug/m3)", "CO (mg/m3)", "Ozone (ug/m3)",
    "Benzene (ug/m3)", "Toluene (ug/m3)",
]
CUACA = ["RH (%)", "WS (m/s)", "AT (degree C)"]
KOLOM_WAKTU = ["From Date", "To Date"]

BATAS_INTERPOLASI_JAM = 6   # celah kosong <= 6 jam diisi dengan interpolasi waktu
FAKTOR_IQR = 3.0            # outlier: nilai > Q3 + 3 x IQR dibatasi (capping)

# ----------------------------------------------------------------------------
# ISPU (Permen LHK No. P.14/MENLHK/SETJEN/KUM.1/7/2020)
# Batas atas tiap kategori per parameter, dalam ug/m3 (CO dikonversi dari mg/m3).
# Urutan kategori: Baik, Sedang, Tidak Sehat, Sangat Tidak Sehat, Berbahaya
# ----------------------------------------------------------------------------
BATAS_INDEKS = [0, 50, 100, 200, 300, 500]
PARAMETER_ISPU = {
    # kode: (kolom, faktor ke ug/m3, rata-rata yang dipakai, batas konsentrasi)
    "PM2.5": ("PM2.5 (ug/m3)", 1, "24 jam", [15.5, 55.4, 150.4, 250.4, 500]),
    "PM10": ("PM10 (ug/m3)", 1, "24 jam", [50, 150, 350, 420, 500]),
    "SO2": ("SO2 (ug/m3)", 1, "24 jam", [52, 180, 400, 800, 1200]),
    "NO2": ("NO2 (ug/m3)", 1, "24 jam", [80, 200, 1130, 2260, 3000]),
    "CO": ("CO (mg/m3)", 1000, "8 jam", [4000, 8000, 15000, 30000, 45000]),
    "O3": ("Ozone (ug/m3)", 1, "8 jam", [120, 235, 400, 800, 1000]),
}
KATEGORI = [
    {"nama": "Baik", "batas": 50, "warna": "#2E9E5B",
     "saran": "Udara bersih. Aktivitas di luar ruangan aman untuk semua orang."},
    {"nama": "Sedang", "batas": 100, "warna": "#2F6FD0",
     "saran": "Dapat diterima bagi kebanyakan orang. Kelompok yang sangat sensitif sebaiknya mengurangi aktivitas berat di luar."},
    {"nama": "Tidak Sehat", "batas": 200, "warna": "#E3B019",
     "saran": "Mulai merugikan kesehatan. Batasi aktivitas berat di luar ruangan, terutama anak-anak, lansia, dan penderita gangguan pernapasan."},
    {"nama": "Sangat Tidak Sehat", "batas": 300, "warna": "#D43B3B",
     "saran": "Berisiko bagi banyak orang. Hindari aktivitas di luar ruangan dan gunakan masker bila harus keluar."},
    {"nama": "Berbahaya", "batas": 500, "warna": "#1B1B1F",
     "saran": "Berbahaya bagi seluruh populasi. Tetap di dalam ruangan dan cari bantuan medis jika muncul gejala."},
]
NAMA_KATEGORI = [k["nama"] for k in KATEGORI]


def kategori_dari_ispu(nilai):
    """Mengubah nilai ISPU menjadi indeks kategori (0-4)."""
    for i, k in enumerate(KATEGORI):
        if nilai <= k["batas"]:
            return i
    return len(KATEGORI) - 1


# ----------------------------------------------------------------------------
# Fungsi bantu
# ----------------------------------------------------------------------------
def _f(x, nd=4):
    return None if pd.isna(x) else round(float(x), nd)


def statistik(df, kolom):
    hasil = {}
    for c in kolom:
        s = df[c]
        hasil[c] = {
            "kosong": int(s.isna().sum()),
            "rata2": _f(s.mean()),
            "std": _f(s.std()),
            "min": _f(s.min()),
            "median": _f(s.median()),
            "maks": _f(s.max()),
        }
    return hasil


def muat_data_mentah(path=RAW_FILE):
    df = pd.read_csv(path, parse_dates=KOLOM_WAKTU)
    return df.sort_values("From Date").reset_index(drop=True)


# ----------------------------------------------------------------------------
# Pembersihan
# ----------------------------------------------------------------------------
def bersihkan(mentah):
    """Mengembalikan (data_bersih, laporan)."""
    lap = {
        "baris_awal": int(len(mentah)),
        "kolom_awal": int(mentah.shape[1]),
        "kolom_dihapus": [
            {"kolom": c, "kosong_persen": round(mentah[c].isna().mean() * 100, 1)}
            for c in KOLOM_DIHAPUS if c in mentah.columns
        ],
    }

    # 1) Hapus kolom yang tidak dipakai
    df = mentah.drop(columns=KOLOM_DIHAPUS, errors="ignore").copy()
    kolom_angka = [c for c in df.columns if c not in KOLOM_WAKTU]
    lap["kolom_angka"] = kolom_angka
    lap["sel_kosong_sebelum"] = int(df[kolom_angka].isna().sum().sum())
    lap["statistik_sebelum"] = statistik(df, kolom_angka)

    # 2) Hapus data ganda (baris sama persis / jam yang sama)
    n0 = len(df)
    df = df.drop_duplicates().drop_duplicates(subset="From Date", keep="first")
    lap["duplikat_dihapus"] = int(n0 - len(df))

    # 3) Nilai negatif tidak mungkin secara fisik -> noise sensor, dijadikan 0
    negatif = {}
    for c in POLUTAN + ["WS (m/s)"]:
        m = df[c] < 0
        negatif[c] = int(m.sum())
        df.loc[m, c] = 0.0
    lap["negatif_diperbaiki"] = {k: v for k, v in negatif.items() if v}

    # 4) Kelembapan tidak boleh > 100 %
    m = df["RH (%)"] > 100
    lap["rh_dibatasi"] = int(m.sum())
    df.loc[m, "RH (%)"] = 100.0

    # 5) Outlier ekstrem pada polutan dibatasi (capping) dengan aturan IQR
    outlier = {}
    for c in POLUTAN:
        q1, q3 = df[c].quantile([0.25, 0.75])
        iqr = q3 - q1
        if iqr <= 0:
            continue
        batas = q3 + FAKTOR_IQR * iqr
        m = df[c] > batas
        if m.any():
            outlier[c] = int(m.sum())
            df.loc[m, c] = batas
    lap["outlier_dibatasi"] = outlier
    lap["faktor_iqr"] = FAKTOR_IQR

    # 6) Nilai kosong: interpolasi waktu (celah pendek), sisanya median per jam
    idx = df.set_index("From Date")
    kosong0 = idx[kolom_angka].isna().sum()
    for c in kolom_angka:
        idx[c] = idx[c].interpolate(method="time", limit=BATAS_INTERPOLASI_JAM,
                                    limit_area="inside")
    kosong1 = idx[kolom_angka].isna().sum()
    jam = idx.index.hour
    for c in kolom_angka:
        median_jam = idx[c].groupby(jam).transform("median")
        idx[c] = idx[c].fillna(median_jam).fillna(idx[c].median())
    kosong2 = idx[kolom_angka].isna().sum()
    lap["isi_interpolasi"] = int((kosong0 - kosong1).sum())
    lap["isi_median"] = int((kosong1 - kosong2).sum())
    lap["batas_interpolasi_jam"] = BATAS_INTERPOLASI_JAM

    bersih = idx.reset_index()
    bersih = bersih[KOLOM_WAKTU + kolom_angka]
    bersih[kolom_angka] = bersih[kolom_angka].round(4)

    lap["baris_akhir"] = int(len(bersih))
    lap["kolom_akhir"] = int(bersih.shape[1])
    lap["sel_kosong_sesudah"] = int(bersih[kolom_angka].isna().sum().sum())
    lap["statistik_sesudah"] = statistik(bersih, kolom_angka)
    return bersih, lap


# ----------------------------------------------------------------------------
# ISPU harian
# ----------------------------------------------------------------------------
def hitung_ispu_harian(bersih, min_jam=12):
    d = bersih.set_index("From Date")
    hari = d.index.normalize()
    jumlah_jam = d.groupby(hari).size()

    nilai = pd.DataFrame(index=jumlah_jam.index)
    for kode, (kolom, faktor, jendela, _) in PARAMETER_ISPU.items():
        if jendela == "24 jam":
            s = d[kolom].groupby(hari).mean()
        else:  # 8 jam: rata-rata bergerak 8 jam, ambil yang tertinggi per hari
            s = d[kolom].rolling("8h", min_periods=6).mean().groupby(hari).max()
        nilai[kode] = s * faktor

    sub = pd.DataFrame(index=nilai.index)
    for kode, (_, _, _, bp) in PARAMETER_ISPU.items():
        sub[kode] = np.interp(nilai[kode].fillna(0), [0] + bp, BATAS_INDEKS)

    hasil = pd.DataFrame(index=nilai.index)
    for kode, (_, faktor, _, _) in PARAMETER_ISPU.items():
        hasil[f"nilai_{kode}"] = (nilai[kode] / faktor).round(3)  # satuan asli
    for kode in PARAMETER_ISPU:
        hasil[f"ispu_{kode}"] = sub[kode].round(1)
    hasil["ISPU"] = sub.max(axis=1).round().astype(int)
    hasil["Polutan Dominan"] = sub.idxmax(axis=1)
    hasil["Kategori"] = [NAMA_KATEGORI[kategori_dari_ispu(v)] for v in hasil["ISPU"]]
    hasil["Jumlah Jam Data"] = jumlah_jam
    hasil = hasil[hasil["Jumlah Jam Data"] >= min_jam]
    hasil.index.name = "Tanggal"
    return hasil


# ----------------------------------------------------------------------------
# Pipeline
# ----------------------------------------------------------------------------
def jalankan_pipeline(simpan=True):
    mentah = muat_data_mentah()
    bersih, lap = bersihkan(mentah)
    ispu = hitung_ispu_harian(bersih)
    lap["hari_ispu"] = int(len(ispu))
    if simpan:
        DATA_DIR.mkdir(exist_ok=True)
        bersih.to_csv(CLEAN_FILE, index=False)
        ispu.to_csv(ISPU_FILE)
        REPORT_FILE.write_text(json.dumps(lap, indent=2, ensure_ascii=False), encoding="utf-8")
    return mentah, bersih, ispu, lap


if __name__ == "__main__":
    _, bersih, ispu, lap = jalankan_pipeline()
    print("=== RINGKASAN PEMBERSIHAN ===")
    print(f"Baris            : {lap['baris_awal']} -> {lap['baris_akhir']}")
    print(f"Kolom            : {lap['kolom_awal']} -> {lap['kolom_akhir']}")
    print(f"Kolom dihapus    : {', '.join(k['kolom'] for k in lap['kolom_dihapus'])}")
    print(f"Duplikat dihapus : {lap['duplikat_dihapus']}")
    print(f"Negatif -> 0     : {sum(lap['negatif_diperbaiki'].values())}")
    print(f"Outlier dibatasi : {sum(lap['outlier_dibatasi'].values())}")
    print(f"Sel kosong       : {lap['sel_kosong_sebelum']} -> {lap['sel_kosong_sesudah']}")
    print(f"  diisi interpolasi: {lap['isi_interpolasi']}, diisi median per jam: {lap['isi_median']}")
    print("\n=== DISTRIBUSI KATEGORI KUALITAS UDARA (harian) ===")
    print(ispu["Kategori"].value_counts().reindex(NAMA_KATEGORI).fillna(0).astype(int).to_string())
    print(f"\nFile tersimpan di: {DATA_DIR}")
