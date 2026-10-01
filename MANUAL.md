# คู่มือการใช้งาน RFID_Reader

คู่มือทีละขั้นสำหรับติดตั้งและใช้งานเครื่องอ่าน **Zebra RFD4031** บน **Raspberry Pi 4/5**
เริ่มจากศูนย์จนถึงระบบที่เปิดเครื่องมาแล้วรอรับ API ได้เลย

ทุกขั้นมี **ผลลัพธ์ที่ควรเห็น** กำกับไว้ ถ้าได้ไม่เหมือนให้ดู [ขั้นที่ 8 แก้ปัญหา](#ขั้นที่-8-แก้ปัญหา)

**สารบัญ**

1. [เตรียมอุปกรณ์](#ขั้นที่-1-เตรียมอุปกรณ์)
2. [ติดตั้งโปรแกรม](#ขั้นที่-2-ติดตั้งโปรแกรม)
3. [ให้สิทธิ์เข้าถึงพอร์ต serial](#ขั้นที่-3-ให้สิทธิ์เข้าถึงพอร์ต-serial)
4. [ตรวจว่าเจอเครื่องอ่าน](#ขั้นที่-4-ตรวจว่าเจอเครื่องอ่าน)
5. [ทดสอบอ่านแท็ก](#ขั้นที่-5-ทดสอบอ่านแท็ก)
6. [หากำลังส่งเสาอากาศที่เหมาะสม](#ขั้นที่-6-หากำลังส่งเสาอากาศที่เหมาะสม)
7. [ตั้งให้ทำงานอัตโนมัติตอนเปิดเครื่อง](#ขั้นที่-7-ตั้งให้ทำงานอัตโนมัติตอนเปิดเครื่อง)
8. [แก้ปัญหา](#ขั้นที่-8-แก้ปัญหา)
9. [ให้ระบบอื่นเรียกใช้](#ขั้นที่-9-ให้ระบบอื่นเรียกใช้)

---

## ขั้นที่ 1 เตรียมอุปกรณ์

**ที่ต้องมี**

| อุปกรณ์ | หมายเหตุ |
|---|---|
| Raspberry Pi 4 หรือ 5 | ลง Raspberry Pi OS (64-bit) แล้ว |
| Zebra RFD4031 sled | ใส่แบตเตอรี่แล้ว |
| สาย USB-C | ต่อจาก sled เข้า Pi |
| แท็ก UHF RFID | สำหรับทดสอบ |

**ขั้นตอน**

1. ใส่แบตเตอรี่เข้า sled
2. ต่อสาย USB-C จาก sled เข้าพอร์ต USB ของ Pi
3. ตรวจว่า Pi มองเห็นอุปกรณ์

```bash
lsusb | grep -i zebra
```

**ควรเห็น** — บรรทัดที่มี `Zebra` หรือ `Symbol` และรหัส `05e0:`

```
Bus 001 Device 005: ID 05e0:1701 Symbol Technologies RFD4031
```

ถ้าไม่เห็นอะไรเลย ดู [ปัญหา: Pi ไม่เห็น sled](#ปัญหา-pi-ไม่เห็น-sled)

> **โหมดของ sled สำคัญ**
> รหัส PID บอกโหมดที่ sled อยู่
> `1701` = USB-CDC — **ถูกต้อง** ใช้งานได้
> `1200` = HID-Keyboard — ผิดโหมด ต้อง factory reset ดู [ขั้นที่ 8](#ปัญหา-sled-อยู่โหมด-hid-pid_1200)

---

## ขั้นที่ 2 ติดตั้งโปรแกรม

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv git
```

ดาวน์โหลดโค้ด

```bash
cd ~
git clone https://github.com/FongZ7/RFID_Reader.git
cd RFID_Reader
```

สร้าง virtual environment แล้วลง dependency

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**ควรเห็น** — ท้ายสุดขึ้น `Successfully installed Flask-... paho-mqtt-... pyserial-... waitress-...`

> ใช้ venv ไม่บังคับ แต่แนะนำ — Raspberry Pi OS รุ่นใหม่กันการ `pip install` ลงระบบ
> และ `install.sh` จะเลือก python ใน `venv/` ให้อัตโนมัติถ้าเจอ

---

## ขั้นที่ 3 ให้สิทธิ์เข้าถึงพอร์ต serial

ผู้ใช้ต้องอยู่ในกลุ่ม `dialout` ไม่อย่างนั้นจะเปิดพอร์ตไม่ได้

```bash
sudo usermod -aG dialout $USER
```

**ต้อง logout แล้ว login ใหม่** หรือรีบูต สิทธิ์จึงจะมีผล

```bash
sudo reboot
```

กลับมาแล้วตรวจ

```bash
id -nG | tr ' ' '\n' | grep dialout
```

**ควรเห็น** — `dialout`

> ขั้นนี้ `install.sh` ทำให้อัตโนมัติด้วย และตัว service เองรันด้วย `Group=dialout`
> จึงทำงานได้ทันทีไม่ต้องรอ logout

---

## ขั้นที่ 4 ตรวจว่าเจอเครื่องอ่าน

```bash
source venv/bin/activate
python3 rfid_cli.py --ports
```

**ควรเห็น**

```
/dev/ttyS0     n/a
/dev/ttyACM1   RFD4031-G10B700-TH::::EA - SSI Interface
/dev/ttyACM0   RFD4031-G10B700-TH::::EA - ZETI Interface  <-- ZETI
```

เครื่องหมาย `<-- ZETI` คือพอร์ตที่โปรแกรมจะใช้ โปรแกรมหาเองทุกครั้ง ไม่ต้องตั้งค่า

> **ทำไมมีสองพอร์ต**
> `ZETI Interface` = ฝั่ง RFID — พอร์ตที่เราใช้
> `SSI Interface` = ฝั่งเครื่องอ่านบาร์โค้ด พูด protocol binary คนละแบบ
> เลข `ttyACM` **สลับกันได้** ทุกครั้งที่เสียบใหม่ จึงไม่ควรไปตั้งค่าตายตัว

ดูข้อมูลเครื่อง

```bash
python3 rfid_cli.py --info
```

**ควรเห็น**

```
connected /dev/ttyACM0
port    : /dev/ttyACM0
model   : RFD40
power   : 25.0 dBm
  CRIMAN_DEVICE    PAAFKS00-013-R05
  BLUETOOTH        17.92.1.p149
  NGE              2.0.54.0
  PL5000           PAAEOC20-003-R01
  HARDWARE         HWID_3_DV_MV,RFD40,PRE+
  WIFI             17.92.1.p149.84
```

ถ้าขึ้น `no ZETI serial port found` ดู [ขั้นที่ 8](#ปัญหา-no-zeti-serial-port-found)

---

## ขั้นที่ 5 ทดสอบอ่านแท็ก

วางแท็กไว้หน้าเสาอากาศของ sled ห่างประมาณ 10–30 ซม. แล้ว

```bash
python3 rfid_cli.py --ms 1000
```

**ควรเห็น**

```
connected /dev/ttyACM0
port    : /dev/ttyACM0
model   : RFD40
power   : 25.0 dBm

2 tag(s) in 1034 ms
  E200001D890B00711360296B
  E200001D890B02471360DE43
```

ตัวเลือกที่ใช้บ่อย

| คำสั่ง | ทำอะไร |
|---|---|
| `python3 rfid_cli.py` | อ่านครั้งเดียว 1000 ms |
| `python3 rfid_cli.py --ms 2000` | ยืดเวลาอ่านเป็น 2 วินาที |
| `python3 rfid_cli.py --dbm 10` | ตั้งกำลังส่ง 10 dBm ก่อนอ่าน |
| `python3 rfid_cli.py --minrssi -60` | ตัดแท็กที่สัญญาณอ่อนกว่า −60 |
| `python3 rfid_cli.py --loop` | อ่านซ้ำเรื่อยๆ จนกด Ctrl+C |
| `python3 rfid_cli.py --device /dev/ttyACM0` | ระบุพอร์ตเอง (ปกติไม่ต้อง) |
| `python3 rfid_cli.py --raw gr` | ส่งคำสั่ง ZETI ดิบ — ที่นี่คือดู RF region |

ถ้าได้ `0 tag(s)` ดู [ปัญหา: อ่านไม่เจอแท็ก](#ปัญหา-อ่านไม่เจอแท็ก)

---

## ขั้นที่ 6 หากำลังส่งเสาอากาศที่เหมาะสม

ขั้นนี้สำคัญกับการใช้งานจริง กำลังส่งสูงเกินไปจะเก็บแท็กอื่นที่ไม่ต้องการติดมาด้วย
ต่ำเกินไปก็อ่านแท็กเป้าหมายไม่ติด

**วางแท็กเป้าหมายไว้ที่ระยะใช้งานจริง** และเอาแท็กอื่นออกให้ไกล แล้ว

```bash
python3 rfid_cli.py --sweep
```

**ควรเห็น** — ตารางไล่กำลังส่งทีละ 5 dBm

```
sweeping antenna power - target tag in place, others out of range

 5.0 dBm  1 tag(s)  1360296B
10.0 dBm  1 tag(s)  1360296B
15.0 dBm  2 tag(s)  1360296B, 1360DE43
20.0 dBm  3 tag(s)  1360296B, 1360DE43, 74384A2D
25.0 dBm  3 tag(s)  1360296B, 1360DE43, 74384A2D
```

**วิธีอ่านผล** — เลือกค่าสูงสุดที่ยังเห็น **แค่แท็กเป้าหมาย** จากตัวอย่างนี้คือ **10 dBm**
(ที่ 15 dBm เริ่มมีแท็กอื่นโผล่เข้ามา)

จดค่าไว้ใช้ในขั้นต่อไป ถ้ากำลังส่งอย่างเดียวแยกไม่ได้ ให้ใช้ `--minrssi` ช่วยอีกชั้น

---

## ขั้นที่ 7 ตั้งให้ทำงานอัตโนมัติตอนเปิดเครื่อง

### 7.1 ตั้งค่าก่อนติดตั้ง

แก้ค่ากำลังส่งที่ได้จากขั้นที่ 6 ลงในไฟล์ unit

```bash
nano rfid-api.service
```

หาบรรทัดนี้แล้วแก้เลข

```ini
Environment=RFID_DBM=25
```

บรรทัดอื่นที่แก้ได้

```ini
Environment=RFID_MS=1000        # ระยะเวลาอ่านตั้งต้น
Environment=RFID_PORT=8080      # พอร์ต HTTP
#Environment=RFID_MINRSSI=-60   # เอา # ออกถ้าจะใช้
```

ถ้าจะใช้ MQTT ด้วยให้เอา `#` ออกจากสามบรรทัดนี้ และใส่ hostname หรือ IP ของ broker
ที่ใช้งานแทน `<broker-host>`

```ini
#Environment=MQTT_BROKER=<broker-host>
#Environment=MQTT_PORT=1883
#Environment=MQTT_BASE=rfid
```

ถ้ายังไม่มี broker ติดตั้งบน Pi เองได้ แล้วใช้ `localhost`

```bash
sudo apt install -y mosquitto mosquitto-clients
sudo systemctl enable --now mosquitto
```

บันทึกด้วย `Ctrl+O` `Enter` แล้วออกด้วย `Ctrl+X`

### 7.2 ติดตั้ง

```bash
./install.sh
```

**ควรเห็น**

```
user   : pi
dir    : /home/pi/RFID_Reader
python : /home/pi/RFID_Reader/venv/bin/python3
checking dependencies
  pyserial, flask present
  waitress present
writing /etc/systemd/system/rfid-api.service

● rfid-api.service - RFD4031 RFID API (REST)
     Loaded: loaded (/etc/systemd/system/rfid-api.service; enabled; ...)
     Active: active (running) since ...
```

คำว่า **`enabled`** หมายถึงจะขึ้นเองตอนเปิดเครื่อง และ **`active (running)`** หมายถึงกำลังทำงานอยู่

### 7.3 ทดสอบ

```bash
curl http://localhost:8080/api/health
```

**ควรเห็น**

```json
{"success":true,"connected":true,"device":"/dev/ttyACM0","model":"RFD40","powerDbm":10.0,...}
```

```bash
curl "http://localhost:8080/api/read?ms=1000"
```

**ควรเห็น**

```json
{"success":true,"count":1,"tags":["E200001D890B00711360296B"],"readAt":"..."}
```

### 7.4 ทดสอบว่าขึ้นเองจริงหลังรีบูต

```bash
sudo reboot
```

รอ Pi บูตเสร็จ แล้วจาก Pi หรือเครื่องอื่นในวงเดียวกัน

```bash
curl http://localhost:8080/api/health
```

ถ้าตอบได้โดยไม่ต้องสั่งอะไรเลย = เรียบร้อย

### 7.5 คำสั่งดูแลประจำวัน

```bash
sudo systemctl status rfid-api      # ดูสถานะ
sudo systemctl restart rfid-api     # รีสตาร์ต (ใช้หลังแก้ค่า)
sudo systemctl stop rfid-api        # หยุด
sudo systemctl start rfid-api       # เริ่ม
sudo systemctl disable rfid-api     # ไม่ให้ขึ้นเองตอนเปิดเครื่อง
journalctl -u rfid-api -f           # ดู log สด (Ctrl+C เพื่อออก)
journalctl -u rfid-api -n 50        # ดู log 50 บรรทัดล่าสุด
```

### 7.6 แก้ค่าหลังติดตั้งแล้ว

แก้ไฟล์ในโฟลเดอร์โปรเจกต์แล้วรัน `install.sh` ซ้ำ — ปลอดภัย รันซ้ำได้

```bash
nano rfid-api.service
./install.sh
```

หรือแก้ไฟล์ที่ติดตั้งแล้วโดยตรง (แต่จะหายถ้ารัน `install.sh` อีกครั้ง)

```bash
sudo nano /etc/systemd/system/rfid-api.service
sudo systemctl daemon-reload
sudo systemctl restart rfid-api
```

---

## ขั้นที่ 8 แก้ปัญหา

### ปัญหา: Pi ไม่เห็น sled

`lsusb` ไม่ขึ้นอะไรเลย

1. ตรวจว่าใส่แบตเตอรี่ใน sled แล้ว — ไม่มีแบต sled ไม่ทำงานแม้เสียบ USB
2. เปลี่ยนสาย USB-C — สายชาร์จบางเส้นไม่มีสายข้อมูล
3. เสียบพอร์ต USB อื่นของ Pi
4. กดไกเพื่อปลุก sled แล้วลองใหม่

```bash
dmesg | tail -20
```

ดูว่ามีบรรทัด `cdc_acm` กับ `ttyACM` โผล่มาตอนเสียบหรือไม่

### ปัญหา: sled อยู่โหมด HID (PID_1200)

`lsusb` ขึ้น `05e0:1200` แทน `05e0:1701` — sled อยู่โหมดคีย์บอร์ด ใช้กับโปรแกรมนี้ไม่ได้

**วิธี factory reset**

1. ถอดแบตเตอรี่และแหล่งจ่ายไฟออกให้หมด
2. เสียบสาย USB เข้าแหล่งจ่ายไฟ — ไฟ LED แบตจะกะพริบ
3. **ภายใน 5 วินาที** กดไกบน (upper trigger) ค้างไว้
4. **ภายใน 30 วินาที** ใส่แบตเตอรี่กลับ
5. ได้ยินเสียง beep ยืนยัน แล้วปล่อยไก

sled จะรีบูตกลับเป็นค่าโรงงาน **ต้องตั้งค่า RF region ใหม่** ดู
[ปัญหา: อ่านไม่เจอแท็ก](#ปัญหา-อ่านไม่เจอแท็ก) ข้อ 5

> อย่าสับสนกับ *Bootloader Recovery* ซึ่งใช้ **ไกล่าง** — อันนั้นสำหรับแฟลช firmware

### ปัญหา: `no ZETI serial port found`

```
no ZETI serial port found - is the sled plugged in and awake?
```

สาเหตุที่พบบ่อย เรียงตามโอกาส

1. **sled หลับ** — กดไกเพื่อปลุก แล้วลองใหม่
   sled หลับเมื่อไม่ใช้งานประมาณ 20 วินาที และ **หลุดจาก USB ไปเลย** พอร์ตหายทั้งพอร์ต

2. **ไม่มีสิทธิ์ dialout** — ตรวจด้วย

```bash
id -nG | grep dialout
```

ถ้าไม่มีให้ย้อนไป [ขั้นที่ 3](#ขั้นที่-3-ให้สิทธิ์เข้าถึงพอร์ต-serial)

3. **โปรแกรมอื่นถือพอร์ตอยู่** — เครื่องอ่านเปิดได้ครั้งละโปรเซสเดียว ถ้า service
   กำลังรันอยู่ `rfid_cli.py` จะเปิดพอร์ตไม่ได้

```bash
sudo systemctl stop rfid-api     # หยุด service ก่อนทดสอบด้วย CLI
```

ดูว่าใครถือพอร์ตอยู่

```bash
sudo fuser -v /dev/ttyACM0
```

4. **สายหลวม** — ถอดเสียบสาย USB แล้วรอ 5 วินาที

### ปัญหา: อ่านไม่เจอแท็ก

ได้ `0 tag(s)` หรือ `{"count":0,"tags":[]}` ซึ่ง **ไม่ใช่ error** — แปลว่าอ่านแล้วแต่ไม่พบ

1. ขยับแท็กเข้าใกล้เสาอากาศ 10–20 ซม.
2. เพิ่มกำลังส่ง

```bash
python3 rfid_cli.py --dbm 27 --ms 2000
```

3. ตรวจว่าตั้ง `--minrssi` ไว้แรงเกินไปหรือไม่ — ลองเอาออก
4. ตรวจว่าแท็กเป็น **UHF (EPC Gen2)** ไม่ใช่ NFC หรือ HF 13.56 MHz
5. ตรวจ RF region ของ sled — ถ้าเพิ่ง factory reset มาจะยังไม่ได้ตั้ง ทำให้อ่านไม่ติด

```bash
python3 rfid_cli.py --raw gr
```

**ควรเห็น** — region ปัจจุบันพร้อมช่องความถี่ที่ใช้ เครื่องที่ใช้งานในไทยควรเป็น `THA`
ถ้าว่างหรือไม่ใช่ ให้ดูว่ารองรับ region อะไรบ้าง

```bash
python3 rfid_cli.py --raw ga
```

แล้วตั้งค่าด้วย `setregulatory` (`sg`) ใส่รหัสประเทศสามตัวอักษร

```bash
python3 rfid_cli.py --raw "sg .region THA"
```

**ควรเห็น** — `Command:setregulatory ,Status:OK`

> ตั้งค่า region ให้ตรงกับประเทศที่ใช้งานจริงเท่านั้น — เป็นข้อกำหนดทางกฎหมายเรื่อง
> คลื่นความถี่ ไม่ใช่แค่การตั้งค่าให้อ่านติด

### ปัญหา: service ไม่ขึ้น

```bash
sudo systemctl status rfid-api
journalctl -u rfid-api -n 50
```

| ข้อความใน log | สาเหตุ / วิธีแก้ |
|---|---|
| `ModuleNotFoundError: No module named 'serial'` | python ที่ unit ใช้ไม่มี dependency — รัน `./install.sh` ใหม่หลัง `source venv/bin/activate` |
| `Address already in use` | พอร์ต 8080 ถูกใช้แล้ว — เปลี่ยน `RFID_PORT` ในไฟล์ unit |
| `not ready yet (...)` | **ไม่ใช่ปัญหา** เซิร์ฟเวอร์ขึ้นแล้ว รอต่อเครื่องอ่านตอน request แรก |
| `Permission denied: '/dev/ttyACM0'` | ปัญหาสิทธิ์ — unit ต้องมี `Group=dialout` รัน `./install.sh` ใหม่ |

### ปัญหา: เครื่องอื่นเรียก API ไม่ได้

ในเครื่อง Pi เรียกได้ แต่เครื่องอื่นไม่ได้

1. ตรวจว่า bind ทุก interface — ต้องเป็น `RFID_HOST=0.0.0.0` ไม่ใช่ `127.0.0.1`
2. หา IP ของ Pi

```bash
hostname -I
```

3. ลองจากเครื่องอื่น

```bash
curl http://<ip-ของ-pi>:8080/api/health
```

4. ถ้าเปิด firewall ไว้ ต้องเปิดพอร์ต

```bash
sudo ufw allow 8080/tcp
```

### ปัญหา: อ่านช้ากว่าที่ตั้งไว้

ปกติแล้วการอ่านจะใช้เวลาประมาณค่าที่ขอ บวกอีก ~0.2–0.5 วินาที
ถ้าช้ากว่านั้นมาก (เช่นขอ 1 วินาที แต่ใช้ 3 วินาที) แปลว่า sled ไม่ได้ส่งสัญญาณจบ
response มา ลองรีสตาร์ต service และถอดเสียบ sled

---

## ขั้นที่ 9 ให้ระบบอื่นเรียกใช้

เมื่อ service ทำงานแล้ว ระบบอื่นเรียกได้ทันทีโดยไม่ต้องลงอะไรเพิ่ม

### cURL

```bash
curl "http://<ip-ของ-pi>:8080/api/read?ms=1000"
```

```bash
curl -X POST http://<ip-ของ-pi>:8080/api/read \
  -H "Content-Type: application/json" \
  -d '{"timeoutMs":1000,"minRssi":-60}'
```

### Python

```python
import requests

r = requests.get("http://192.168.1.50:8080/api/read", params={"ms": 1000}, timeout=15)
data = r.json()
if data["success"]:
    print("พบ %d แท็ก" % data["count"])
    for epc in data["tags"]:
        print(" ", epc)
else:
    print("เครื่องอ่านมีปัญหา:", data.get("detail"))
```

### C# / .NET

```csharp
using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(15) };
var json = await http.GetStringAsync("http://192.168.1.50:8080/api/read?ms=1000");
Console.WriteLine(json);
```

### Node.js

```javascript
const res = await fetch('http://192.168.1.50:8080/api/read?ms=1000')
const data = await res.json()
console.log(data.count, data.tags)
```

### MQTT (ถ้าเปิดไว้)

```bash
mosquitto_sub -h <broker-host> -t rfid/result &
mosquitto_pub -h <broker-host> -t rfid/read -m '{"requestId":"a1","ms":1000}'
```

### สิ่งที่ฝั่งเรียกใช้ควรเผื่อไว้

| กรณี | สิ่งที่ได้ | ควรทำ |
|---|---|---|
| อ่านสำเร็จ | HTTP 200 `"success":true` | ใช้ค่าใน `tags` |
| ไม่พบแท็ก | HTTP 200 `"count":0` | **ไม่ใช่ error** — แค่ไม่มีแท็กในระยะ |
| เครื่องอ่านหลุด | HTTP 503 `READER_DISCONNECTED` | ลองใหม่อีกครั้ง — request ถัดไปจะต่อเครื่องอ่านใหม่เอง |
| timeout ฝั่ง client | — | ตั้ง timeout ของ client ให้มากกว่า `ms` ที่ขอ อย่างน้อย 5 วินาที |

**ข้อควรระวัง: เครื่องอ่านมีตัวเดียว** คำสั่งที่เข้ามาพร้อมกันจะถูกทำเรียงทีละอัน
ผู้เรียกคนที่สองจะรอคนแรกเสร็จก่อน ถ้าต้องยิงถี่ๆ ให้เผื่อเวลาไว้

---

## ภาคผนวก: ทดสอบโดยไม่ใช้ service

ถ้าจะทดสอบแบบเห็น log ตรงหน้า ให้หยุด service ก่อน (ไม่อย่างนั้นจะแย่งพอร์ตกัน)

```bash
sudo systemctl stop rfid-api
source venv/bin/activate
RFID_DBM=10 python3 rfid_api_server.py
```

**ควรเห็น**

```
10:22:52  RFD4031 API server
10:22:52    device   : autodetect
10:22:52    listen   : http://0.0.0.0:8080
10:22:52    read win : 1000 ms
10:22:52    power    : 10.0 dBm
10:22:57  reader: connected /dev/ttyACM0
10:22:58    reader   : connected (RFD40 on /dev/ttyACM0)
10:22:58    mqtt     : off (set MQTT_BROKER to enable)
10:22:58    server   : waitress

ready.  waiting for requests.
```

กด `Ctrl+C` เพื่อหยุด แล้วเปิด service กลับ

```bash
sudo systemctl start rfid-api
```
