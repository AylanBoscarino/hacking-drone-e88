# E88 UDP Control Protocol

> The binary UDP protocol used to control the E88 drone; flight commands are 9-byte packets (8-byte core + 1-byte prefix) sent in a 50ms loop to 192.168.1.1:7099.

## Overview

The [[e88-drone]] exposes a UDP socket on port 7099 (IP 192.168.1.1 - its WiFi AP address). The companion app [[com-cooingdv-rcfpv-v1-8-0]] connects after the RTSP video stream is established and sends 8-byte control packets at a fixed 50ms interval regardless of joystick activity. A separate 1-second heartbeat keeps the connection alive.

Everything below is derived from static analysis of the decompiled APK (`FlyController$FlyControlTask.smali` for the packet assembly, `SocketClient.java` for the connection lifecycle).

## Network Topology

| Role | Protocol | Address | Port |
|------|----------|---------|------|
| Flight control (send) | UDP | 192.168.1.1 | 7099 |
| Drone telemetry (recv) | UDP | 192.168.1.1 | 7099 (same socket) |
| Video stream | RTSP | 192.168.1.1 | 7070 |
| File browser (media) | HTTP | 192.168.1.1 | 80 |
| Media FTP | FTP | 192.168.1.1 | 21 (implicit) |
| JNI/TC path (alternate) | TCP | 192.168.1.1 | 5000 |

Source: `socket/Config.java`, `socket/SocketClient.java:132`

## Connection Handshake Sequence

1. App opens RTSP stream: `rtsp://192.168.1.1:7070/webcam` via IjkPlayer
2. IjkPlayer fires `onPrepared` -> `SocketClient.startUdpTask()` is called
3. UDP socket opens to `192.168.1.1:7099`
4. `HeartBeatTask` starts: sends `{0x01, 0x01}` every **1000ms**
5. First video frame arrives -> UAV JNI sends `{0x64}` (100) to confirm stream active
6. `FlyController.setController(true)` -> 50ms control loop begins

Source: `SocketClient.java:131-143`, `UAV.java:235`

## Heartbeat Packet

Sent every **1000ms** via UDP to port 7099. Stops when video stream ends.

```text
{0x01, 0x01}   // 2 bytes
```

Source: `SocketClient.java:165-172` (`HeartBeatTask.run()`)

## Control Packet (9 bytes, WiFi/UDP path)

Sent every **50ms** regardless of joystick position. Timer is fixed - not event-driven.

The inner 8-byte core is assembled by `FlyController`, then `SocketClient` prepends a 1-byte WiFi prefix (`0x03`, `CTP_ID_FLYING`) before sending via UDP. Total over the wire: **9 bytes**.

```text
byte[0] = 0x03        WiFi path prefix - CTP_ID_FLYING (FlyCommand.java:74)
byte[1] = 0x66        header magic (102, fixed)
byte[2] = controlByte1    roll/pitch axis (1-255, neutral = 128)
byte[3] = controlByte2    pitch/roll axis (1-255, neutral = 128)
byte[4] = controlAccelerator  throttle   (1-255, neutral = 128)
byte[5] = controlTurn     yaw            (1-255, neutral = 128)
byte[6] = flags           mode bitmask (see below)
byte[7] = checksum        XOR of inner bytes 2-6
byte[8] = 0x99        tail magic  (153, fixed)
```

Source: `FlyController$FlyControlTask.smali` (array assembly) + `FlyCommand.java:74` (`CTP_ID_FLYING = "3"`)

**Axis value range:** 1-255. Values in range 0x68-0x98 (104-152) are snapped to 128 (dead-zone clamp). Values < 1 are clamped to 1, > 255 to 255. Source: `FlyController$FlyControlTask.smali:148-199`

**Checksum formula** (over the inner 8-byte core, bytes 1-5):

```text
checksum = controlByte1 ^ controlByte2 ^ controlAccelerator ^ controlTurn ^ (flags & 0xFF)
```

Source: `FlyController$FlyControlTask.smali:299-319` (XOR chain)

**Flags byte confirmed bit mapping** (resolved from `FlyController.smali` `access$` accessor order):

| Bit | Hex | Field | Meaning |
|-----|-----|-------|---------|
| 0 | 0x01 | `isFastFly` | **Takeoff / arm** - active ~1s, auto-reset via `Handler.postDelayed` |
| 1 | 0x02 | `isFastDrop` | **Land** - active ~1s, auto-reset |
| 2 | 0x04 | `isEmergencyStop` | Emergency stop - motors off immediately |
| 3 | 0x08 | `isCircleTurnEnd` | End of 360 deg flip sequence |
| 4 | 0x10 | `isNoHeadMode` | Headless / no-head mode toggle |
| 5 | 0x20 | `isFastReturn` OR `isUnLock` | Fast return home OR unlock |
| 7 | 0x80 | `isGyroCorrection` | Gyro calibration - active ~2s |

Source: `FlyController.smali:218-414` (accessor resolution)

**Hover / all-neutral packet (Python):**

```python
inner = bytes([0x66, 128, 128, 128, 128, 0x00, 0x00, 0x99])
# checksum = 128^128^128^128^0 = 0
packet = bytes([0x03]) + inner  # 9 bytes total
```

**Takeoff pulse (Python):**

```python
flags = 0x01  # isFastFly bit
checksum = 128 ^ 128 ^ 128 ^ 128 ^ flags  # = 0x01
inner = bytes([0x66, 128, 128, 128, 128, flags, checksum, 0x99])
packet = bytes([0x03]) + inner
# send once; drone arms for ~1 second
```

## Known Discrete Commands (Raw Bytes)

These are sent via the same UDP socket but are separate from the 50ms control loop:

| Command | Bytes | Source |
|---------|-------|--------|
| Heartbeat | `{0x01, 0x01}` | `SocketClient.java:171` |
| Switch camera (front) | `{0x06, 0x01}` | `SocketClient.java:228` |
| Switch camera (down) | `{0x06, 0x02}` | `SocketClient.java:227` |
| Stop controller | `{0x08, 0x01}` | `FlyController.java:70` |
| Battery status ACK low | `{0x09, 0x01}` | `DeviceBLFragment.java:1224` |
| Battery status ACK high | `{0x09, 0x02}` | `DeviceBLFragment.java:1239` |
| Stream confirm (JNI path) | `{0x64}` (100) | `UAV.java:235` |
| Stop control (JNI path) | `{0x65}` (101) | `FlyController.java:68` |

## Takeoff Command

**Resolved.** Takeoff = `isFastFly` flag = **bit 0 (0x01)** in the flags byte (byte[6] of the 9-byte packet). Set it to 1 for one control cycle (~50ms); the field auto-resets via `Handler.postDelayed` after ~1 second in the app.

`FlyCommand.CMD_TAKE_OFF = "0143"` is a dead constant - never called in any decompiled source.

Source: `FlyController.smali` accessor resolution, `FlyController.java:172-188` (`setFastFly` + `postDelayed` reset)

## Video Protocol

- **URL:** `rtsp://192.168.1.1:7070/webcam`
- **Decoder:** IjkPlayer (custom FFmpeg fork) - no separate `.so` needed
- **Codec:** MJPEG - confirmed by `mjpeg-pix-fmt=1` IjkMpOptions. `preferred-video-type=2` and `video-need-transcoding=1` also set.
- **Implication:** MJPEG = sequential JPEGs. Python reimplementation can parse frames without a hardware H.264 decoder.

Source: `SocketClient.java:102-120` (`applyOptionsToVideoView()`)

## Drone Telemetry (Inbound UDP)

The drone sends responses back on the same UDP socket (port 7099). Response buffer is allocated at 20 bytes. Known decoded fields:

| Byte offset | Meaning |
|-------------|---------|
| [0] | Resolution number / device capability byte |
| [1] | `switchCameraReset` flag (1 = needs RTSP restart, 2 = no restart) |
| [3] | Battery/status low byte (triggers `{0x09, 0x01}` if threshold met) |
| [4] | Battery/status high byte (triggers `{0x09, 0x02}` if threshold met) |

Source: `SocketClient.java:147-162`, `DeviceBLFragment.java:1215-1239`

## Related

- [[e88-drone]]
- [[com-cooingdv-rcfpv-v1-8-0]]
- [[24ghz-ism-band]]
- [[ijkplayer]]

## Sources

- [[com-cooingdv-rcfpv-v1-8-0]] - primary source; all protocol details derived from static analysis of this APK
