import cv2
import numpy as np
import paho.mqtt.client as mqtt
import json
import time 
from datetime import datetime
from picamera2 import Picamera2
import os
try:
    from tflite_runtime.interpreter import Interpreter
except ImportError:
    try:
        from ai_edge_litert.interpreter import Interpreter
    except ImportError:
        import tensorflow as tf
        Interpreter = tf.lite.Interpreter


# ==========================================
# KONFIGURASI MQTT (EMQX CLOUD)
# ==========================================
MQTT_BROKER = "g4f48271.ala.asia-southeast1.emqxsl.com"
MQTT_PORT = 8883
MQTT_TOPIC = "smartbin/deposit"
BIN_CODE = "sb001" # Sesuaikan dengan kode unit
MQTT_TOPIC_FLUTTER = f"smartbin/kiosk/{BIN_CODE}/deposit"
MQTT_USERNAME = "smartbin"
MQTT_PASSWORD = "123456" 

# ==========================================
# KONFIGURASI MACHINE LEARNING
# ==========================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(SCRIPT_DIR, "model.tflite")
LABEL_PATH = os.path.join(SCRIPT_DIR, "labels.txt")

# Inisialisasi Model TFLite
interpreter = Interpreter(model_path=MODEL_PATH)
interpreter.allocate_tensors()
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()
height = input_details[0]['shape'][1]
width = input_details[0]['shape'][2]

# Load Label
with open(LABEL_PATH, 'r') as f:
    # Mengambil teks label setelah angka index (jika ada)
    labels = []
    for line in f.readlines():
        parts = line.strip().split(' ', 1)
        if len(parts) > 1 and parts[0].isdigit():
            labels.append(parts[1])
        else:
            labels.append(parts[0])

# ==========================================
# FUNGSI LOGIKA POIN
# ==========================================
def calculate_points(label_name):
    """
    Logika konversi jenis botol ke poin berdasarkan labels.txt.
    """
    mapping = {
        "330ml": (10, "Botol Plastik Kecil"),
        "600ml": (15, "Botol Plastik Sedang"),
        "1500ml": (25, "Botol Plastik Besar")
    }
    
    label_lower = label_name.lower()
    for key, (pts, name) in mapping.items():
        if key.lower() in label_lower:
            return pts, name
            
    return 0, "Non-Botol / Tidak Dikenali"

# ==========================================
# INISIALISASI MQTT CLIENT
# ==========================================
# Inisialisasi MQTT CLIENT
# Gunakan CallbackAPIVersion.VERSION1 untuk kompatibilitas paho-mqtt 2.x
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Terhubung ke MQTT Broker!")
        # Kirim pesan tes saat pertama terhubung
        client.publish(MQTT_TOPIC, json.dumps({"status": "online", "message": "Smartbin connected"}))
    else:
        print(f"Gagal terhubung, kode: {rc}")

def on_publish(client, userdata, mid):
    print(f"Pesan terkirim ke Broker (mid: {mid})")

mqtt_client.on_connect = on_connect
mqtt_client.on_publish = on_publish

# Tambahkan Auth & TLS untuk EMQX Cloud
mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
mqtt_client.tls_set() 

mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()

# ==========================================
# MAIN LOOP (CAMERA & RECOGNITION)
# ==========================================
def main():
    picam2 = Picamera2()

    config = picam2.create_preview_configuration(
      main={"size": (640,480)}
    )

    picam2.configure(config)
    picam2.start()

    print("Sistem Smartbin Aktif. Deteksi otomatis berjalan...")

    # Variabel untuk mencegah pengiriman ganda (spam)
    last_detect_time = 0
    COOLDOWN_SECONDS = 3

    while True:
        try:
            frame = picam2.capture_array()
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            current_time = time.time()
            
            # Jika masih dalam cooldown, lewati frame ini
            if current_time - last_detect_time < COOLDOWN_SECONDS:
                time.sleep(0.1)
                continue

            # 1. Pre-processing gambar untuk ML
            input_img = cv2.resize(frame, (width, height))
            input_img = cv2.cvtColor(input_img, cv2.COLOR_BGR2RGB) # Ubah ke RGB
            input_img = input_img.astype(np.float32)
            
            # Normalisasi ke rentang -1 sampai 1
            input_img = (input_img - 127.5) / 127.5 
            input_img = np.expand_dims(input_img, axis=0)

            # 2. Jalankan Inference
            interpreter.set_tensor(input_details[0]['index'], input_img)
            interpreter.invoke()
            
            # 3. Ambil Hasil
            output_data = interpreter.get_tensor(output_details[0]['index'])
            results = np.squeeze(output_data)
            top_index = np.argmax(results)
            confidence = results[top_index]
            
            label_detected = labels[top_index]

            # Ambang batas keyakinan (tingkatkan agar tidak gampang salah tebak saat otomatis)
            if confidence > 0.85:
                points, bottle_name = calculate_points(label_detected)
                
                if points > 0:
                    # 4. Susun Payload Data
                    # Dalam mode release, Flutter Kiosk sekarang memakai json dari smartbin/deposit/#
                    # tapi menggunakan format JSON standar
                    payload = {
                        "bottle_type": bottle_name,
                        "points": points,
                        "bin_id": BIN_CODE,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    # 5. Kirim ke MQTT
                    # Kirim ke Laravel & Kiosk (Satu topik yang sama)
                    result = mqtt_client.publish(MQTT_TOPIC, json.dumps(payload))
                    
                    if result[0] == 0:
                        print(f"TERDETEKSI: {bottle_name} ({int(confidence*100)}%) - Terkirim ke Sistem!")
                        last_detect_time = current_time # Reset cooldown
                        
                        # [DEBUG] Simpan gambar terakhir yang memicu deteksi agar bisa dicek
                        debug_img_path = os.path.join(SCRIPT_DIR, "last_detected.jpg")
                        cv2.imwrite(debug_img_path, frame)
                        print(f"[DEBUG] Gambar disimpan di: {debug_img_path}")
                    else:
                        print("Gagal mengirim data ke MQTT Broker")

            # Beri sedikit jeda agar CPU Raspberry Pi tidak overheat
            time.sleep(0.2)
            
        except KeyboardInterrupt:
            print("Sistem dihentikan.")
            break
        except Exception as e:
            print(f"Terjadi kesalahan: {e}")
            time.sleep(1)

    picam2.stop()
    mqtt_client.loop_stop()

if __name__ == "__main__":
    main()
