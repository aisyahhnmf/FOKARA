# Data Engineer - Reference Notes
## ETL and ELT
ETL mengekstrak, mentransformasi, lalu memuat data; ELT memuat data terlebih dahulu lalu mentransformasi di platform target. Pilihan bergantung arsitektur dan kebutuhan.
## Storage formats
CSV bersifat teks dan mudah dibaca lintas alat. Parquet adalah format columnar yang mendukung tipe data dan kompresi efisien untuk analitik.
## Data modeling
Fact table merekam kejadian atau ukuran pada grain tertentu; dimension table menyimpan konteks deskriptif seperti waktu, produk, atau pelanggan.
## Reliability
Idempotency memastikan pengulangan operasi tidak menghasilkan efek duplikasi yang tidak diinginkan. Checkpoint, retry, dead-letter/quarantine, dan observability membantu pemulihan.
## Orchestration and governance
Orchestration mengatur jadwal, dependensi, retry, dan pemantauan workflow. Governance mencakup klasifikasi, kontrol akses least privilege, lineage, audit, dan retensi.
