# RFID_Reader

REST + MQTT API สำหรับเครื่องอ่าน RFID **Zebra RFD4031** เขียนด้วย Python ล้วน
ออกแบบให้ **Raspberry Pi 4/5** เป็นตัวหลักในการทำงาน

ซอฟต์แวร์ยิงคำสั่งเข้ามา → เครื่องอ่านทำงาน → ได้ array ของ EPC กลับไป
**ไม่ต้องเหนี่ยวไก** — สั่งอ่านจากซอฟต์แวร์ทั้งหมด

```
GET  /api/read        -> {"success":true,"count":2,"tags":["EPC1","EPC2"],"readAt":"..."}
     ไม่พบแท็ก        -> {"success":true,"count":0,"tags":[],"readAt":"..."}
     เครื่องอ่านหลุด   -> HTTP 503 {"success":false,"error":"READER_DISCONNECTED"}
GET  /api/health      -> สถานะเครื่องอ่าน
```

📖 **คู่มือการใช้งานทีละขั้นตอน** — [อ่านบนเว็บ (MANUAL.md)](MANUAL.md) ·
[ดาวน์โหลดไฟล์ Word](docs/RFID_Reader-Manual-TH.docx)

---

## ทำไมไม่ใช้ Zebra SDK

Zebra มี **RFID Host SDK** สำหรับ Windows/Linux จริง แต่รองรับเฉพาะเครื่องอ่านแบบ
*fixed reader* (FX7500, FX9600, ATR7000) **ไม่รองรับ RFD40** และ Zebra ระบุชัดว่า
**ไม่รองรับ ARM** ไฟล์ `.so`/`.dll` เป็น x86 จึงโหลดบน Raspberry Pi ไม่ได้เลย
ส่วน SDK ที่รองรับ RFD40 จริงคือสาย **Android**

ทางออก: พอร์ต serial ฝั่ง RFID ของ sled พูด **ZETI** (Zebra Easy Text Interface)
เป็น ASCII ธรรมดา ปิดท้ายด้วย CR LF มีเอกสารอยู่ใน *RFD8500/i RFID Developer Guide*
ภาคผนวก A — ใช้แค่ `pyserial` ก็พอ

ทดสอบกับของจริงแล้ว — `RFD4031-G10B700-TH` firmware `PAAFKS00-013-R05`:

```
-> cn   <- Command: connect,Status:Connection Successful
-> gv   <- ,,HARDWARE,HWID_3_DV_MV,RFD40,PRE+
           ,,NGE,2.0.54.0
           ,,CRIMAN_DEVICE,PAAFKS00-013-R05
           ,,WIFI,17.92.1.p149.84
```

### sled เปิด serial สองพอร์ต

มีพอร์ตเดียวที่พูด ZETI อีกพอร์ตเป็น **เครื่องอ่านบาร์โค้ด** ซึ่งตอบเป็น binary SSI
ถ้าส่งคำสั่ง ZETI ผิดพอร์ตจะได้ `\x05\xd1\x00\x80\x01\xfe\xa9` กลับมา
`zeti.find_port()` จึงหาพอร์ตที่ถูกต้องโดยถามทีละพอร์ต ไม่ต้องกำหนดเลขพอร์ตเอง

| เครื่อง | พอร์ต |
|---|---|
| Raspberry Pi | `/dev/ttyACM0` (ZETI Interface) · `/dev/ttyACM1` (SSI Interface) |
| Windows | `COM15` · `COM16` |

บน Linux ตัว descriptor บอกชื่อ interface มาให้ด้วย:

```
/dev/ttyACM1   RFD4031-G10B700-TH::::EA - SSI Interface
/dev/ttyACM0   RFD4031-G10B700-TH::::EA - ZETI Interface  <-- ZETI
```

### Wi-Fi ในตัว sled ส่งข้อมูลแท็กไม่ได้

เรื่องนี้ปิดเคสแล้ว ไม่ต้องรื้อใหม่ ตัว sled ไม่เปิดพอร์ตให้ต่อเข้า และ MQTT ในตัวมัน
เป็น **Reader Management เท่านั้น** — `rfd4031-prg-en.pdf` หน้า 25 จัด MQTT ไว้ใต้หัวข้อ
*Mobile Device Management* (partner 42Gears, SOTI) คำตอบจาก Zebra ใน developer forum:
*"the MQTT if defined can only be available for Reader Management functionality and not
for RFID expected interactions."*

ด้วยเหตุนี้สถาปัตยกรรมจึงเป็น: sled ต่อ USB เข้า Pi แล้ว **Pi** เป็นตัวพูดกับเน็ตเวิร์ก

---

## เริ่มใช้งานเร็ว

```bash
git clone https://github.com/FongZ7/RFID_Reader.git
cd RFID_Reader
pip3 install -r requirements.txt
sudo usermod -aG dialout $USER      # แล้ว logout/login
python3 rfid_cli.py --ports         # ดูว่าพอร์ตไหนเป็น ZETI
python3 rfid_cli.py --ms 1000       # อ่านแท็ก
./install.sh                        # ตั้งให้ทำงานอัตโนมัติตอนเปิดเครื่อง
```

รายละเอียดทีละขั้นอยู่ใน **[MANUAL.md](MANUAL.md)**

---

## REST API

| Method | Path | ทำอะไร |
|---|---|---|
| `GET` | `/api/health` | สถานะเครื่องอ่าน (`/health` ก็ได้) |
| `GET` | `/api/read?ms=1000` | สั่งอ่าน คืน array EPC |
| `POST` | `/api/read` | เหมือนกัน แต่ส่ง parameter มาใน JSON body |

พารามิเตอร์ ใส่หรือไม่ใส่ก็ได้ ใช้ได้ทั้งใน query string และ JSON body:

| ชื่อ | ความหมาย |
|---|---|
| `ms` / `timeoutMs` | ระยะเวลาอ่าน จำกัดอยู่ที่ 50–10000 ms |
| `minRssi` | ตัดแท็กที่สัญญาณอ่อนกว่าค่านี้ เช่น `-60` |

```bash
curl "http://<pi-ip>:8080/api/read?ms=1000"
curl -X POST http://<pi-ip>:8080/api/read -H "Content-Type: application/json" -d '{"timeoutMs":1000}'
curl http://<pi-ip>:8080/api/health
```

ตัวอย่างคำตอบ:

```json
{"success":true,"count":2,"tags":["E200001D890B00711360296B","E200001D890B02471360DE43"],"readAt":"2026-10-01T10:23:16+07:00"}
{"success":true,"count":0,"tags":[],"readAt":"2026-10-01T10:23:16+07:00"}
{"success":false,"error":"READER_DISCONNECTED","detail":"no ZETI serial port found - is the sled plugged in and awake?"}
```

`/api/health`:

```json
{"success":true,"connected":true,"device":"/dev/ttyACM0","model":"RFD40",
 "powerDbm":25.0,"defaultMs":1000,"minRssi":null,"lastError":"","at":"..."}
```

---

## MQTT (ไม่บังคับ)

ตั้ง `MQTT_BROKER` แล้วเซิร์ฟเวอร์จะรับคำสั่งทาง MQTT ด้วย เหมาะกับกรณีที่ฝั่งลูกค้า
ไม่ควรต้องต่อเข้า Pi โดยตรง เพราะทั้งสองฝ่ายต่อ **ออก** ไปหา broker

| Topic | ทิศทาง | Payload |
|---|---|---|
| `rfid/read` | ลูกค้า → Pi | อะไรก็ได้ ว่างก็ได้ |
| `rfid/result` | Pi → ลูกค้า | `{"status":"ok","count":2,"tags":[...]}` |
| `rfid/status` | Pi → ลูกค้า | retained + LWT, `{"connected":true}` |

ฟิลด์ในคำสั่ง ใส่หรือไม่ใส่ก็ได้:

| ชื่อ | ความหมาย |
|---|---|
| `ms` / `timeoutMs` | ระยะเวลาอ่าน 50–10000 ms |
| `minRssi` | ตัดแท็กสัญญาณอ่อน |
| `requestId` | ข้อความอะไรก็ได้ เซิร์ฟเวอร์ใส่กลับมาในคำตอบ |
| `replyTo` | ให้ตอบมาที่ topic นี้แทน `rfid/result` |

แทน `<broker-host>` ด้วย hostname หรือ IP ของ broker ที่ใช้ — ถ้ายังไม่มีก็ติดตั้ง
Mosquitto เองได้ (`sudo apt install mosquitto` แล้วใช้ `localhost`)

```bash
mosquitto_sub -h <broker-host> -t rfid/result &
mosquitto_pub -h <broker-host> -t rfid/read -m '{"requestId":"a1","ms":1000}'
```

```json
{"status":"ok",     "requestId":"a1", "count":2, "tags":["E200...43","E200...6B"]}
{"status":"no_tag", "requestId":"a1", "count":0, "tags":[]}
{"status":"error",  "requestId":"a1", "count":0, "tags":[], "error":"..."}
```

ถ้าคำสั่งไม่ได้ส่ง `requestId` มา คำตอบก็ไม่มีฟิลด์นี้

**ทำไมต้องมี `requestId`**: เครื่องอ่านมีตัวเดียว และคำตอบทุกใบไปลงที่ `rfid/result`
เหมือนกันหมด ถ้ามีสอง client สั่งพร้อมกันจะแยกไม่ออกว่าใบไหนของใคร ให้เทียบ `requestId`
หรือให้แต่ละ client มี `replyTo` ของตัวเอง คำสั่งที่เข้ามาพร้อมกันจะถูกทำเรียงทีละอัน

---

## การตั้งค่า

ตั้งผ่าน environment variable ทั้งหมด ไม่ใส่ก็ได้:

| ตัวแปร | ค่าตั้งต้น | ความหมาย |
|---|---|---|
| `RFID_DEVICE` | หาเอง | พอร์ต serial เช่น `/dev/ttyACM0` — **แนะนำให้ไม่ตั้ง** เพราะเลขพอร์ตเลื่อนได้ทุกครั้งที่เสียบ |
| `RFID_BAUD` | `115200` | |
| `RFID_MS` | `1000` | ระยะเวลาอ่านตั้งต้น |
| `RFID_DBM` | ค่าที่ค้างใน sled | กำลังส่งเสาอากาศ หน่วย dBm |
| `RFID_MINRSSI` | ปิด | ตัดแท็กสัญญาณอ่อน |
| `RFID_HOST` | `0.0.0.0` | ทุก interface |
| `RFID_PORT` | `8080` | |
| `MQTT_BROKER` | ไม่ตั้ง = ปิด MQTT | |
| `MQTT_PORT` | `1883` | |
| `MQTT_BASE` | `rfid` | คำนำหน้า topic |
| `MQTT_USER` / `MQTT_PASS` | ไม่ตั้ง | |

---

## ทำงานอัตโนมัติตอนเปิดเครื่อง

คำสั่งเดียว — สคริปต์จะเติม user, path และ python (เลือก `venv/` ในโฟลเดอร์ก่อนถ้ามี)
ลงใน unit แล้ว enable + start ให้:

```bash
./install.sh
```

ใช้งานประจำวัน:

```bash
sudo systemctl status rfid-api
sudo systemctl restart rfid-api
journalctl -u rfid-api -f        # ดู log สด
```

### กรณี sled ยังไม่พร้อม

ตอนบูต systemd อาจ start service ก่อนที่ USB จะ enumerate เสร็จ และ sled จะ
**หลุดจาก USB ไปเลย** เวลามันหลับ (ไม่ใช่แค่เงียบ — พอร์ตหายไปทั้งพอร์ต)
ทั้งสองกรณีไม่นับเป็นความล้มเหลว เซิร์ฟเวอร์ขึ้นปกติ เขียน log บอก แล้วค่อยต่อ
เครื่องอ่านตอนมี request เข้ามาครั้งแรก

request ที่เข้ามาตอน sled ไม่อยู่จะได้ HTTP 503 พร้อม

```json
{"success":false,"error":"READER_DISCONNECTED","detail":"no ZETI serial port found - is the sled plugged in and awake?"}
```

request ถัดไปจะต่อใหม่ให้เอง รวมถึงหาพอร์ตใหม่ด้วย เพราะเลข `/dev/ttyACM` เปลี่ยนได้

`Restart=always` ครอบกรณีที่โปรเซสตายด้วยสาเหตุอื่น

---

## โครงสร้างไฟล์

```
RFID_Reader/
├── zeti.py              ZETI protocol บน pyserial — โค้ดส่วนเดียวที่คุยกับเครื่องอ่าน
├── rfid_api_server.py   REST + MQTT, เครื่องอ่านตัวเดียวใต้ lock เดียว
├── rfid_cli.py          เครื่องมือทดสอบ + --sweep หากำลังส่งที่เหมาะสม
├── install.sh           ติดตั้ง service ให้ทำงานตอนเปิดเครื่อง
├── rfid-api.service     แม่แบบ systemd unit (__USER__, __DIR__, __PYTHON__)
├── requirements.txt
├── README.md
├── MANUAL.md            คู่มือการใช้งานทีละขั้นตอน
└── docs/
    └── RFID_Reader-Manual-TH.docx    คู่มือฉบับไฟล์ Word (สร้างจาก MANUAL.md)
```

---

## บันทึกเรื่อง ZETI ที่ควรรู้

กว่าจะได้มาเสียเวลาไปไม่น้อย เอกสารฉบับเต็มคือภาคผนวก A ของ RFD8500 Developer Guide

| คำสั่ง | ความหมาย |
|---|---|
| `cn` / `dc` | เปิด / ปิด ASCII session — คำสั่งอื่นจะตอบ `Status:ASCII Connection not present` ถ้ายังไม่ `cn` |
| `gv` | เวอร์ชัน ตอบมาบรรทัดละ `,,KEY,VALUE` |
| **`a`** | **abort** |
| **`ac .p 100`** | **กำลังส่งเสาอากาศ หน่วยเป็นสิบเท่าของ dBm** — `100` = 10.0 dBm |
| `ac .n` | อ่านค่า antenna config ปัจจุบันกลับมา |
| `rc .iz .ir` | report config — ใส่ firstseentime กับ RSSI |
| `st .d` | start trigger ค่าตั้งต้น = เริ่มทันทีที่ส่ง `in` |
| `ot .ip .et .to 1000` | stop trigger — ไม่สนใจไก หยุดเมื่อครบ 1000 ms |
| `in` | inventory บรรทัดแท็กเป็น `,,<EPC>,<firstseentime>,<rssi>` |

- **`ac` ไม่ใช่ abort** — abort คือ `a` ส่ง `ac` เปล่าๆ จะไปเขียนทับ antenna config
  แบบเงียบๆ ไม่ได้หยุดอะไร
- จำนวนฟิลด์ในบรรทัดแท็กขึ้นกับ report config จึง parse ตามตำแหน่งและยอมให้ฟิลด์ขาดได้
  (`_parse_tag_line()` ทำแบบนั้น)
- **response ของ inventory จบด้วยบรรทัดว่าง** ไม่ใช่ `Notification:StopOperation`
  เพราะ notification ปิดอยู่ตามค่าตั้งต้น ถ้าไปรอ notification การอ่าน 1 วินาทีจะใช้เวลา 3 วินาที
- report config ค้างอยู่ในตัว sled จึงต้องกำหนดทั้งชุด ไม่ใช่แค่เพิ่มฟิลด์ที่อยากได้
  ไม่อย่างนั้นตำแหน่งคอลัมน์จะเลื่อนตามค่าที่ค้างจากของเดิม
- sled หลุดจาก USB เวลาหลับ ทุกการอ่านจึงลองต่อใหม่หนึ่งครั้งก่อนยอมแพ้
  และหาพอร์ตใหม่ด้วยเพราะเลขพอร์ตเลื่อนได้

---

## เรื่องที่ยังค้าง — กำลังส่งเสาอากาศ

ที่ 25 dBm เครื่องอ่านเก็บแท็กอื่นที่อยู่ในห้องติดมาด้วย ที่ 10 dBm สะอาด แต่ยังไม่ได้
ยืนยันว่าแท็กเป้าหมายยังอ่านติดที่ระยะใช้งานจริง ใช้ `rfid_cli.py --sweep` โดยวางแท็ก
เป้าหมายไว้ เลือกค่าสูงสุดที่ยังเห็น **แค่แท็กนั้น** แล้วตั้งค่า `RFID_DBM`
