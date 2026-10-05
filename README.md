# Pemantauan TrustPositif dengan GitHub Actions

Workflow memeriksa setiap jam pada menit 17 (UTC), dengan tombol Run workflow untuk pemeriksaan manual. Laptop dan Codespace boleh dimatikan setelah workflow berhasil aktif.

Alur: Surfshark Jakarta -> unduh daftar Komdigi sementara -> baca domain_checks di Firebase -> tandai domain yang ditemukan sebagai blocked=true/status=diblokir -> hapus unduhan dan kredensial sementara.
Domain yang tidak ditemukan, domain tidak valid, dan domain yang sudah diblokir tidak diubah. Seluruh daftar Komdigi tidak dikirim ke Firebase dan tidak diunggah sebagai artifact.

GitHub repository Secrets yang wajib tersedia:
- FIREBASE_SERVICE_ACCOUNT: seluruh JSON service account Firebase.
- SURFSHARK_USERNAME: username manual OpenVPN (bukan email login).
- SURFSHARK_PASSWORD: password manual OpenVPN.

Secrets diatur pada Settings > Secrets and variables > Actions. Jangan simpan nilai Secrets di kode atau commit. Workflow hanya diberi contents:read.

Jadwal GitHub Actions dapat terlambat atau terlewat. Pada repository publik, jadwal dinonaktifkan setelah 60 hari tanpa aktivitas repository; aktifkan kembali melalui tab Actions jika perlu. Runner standar publik gratis menurut ketentuan GitHub saat konfigurasi dibuat. Tidak menggunakan runner besar atau berbayar.

Uji lokal: python -m unittest discover -s tests
Workflow: .github/workflows/trustpositif.yml

Codespaces hanya dipakai untuk mengedit kode. Skrip connect-vpn.sh dan run-updater.sh tetap tersedia untuk uji manual di Codespace.
