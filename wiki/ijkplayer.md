# IjkPlayer

> Bilibili's open-source Android/iOS video player based on FFmpeg; used by the E88 drone app to decode RTSP/MJPEG streams from the drone.

## Overview

IjkPlayer (`tv.danmaku.ijk.media`) is a custom FFmpeg-based media player developed by Bilibili. It is widely used in Chinese Android apps for video decoding, particularly for non-standard streams (RTSP, MJPEG, custom protocols) where the Android MediaPlayer API is insufficient.

In the [[e88-drone]] / [[com-cooingdv-rcfpv-v1-8-0]] context, IjkPlayer is used to decode the drone's RTSP video stream. The player is configured with specific options that reveal the video codec and stream characteristics.

## Key Claims

- **Used by:** [[com-cooingdv-rcfpv-v1-8-0]] for E88 FPV video streaming. Source: [[com-cooingdv-rcfpv-v1-8-0]]
- **Stream URL:** `rtsp://192.168.1.1:7070/webcam`. Source: [[com-cooingdv-rcfpv-v1-8-0]]
- **MJPEG mode enabled:** `mjpeg-pix-fmt=1` - confirms drone transmits MJPEG. Source: [[com-cooingdv-rcfpv-v1-8-0]]
- **Hardware decoding disabled:** `mediacodec=0` - software decode only. Source: [[com-cooingdv-rcfpv-v1-8-0]]
- **Transcoding enabled:** `video-need-transcoding=1`. Source: [[com-cooingdv-rcfpv-v1-8-0]]
- **x264 options set:** `x264-option-preset=0`, `tune=5`, `profile=1`, `crf=23` - suggests re-encoding capability. Source: [[com-cooingdv-rcfpv-v1-8-0]]

## Related

- [[e88-drone]]
- [[com-cooingdv-rcfpv-v1-8-0]]
- [[e88-udp-control-protocol]]

## Sources

- [[com-cooingdv-rcfpv-v1-8-0]] - reveals IjkPlayer configuration options used for E88 stream
