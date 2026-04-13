# E88 Drone

> Budget 2.4 GHz WiFi FPV quadcopter produced by Donghang Toy Factory, FCC-certified April 2024.

## Overview

The E88 is a toy-grade WiFi FPV quadcopter from [[donghang-toy-factory]] in [[chenghai-toy-manufacturing|Chenghai, Shantou]]. It is sold under various retail names emphasizing "1080p HD" or "4K" camera capability; the FCC filing does not verify camera specifications and those claims should be treated as unconfirmed marketing.

The drone's radio system uses a single 2.4 GHz WiFi transceiver for both RC control and FPV video downlink. The pilot connects a smartphone (or proprietary remote with phone holder) to the drone's WiFi hotspot (`192.168.1.1`) and uses a companion app for control and live video. Analysis of the decompiled companion app ([[com-cooingdv-rcfpv-v1-8-0]]) reveals the full control protocol: UDP on port 7099 for flight commands, RTSP on port 7070 for video (MJPEG codec). See [[e88-udp-control-protocol]] for the complete packet specification.

## Key Claims

- **FCC ID:** 2BFPZ-E88. Source: [[2bfpz-e88]]
- **Grantee code:** 2BFPZ = Shantou Chenghai District Donghang Toy Factory. Source: [[2bfpz-e88]]
- **Equipment class:** DXX - Part 15 Low Power Communication Device Transmitter. Source: [[2bfpz-e88]]
- **FCC Rule Part:** 15C (unlicensed spread spectrum / digitally modulated transmitter above 1 GHz). Source: [[2bfpz-e88]]
- **Operating frequency:** 2420-2460 MHz (40 MHz occupied bandwidth within the 2.4 GHz ISM band). Source: [[2bfpz-e88]]
- **Radio architecture:** Single 2.4 GHz WiFi radio; drone operates as WiFi access point for both control uplink and FPV video downlink. Source: [[2bfpz-e88]]
- **Test standard:** FCC §15.249 (intentional radiators in unlicensed 2400-2483.5 MHz band). Source: [[2bfpz-e88]]
- **FCC grant date:** 2024-04-17. Source: [[2bfpz-e88]]
- **Test firm:** Dongguan Yaxu (AiT) Technology Limited. Source: [[2bfpz-e88]]
- **TCB (Telecom Certification Body):** Eurofins Product Service GmbH, Germany. Source: [[2bfpz-e88]]
- **Confidential exhibits:** Schematic and block diagram filed under long-term FCC confidentiality - not publicly accessible. Source: [[2bfpz-e88]]
- **Public exhibits:** User manual, internal photos, external photos, RF exposure info, test reports, antenna spec, label/location info. Source: [[2bfpz-e88]]
- **Marketed specs (unverified):** 1080p HD / 4K camera, FPV WiFi, carrying bag included. Source: [[2bfpz-e88]]

## Radio Technical Detail

| Parameter | Value |
|-----------|-------|
| FCC ID | 2BFPZ-E88 |
| Frequency range | 2420-2460 MHz |
| Bandwidth | 40 MHz |
| ISM band coverage | Partial (full ISM: 2400-2483.5 MHz) |
| Protocol | WiFi (802.11 b/g/n, inferred from frequency + FPV architecture) |
| FCC rule part | 15C |
| Test standard | §15.249 |
| Modulation class | Spread spectrum / digital (Part 15C) |
| RF exposure | Filed separately (RF Exposure Info exhibit) |

## Related

- [[donghang-toy-factory]]
- [[chenghai-toy-manufacturing]]
- [[fcc-part-15c]]
- [[24ghz-ism-band]]
- [[e88-udp-control-protocol]]
- [[com-cooingdv-rcfpv-v1-8-0]]
- [[ijkplayer]]

## Sources

- [[2bfpz-e88]] - FCC equipment authorization filing; primary source of all verified radio and regulatory specs
- [[com-cooingdv-rcfpv-v1-8-0]] - decompiled companion app; source of UDP control protocol, packet structure, and video codec details
