# SmartBin IoT Raspberry Pi

Repositori ini berisi skrip Python untuk sistem deteksi botol otomatis di Raspberry Pi menggunakan kamera dan model Machine Learning (TFLite). Skrip ini berjalan secara *headless* (tanpa antarmuka grafis) dan mengirimkan hasil deteksi beserta estimasi poin ke *broker* MQTT.

## Prasyarat

- Raspberry Pi dengan sistem operasi Raspberry Pi OS
- Modul Kamera (Picamera2)
- Koneksi Internet
- Python 3
- Model TensorFlow Lite (`model.tflite`) dan berkas label (`labels.txt`)

## Cara Deploy agar Berjalan Otomatis (Systemd Service)

Agar skrip `smartbin_iot.py` otomatis berjalan di latar belakang setiap kali Raspberry Pi dinyalakan (*booting*), kita perlu membuat layanan (*service*) menggunakan Systemd.

### 1. Buat Berkas Layanan Baru

Buka terminal di Raspberry Pi Anda dan buat berkas konfigurasi layanan baru:

```bash
sudo nano /etc/systemd/system/smartbin.service
```

### 2. Masukkan Konfigurasi Layanan

Salin dan tempel kode berikut ke dalam berkas yang baru saja dibuka. 
*(Catatan: Pastikan mengubah path `/home/pi/Development/...` jika lokasi direktori repositori ini di Raspberry Pi Anda berbeda.)*

```ini
[Unit]
Description=Smartbin IoT Auto-Detection Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/Development/smartbin/rasberry-py
# Pastikan path Python mengarah ke virtual environment jika Anda menggunakannya
ExecStart=/usr/bin/python3 /home/pi/Development/smartbin/rasberry-py/smartbin_iot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Simpan berkas tersebut (Tekan `CTRL+X`, tekan `Y`, lalu `Enter`).

### 3. Aktifkan dan Jalankan Layanan

Setelah berkas konfigurasi tersimpan, jalankan perintah berikut secara berurutan:

```bash
# 1. Memuat ulang daftar service sistem agar membaca konfigurasi baru
sudo systemctl daemon-reload

# 2. Mengaktifkan layanan agar otomatis berjalan setiap kali mesin menyala (booting)
sudo systemctl enable smartbin.service

# 3. Memulai layanan sekarang juga tanpa perlu restart
sudo systemctl start smartbin.service
```

### 4. Perintah Berguna (Maintenance)

Berikut adalah beberapa perintah yang sering digunakan untuk mengecek kondisi sistem IoT Anda:

**Cek Status Layanan:**
Melihat apakah layanan aktif atau terjadi *error*.
```bash
sudo systemctl status smartbin.service
```

**Melihat Log (Print Console) Secara Realtime:**
Berguna untuk melihat apakah deteksi berjalan lancar.
```bash
journalctl -u smartbin.service -f
```

**Memberhentikan Layanan:**
```bash
sudo systemctl stop smartbin.service
```

**Memulai Ulang (Restart) Layanan:**
```bash
sudo systemctl restart smartbin.service
```
