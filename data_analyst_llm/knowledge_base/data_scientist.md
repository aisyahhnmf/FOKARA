# Data Scientist - Reference Notes
## Learning types
Supervised learning menggunakan target/label untuk mempelajari pemetaan; unsupervised learning mencari struktur/pola tanpa label target.
## Evaluation
Pisahkan train/validation/test dengan benar. Hindari data leakage. Accuracy dapat menyesatkan pada kelas tidak seimbang; pertimbangkan precision, recall, F1, ROC-AUC atau PR-AUC sesuai konteks.
## Overfitting and validation
Overfitting terjadi ketika model terlalu menyesuaikan data latih dan gagal generalisasi. Pendekatan dapat mencakup regularisasi, pembatasan kompleksitas, cross-validation, dan data tambahan.
## Imbalanced classification
Lakukan split terlebih dahulu; resampling hanya pada data training. Pertimbangkan class weights, threshold tuning, precision-recall, dan biaya kesalahan.
## Deployment and monitoring
Pantau kualitas input, data drift, concept drift, performa aktual, latency, dan kegagalan pipeline. Versioning dan rollback mendukung reproducibility.
