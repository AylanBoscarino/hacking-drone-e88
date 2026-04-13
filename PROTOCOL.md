# Holy Stone HS175D (E88) — Protocolo de Controle WiFi

## Conexão

| Parâmetro       | Valor                              |
| --------------- | ---------------------------------- |
| Rede WiFi       | AP criado pelo drone               |
| IP do Drone     | `192.168.1.1`                      |
| Porta Comando   | `7099/UDP`                         |
| Porta Vídeo     | `7070/TCP (RTSP)`                  |
| URL Vídeo       | `rtsp://192.168.1.1:7070/webcam`   |
| FTP             | `ftp://ftp:ftp@192.168.1.1/0/`     |
| Fotos HTTP      | `http://192.168.1.1/PHOTO/O/{name}`|

## Pacote de Controle de Voo (9 bytes via WiFi)

O app Android usa a classe `SocketClient` que encapsula os 8 bytes de voo num pacote de 9 bytes:

```
Índice:  [0]    [1]    [2]    [3]    [4]    [5]    [6]    [7]    [8]
Campo:   CTP_ID HEADER ROLL   PITCH  THROT  YAW    FLAGS  CHKSUM FOOTER
Hex:     0x03   0x66   ...    ...    ...    ...    ...    ...    0x99
```

### Detalhes de cada byte

| Byte | Nome     | Valor Padrão | Range   | Descrição                                  |
| ---- | -------- | ------------ | ------- | ------------------------------------------ |
| 0    | CTP_ID   | `0x03`       | fixo    | CTP_ID_FLYING — prefixo WiFi (FlyCommand.java:74) |
| 1    | HEADER   | `0x66`       | fixo    | Marcador de início do pacote (102 dec)     |
| 2    | ROLL     | `0x80` (128) | 1–255   | Eixo lateral (esq/dir). 128=centro         |
| 3    | PITCH    | `0x80` (128) | 1–255   | Eixo frontal (frente/trás). 128=centro     |
| 4    | THROTTLE | `0x80` (128) | 0–255   | Acelerador (sobe/desce). 128=hover         |
| 5    | YAW      | `0x80` (128) | 1–255   | Rotação (giro esq/dir). 128=centro         |
| 6    | FLAGS    | `0x00`       | bitmask | Flags de ação especial (ver abaixo)        |
| 7    | CHECKSUM | calculado    | 0–255   | XOR dos bytes 2–6                          |
| 8    | FOOTER   | `0x99`       | fixo    | Marcador de fim do pacote (153 dec)        |

### Dead Zone (Roll/Pitch/Yaw)

Se o valor estiver entre `0x68` (104) e `0x98` (152), é forçado para `0x80` (128 = centro).
Valores fora desse range são enviados como estão (clamped a 1–255).

### Throttle (Byte 4 — controlAccelerator)

Se `controlAccelerator == 1`, é resetado para `0` no próximo tick.
Fora isso, clamped a 0–255.

### FLAGS (Byte 6 — Bitmask)

| Bit  | Valor | Flag              | Descrição                         |
| ---- | ----- | ----------------- | --------------------------------- |
| 0    | 0x01  | isFastFly         | Decolagem/subida rápida           |
| 1    | 0x02  | isFastDrop        | Descida rápida                    |
| 2    | 0x04  | isEmergencyStop   | Parada de emergência (kill motors)|
| 3    | 0x08  | isCircleTurnEnd   | Fim do giro 360°                  |
| 4    | 0x10  | isNoHeadMode      | Modo sem cabeça (headless)        |
| 5    | 0x20  | isFastReturn/isUnLock | Return-to-home OU unlock      |
| 6    | —     | (não usado)       |                                   |
| 7    | 0x80  | isGyroCorrection  | Calibração do giroscópio          |

### Checksum (Byte 7)

```
checksum = ROLL ^ PITCH ^ THROTTLE ^ YAW ^ (FLAGS & 0xFF)
```

## Heartbeat

Enquanto conectado, o app envia `[0x01, 0x01]` a cada **1000ms** para manter a conexão viva.

## Outros Comandos (2 bytes)

| Bytes        | Ação                          |
| ------------ | ----------------------------- |
| `[0x01, 0x01]` | Heartbeat                  |
| `[0x06, 0x01]` | Trocar para câmera frontal |
| `[0x06, 0x02]` | Trocar para câmera inferior|
| `[0x08, 0x01]` | Desconectar controle       |
| `[0x09, 0x01]` | Ack foto tirada            |
| `[0x09, 0x02]` | Ack vídeo gravado          |

## Telemetria / Feedback Externo

### Retorno UDP observado

Nos voos instrumentados até agora, o drone respondeu repetidamente com:

```text
48 02 00 00 00
```

Características observadas:

- Mesmo payload em todos os pacotes RX capturados
- Cadência aproximada de `~50-55ms` entre respostas (`~18-20 Hz`)
- Sem mudança visível durante `takeoff`, `land`, `gyro calibration` ou comandos de eixo

Conclusão prática:

- Esse retorno **não se comporta como telemetria rica**
- Ele parece ser apenas um **ack / keepalive / status mínimo de link**
- Isto é uma **inferência baseada nas capturas**, não uma prova formal do significado semântico do payload

### Sensores disponíveis para o controlador externo

Até o momento, para um controlador rodando no computador:

- **Vídeo RTSP** é o único feedback sensorial útil exposto externamente
- **UDP RX** serve como indicação de que o link está vivo, mas não expõe atitude, altitude, bateria ou estado de voo útil

Observação:

- O drone quase certamente possui sensores internos (por exemplo IMU/giroscópio), pois aceita comando de calibração e realiza estabilização básica
- Porém, **esses sensores não parecem ser exportados** pelo protocolo WiFi observado até agora

## Sequência de Inicialização (do código)

1. Conectar ao WiFi do drone
2. Abrir stream RTSP em `rtsp://192.168.1.1:7070/webcam`
3. Ao receber `onPrepared` do player, iniciar `UdpComm` na porta 7099
4. Começar heartbeat (`[0x01, 0x01]` a cada 1s)
5. Começar loop de controle (pacote de 9 bytes a cada 50ms)

## Notas

- O drone tem dois caminhos de comunicação: **WiFi** (SocketClient) e **BLE** (UAV/GLJni/TCJni)
- No caminho WiFi, o pacote de 8 bytes é prefixado com `CTP_ID_FLYING=0x03` resultando em 9 bytes
- No caminho BLE, os 8 bytes são enviados diretamente (sem CMD_ID prefix)
- A decolagem usa flag `isFastFly` (bit 0 = 0x01) — não é um comando separado
- O app não parece ter um handshake obrigatório antes de enviar comandos
