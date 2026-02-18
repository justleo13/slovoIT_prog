import sys
import os
import socket
import threading
import zipfile
import time
from pathlib import Path
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

PORT = 50505
BUFFER = 65536

# =====================
# Helpers
# =====================

def zip_folder(folder):
    zip_name = folder + ".zip"
    with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(folder):
            for f in files:
                fp = os.path.join(root, f)
                z.write(fp, os.path.relpath(fp, folder))
    return zip_name

def get_hostname():
    return socket.gethostname()

# =====================
# Network Discovery
# =====================

def discover_devices(timeout=0.5):
    found = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)
    try:
        sock.sendto(b"SLOVO_DISCOVER", ("255.255.255.255", PORT))
        while True:
            data, addr = sock.recvfrom(1024)
            found.append((data.decode(), addr[0]))
    except:
        pass
    return found

class DiscoverServer(threading.Thread):
    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("", PORT))
        hostname = get_hostname().encode()
        while True:
            data, addr = sock.recvfrom(1024)
            if data == b"SLOVO_DISCOVER":
                sock.sendto(hostname, addr)

# =====================
# File Receiver
# =====================

class Receiver(QThread):
    progress = Signal(int)
    speed = Signal(str)
    log = Signal(str)

    def run(self):
        server = socket.socket()
        server.bind(("", PORT+1))
        server.listen(1)
        downloads = Path.home() / "Downloads"

        while True:
            conn, addr = server.accept()
            self.log.emit(f"📥 Подключение: {addr[0]}")

            header = conn.recv(1024).decode().split("|")
            filename = header[0]
            size = int(header[1])

            filepath = downloads / filename
            received = 0
            start = time.time()

            with open(filepath, "wb") as f:
                while received < size:
                    chunk = conn.recv(BUFFER)
                    f.write(chunk)
                    received += len(chunk)
                    self.progress.emit(int(received/size*100))
                    spd = received / (time.time()-start+0.001)
                    self.speed.emit(f"{spd/1024/1024:.2f} MB/s")

            # распаковка, если это архив папки
            if filename.endswith(".zip"):
                import shutil
                shutil.unpack_archive(filepath, downloads)
                os.remove(filepath)

            self.log.emit(f"✅ Сохранено: {filename}")
            self.progress.emit(0)
            conn.close()

# =====================
# File Sender
# =====================

class Sender(QThread):
    progress = Signal(int)
    speed = Signal(str)
    log = Signal(str)

    def __init__(self, ip, path):
        super().__init__()
        self.ip = ip
        self.path = path

    def run(self):
        path = self.path
        if os.path.isdir(path):
            path = zip_folder(path)

        size = os.path.getsize(path)
        name = os.path.basename(path)

        sock = socket.socket()
        try:
            sock.connect((self.ip, PORT+1))
        except:
            self.log.emit("❌ Получатель не найден")
            return

        sock.send(f"{name}|{size}".encode())

        sent = 0
        start = time.time()

        with open(path, "rb") as f:
            while True:
                chunk = f.read(BUFFER)
                if not chunk:
                    break
                sock.send(chunk)
                sent += len(chunk)
                self.progress.emit(int(sent/size*100))
                spd = sent / (time.time()-start+0.001)
                self.speed.emit(f"{spd/1024/1024:.2f} MB/s")

        sock.close()
        self.log.emit(f"✅ Отправлено: {name}")

# =====================
# GUI
# =====================

class SlovoIT(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("slovoIT")
        self.setMinimumSize(550, 450)
        self.setAcceptDrops(True)

        layout = QVBoxLayout()
        layout.setSpacing(12)

        # Title
        self.title = QLabel(f"🌐 slovoIT  |  Host: {get_hostname()}")
        self.title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title)

        # Device list
        self.devices = QComboBox()
        layout.addWidget(self.devices)

        self.btn_scan = QPushButton("🔍 Найти устройства")
        self.btn_file = QPushButton("📄 Отправить файл")
        self.btn_folder = QPushButton("📁 Отправить папку")

        layout.addWidget(self.btn_scan)
        layout.addWidget(self.btn_file)
        layout.addWidget(self.btn_folder)

        self.progress = QProgressBar()
        self.speed = QLabel("0 MB/s")
        self.log = QTextEdit()
        self.log.setReadOnly(True)

        layout.addWidget(self.progress)
        layout.addWidget(self.speed)
        layout.addWidget(self.log)

        self.setLayout(layout)

        # Signals
        self.btn_scan.clicked.connect(self.scan_devices)
        self.btn_file.clicked.connect(self.send_file)
        self.btn_folder.clicked.connect(self.send_folder)

        # Start discovery server & receiver
        DiscoverServer().start()
        self.receiver = Receiver()
        self.receiver.progress.connect(self.progress.setValue)
        self.receiver.speed.connect(self.speed.setText)
        self.receiver.log.connect(self.log.append)
        self.receiver.start()

        # Style mac-like
        self.setStyleSheet("""
QWidget { 
    background:#1E1E1E; 
    color:#EEEEEE; 
    font-size:14px; 
    font-family: "Segoe UI", "San Francisco", sans-serif;
}

QPushButton { 
    background:#2A2A2A; 
    border:1px solid #444444; 
    padding:12px; 
    border-radius:15px; 
    color:#FFFFFF;
}

QPushButton:hover { 
    background:#3A3A3A; 
}

QComboBox, QProgressBar { 
    background:#2A2A2A; 
    border:1px solid #444444; 
    border-radius:12px; 
    padding:6px; 
    color:#FFFFFF;
}

QProgressBar::chunk { 
    background:#0A84FF; 
    border-radius:10px;
}

QTextEdit { 
    background:#2A2A2A; 
    border:1px solid #444444; 
    border-radius:12px; 
    color:#FFFFFF;
}

QLabel { 
    color:#FFFFFF; 
    font-weight:bold; 
}

QScrollBar:vertical {
    background: #2A2A2A;
    width: 12px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #555555;
    min-height: 20px;
    border-radius: 6px;
}
QScrollBar::handle:vertical:hover {
    background: #777777;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
""")


    # Drag & drop
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.accept()

    def dropEvent(self, e):
        path = e.mimeData().urls()[0].toLocalFile()
        self.send_to_selected(path)

    # Scan devices
    def scan_devices(self):
        self.devices.clear()
        self.log.append("🔍 Поиск устройств...")
        for name, ip in discover_devices():
            self.devices.addItem(f"{name} ({ip})", ip)
        if self.devices.count():
            self.log.append("✅ Устройства найдены")
        else:
            self.log.append("❌ Никого нет в сети")

    # Send
    def send_file(self):
        path, _ = QFileDialog.getOpenFileName(self)
        if path:
            self.send_to_selected(path)

    def send_folder(self):
        path = QFileDialog.getExistingDirectory(self)
        if path:
            self.send_to_selected(path)

    def send_to_selected(self, path):
        if self.devices.count()==0:
            self.log.append("❌ Сначала найди устройство")
            return
        ip = self.devices.currentData()
        self.sender = Sender(ip, path)
        self.sender.progress.connect(self.progress.setValue)
        self.sender.speed.connect(self.speed.setText)
        self.sender.log.connect(self.log.append)
        self.sender.start()


# =====================
# Run App
# =====================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = SlovoIT()
    w.show()
    sys.exit(app.exec())
