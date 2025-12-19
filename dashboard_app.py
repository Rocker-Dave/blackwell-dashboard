from flask import Flask, render_template
import subprocess
import socket
import requests
import time

# ==== CONFIG ====
# URL where your server API is running
SERVER_BASE_URL = "http://YOUR_SERVER_IP_OR_DOMAIN:5000"  # <-- CHANGE THIS
INTERNET_TEST_HOST = "8.8.8.8"

# Subnet to scan for devices on /devices page
NETWORK_PREFIX = "192.168.1."       # <-- CHANGE to match your LAN
HOST_RANGE = range(1, 50)           # e.g. 1–49 for testing; you can expand later

# Optional friendly names for known IPs
FRIENDLY_NAMES = {
    "192.168.1.10": "Ubuntu Server",
    "192.168.1.20": "Gaming PC",
    "192.168.1.30": "Living Room TV",
}

app = Flask(__name__)


def run_cmd(cmd: str) -> str:
    try:
        out = subprocess.check_output(
            cmd, shell=True,
            stderr=subprocess.STDOUT,
            text=True
        )
        return out.strip()
    except Exception as e:
        return f"error: {e}"


def check_ping(host: str) -> bool:
    """Return True if host replies to a single ping."""
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-w", "1", host],  # -w 1 = 1s deadline
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return (result.returncode == 0)
    except Exception:
        return False


def ping_with_latency(host: str):
    """
    Ping host once, return (reachable: bool, latency_ms: float|None).
    If parsing fails, latency_ms will be None.
    """
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-w", "1", host],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode != 0:
            return False, None

        for line in result.stdout.splitlines():
            if "time=" in line:
                try:
                    part = line.split("time=")[1]
                    ms_str = part.split()[0]
                    return True, float(ms_str)
                except Exception:
                    return True, None
        return True, None
    except Exception:
        return False, None


def get_local_status():
    hostname = socket.gethostname()
    uname = run_cmd("uname -a")
    uptime = run_cmd("uptime")
    disk = run_cmd("df -h / | tail -n 1")
    internet_ok = check_ping(INTERNET_TEST_HOST)

    return {
        "hostname": hostname,
        "uname": uname,
        "uptime": uptime,
        "disk_root": disk,
        "internet_ok": internet_ok,
        "time": time.time(),
    }


def get_server_status():
    try:
        r_ping = requests.get(f"{SERVER_BASE_URL}/api/ping", timeout=2)
        ping_ok = r_ping.status_code == 200 and r_ping.json().get("ok", False)
    except Exception:
        ping_ok = False

    status_data = None
    try:
        r_status = requests.get(f"{SERVER_BASE_URL}/api/status", timeout=3)
        if r_status.status_code == 200:
            status_data = r_status.json()
    except Exception:
        status_data = None

    return {
        "reachable": ping_ok,
        "status": status_data,
    }


def get_notes_summary():
    try:
        r = requests.get(f"{SERVER_BASE_URL}/api/notes/summary", timeout=3)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {"count": 0, "notes": []}


def get_devices_status():
    """
    Scan NETWORK_PREFIX + HOST_RANGE with ping and return a list of
    reachable devices with latency.
    """
    devices_status = []
    for host in HOST_RANGE:
        ip = f"{NETWORK_PREFIX}{host}"
        reachable, latency = ping_with_latency(ip)
        if reachable:
            name = FRIENDLY_NAMES.get(ip, f"Device {ip}")
            devices_status.append({
                "name": name,
                "ip": ip,
                "reachable": True,
                "latency": latency,
            })
    return devices_status


@app.route("/")
def index():
    local = get_local_status()
    server = get_server_status()
    notes = get_notes_summary()
    return render_template(
        "home.html",
        local=local,
        server=server,
        notes=notes,
        server_url=SERVER_BASE_URL,
        now=time.strftime("%Y-%m-%d %H:%M:%S"),
        active_tab="home",
        title="Home Dashboard",
    )


@app.route("/devices")
def devices_page():
    devices = get_devices_status()
    return render_template(
        "devices.html",
        devices=devices,
        network_prefix=NETWORK_PREFIX,
        host_range=HOST_RANGE,
        now=time.strftime("%Y-%m-%d %H:%M:%S"),
        active_tab="devices",
        title="Devices - Home Dashboard",
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=4444, debug=True)
