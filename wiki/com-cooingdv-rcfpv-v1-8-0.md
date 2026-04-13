# RC FPV App - com.cooingdv.rcfpv v1.8.0 (Decompiled)

> Decompiled Android companion app for the E88 drone; source of the drone's UDP control protocol and video streaming implementation.

**Type:** misc  
**Date ingested:** 2026-04-13  
**Original file:** `sources/misc/code/com_cooingdv_rcfpv_v1.8.0/`

## Summary

`com.cooingdv.rcfpv` is the official Android companion app for [[e88-drone]] and compatible [[chenghai-toy-manufacturing|Chenghai-platform]] drones. The app connects to the drone's WiFi access point (`192.168.1.1`) and provides FPV video streaming, photo/video capture, and flight control. It was reverse engineered via APK decompilation (apktool + Jadx/CFR) and documented via the autoresearch:learn workflow.

The codebase splits into two concerns: a small, focused drone communication core (`socket/`, `tools/FlyController`, `tools/FlyCommand`) and a disproportionately large ad monetization layer (8 networks: AppLovin, IronSource, Pangle, Facebook AN, Vungle, Amazon APS, Mintegral, Bigo). For protocol reverse engineering, only the drone core is relevant.

Key source files:

- `code/sources/com/cooingdv/rcfpv/socket/Config.java` - all network constants
- `code/sources/com/cooingdv/rcfpv/socket/SocketClient.java` - connection lifecycle, heartbeat, video
- `code/sources/com/cooingdv/rcfpv/socket/UdpComm.java` - UDP send/receive threading
- `code/sources/com/cooingdv/rcfpv/tools/FlyCommand.java` - command constant definitions
- `code/sources/com/cooingdv/rcfpv/tools/FlyController.java` - joystick loop and packet builder
- `apktool_out/smali_classes2/com/cooingdv/rcfpv/tools/FlyController$FlyControlTask.smali` - full packet assembly (Java decompile failed here)
- `code/sources/com/cooingdv/bl60xmjpeg/UAV.java` - JNI path for alternate device types

## Key Takeaways

- The drone control protocol runs over UDP to port 7099 on 192.168.1.1; all flight commands are 8-byte packets sent at 50ms intervals regardless of joystick state
- Video is RTSP at `rtsp://192.168.1.1:7070/webcam` decoded by IjkPlayer (custom FFmpeg); MJPEG options explicitly enabled - not H.264
- The app is aggressively monetized with 8 ad networks; entirely irrelevant to protocol reimplementation

## Topics Covered

- [[e88-drone]]
- [[e88-udp-control-protocol]]
- [[chenghai-toy-manufacturing]]
- [[ijkplayer]]
