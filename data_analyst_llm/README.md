# FOKARA - Data Analyst Starter Package

Paket awal untuk Question Bank, rubric, prompt engineering, RAG, evaluasi jawaban LLM, dan data dummy.

## Keputusan desain
- 7 pertanyaan utama: 2 umum + 5 teknis.
- 2 pertanyaan umum berlaku untuk seluruh role dan level.
- 3 role: Data Analyst, Data Scientist, Data Engineer.
- 3 level: Beginner, Intermediate, Advanced.
- Total question bank: 47 pertanyaan (2 umum + 3 x 3 x 5 teknis).
- Rubrik umum: relevance, communication, self_awareness, persuasiveness.
- Rubrik teknis: relevance, technical_accuracy, reasoning, problem_solving, communication.
- Skor 0-4. Standar interpretasi disesuaikan level.
- Follow-up maksimal 2 per pertanyaan utama; aplikasi harus menyimpan counter dan parent_question_id.

## Struktur folder
- data/: question bank, rubric, schema, dummy data
- prompts/: prompt generation, evaluation, follow-up, RAG
- knowledge_base/: dokumen referensi ringkas per role
- src/: question selector, RAG engine, LLM engine, contoh runner

## Instalasi
Disarankan Python 3.10 atau 3.11.
1. Buat virtual environment.
2. `pip install -r requirements.txt`
3. Salin `.env.example` menjadi `.env`, lalu isi GROQ_API_KEY.
4. Atur environment variable dari `.env` (atau gunakan python-dotenv di aplikasi).
5. Bangun index: `python src/rag_engine.py`
6. Uji pemilihan pertanyaan: `python src/question_selector.py`
7. Uji personalisasi pertanyaan: `python src/run_question_generation.py TECH-002`
8. Uji evaluasi: `python src/run_evaluation.py`
9. Fungsi follow-up tersedia di `src/followup_engine.py` dan dipanggil backend setelah evaluasi.

Catatan: script contoh belum otomatis memuat `.env`. Jalankan `set -a; source .env; set +a` pada Linux/macOS, atau atur environment variable melalui terminal/IDE di Windows. Alternatifnya tambahkan `from dotenv import load_dotenv; load_dotenv()` pada awal `llm_engine.py`.

## Alur sistem
1. Backend menerima role dan experience_level.
2. `get_session_questions()` mengambil 2 pertanyaan umum + 5 pertanyaan teknis.
3. Untuk pertanyaan teknis, RAG mengambil konteks berdasarkan role.
4. LLM menghasilkan evaluasi JSON.
5. Backend memvalidasi JSON dan menyimpan hasil per question_id.
6. Jika perlu follow-up dan jumlah follow-up < 2, backend meminta prompt follow-up.
7. Simpan follow-up sebagai child dari pertanyaan utama dengan parent_question_id.

## Catatan integrasi
- `question_bank.csv` dapat diimpor ke tabel database.
- Simpan role dan experience_level pada setiap interview_session.
- Simpan prompt_version, model_name, retrieved_sources, dan created_at untuk audit.
- Jangan menyimpan API key di repository.
- Dummy data ditandai `is_synthetic=true`; tidak boleh dipresentasikan sebagai hasil pengguna nyata.
- CV observations berasal dari modul Computer Vision, bukan dibuat oleh LLM evaluator.
- Hasil analisis statistik dan clustering harus menggunakan data yang cukup; data dummy hanya untuk menguji pipeline.

## Batasan prototipe
RAG saat ini menggunakan dokumen Markdown ringkas buatan untuk demonstrasi. Sebelum evaluasi serius, tambahkan referensi tepercaya, tanggal/versi sumber, dan pemeriksaan isi dokumen. Embedding retrieval tidak menjamin jawaban benar. Evaluasi LLM perlu dibandingkan dengan penilai manusia atau answer key yang ditinjau.
