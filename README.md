# Dashboard Kualitas Udara

Pembersihan data + website (Flask) untuk `air_quality_train.csv`.

## Cara menjalankan di VS Code
1. Buka folder ini di VS Code, lalu buka Terminal (Ctrl + `).
2. Buat virtual environment dan pasang paket:
   ```
   python -m venv .venv
   .venv\Scripts\activate        # Windows  (macOS/Linux: source .venv/bin/activate)
   pip install -r requirements.txt
   ```
3. Pastikan file data ada di `data/air_quality_train.csv`.
4. (Opsional) Jalankan pembersihan saja: `python cleaning.py`
5. Jalankan website: `python app.py`, lalu buka http://127.0.0.1:5000

Koneksi internet dibutuhkan di browser untuk memuat Chart.js dan font dari CDN.

## Isi folder
| File | Fungsi |
|---|---|
| `cleaning.py` | Pembersihan data dan perhitungan ISPU |
| `app.py` | Server Flask dan API JSON |
| `templates/index.html`, `static/` | Tampilan website |
| `data/` | Data asli dan hasil (`air_quality_clean.csv`, `ispu_harian.csv`, `laporan_pembersihan.json`) |

## Pengaturan yang bisa diubah (di `cleaning.py`)
- `KOLOM_DIHAPUS`: daftar kolom yang dibuang
- `BATAS_INTERPOLASI_JAM`: panjang celah kosong maksimal yang diisi interpolasi
- `FAKTOR_IQR`: kepekaan pembatasan outlier
