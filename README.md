# SRE Technical Challenge: Log Analysis & Observability

## Overview
Repositori ini berisi hasil investigasi dan analisis terhadap dataset log berukuran 10K baris (*production-like*). Analisis ini bertujuan untuk mengidentifikasi isu operasional terkait keandalan layanan (*reliability*), performa, insiden, dan inefisiensi biaya (lonjakan penyimpanan log), serta memberikan rekomendasi perbaikan struktural.

## Approach & Methodology
*   **Tools Used:** 
    *   Python dengan pustaka `pandas` untuk pemrosesan dan ekstraksi data berbasis *in-memory data frame*.
    *   **Google Gemini AI** dimanfaatkan sebagai asisten AI interaktif untuk mempercepat pembuatan *script* analisis, *troubleshooting error* pemrosesan data, dan membantu menstrukturkan draf laporan operasional ini.
*   **Assumptions:**
    *   Dataset merupakan representasi dari arsitektur *microservices*.
    *   Semua *timestamp* dicatat dalam zona waktu UTC.
    *   Format log diekstrak secara dinamis untuk mengantisipasi ketidakkonsistenan skema antar layanan.

---

## 1. Explore the Dataset
Berdasarkan ekstraksi dataset, didapatkan profil sistem sebagai berikut:
*   **Time Range:** `2026-06-17 10:00:03 UTC` hingga `2026-06-17 14:59:55 UTC` (Total durasi ~5 jam).
*   **Teams:** Terdiri dari 5 tim pengembang (`checkout`, `user`, `search`, `marketing`, `internal`).
*   **Services:** Melibatkan 8 layanan utama (`order-api`, `profile-api`, `payment-api`, `search-api`, `campaign-api`, `recommendation-api`, `auth-api`, `admin-api`).
*   **Traffic Patterns:** Dataset memuat 10.000 *requests* secara keseluruhan.

## 2. Reliability Analysis
*   **Error Rates:** Terdapat tingkat kegagalan (*Global 5xx Error Rate*) sebesar **2.62%**.
*   **Unhealthy Services:** `payment-api` adalah layanan dengan tingkat kesehatan terburuk, mencatatkan **190 error (5xx)**, jauh melampaui layanan lain seperti `order-api` (18 error) dan `recommendation-api` (17 error).
*   **Failure Patterns:** Tingginya *error* pada `payment-api` memiliki potensi kuat memicu kegagalan beruntun (*cascading failure*) pada layanan yang bergantung padanya di ranah *checkout*.

## 3. Performance Analysis
*   **Slow Services & Endpoints:** `payment-api` mengalami degradasi performa yang sangat parah. Sementara p50 berada di angka normal (106.0 ms), **latensi p99 melonjak drastis hingga 55,025.54 ms (~55 detik)**. Sebagai perbandingan, layanan lain memiliki latensi p99 maksimal di kisaran 350 - 435 ms.
*   **Latency Trends:** Tingginya latensi p99 pada *layer* pembayaran berbanding lurus dengan peningkatan status HTTP 5xx akibat *timeout* yang terjadi pada layanan *upstream* yang memanggilnya.

## 4. Incident Investigation
*   **Did any incident occur?** Ya, terdeteksi sebuah insiden operasional.
*   **When did it start?** Insiden memuncak pada **2026-06-17 pukul 14:32:00 UTC** dengan laju *error* mencapai **16 errors/menit**.
*   **Which services were affected?** Insiden berpusat pada `payment-api` yang mengalami *hang* atau proses tak terhingga (*infinite blocking*), yang kemudian berdampak pada layanan lain seperti `order-api`.
*   **Evidence:** Adanya lonjakan (*spike*) drastis pada persentase status HTTP 500 dan korelasi langsung dengan *timeout* 55 detik di latensi p99.

## 5. Cost Analysis (OpenSearch Growth)
Terdapat anomali biaya penyimpanan log (*storage cost*) yang sangat signifikan:
*   **Top Contributors:** Tim **marketing** mendominasi volume log dengan total **~40.18 MB** (dari sampel 10K), sangat timpang dibandingkan tim di urutan kedua (`checkout` sebesar **~2.48 MB**) dan `search` (**~1.92 MB**).
*   **Driving Factors:** Layanan milik tim marketing kemungkinan besar melakukan praktik *verbose logging*, seperti mencetak seluruh *request payload*, atribut promosi, atau *raw data* yang membengkakkan ukuran indeks per dokumen di OpenSearch.

---

## 6. SRE Recommendations

### Reliability
*   **Resiliency Patterns:** Implementasikan pola *Circuit Breaker* dan *Retry with Exponential Backoff* pada layanan `order-api` saat memanggil `payment-api` untuk mencegah *resource exhaustion*.
*   **Alerting:** Konfigurasikan peringatan (*alert*) berbasis *Burn-Rate* pada metrik ketersediaan (*availability*).

### Performance
*   **Timeout Budgets:** Terapkan batasan waktu (*strict timeout*) yang agresif (misalnya maksimal 3-5 detik) antar *microservices* untuk mencegah *hanging requests* hingga 55 detik yang memblokir *thread pool*.
*   **Dependency Audit:** Lakukan investigasi pada *third-party payment gateway* yang berintegrasi dengan `payment-api` untuk mengetahui akar masalah kemacetan pada persentil 99.

### Observability
*   **Distributed Tracing:** Mengingat arsitektur ini sudah memiliki `trace_id`, pastikan OpenTelemetry diintegrasikan secara penuh untuk memvisualisasikan grafik ketergantungan layanan di Jaeger/Tempo.

### Cost Optimization
*   **Log Sanitization:** Tim `marketing` **harus** menghentikan pencatatan *payload* berukuran besar (seperti `request_body`) di tingkat produksi.
*   **Strict Log Schema:** Terapkan validasi ukuran maksimal per baris log (misal < 2KB) sebelum dikirim ke *collector*.

---

## Bonus Question: Scaling to 20 TB/day
Jika volume log melonjak drastis hingga 20 TB/hari, memompa seluruh data langsung ke mesin pencari teks (OpenSearch) akan menguras biaya penyimpanan dan memicu *bottleneck* pengindeksan. Solusi terbaik adalah mendesain ulang arsitektur menjadi **Data Lakehouse**:

1.  **Decoupled Ingestion:** Log dari *cluster* Kubernetes didorong melalui agen ringan (seperti Vector/Fluent-bit) ke sistem *message broker* (seperti Apache Kafka) untuk menyerap lonjakan *traffic* sementara.
2.  **Streaming & Processing:** Mesin analitik terdistribusi (seperti Apache Spark) mengonsumsi data dari Kafka untuk melakukan pembersihan *real-time*, agregasi latensi per menit, dan *dynamic sampling* (misal: hanya simpan 5% log sukses, tapi 100% log *error*).
3.  **Medallion Architecture:**
    *   **Bronze (Raw Logs):** Semua log mentah 20TB disimpan ke Object Storage (S3/GCS) dalam format kompresi Apache Parquet (sangat murah untuk *cold storage* dan audit kepatuhan).
    *   **Silver (Filtered):** Log berstatus *error* diteruskan ke OpenSearch atau ClickHouse untuk investigasi.
    *   **Gold (Aggregated):** Matriks latensi (p50, p99) dan *error rates* yang sudah diagregasi dikirim ke Prometheus untuk dasbor analitik.

---