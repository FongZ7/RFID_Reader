# คู่มือการใช้งาน RFID_Reader

คู่มือทีละขั้นสำหรับติดตั้งและใช้งานเครื่องอ่าน **Zebra RFD4031** บน **Raspberry Pi 4/5**
เริ่มจากศูนย์จนถึงระบบที่เปิดเครื่องมาแล้วรอรับ API ได้เลย

ทุกขั้นมี **ผลลัพธ์ที่ควรเห็น** กำกับไว้ ถ้าได้ไม่เหมือนให้ดู [ขั้นที่ 9 แก้ปัญหา](#ขั้นที่-9-แก้ปัญหา)

**สารบัญ**

1. [เตรียมอุปกรณ์](#ขั้นที่-1-เตรียมอุปกรณ์)
2. [ติดตั้งโปรแกรม](#ขั้นที่-2-ติดตั้งโปรแกรม)
3. [ให้สิทธิ์เข้าถึงพอร์ต serial](#ขั้นที่-3-ให้สิทธิ์เข้าถึงพอร์ต-serial)
4. [ตรวจว่าเจอเครื่องอ่าน](#ขั้นที่-4-ตรวจว่าเจอเครื่องอ่าน)
5. [ทดสอบอ่านแท็ก](#ขั้นที่-5-ทดสอบอ่านแท็ก)
6. [หากำลังส่งเสาอากาศที่เหมาะสม](#ขั้นที่-6-หากำลังส่งเสาอากาศที่เหมาะสม)
7. [ตั้งให้ทำงานอัตโนมัติตอนเปิดเครื่อง](#ขั้นที่-7-ตั้งให้ทำงานอัตโนมัติตอนเปิดเครื่อง)
8. [ให้ Pi ปล่อย Wi-Fi เอง](#ขั้นที่-8-ให้-pi-ปล่อย-wi-fi-เอง)
   [เสริม — ให้ Pi มี MQTT broker ของตัวเอง](#เสริม--ให้-pi-มี-mqtt-broker-ของตัวเอง)
   [เสริม — ติดตั้งหลายเครื่อง (หุ่นยนต์หลายตัว)](#เสริม--ติดตั้งหลายเครื่อง-หุ่นยนต์หลายตัว)
9. [แก้ปัญหา](#ขั้นที่-9-แก้ปัญหา)
10. [ให้ระบบอื่นเรียกใช้](#ขั้นที่-10-ให้ระบบอื่นเรียกใช้)

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
> `1200` = HID-Keyboard — ผิดโหมด ต้อง factory reset ดู [ขั้นที่ 9](#ปัญหา-sled-อยู่โหมด-hid-pid_1200)

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

ถ้าขึ้น `no ZETI serial port found` ดู [ขั้นที่ 9](#ปัญหา-no-zeti-serial-port-found)

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

## ขั้นที่ 8 ให้ Pi ปล่อย Wi-Fi เอง

ขั้นนี้ **ไม่บังคับ** ทำเมื่อหน้างานไม่มีเน็ตเวิร์กให้ใช้ หรืออยากให้ชุดนี้ทำงานได้
ด้วยตัวเองโดยไม่พึ่ง Wi-Fi ของที่อื่น

Pi จะปล่อย Wi-Fi ของตัวเอง แล้วมือถือ โน้ตบุ๊ก หรือเครื่องของลูกค้าเกาะเข้ามา
เรียก API ได้เลย

```
[มือถือ/โน้ตบุ๊ก] ---Wi-Fi ที่ Pi ปล่อย---> [Pi + sled ต่อ USB]
       curl /api/read                            อ่านแท็ก
```

> ⚠️ **ตัว sled ไม่ได้เกาะ Wi-Fi นี้** มันยังต่อ USB กับ Pi เหมือนเดิม
> Wi-Fi ที่ปล่อยออกมามีไว้ให้ **ฝั่งที่เรียก API** เกาะเท่านั้น
> เหตุผลอยู่ท้ายขั้นนี้

### 8.1 ข้อควรรู้ก่อนทำ

> ⚠️ **Pi มีวิทยุ Wi-Fi ตัวเดียว** ตอนเป็น access point จะเกาะ Wi-Fi อื่นไม่ได้
> **ถ้ากำลัง SSH เข้ามาทาง Wi-Fi จะหลุดทันทีที่สั่ง** ให้ทำผ่าน
> **สาย LAN** หรือ **หน้าจอ+คีย์บอร์ดต่อตรงที่ Pi**
>
> ถ้า Pi ต้องต่ออินเทอร์เน็ตด้วย ให้เสียบสาย LAN ควบคู่ไป — AP ใช้ Wi-Fi
> ส่วนอินเทอร์เน็ตมาทาง LAN

ตรวจว่าตั้งประเทศของ Wi-Fi แล้ว ไม่ตั้งไว้วิทยุจะถูกล็อกและเปิด AP ไม่ได้

```bash
sudo raspi-config
```

ไปที่ **Localisation Options → WLAN Country** เลือก **TH Thailand** แล้วออก

### 8.2 เปิด AP

```bash
cd ~/RFID_Reader
./setup_ap.sh --ssid RFID-READER --password rfid12345
```

สคริปต์จะสรุปค่าที่จะตั้งให้ดูแล้วถามยืนยัน พิมพ์ `y` แล้ว Enter

**ควรเห็น**

```
interface : wlan0
  GENERAL.STATE:100 (connected)
  GENERAL.CONNECTION:rfid-ap

AP 'rfid-ap' is ACTIVE
  address : 10.42.0.1/24
  clients join SSID: RFID-READER

  API from a joined client:
    curl http://10.42.0.1:8080/api/health
```

ข้อกำหนดของรหัสผ่าน: **อย่างน้อย 8 ตัวอักษร** (ข้อบังคับของ WPA2)

### 8.3 ทดสอบจากเครื่องอื่น

1. ที่มือถือหรือโน้ตบุ๊ก เปิดรายการ Wi-Fi หาชื่อ **RFID-READER** แล้วเชื่อมต่อ
2. ใส่รหัสที่ตั้งไว้
3. เรียก API ที่ **10.42.0.1**

```bash
curl http://10.42.0.1:8080/api/health
curl "http://10.42.0.1:8080/api/read?ms=1000"
```

จากมือถือเปิดเบราว์เซอร์แล้วพิมพ์ `http://10.42.0.1:8080/api/read?ms=1000` ก็ได้
จะเห็น JSON กลับมาเลย

### 8.4 คำสั่งอื่น

| คำสั่ง | ทำอะไร |
|---|---|
| `./setup_ap.sh --status` | ดูสถานะ AP ปัจจุบันและ IP |
| `./setup_ap.sh --off` | เลิกเป็น AP กลับไปเกาะ Wi-Fi ตามปกติ |
| `./setup_ap.sh --band a --channel 36` | ใช้ 5 GHz (เร็วกว่าแต่ไปไม่ไกลเท่า) |
| `./setup_ap.sh --ssid X --password Y` | เปลี่ยนชื่อ/รหัส รันซ้ำได้เลย |

AP จะขึ้นเองหลังรีบูต ทดสอบได้ด้วย

```bash
sudo reboot
```

แล้วเช็คจากมือถือว่ายังเห็นชื่อ Wi-Fi อยู่

### 8.5 ทำไม sled ไม่เกาะ Wi-Fi นี้

เป็นข้อจำกัดของตัว sled เอง ไม่ใช่สิ่งที่ตั้งค่าได้ มีหลักฐานสามชั้น

1. **sled ไม่เปิดพอร์ตให้ต่อเข้า** — ทดสอบแล้ว sled เข้า Wi-Fi และตอบ ARP ได้
   (สถานะ `Reachable`) แต่ไม่ตอบ ICMP และสแกนพอร์ต 1–1024 บวกพอร์ต RFID/IoT
   ที่ใช้กันทั่วไป **ไม่พบอะไร listening เลย** จึงไม่มีปลายทางให้ส่งคำสั่งไป
2. **Zebra ตอบเองในฟอรั่มนักพัฒนา** — *"the MQTT if defined can only be available
   for Reader Management functionality and not for RFID expected interactions"*
3. **คู่มือยืนยัน** — `rfd4031-prg-en.pdf` หน้า 25 จัด MQTT ไว้ใต้หัวข้อ
   *Mobile Device Management Overview* (partner 42Gears, SOTI) ไม่ใช่เส้นทางข้อมูลแท็ก

ถ้าให้ sled เกาะ Wi-Fi นี้ มันจะเชื่อมได้จริง แต่สั่งอ่านไม่ได้ — ใช้ได้แค่ให้ระบบ
MDM เข้ามาจัดการเครื่อง

**ถ้าต้องการให้ sled ไร้สายจริงๆ** ทางที่ Zebra รองรับคือ **Bluetooth SPP**
ซึ่ง ZETI วิ่งได้ — Pi แพร์กับ sled แล้วคุยผ่าน `/dev/rfcomm0` โค้ดชุดนี้ใช้ได้เลย
ไม่ต้องแก้ protocol แต่ยังไม่ได้ทำในเวอร์ชันนี้

---

## เสริม — ให้ Pi มี MQTT broker ของตัวเอง

ขั้นนี้ **ไม่บังคับ** ทำเมื่อฝั่งที่เรียกใช้ (หุ่นยนต์ เครื่องควบคุม) ถนัดคุย MQTT
มากกว่า REST หรืออยากให้ชุดนี้จบในตัวโดยไม่ต้องพึ่ง broker ที่อื่น

```
[หุ่นยนต์] --MQTT--> [Pi: mosquitto] --> [Pi: rfid-api] --USB/ZETI--> [sled]
[หุ่นยนต์] --REST--------------------> [Pi: rfid-api] --USB/ZETI--> [sled]
```

> ⚠️ **sled ไม่ได้เป็น MQTT client** และไม่เคยเห็น MQTT เลย ทุกคำสั่งไปถึงมันผ่าน
> **USB/ZETI** เสมอ MQTT ตรงนี้คือช่องทางให้ **หุ่นยนต์คุยกับ Pi** เป็นทางเลือก
> แทน REST — ไม่ใช่การส่ง MQTT ไปหา sled ซึ่งทำไม่ได้
> (เหตุผลอยู่ในหัวข้อ [8.5 ทำไม sled ไม่เกาะ Wi-Fi นี้](#85-ทำไม-sled-ไม่เกาะ-wi-fi-นี้)
> ของขั้นที่ 8)

### ติดตั้ง

```bash
cd ~/RFID_Reader
./setup_mqtt.sh
```

สคริปต์จะลง Mosquitto ตั้งค่าให้รับที่พอร์ต 1883 เปิด service ให้ขึ้นเองตอนบูต
แล้วแก้ unit ของ rfid-api ให้ชี้มาที่ `127.0.0.1` พร้อมรีสตาร์ตให้

ถ้าอยากใส่รหัสผ่าน (แนะนำถ้าวง LAN ไม่ได้ปิดสนิท)

```bash
./setup_mqtt.sh --user bot --password s3cret1234
```

**ควรเห็น** ท้ายสุด

```
MQTT is live.

  broker : 192.168.1.50:1883
  topics : rfid/read   -> publish a command here
           rfid/result <- the EPC array comes back here
           rfid/status <- retained, {"connected":true}
```

### ทดสอบจากหุ่นยนต์ / เครื่องอื่นในวง LAN

เปิดหน้าต่างแรกค้างไว้เพื่อฟังผล

```bash
mosquitto_sub -h <ip-ของ-pi> -t 'rfid/#' -v
```

หน้าต่างที่สองยิงคำสั่ง

```bash
mosquitto_pub -h <ip-ของ-pi> -t rfid/read -m '{"requestId":"t1","ms":1000}'
```

**ควรเห็น** ที่หน้าต่างแรก

```
rfid/result {"status": "ok", "count": 2, "tags": ["E200...6B", "E200...43"], "requestId": "t1"}
```

REST ยังใช้ได้พร้อมกัน ไม่ต้องเลือกอย่างใดอย่างหนึ่ง

```bash
curl "http://<ip-ของ-pi>:8080/api/read?ms=1000"
```

### เลิกใช้

```bash
./setup_mqtt.sh --off
```

REST ยังทำงานต่อตามปกติ

---

## เสริม — ติดตั้งหลายเครื่อง (หุ่นยนต์หลายตัว)

เมื่อมีหุ่นยนต์หลายตัว แต่ละตัวมีชุด Pi + sled ของตัวเอง ทุกเครื่องลงซอฟต์แวร์
ชุดเดียวกัน แต่มี **4 อย่างที่ห้ามซ้ำกัน**

| สิ่งที่ต้องไม่ซ้ำ | ทำไม |
|---|---|
| **hostname** | ใช้แยกเครื่องบนเน็ตเวิร์ก และเป็นฐานของ client id |
| **MQTT client id** | ⚠️ ซ้ำแล้วเครื่องเตะกันออกจาก broker — ดูด้านล่าง |
| **MQTT topic** (`MQTT_BASE`) | ไม่งั้นสั่งเครื่องหนึ่งแล้วอีกเครื่องตอบด้วย |
| **IP address** | ตั้ง static หรือจอง DHCP ไว้ หุ่นยนต์จะได้รู้ว่ายิงไปที่ไหน |

> ⚠️ **กับดักที่เจ็บที่สุด: MQTT client id ซ้ำ**
>
> สเปก MQTT อนุญาตให้ client id หนึ่งต่อได้ครั้งละหนึ่งการเชื่อมต่อ ถ้าเครื่องที่สอง
> ต่อเข้ามาด้วย id เดียวกัน **broker จะตัดเครื่องแรกทิ้งทันที** แล้วเครื่องแรกก็ต่อ
> กลับมาเตะเครื่องที่สองออก วนไปเรื่อยๆ
>
> Raspberry Pi OS ทุกเครื่องมี hostname เหมือนกันตั้งแต่ลงเสร็จ ถ้าโคลน SD card
> ไปใช้หลายเครื่องจะเจอปัญหานี้ทันที **อาการที่เห็นคืออ่านได้บ้างไม่ได้บ้างแบบสุ่ม**
> ไม่มีอะไรบอกว่าเกี่ยวกับ MQTT เลย หาสาเหตุยากมาก
>
> โปรแกรมรุ่นนี้ป้องกันให้แล้วโดยเติม `/etc/machine-id` ต่อท้าย ซึ่งไม่ซ้ำกันต่อการ
> ติดตั้งหนึ่งครั้ง แต่ **ถ้าโคลน SD card มา `machine-id` จะซ้ำด้วย** จึงควรตั้งชื่อ
> ให้ชัดเจนด้วย `provision.sh` อยู่ดี

### ตั้งค่าแต่ละเครื่องด้วยคำสั่งเดียว

ที่ Pi ของหุ่นยนต์ตัวที่ 1

```bash
cd ~/RFID_Reader
./provision.sh --name robot01
```

ตัวที่ 2

```bash
./provision.sh --name robot02
```

สคริปต์จะตั้งให้ครบในครั้งเดียว

| ตั้งอะไร | ค่าที่ได้ |
|---|---|
| hostname | `robot01` |
| `MQTT_BASE` | `rfid/robot01` |
| `MQTT_CLIENT_ID` | `rfid-robot01` |

เพิ่มกำลังส่งเฉพาะเครื่องนั้น หรือตั้ง Wi-Fi ของตัวเองไปด้วยก็ได้

```bash
./provision.sh --name robot02 --dbm 12 --ap-ssid RFID-ROBOT02 --ap-pass rfid12345
```

ดูว่าเครื่องนี้ถูกตั้งเป็นอะไรไว้

```bash
./provision.sh --show
```

**ควรเห็น**

```
hostname      : robot01
machine-id    : a1b2c3d4
IP addresses  : 10.20.41.142
service settings:
  RFID_MS=1000
  RFID_DBM=25
  MQTT_BASE=rfid/robot01
  MQTT_CLIENT_ID=rfid-robot01
```

รีบูตหนึ่งครั้งหลังเปลี่ยน hostname เพื่อให้ทุกอย่างลงตัว

```bash
sudo reboot
```

### ฝั่งหุ่นยนต์เรียกใช้

**แบบ REST** — แต่ละตัวเรียก Pi ของตัวเอง

```bash
curl "http://10.20.41.142:8080/api/read?ms=1000"
```

**แบบ MQTT** — broker ตัวเดียวคุมได้ทุกเครื่อง สั่งเจาะจงเครื่อง

```bash
mosquitto_pub -h <broker> -t rfid/robot01/read -m '{"requestId":"a1","ms":1000}'
```

ฟังผลจากทุกเครื่องพร้อมกันด้วย wildcard `+` (แทนหนึ่งระดับ)

```bash
mosquitto_sub -h <broker> -t "rfid/+/result" -v
```

เช็คว่าเครื่องไหนออนไลน์อยู่บ้าง — `status` เป็น retained จึงได้ค่าล่าสุดของทุกเครื่อง
ทันทีที่ subscribe ไม่ต้องรอ

```bash
mosquitto_sub -h <broker> -t "rfid/+/status" -v
```

```
rfid/robot01/status {"connected": true, ...}
rfid/robot02/status {"connected": false, "reason": "connection lost"}
```

เครื่องที่ตายหรือสายหลุดจะขึ้น `connected: false` ให้เอง เพราะ broker ส่ง LWT แทน

### จะวาง broker ไว้ไหน

| แบบ | เหมาะกับ |
|---|---|
| **broker กลางหนึ่งตัว** (บนเซิร์ฟเวอร์ หรือบน Pi เครื่องใดเครื่องหนึ่ง) | คุมทุกหุ่นจากที่เดียว ใช้ wildcard ได้ — **แนะนำเมื่อมีหลายตัว** |
| **broker บนทุก Pi** (`./setup_mqtt.sh` ทุกเครื่อง) | แต่ละหุ่นจบในตัว ไม่พึ่งกัน แต่ฝั่งควบคุมต้องต่อหลาย broker |

ถ้าใช้ broker กลาง ไม่ต้องรัน `setup_mqtt.sh` บน Pi ทุกเครื่อง — แก้ unit ให้ชี้ไป
ที่ broker กลางแทน

```bash
sudo nano /etc/systemd/system/rfid-api.service
```

```ini
Environment=MQTT_BROKER=10.20.41.10
```

```bash
sudo systemctl restart rfid-api
```

### ถ้าโคลน SD card ไปใช้

เร็วกว่าลงใหม่ แต่ต้องล้างของที่ต้องไม่ซ้ำออกก่อนใช้งานเครื่องที่สอง

```bash
sudo rm -f /etc/machine-id /var/lib/dbus/machine-id
sudo systemd-machine-id-setup
sudo dbus-uuidgen --ensure
./provision.sh --name robot02
sudo reboot
```

ถ้าไม่ทำขั้นนี้ `machine-id` จะซ้ำกันทั้งกอง และกลับไปเจอปัญหา client id ชนกันเหมือนเดิม

---

## ขั้นที่ 9 แก้ปัญหา

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

### ปัญหา: AP ไม่ขึ้น หรือมองไม่เห็นชื่อ Wi-Fi

```bash
./setup_ap.sh --status
```

| อาการ | สาเหตุ / วิธีแก้ |
|---|---|
| `nmcli not found` | Raspberry Pi OS เก่ากว่า Bookworm ไม่มี NetworkManager — อัปเกรด OS หรือตั้ง hostapd+dnsmasq เอง |
| สคริปต์เตือน `Soft blocked: yes` | ยังไม่ตั้งประเทศของ Wi-Fi — `sudo raspi-config` → Localisation → WLAN Country แล้ว `sudo rfkill unblock wlan` |
| สคริปต์เตือน `regulatory domain is 00` | เหมือนข้อบน ต้องตั้งประเทศก่อน ไม่งั้นวิทยุปฏิเสธโหมด AP |
| `Error: 802-11-wireless-security.psk: property is invalid` | รหัสผ่านสั้นกว่า 8 ตัวอักษร |
| AP ขึ้นแต่หลังรีบูตหายไป | มี Wi-Fi profile อื่นแย่งวิทยุ — สคริปต์ปิด autoconnect ของ profile อื่นให้แล้ว ตรวจด้วย `nmcli connection show` |
| เห็นชื่อ Wi-Fi แต่เชื่อมไม่ได้ | ลองเปลี่ยนช่อง `./setup_ap.sh --channel 6` หรือใช้ 2.4 GHz ถ้าตั้ง 5 GHz ไว้ |

ถ้าเชื่อม Wi-Fi ได้แต่เรียก API ไม่ได้ ให้ตรวจว่า service ทำงานอยู่

```bash
sudo systemctl status rfid-api
ip -4 addr show wlan0
```

IP ของ Pi บนวง AP ควรเป็น `10.42.0.1` ถ้าเป็นเลขอื่นให้ใช้เลขที่เห็นจริงแทน

### ปัญหา: SSH หลุดตอนสั่ง setup_ap.sh

เป็นพฤติกรรมปกติ ไม่ใช่ความเสียหาย — Pi มีวิทยุ Wi-Fi ตัวเดียว พอเปลี่ยนไปเป็น AP
มันจะหลุดจาก Wi-Fi เดิมที่ SSH วิ่งอยู่

**วิธีกลับเข้าไป** เลือกทางใดทางหนึ่ง

1. เสียบสาย LAN แล้ว SSH เข้าทาง IP ของ LAN
2. ต่อหน้าจอกับคีย์บอร์ดที่ Pi โดยตรง
3. เกาะ Wi-Fi ที่ Pi ปล่อย (`RFID-READER`) แล้ว SSH ไปที่ `10.42.0.1`

ทางที่ 3 ใช้ได้เลยเพราะ AP ขึ้นมาแล้ว ถ้าจะเลิกเป็น AP ก็สั่ง `./setup_ap.sh --off`

### ปัญหา: อ่านช้ากว่าที่ตั้งไว้

ปกติแล้วการอ่านจะใช้เวลาประมาณค่าที่ขอ บวกอีก ~0.2–0.5 วินาที
ถ้าช้ากว่านั้นมาก (เช่นขอ 1 วินาที แต่ใช้ 3 วินาที) แปลว่า sled ไม่ได้ส่งสัญญาณจบ
response มา ลองรีสตาร์ต service และถอดเสียบ sled

---

## ขั้นที่ 10 ให้ระบบอื่นเรียกใช้

เมื่อ service ทำงานแล้ว ระบบอื่นเรียกได้ทันทีโดยไม่ต้องลงอะไรเพิ่ม

IP ที่ใช้เรียกขึ้นกับว่าเข้ามาทางไหน

| เข้ามาทาง | IP ที่ใช้ | หาด้วย |
|---|---|---|
| Wi-Fi ที่ Pi ปล่อยเอง (ขั้นที่ 8) | `10.42.0.1` | `./setup_ap.sh --status` |
| LAN หรือ Wi-Fi วงเดียวกัน | IP ของ Pi ในวงนั้น | `hostname -I` |
| ที่ตัว Pi เอง | `localhost` | — |

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
