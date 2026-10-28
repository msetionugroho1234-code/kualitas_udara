/* Dashboard kualitas udara – logika tampilan */
const $ = (s, r = document) => r.querySelector(s);
const ambil = async (url) => {
  const res = await fetch(url);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Terjadi kesalahan");
  return data;
};
const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const fmt = (v, nd = 2) =>
  v === null || v === undefined ? "–" : Number(v).toLocaleString("id-ID", { maximumFractionDigits: nd });
const singkat = (k) => k.replace(/\s*\(.*\)/, "");
const satuan = (k) => (k.match(/\((.*)\)/) || [, ""])[1];
const WARNA_SERI = ["#0B6E75", "#C2410C", "#6D28D9", "#B45309", "#BE185D", "#15803D",
                    "#1D4ED8", "#A21CAF", "#4D7C0F", "#0E7490", "#9F1239"];
const SKALA_MAKS = 350; // skala ISPU yang digambar: 0 – 350

let meta, ringkasan, tanggalAktif;
const sudahMuat = { tren: false, banding: false };
const grafik = {};

const warnaKat = (i) => (i === 4 ? css("--berbahaya") : meta.kategori[i].warna);

function buatGrafik(kunci, kanvas, konfigurasi) {
  if (grafik[kunci]) grafik[kunci].destroy();
  Chart.defaults.font.family = css("--isi");
  Chart.defaults.color = css("--tinta-redup");
  Chart.defaults.borderColor = css("--garis");
  grafik[kunci] = new Chart($(kanvas), konfigurasi);
}

/* ------------------------------------------------------------ tab */
document.querySelectorAll(".tab button").forEach((tombol) => {
  tombol.addEventListener("click", () => {
    document.querySelectorAll(".tab button").forEach((b) => {
      b.classList.toggle("aktif", b === tombol);
      b.setAttribute("aria-selected", b === tombol);
    });
    document.querySelectorAll(".panel").forEach((p) => (p.hidden = p.id !== `tab-${tombol.dataset.tab}`));
    if (tombol.dataset.tab === "tren" && !sudahMuat.tren) { sudahMuat.tren = true; muatTren(); }
    if (tombol.dataset.tab === "banding" && !sudahMuat.banding) { sudahMuat.banding = true; muatBanding(); }
  });
});

/* ------------------------------------------------------------ kategori */
function bangunSkala() {
  const lebar = [50, 50, 100, 100, 50];
  $("#skala").innerHTML = meta.kategori
    .map((k, i) => `<div style="width:${(lebar[i] / SKALA_MAKS) * 100}%;background:${warnaKat(i)}"></div>`).join("");
  $("#skala-label").innerHTML = meta.kategori
    .map((k, i) => `<span style="width:${(lebar[i] / SKALA_MAKS) * 100}%">${k.nama}</span>`).join("");
}

function tampilkanHari(d) {
  tanggalAktif = d.tanggal;
  $("#tanggal").value = d.tanggal;
  const warna = warnaKat(d.kategori);
  const hero = $(".hero");
  hero.style.setProperty("--warna-kat", warna);
  $("#ispu-nilai").textContent = d.ispu;
  $("#kat-nama").textContent = meta.kategori[d.kategori].nama;
  $("#kat-saran").textContent = meta.kategori[d.kategori].saran;
  $("#kat-dominan").textContent = d.dominan;

  const pos = Math.min(d.ispu, SKALA_MAKS) / SKALA_MAKS * 100;
  $("#penanda").style.left = `${pos}%`;
  $("#penanda-teks").textContent = d.ispu;

  const maks = Math.max(...d.parameter.map((p) => p.ispu), 1);
  const batas = Math.max(maks * 1.25, 50);
  $("#param-bar").innerHTML = d.parameter.map((p) => `
    <div class="param ${p.kode === d.dominan ? "dom" : ""}">
      <span class="nama">${p.kode}</span>
      <span class="jalur" title="Indeks ${fmt(p.ispu, 1)}"><span class="isi" style="display:block;width:${(p.ispu / batas) * 100}%;background:${warnaKat(p.kategori)}"></span></span>
      <span class="nilai">${fmt(p.nilai)} ${p.satuan}</span>
    </div>`).join("");

  document.querySelectorAll(".kalender button").forEach((b) =>
    b.classList.toggle("dipilih", b.dataset.t === d.tanggal));
}

async function pilihHari(tgl) {
  try { tampilkanHari(await ambil(`/api/kategori/hari?tanggal=${tgl}`)); }
  catch (e) { $("#kat-saran").textContent = e.message; }
}

function geser(hari) {
  const idx = ringkasan.hari.findIndex((h) => h.t === tanggalAktif);
  const baru = ringkasan.hari[Math.min(Math.max(idx + hari, 0), ringkasan.hari.length - 1)];
  if (baru) pilihHari(baru.t);
}

function tampilkanRingkasan() {
  $("#distribusi").innerHTML = ringkasan.distribusi
    .filter((d) => d.jumlah > 0)
    .map((d) => `<div style="width:${d.persen}%;background:${warnaKat(d.kategori)}" title="${meta.kategori[d.kategori].nama}: ${d.jumlah} hari"></div>`).join("");
  const legenda = ringkasan.distribusi.map((d) => `
    <li><i style="background:${warnaKat(d.kategori)}"></i>${meta.kategori[d.kategori].nama}
      <span class="jml">${d.jumlah} hari (${fmt(d.persen, 1)}%)</span></li>`).join("");
  $("#distribusi").insertAdjacentHTML("afterend", `<ul class="legenda">${legenda}</ul>`);
  const t = ringkasan.terburuk;
  $("#ringkas-teks").textContent =
    `Rata-rata ISPU ${fmt(ringkasan.rata_ispu, 1)}. Hari terburuk: ${t.tanggal} dengan ISPU ${t.ispu}, ditentukan oleh ${t.dominan}.`;

  $("#kalender").innerHTML = ringkasan.hari.map((h) => `
    <button type="button" data-t="${h.t}" style="--warna:${warnaKat(h.kategori)}"
      title="${h.t}: ISPU ${h.ispu} (${meta.kategori[h.kategori].nama})"
      aria-label="${h.t}, ISPU ${h.ispu}, ${meta.kategori[h.kategori].nama}"></button>`).join("");
  $("#kalender").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (b) pilihHari(b.dataset.t);
  });
}

/* ------------------------------------------------------------ tren */
function bangunChip() {
  const bawaan = ["PM2.5 (ug/m3)", "PM10 (ug/m3)"];
  $("#chip-polutan").innerHTML = meta.polutan.map((p, i) => `
    <label class="chip" style="--warna:${WARNA_SERI[i % WARNA_SERI.length]}">
      <input type="checkbox" value="${p}" ${bawaan.includes(p) ? "checked" : ""}>
      <span><i></i>${singkat(p)}</span>
    </label>`).join("");
  $("#chip-polutan").addEventListener("change", (e) => {
    if (!document.querySelector("#chip-polutan input:checked")) e.target.checked = true;
    muatTren();
  });
}

async function muatTren() {
  const params = new URLSearchParams();
  document.querySelectorAll("#chip-polutan input:checked").forEach((c) => params.append("param", c.value));
  params.set("resolusi", $("#tren-resolusi").value);
  if ($("#tren-mulai").value) params.set("mulai", $("#tren-mulai").value);
  if ($("#tren-selesai").value) params.set("selesai", $("#tren-selesai").value);
  let d;
  try { d = await ambil(`/api/tren?${params}`); }
  catch (e) { $("#tren-info").textContent = e.message; return; }

  const norm = $("#tren-skala").value === "norm";
  const unit = [...new Set(d.series.map((s) => satuan(s.kolom)))];
  $("#tren-info").textContent = norm
    ? "Tiap polutan ditampilkan sebagai persen dari nilai tertingginya, sehingga pola perubahan bisa dibandingkan."
    : unit.length > 1 ? "Satuan berbeda antar polutan. Pilih skala dinormalisasi untuk membandingkan pola." : "";

  const datasets = d.series.map((s) => {
    const i = meta.polutan.indexOf(s.kolom);
    const maks = Math.max(...s.nilai.filter((v) => v !== null), 1e-9);
    return {
      label: singkat(s.kolom),
      data: norm ? s.nilai.map((v) => (v === null ? null : (v / maks) * 100)) : s.nilai,
      borderColor: WARNA_SERI[i % WARNA_SERI.length], backgroundColor: WARNA_SERI[i % WARNA_SERI.length],
      borderWidth: d.label.length > 600 ? 1.2 : 2, pointRadius: d.label.length > 120 ? 0 : 2.5,
      tension: 0.2, spanGaps: false,
    };
  });
  buatGrafik("tren", "#grafik-tren", {
    type: "line",
    data: { labels: d.label, datasets },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: { ticks: { maxTicksLimit: 10, maxRotation: 0 } },
        y: { beginAtZero: true, title: { display: true, text: norm ? "% dari nilai tertinggi" : unit.join(" / ") } },
      },
      plugins: { legend: { position: "top", align: "start" } },
    },
  });

  $("#tabel-tren tbody").innerHTML = d.ringkasan.map((r) => `
    <tr><td>${singkat(r.kolom)} <small>${satuan(r.kolom)}</small></td>
    <td class="angka">${fmt(r.rata2)}</td><td class="angka">${fmt(r.min)}</td>
    <td class="angka">${fmt(r.maks)}</td><td>${r.waktu_maks}</td></tr>`).join("");
}

/* ------------------------------------------------------------ sebelum & sesudah */
async function muatBanding() {
  const L = await ambil("/api/perbandingan");
  const negatif = Object.values(L.negatif_diperbaiki).reduce((a, b) => a + b, 0);
  const outlier = Object.values(L.outlier_dibatasi).reduce((a, b) => a + b, 0);

  $("#ringkas-angka").innerHTML = `<dl style="display:contents">
    <div><dt>Kolom</dt><dd>${L.kolom_awal} → ${L.kolom_akhir}</dd></div>
    <div><dt>Baris data</dt><dd>${fmt(L.baris_awal, 0)} → ${fmt(L.baris_akhir, 0)}</dd></div>
    <div><dt>Sel kosong</dt><dd>${fmt(L.sel_kosong_sebelum, 0)} → ${fmt(L.sel_kosong_sesudah, 0)}</dd></div>
    <div><dt>Nilai negatif diperbaiki</dt><dd>${fmt(negatif, 0)}</dd></div>
    <div><dt>Outlier dibatasi</dt><dd>${fmt(outlier, 0)}</dd></div></dl>`;

  $("#langkah").innerHTML = `
    <li><b>Hapus ${L.kolom_dihapus.length} kolom</b><span>Sesuai permintaan, kolom ini tidak dipakai lagi.</span></li>
    <li><b>Cek data ganda</b><span>${L.duplikat_dihapus} baris ganda dihapus.</span></li>
    <li><b>Perbaiki nilai tidak wajar</b><span>${fmt(negatif, 0)} konsentrasi negatif dijadikan 0 (noise sensor); ${L.rh_dibatasi} kelembapan di atas 100% dibatasi ke 100%.</span></li>
    <li><b>Batasi outlier ekstrem</b><span>Nilai di atas Q3 + ${L.faktor_iqr}×IQR dibatasi pada ambang itu: ${fmt(outlier, 0)} nilai.</span></li>
    <li><b>Isi nilai kosong</b><span>${fmt(L.isi_interpolasi, 0)} sel diisi interpolasi waktu (celah ≤ ${L.batas_interpolasi_jam} jam), ${fmt(L.isi_median, 0)} sel diisi median pada jam yang sama.</span></li>`;

  $("#kolom-hapus").innerHTML = L.kolom_dihapus.map((k) =>
    `<li>${k.kolom} <small>${fmt(k.kosong_persen, 1)}% kosong</small></li>`).join("");

  const kol = L.kolom_angka;
  $("#tabel-banding tbody").innerHTML = kol.map((c) => {
    const a = L.statistik_sebelum[c], b = L.statistik_sesudah[c];
    return `<tr><td>${c}</td>
      <td class="angka lama">${fmt(a.kosong, 0)}</td><td class="angka baik">${fmt(b.kosong, 0)}</td>
      <td class="angka lama">${fmt(a.rata2)}</td><td class="angka">${fmt(b.rata2)}</td>
      <td class="angka lama">${fmt(a.min)}</td><td class="angka">${fmt(b.min)}</td>
      <td class="angka lama">${fmt(a.maks)}</td><td class="angka">${fmt(b.maks)}</td></tr>`;
  }).join("");

  $("#grafik-kosong").parentElement.style.height = "440px";
  buatGrafik("kosong", "#grafik-kosong", {
    type: "bar",
    data: {
      labels: kol.map(singkat),
      datasets: [
        { label: "Sebelum", data: kol.map((c) => L.statistik_sebelum[c].kosong), backgroundColor: "#9AA7AD" },
        { label: "Sesudah", data: kol.map((c) => L.statistik_sesudah[c].kosong), backgroundColor: css("--aksen") },
      ],
    },
    options: {
      indexAxis: "y", responsive: true, maintainAspectRatio: false,
      scales: { x: { title: { display: true, text: "Jumlah sel kosong" } }, y: { grid: { display: false } } },
      plugins: { legend: { position: "top", align: "start" } },
    },
  });

  $("#banding-kolom").innerHTML = kol.map((c) =>
    `<option value="${c}" ${c === "Benzene (ug/m3)" ? "selected" : ""}>${c}</option>`).join("");
  muatSeriBanding();
}

async function muatSeriBanding() {
  const q = new URLSearchParams({ param: $("#banding-kolom").value, resolusi: $("#banding-resolusi").value });
  const d = await ambil(`/api/perbandingan/seri?${q}`);
  const banyak = d.label.length > 600;
  buatGrafik("banding", "#grafik-banding", {
    type: "line",
    data: {
      labels: d.label,
      datasets: [
        { label: "Sebelum dibersihkan", data: d.sebelum, borderColor: "#8C9AA1", backgroundColor: "#8C9AA1",
          borderWidth: 2.2, pointRadius: banyak ? 0 : 2, spanGaps: false, tension: 0.15 },
        { label: "Sesudah dibersihkan", data: d.sesudah, borderColor: css("--aksen"), backgroundColor: css("--aksen"),
          borderWidth: 1.6, pointRadius: banyak ? 0 : 2, spanGaps: false, tension: 0.15 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      interaction: { mode: "index", intersect: false },
      scales: { x: { ticks: { maxTicksLimit: 10, maxRotation: 0 } }, y: { title: { display: true, text: satuan($("#banding-kolom").value) } } },
      plugins: { legend: { position: "top", align: "start" } },
    },
  });
}

/* ------------------------------------------------------------ mulai */
async function mulai() {
  meta = await ambil("/api/meta");
  $("#rentang").textContent = `Data per jam, ${meta.waktu.mulai} sampai ${meta.waktu.selesai}`;
  bangunSkala();
  bangunChip();

  $("#tanggal").min = meta.ispu.mulai; $("#tanggal").max = meta.ispu.selesai;
  for (const id of ["#tren-mulai", "#tren-selesai"]) {
    $(id).min = meta.waktu.mulai; $(id).max = meta.waktu.selesai;
  }

  ringkasan = await ambil("/api/kategori/ringkasan");
  tampilkanRingkasan();
  await pilihHari(ringkasan.hari[ringkasan.hari.length - 1].t);

  $("#tanggal").addEventListener("change", (e) => e.target.value && pilihHari(e.target.value));
  $("#hari-sebelum").addEventListener("click", () => geser(-1));
  $("#hari-sesudah").addEventListener("click", () => geser(1));
  ["#tren-resolusi", "#tren-mulai", "#tren-selesai", "#tren-skala"].forEach((id) =>
    $(id).addEventListener("change", muatTren));
  ["#banding-kolom", "#banding-resolusi"].forEach((id) => $(id).addEventListener("change", muatSeriBanding));
}
mulai().catch((e) => ($("#rentang").textContent = "Gagal memuat data: " + e.message));
