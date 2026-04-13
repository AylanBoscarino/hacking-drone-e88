"""
Holy Stone HS175D (E88) — Controlador WiFi
Protocolo reconstruído via engenharia reversa do APK com.cooingdv.rcfpv v1.8.0

Uso:
  1. Conecte-se ao WiFi do drone
  2. python drone_controller.py
"""

from datetime import datetime
from pathlib import Path
import socket
import threading
import time

# ── Configuração ──────────────────────────────────────────────────────────────

DRONE_IP = "192.168.1.1"
CMD_PORT = 7099
RTSP_URL = "rtsp://192.168.1.1:7070/webcam"

HEADER = 0x66
FOOTER = 0x99
CTP_ID_FLYING = 0x03  # prefixo WiFi (FlyCommand.CTP_ID_FLYING = "3")
NEUTRAL = 0x80  # 128 = centro/hover

# Dead zone: valores entre 0x68 e 0x98 são forçados para 0x80
DEADZONE_LOW = 0x68   # 104
DEADZONE_HIGH = 0x98  # 152

# Intervalos
CONTROL_INTERVAL = 0.050  # 50ms
HEARTBEAT_INTERVAL = 1.0  # 1s
REPORTS_DIR = Path("flight_reports")
RX_VERBOSE = True

# ── Flags (byte 6) ───────────────────────────────────────────────────────────

FLAG_FAST_FLY       = 0x01  # bit 0 — decolagem/subida rápida
FLAG_FAST_DROP      = 0x02  # bit 1 — descida rápida / pouso
FLAG_EMERGENCY_STOP = 0x04  # bit 2 — parada de emergência
FLAG_CIRCLE_END     = 0x08  # bit 3 — fim do giro 360°
FLAG_HEADLESS       = 0x10  # bit 4 — modo sem cabeça
FLAG_UNLOCK         = 0x20  # bit 5 — unlock / return-to-home
FLAG_GYRO_CAL       = 0x80  # bit 7 — calibração do giroscópio


# ── Funções do Protocolo ─────────────────────────────────────────────────────

def apply_deadzone(value: int) -> int:
    """Aplica a dead zone do controle: valores próximos do centro viram 128."""
    if DEADZONE_LOW <= value <= DEADZONE_HIGH:
        return NEUTRAL
    return max(1, min(255, value))


def apply_trim(value: int, trim_steps: int) -> int:
    """Aplica trim em cima do eixo ja neutralizado pela dead zone."""
    return max(1, min(255, value + trim_steps * 2))


def build_control_packet(
    roll: int = NEUTRAL,
    pitch: int = NEUTRAL,
    throttle: int = NEUTRAL,
    yaw: int = NEUTRAL,
    flags: int = 0x00,
    preprocess_axes: bool = True,
) -> bytes:
    """
    Monta o pacote de controle de 9 bytes para envio via WiFi/UDP.

    Formato: [CTP_ID, HEADER, ROLL, PITCH, THROTTLE, YAW, FLAGS, CHECKSUM, FOOTER]

    Ordem dos bytes internos (do Smali):
      byte[0] = 0x66 (header)
      byte[1] = controlByte1  (roll)
      byte[2] = controlByte2  (pitch)
      byte[3] = controlAccelerator (throttle)  ← wiki tinha trocado com byte[4]
      byte[4] = controlTurn (yaw)
      byte[5] = flags
      byte[6] = checksum
      byte[7] = 0x99 (footer)

    O SocketClient prefixa com CTP_ID_FLYING=3 → 9 bytes total.
    """
    if preprocess_axes:
        roll = apply_deadzone(roll)
        pitch = apply_deadzone(pitch)
        yaw = apply_deadzone(yaw)
    throttle = max(0, min(255, throttle))
    flags = flags & 0xFF

    checksum = roll ^ pitch ^ throttle ^ yaw ^ flags

    return bytes([
        CTP_ID_FLYING,
        HEADER,
        roll,
        pitch,
        throttle,
        yaw,
        flags,
        checksum,
        FOOTER,
    ])


def build_heartbeat() -> bytes:
    """Pacote de heartbeat para manter a conexão viva."""
    return bytes([0x01, 0x01])


def build_simple_command(cmd: int, arg: int) -> bytes:
    """Comando simples de 2 bytes."""
    return bytes([cmd, arg])


def format_bytes(data: bytes) -> str:
    """Renderiza um pacote como hex separado por espaços."""
    return data.hex(" ")


class FlightReport:
    """Persistência simples de um relatório de voo por execução."""

    def __init__(self, base_dir: Path = REPORTS_DIR):
        self.started_at = datetime.now().astimezone()
        self._started_monotonic = time.monotonic()
        self._lock = threading.Lock()

        report_dir = base_dir / self.started_at.strftime("%Y-%m-%d")
        report_dir.mkdir(parents=True, exist_ok=True)
        self.path = report_dir / f"flight_{self.started_at.strftime('%H-%M-%S')}.txt"
        self._fh = self.path.open("a", encoding="utf-8", buffering=1)

        self.control_packets_sent = 0
        self.control_state_changes = 0
        self.heartbeats_sent = 0
        self.simple_commands_sent = 0
        self.recv_packets = 0
        self.recv_unique_packets = 0
        self.commands_issued = 0

    def _timestamp(self) -> str:
        return datetime.now().astimezone().isoformat(timespec="milliseconds")

    def log(self, level: str, event: str, message: str = "", **fields):
        parts = [self._timestamp(), level, event]
        if message:
            parts.append(message)
        for key, value in fields.items():
            parts.append(f"{key}={value}")
        line = " | ".join(parts)
        with self._lock:
            self._fh.write(line + "\n")

    def log_session_start(self, ip: str, port: int, rtsp_url: str):
        self.log(
            "INFO",
            "session_start",
            "Controlador iniciado",
            drone_ip=ip,
            cmd_port=port,
            rtsp_url=rtsp_url,
            report_path=self.path,
        )

    def log_control_packet(self, packet: bytes, **state):
        self.control_packets_sent += 1
        self.control_state_changes += 1
        self.log("TX", "control_packet", raw=format_bytes(packet), **state)

    def count_control_packet(self):
        self.control_packets_sent += 1

    def log_heartbeat(self, packet: bytes):
        self.heartbeats_sent += 1
        if self.heartbeats_sent == 1:
            self.log("TX", "heartbeat_start", raw=format_bytes(packet))

    def log_simple_command(self, packet: bytes, description: str):
        self.simple_commands_sent += 1
        self.log("TX", "simple_command", description, raw=format_bytes(packet))

    def log_recv(self, packet: bytes, addr, repeated: bool):
        self.recv_packets += 1
        if not repeated:
            self.recv_unique_packets += 1
        self.log(
            "RX",
            "udp_packet",
            raw=format_bytes(packet),
            source=f"{addr[0]}:{addr[1]}",
            repeated=str(repeated).lower(),
        )

    def log_command(self, name: str, **state):
        self.commands_issued += 1
        self.log("CMD", name, **state)

    def log_error(self, message: str, **fields):
        self.log("ERROR", "runtime_error", message, **fields)

    def close(self):
        duration = time.monotonic() - self._started_monotonic
        self.log(
            "INFO",
            "session_end",
            "Controlador finalizado",
            duration_s=f"{duration:.2f}",
            control_packets_sent=self.control_packets_sent,
            control_state_changes=self.control_state_changes,
            heartbeats_sent=self.heartbeats_sent,
            simple_commands_sent=self.simple_commands_sent,
            recv_packets=self.recv_packets,
            recv_unique_packets=self.recv_unique_packets,
            commands_issued=self.commands_issued,
        )
        with self._lock:
            self._fh.close()


# ── Classe Principal ─────────────────────────────────────────────────────────

class DroneController:
    """Controlador do drone HS175D via UDP."""

    def __init__(self, ip: str = DRONE_IP, port: int = CMD_PORT):
        self.ip = ip
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(2.0)
        self.report = FlightReport()

        # Estado dos eixos
        self.roll = NEUTRAL
        self.pitch = NEUTRAL
        self.throttle = NEUTRAL
        self.yaw = NEUTRAL
        self.flags = 0x00

        # Trim — offsets somados ao valor neutro (range -12 a +12)
        self.trim_roll = 0
        self.trim_pitch = 0
        self.trim_yaw = 0
        self.trim_throttle = 0

        # Telemetria
        self._last_recv = None
        self._last_control_packet = None
        self._last_logged_state = None
        self._report_closed = False

        # Threads
        self._running = False
        self._control_thread = None
        self._heartbeat_thread = None
        self._recv_thread = None

    def _snapshot(self):
        """Estado atual para log e inspeção."""
        effective_roll = apply_trim(apply_deadzone(self.roll), self.trim_roll)
        effective_pitch = apply_trim(apply_deadzone(self.pitch), self.trim_pitch)
        effective_throttle = max(0, min(255, self.throttle + self.trim_throttle * 2))
        effective_yaw = apply_trim(apply_deadzone(self.yaw), self.trim_yaw)
        return {
            "roll": self.roll,
            "pitch": self.pitch,
            "throttle": self.throttle,
            "yaw": self.yaw,
            "flags": f"0x{self.flags:02x}",
            "trim_roll": self.trim_roll,
            "trim_pitch": self.trim_pitch,
            "trim_throttle": self.trim_throttle,
            "trim_yaw": self.trim_yaw,
            "effective_roll": effective_roll,
            "effective_pitch": effective_pitch,
            "effective_throttle": effective_throttle,
            "effective_yaw": effective_yaw,
        }

    def send(self, data: bytes):
        """Envia bytes crus para o drone."""
        self.sock.sendto(data, (self.ip, self.port))

    def send_control(self):
        """Envia o pacote de controle atual, aplicando trim."""
        effective_roll = apply_trim(apply_deadzone(self.roll), self.trim_roll)
        effective_pitch = apply_trim(apply_deadzone(self.pitch), self.trim_pitch)
        effective_throttle = max(0, min(255, self.throttle + self.trim_throttle * 2))
        effective_yaw = apply_trim(apply_deadzone(self.yaw), self.trim_yaw)

        pkt = build_control_packet(
            effective_roll,
            effective_pitch,
            effective_throttle,
            effective_yaw,
            self.flags,
            preprocess_axes=False,
        )
        self.send(pkt)
        state = self._snapshot()

        if pkt != self._last_control_packet:
            self.report.log_control_packet(pkt, **state)
            self._last_control_packet = pkt
            self._last_logged_state = state
        else:
            self.report.count_control_packet()

    # ── Loop de Controle ─────────────────────────────────────────────────

    def _control_loop(self):
        """Envia comandos de controle a cada 50ms."""
        while self._running:
            self.send_control()
            time.sleep(CONTROL_INTERVAL)

    def _heartbeat_loop(self):
        """Envia heartbeat a cada 1s."""
        while self._running:
            packet = build_heartbeat()
            self.send(packet)
            self.report.log_heartbeat(packet)
            time.sleep(HEARTBEAT_INTERVAL)

    def _recv_loop(self):
        """Recebe respostas do drone (max 20 bytes, como no app original).
        Em modo verbose, registra tambem pacotes repetidos."""
        while self._running:
            try:
                data, addr = self.sock.recvfrom(20)
                repeated = data == self._last_recv
                if RX_VERBOSE or not repeated:
                    self.report.log_recv(data, addr, repeated=repeated)
                self._last_recv = data
            except socket.timeout:
                pass
            except OSError:
                break

    # ── Controle de Lifecycle ────────────────────────────────────────────

    def start(self):
        """Inicia os loops de heartbeat, controle e recepção."""
        if self._running:
            return
        self._running = True
        self.report.log_session_start(self.ip, self.port, RTSP_URL)

        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True
        )
        self._control_thread = threading.Thread(
            target=self._control_loop, daemon=True
        )
        self._recv_thread = threading.Thread(
            target=self._recv_loop, daemon=True
        )

        self._heartbeat_thread.start()
        self._control_thread.start()
        self._recv_thread.start()
        print(f"[INFO] Controlador iniciado -> {self.ip}:{self.port}")
        print(f"[INFO] Relatorio de voo -> {self.report.path}")

    def stop(self):
        """Para todos os loops e envia comando de desconexão."""
        if self._report_closed:
            return

        self._running = False
        packet = build_simple_command(0x08, 0x01)
        try:
            self.send(packet)  # desconectar
            self.report.log_simple_command(packet, "disconnect")
        except OSError as exc:
            self.report.log_error("Falha ao enviar comando de desconexao", error=str(exc))
        try:
            self.sock.close()
        finally:
            self.report.close()
            self._report_closed = True
        print("[INFO] Controlador parado.")

    # ── Comandos de Alto Nível ───────────────────────────────────────────

    def hover(self):
        """Todos os eixos em neutro — drone mantém posição."""
        self.roll = NEUTRAL
        self.pitch = NEUTRAL
        self.throttle = NEUTRAL
        self.yaw = NEUTRAL
        self.flags = 0x00
        self.report.log_command("hover", **self._snapshot())

    def takeoff(self):
        """Seta flag de decolagem (isFastFly). O app seta por ~1s."""
        self.flags |= FLAG_FAST_FLY
        print("[CMD] Takeoff!")
        self.report.log_command("takeoff", **self._snapshot())
        # Reset da flag após 1 segundo (como o app faz)
        threading.Timer(1.0, self._clear_flag, args=[FLAG_FAST_FLY]).start()

    def land(self):
        """Seta flag de descida rápida (isFastDrop). O app seta por ~1s."""
        self.flags |= FLAG_FAST_DROP
        print("[CMD] Landing!")
        self.report.log_command("land", **self._snapshot())
        threading.Timer(1.0, self._clear_flag, args=[FLAG_FAST_DROP]).start()

    def emergency_stop(self):
        """Parada de emergência — desliga motores."""
        self.flags |= FLAG_EMERGENCY_STOP
        print("[CMD] EMERGENCY STOP!")
        self.report.log_command("emergency_stop", **self._snapshot())
        threading.Timer(1.0, self._clear_flag, args=[FLAG_EMERGENCY_STOP]).start()

    def calibrate_gyro(self):
        """Calibração do giroscópio."""
        self.flags |= FLAG_GYRO_CAL
        print("[CMD] Gyro calibration")
        self.report.log_command("calibrate_gyro", **self._snapshot())
        threading.Timer(2.0, self._clear_flag, args=[FLAG_GYRO_CAL]).start()

    def set_throttle(self, value: int):
        """Define o throttle (0=descer máx, 128=hover, 255=subir máx)."""
        self.throttle = max(0, min(255, value))
        self.report.log_command("set_throttle", **self._snapshot())

    def set_yaw(self, value: int):
        """Define o yaw (1=esquerda máx, 128=centro, 255=direita máx)."""
        self.yaw = max(1, min(255, value))
        self.report.log_command("set_yaw", **self._snapshot())

    def set_pitch(self, value: int):
        """Define o pitch (1=trás máx, 128=centro, 255=frente máx)."""
        self.pitch = max(1, min(255, value))
        self.report.log_command("set_pitch", **self._snapshot())

    def set_roll(self, value: int):
        """Define o roll (1=esquerda máx, 128=centro, 255=direita máx)."""
        self.roll = max(1, min(255, value))
        self.report.log_command("set_roll", **self._snapshot())

    def switch_camera(self, front: bool = True):
        """Troca entre câmera frontal e inferior."""
        packet = build_simple_command(0x06, 0x01 if front else 0x02)
        if front:
            self.send(packet)
        else:
            self.send(packet)
        self.report.log_simple_command(packet, f"switch_camera:{'front' if front else 'bottom'}")

    def _clear_flag(self, flag: int):
        """Remove uma flag após o timeout."""
        self.flags &= ~flag
        self.report.log_command("clear_flag", cleared=f"0x{flag:02x}", **self._snapshot())


# ── CLI Interativo ───────────────────────────────────────────────────────────

def print_help():
    print("""
╔══════════════════════════════════════════════════╗
║  HS175D Drone Controller — Comandos              ║
╠══════════════════════════════════════════════════╣
║  t        — Takeoff (decolagem)                  ║
║  l        — Land (pouso)                         ║
║  e        — Emergency Stop                       ║
║  g        — Calibrar giroscópio                  ║
║  h        — Hover (todos eixos neutros)          ║
║  w/s      — Pitch frente/trás                    ║
║  a/d      — Roll esquerda/direita                ║
║  q/r      — Yaw esquerda/direita                 ║
║  u/j      — Throttle sobe/desce                  ║
║  c        — Trocar câmera                        ║
║  p        — Mostrar estado atual                  ║
║  x        — Sair                                  ║
║  ?        — Mostrar esta ajuda                    ║
╠══════════════════════════════════════════════════╣
║  TRIM (compensa drift, persiste entre comandos)  ║
║  tr+/tr-  — Trim roll  (esq/dir)                ║
║  tp+/tp-  — Trim pitch (frente/trás)            ║
║  ty+/ty-  — Trim yaw   (giro)                   ║
║  tt+/tt-  — Trim throttle (sobe/desce)           ║
║  tr0      — Reset todos os trims                 ║
╚══════════════════════════════════════════════════╝
""")


def main():
    drone = DroneController()
    camera_front = True

    print("═" * 50)
    print("  HS175D Drone Controller")
    print("  Conecte-se ao WiFi do drone antes de começar!")
    print("═" * 50)
    print_help()

    drone.start()

    step = 30  # incremento para cada pressionamento

    try:
        while True:
            cmd = input("> ").strip().lower()

            if cmd == "t":
                drone.takeoff()
            elif cmd == "l":
                drone.land()
            elif cmd == "e":
                drone.emergency_stop()
            elif cmd == "g":
                drone.calibrate_gyro()
            elif cmd == "h":
                drone.hover()
                print("[CMD] Hover")
            elif cmd == "w":
                drone.set_pitch(min(255, drone.pitch + step))
                print(f"[CMD] Pitch → {drone.pitch}")
            elif cmd == "s":
                drone.set_pitch(max(1, drone.pitch - step))
                print(f"[CMD] Pitch → {drone.pitch}")
            elif cmd == "a":
                drone.set_roll(max(1, drone.roll - step))
                print(f"[CMD] Roll → {drone.roll}")
            elif cmd == "d":
                drone.set_roll(min(255, drone.roll + step))
                print(f"[CMD] Roll → {drone.roll}")
            elif cmd == "q":
                drone.set_yaw(max(1, drone.yaw - step))
                print(f"[CMD] Yaw → {drone.yaw}")
            elif cmd == "r":
                drone.set_yaw(min(255, drone.yaw + step))
                print(f"[CMD] Yaw → {drone.yaw}")
            elif cmd == "u":
                drone.set_throttle(min(255, drone.throttle + step))
                print(f"[CMD] Throttle → {drone.throttle}")
            elif cmd == "j":
                drone.set_throttle(max(0, drone.throttle - step))
                print(f"[CMD] Throttle → {drone.throttle}")
            elif cmd == "c":
                camera_front = not camera_front
                drone.switch_camera(camera_front)
                print(f"[CMD] Camera → {'frontal' if camera_front else 'inferior'}")
            elif cmd == "p":
                effective_roll = apply_trim(apply_deadzone(drone.roll), drone.trim_roll)
                effective_pitch = apply_trim(apply_deadzone(drone.pitch), drone.trim_pitch)
                effective_throttle = max(
                    0, min(255, drone.throttle + drone.trim_throttle * 2)
                )
                effective_yaw = apply_trim(apply_deadzone(drone.yaw), drone.trim_yaw)
                pkt = build_control_packet(
                    effective_roll,
                    effective_pitch,
                    effective_throttle,
                    effective_yaw,
                    drone.flags,
                    preprocess_axes=False,
                )
                print(f"  Roll={drone.roll} Pitch={drone.pitch} "
                      f"Throttle={drone.throttle} Yaw={drone.yaw} "
                      f"Flags=0x{drone.flags:02x}")
                print(f"  Trim: R={drone.trim_roll:+d} P={drone.trim_pitch:+d} "
                      f"T={drone.trim_throttle:+d} Y={drone.trim_yaw:+d}")
                print(f"  Packet: {pkt.hex(' ')}")
                drone.report.log_command("print_status", packet=format_bytes(pkt), **drone._snapshot())
            # ── Trim commands ────────────────────────────────────────
            elif cmd == "tr+":
                drone.trim_roll = min(12, drone.trim_roll + 1)
                print(f"[TRIM] Roll = {drone.trim_roll:+d}")
                drone.report.log_command("trim_roll_up", **drone._snapshot())
            elif cmd == "tr-":
                drone.trim_roll = max(-12, drone.trim_roll - 1)
                print(f"[TRIM] Roll = {drone.trim_roll:+d}")
                drone.report.log_command("trim_roll_down", **drone._snapshot())
            elif cmd == "tp+":
                drone.trim_pitch = min(12, drone.trim_pitch + 1)
                print(f"[TRIM] Pitch = {drone.trim_pitch:+d}")
                drone.report.log_command("trim_pitch_up", **drone._snapshot())
            elif cmd == "tp-":
                drone.trim_pitch = max(-12, drone.trim_pitch - 1)
                print(f"[TRIM] Pitch = {drone.trim_pitch:+d}")
                drone.report.log_command("trim_pitch_down", **drone._snapshot())
            elif cmd == "ty+":
                drone.trim_yaw = min(12, drone.trim_yaw + 1)
                print(f"[TRIM] Yaw = {drone.trim_yaw:+d}")
                drone.report.log_command("trim_yaw_up", **drone._snapshot())
            elif cmd == "ty-":
                drone.trim_yaw = max(-12, drone.trim_yaw - 1)
                print(f"[TRIM] Yaw = {drone.trim_yaw:+d}")
                drone.report.log_command("trim_yaw_down", **drone._snapshot())
            elif cmd == "tt+":
                drone.trim_throttle = min(12, drone.trim_throttle + 1)
                print(f"[TRIM] Throttle = {drone.trim_throttle:+d}")
                drone.report.log_command("trim_throttle_up", **drone._snapshot())
            elif cmd == "tt-":
                drone.trim_throttle = max(-12, drone.trim_throttle - 1)
                print(f"[TRIM] Throttle = {drone.trim_throttle:+d}")
                drone.report.log_command("trim_throttle_down", **drone._snapshot())
            elif cmd == "tr0":
                drone.trim_roll = 0
                drone.trim_pitch = 0
                drone.trim_yaw = 0
                drone.trim_throttle = 0
                print("[TRIM] Todos os trims resetados")
                drone.report.log_command("trim_reset", **drone._snapshot())
            elif cmd == "x":
                break
            elif cmd == "?":
                print_help()
            elif cmd == "":
                pass
            else:
                print(f"Comando desconhecido: '{cmd}'. Digite '?' para ajuda.")
                drone.report.log_command("unknown_command", raw=cmd)

    except KeyboardInterrupt:
        print("\n[INFO] Ctrl+C detectado")
        drone.report.log_command("keyboard_interrupt")
    finally:
        drone.stop()


if __name__ == "__main__":
    main()
