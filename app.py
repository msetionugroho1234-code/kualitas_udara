"""
app.py - Website dashboard kualitas udara (Flask).
Jalankan:  python app.py   lalu buka http://127.0.0.1:5000
"""
import pandas as pd
from flask import Flask, jsonify, render_template, request, send_file

import cleaning as cl

app = Flask(__name__)

MENTAH, BERSIH, ISPU, LAPORAN = cl.jalankan_pipeline()
BERSIH_IDX = BERSIH.set_index("From Date")
MENTAH_IDX = MENTAH.set_index("From Date")

SATUAN_ISPU = {"PM2.5": "µg/m³", "PM10": "µg/m³", "SO2": "µg/m³",
               "NO2": "µg/m³", "CO": "mg/m³", "O3": "µg/m³"}
RESOLUSI = {"jam": None, "hari": "D", "minggu": "W", "bulan": "MS"}


def daftar(seri, nd=3):
    """Series -> list JSON-aman (NaN menjadi null)."""
    return [None if pd.isna(v) else round(float(v), nd) for v in seri]


def label_waktu(index, resolusi):
    fmt = "%Y-%m-%d %H:%M" if resolusi == "jam" else "%Y-%m-%d"
    return [t.strftime(fmt) for t in index]


def agregasi(df_idx, kolom, resolusi):
    if RESOLUSI[resolusi] is None:
        return df_idx[kolom]
    return df_idx[kolom].resample(RESOLUSI[resolusi]).mean()


def resolusi_valid():
    r = request.args.get("resolusi", "hari")
    return r if r in RESOLUSI else "hari"


@app.route("/")
def beranda():
    return render_template("index.html")


@app.route("/api/meta")
def meta():
    return jsonify({
        "polutan": cl.POLUTAN,
        "kolom_angka": LAPORAN["kolom_angka"],
        "waktu": {"mulai": BERSIH["From Date"].min().strftime("%Y-%m-%d"),
                  "selesai": BERSIH["From Date"].max().strftime("%Y-%m-%d")},
        "ispu": {"mulai": ISPU.index.min().strftime("%Y-%m-%d"),
                 "selesai": ISPU.index.max().strftime("%Y-%m-%d")},
        "kategori": cl.KATEGORI,
    })


@app.route("/api/kategori/hari")
def kategori_hari():
    tgl = pd.to_datetime(request.args.get("tanggal"), errors="coerce")
    if pd.isna(tgl) or tgl not in ISPU.index:
        return jsonify({"error": "Tanggal tidak ada dalam data."}), 404
    r = ISPU.loc[tgl]
    i = cl.kategori_dari_ispu(r["ISPU"])
    parameter = []
    for kode in cl.PARAMETER_ISPU:
        sub = float(r[f"ispu_{kode}"])
        j = cl.kategori_dari_ispu(round(sub))
        parameter.append({"kode": kode, "nilai": float(r[f"nilai_{kode}"]),
                          "satuan": SATUAN_ISPU[kode], "ispu": sub,
                          "kategori": j,
                          "rata_rata": cl.PARAMETER_ISPU[kode][2]})
    return jsonify({
        "tanggal": tgl.strftime("%Y-%m-%d"), "ispu": int(r["ISPU"]),
        "kategori": i, "dominan": r["Polutan Dominan"],
        "jam_data": int(r["Jumlah Jam Data"]), "parameter": parameter,
    })


@app.route("/api/kategori/ringkasan")
def kategori_ringkasan():
    jumlah = ISPU["Kategori"].value_counts()
    distribusi = [{"kategori": i, "jumlah": int(jumlah.get(k["nama"], 0)),
                   "persen": round(jumlah.get(k["nama"], 0) / len(ISPU) * 100, 1)}
                  for i, k in enumerate(cl.KATEGORI)]
    terburuk = ISPU["ISPU"].idxmax()
    return jsonify({
        "hari": [{"t": t.strftime("%Y-%m-%d"), "ispu": int(v),
                  "kategori": cl.kategori_dari_ispu(v)} for t, v in ISPU["ISPU"].items()],
        "distribusi": distribusi,
        "rata_ispu": round(float(ISPU["ISPU"].mean()), 1),
        "terburuk": {"tanggal": terburuk.strftime("%Y-%m-%d"),
                     "ispu": int(ISPU.loc[terburuk, "ISPU"]),
                     "dominan": ISPU.loc[terburuk, "Polutan Dominan"]},
        "dominan": {k: int(v) for k, v in ISPU["Polutan Dominan"].value_counts().items()},
    })


@app.route("/api/tren")
def tren():
    resolusi = resolusi_valid()
    params = [p for p in request.args.getlist("param") if p in cl.POLUTAN] or ["PM2.5 (ug/m3)"]
    data = BERSIH_IDX
    mulai, selesai = request.args.get("mulai"), request.args.get("selesai")
    if mulai or selesai:
        akhir = f"{selesai} 23:59:59" if selesai else None
        data = data.loc[mulai or None: akhir]
    if data.empty:
        return jsonify({"error": "Tidak ada data pada rentang tanggal tersebut."}), 404

    seri = agregasi(data, params, resolusi)
    ringkas = []
    for p in params:
        s = data[p]
        ringkas.append({"kolom": p, "rata2": round(float(s.mean()), 3),
                        "min": round(float(s.min()), 3), "maks": round(float(s.max()), 3),
                        "waktu_maks": s.idxmax().strftime("%Y-%m-%d %H:%M")})
    return jsonify({
        "resolusi": resolusi, "label": label_waktu(seri.index, resolusi),
        "series": [{"kolom": p, "nilai": daftar(seri[p])} for p in params],
        "ringkasan": ringkas,
    })


@app.route("/api/perbandingan")
def perbandingan():
    return jsonify(LAPORAN)


@app.route("/api/perbandingan/seri")
def perbandingan_seri():
    resolusi = resolusi_valid()
    kolom = request.args.get("param", "PM2.5 (ug/m3)")
    if kolom not in LAPORAN["kolom_angka"]:
        return jsonify({"error": "Kolom tidak dikenal."}), 400
    sebelum = agregasi(MENTAH_IDX, [kolom], resolusi)[kolom]
    sesudah = agregasi(BERSIH_IDX, [kolom], resolusi)[kolom].reindex(sebelum.index)
    return jsonify({"label": label_waktu(sebelum.index, resolusi),
                    "sebelum": daftar(sebelum), "sesudah": daftar(sesudah)})


@app.route("/api/unduh/<jenis>")
def unduh(jenis):
    berkas = {"bersih": cl.CLEAN_FILE, "ispu": cl.ISPU_FILE, "laporan": cl.REPORT_FILE}
    if jenis not in berkas:
        return jsonify({"error": "Berkas tidak ada."}), 404
    return send_file(berkas[jenis], as_attachment=True)


if __name__ == "__main__":
 app.run(debug=True, use_reloader=False)