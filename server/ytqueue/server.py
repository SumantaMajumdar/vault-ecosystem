import os
import sys
import json
import socket
import subprocess
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import urllib.parse
import urllib.request
import re

PORT = 8085
DEFAULT_VOLUME = 30
MAX_VOLUME = 80
MPV_SOCKET = "/tmp/mpv-socket"
STATIC_DIR = os.path.dirname(os.path.abspath(__file__))

# Single Shared Queue & Player State
mpv_process = None
queue = []
current_track = None
lock = threading.Lock()

# Cached status for clients so multiple concurrent devices don't spam mpv IPC
cached_status = {
    "playing": False,
    "paused": False,
    "time_pos": 0,
    "duration": 0,
    "volume": DEFAULT_VOLUME,
    "title": "Nothing Playing",
    "artist": "",
    "art": None,
    "queue": []
}
last_status_poll = 0

def ensure_mpv_running():
    global mpv_process
    if mpv_process is not None and mpv_process.poll() is None:
        return
    if os.path.exists(MPV_SOCKET):
        try:
            os.remove(MPV_SOCKET)
        except OSError:
            pass

    cmd = [
        "mpv",
        "--idle=yes",
        f"--input-ipc-server={MPV_SOCKET}",
        "--no-video",
        "--ao=pulse",
        "--ytdl-format=bestaudio/best",
        "--keep-open=no",
        f"--volume={DEFAULT_VOLUME}"
    ]
    env = os.environ.copy()
    env["XDG_RUNTIME_DIR"] = "/run/user/1000"
    env["PULSE_SERVER"] = "unix:/run/user/1000/pulse/native"
    mpv_process = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Wait up to 1.5s for mpv IPC socket to be ready
    for _ in range(15):
        if os.path.exists(MPV_SOCKET):
            break
        time.sleep(0.1)

def kill_mpv():
    global mpv_process
    if mpv_process is not None:
        try:
            mpv_process.terminate()
            mpv_process.wait(timeout=2)
        except Exception:
            try:
                mpv_process.kill()
            except Exception:
                pass
        mpv_process = None
    if os.path.exists(MPV_SOCKET):
        try:
            os.remove(MPV_SOCKET)
        except OSError:
            pass

def send_mpv_cmd(command):
    if not os.path.exists(MPV_SOCKET):
        return None
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect(MPV_SOCKET)
        msg = json.dumps({"command": command}) + "\n"
        s.sendall(msg.encode("utf-8"))

        buffer = ""
        while True:
            chunk = s.recv(4096).decode("utf-8", errors="ignore")
            if not chunk:
                break
            buffer += chunk
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if "error" in data:
                        s.close()
                        return data
                except Exception:
                    pass
        s.close()
        return None
    except Exception:
        return None

def get_mpv_prop(prop):
    res = send_mpv_cmd(["get_property", prop])
    if res and res.get("error") == "success":
        return res.get("data")
    return None

KNOWN_SINKS = [
    {
        "id": "dual_speaker_headphones",
        "name": "Dual Output (Speakers + 3.5mm Jack)",
        "icon": "🔊🎧"
    },
    {
        "id": "alsa_output.platform-avs_max98357a.18.auto.stereo-fallback",
        "name": "Internal Speakers (MAX98357A)",
        "icon": "🔊"
    },
    {
        "id": "alsa_output.platform-avs_da7219.19.auto.stereo-fallback",
        "name": "Headphones / 3.5mm Jack (DA7219)",
        "icon": "🎧"
    },
    {
        "id": "alsa_output.platform-avs_hdaudio.20.auto.stereo-fallback",
        "name": "HDMI Audio Output",
        "icon": "📺"
    }
]

def get_current_sink():
    env = os.environ.copy()
    env["XDG_RUNTIME_DIR"] = "/run/user/1000"
    env["PULSE_SERVER"] = "unix:/run/user/1000/pulse/native"
    try:
        res = subprocess.run(["/usr/bin/pactl", "get-default-sink"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=2, env=env)
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return "dual_speaker_headphones"

def set_current_sink(sink_id):
    env = os.environ.copy()
    env["XDG_RUNTIME_DIR"] = "/run/user/1000"
    env["PULSE_SERVER"] = "unix:/run/user/1000/pulse/native"
    try:
        subprocess.run(["/usr/bin/pactl", "set-default-sink", sink_id], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, timeout=2)
        # Move all currently active playing sink-inputs to the new sink immediately
        list_res = subprocess.run(["/usr/bin/pactl", "list", "sink-inputs", "short"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=env, timeout=2)
        if list_res.returncode == 0:
            for line in list_res.stdout.splitlines():
                parts = line.strip().split()
                if parts:
                    inp_id = parts[0]
                    subprocess.run(["/usr/bin/pactl", "move-sink-input", inp_id, sink_id], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, timeout=2)
        return True
    except Exception:
        return False

def update_status_cache():
    global cached_status, last_status_poll, current_track
    now = time.time()
    if now - last_status_poll < 0.5:
        return cached_status

    last_status_poll = now
    curr_sink = get_current_sink()
    with lock:
        has_current = current_track is not None
        has_queue = len(queue) > 0

    if not has_current and not has_queue:
        with lock:
            cached_status = {
                "playing": False,
                "paused": False,
                "time_pos": 0,
                "duration": 0,
                "volume": cached_status.get("volume", 30),
                "title": "Nothing Playing",
                "artist": "",
                "art": None,
                "queue": [],
                "active_sink": curr_sink,
                "sinks": KNOWN_SINKS
            }
        return cached_status

    idle = get_mpv_prop("idle-active")
    paused = get_mpv_prop("pause")
    time_pos = get_mpv_prop("time-pos")
    duration = get_mpv_prop("duration")
    volume = get_mpv_prop("volume")
    media_title = get_mpv_prop("media-title")

    with lock:
        # If current_track title is just a raw URL or "Buffering audio...", but MPV has discovered media-title, use MPV's title
        curr_title = current_track.get("title") if current_track else media_title
        if (not curr_title or curr_title.startswith("http://") or curr_title.startswith("https://")) and media_title:
            curr_title = media_title

        title = curr_title or "Nothing Playing"
        artist = (current_track["artist"] if current_track else "") or "YouTube"
        art = current_track["art"] if current_track else None
        q_copy = list(queue)

        is_playing = (not idle) if idle is not None else False
        display_title = title if (is_playing or current_track) else "Nothing Playing"
        display_artist = artist if (is_playing or current_track) else ""
        display_art = art if (is_playing or current_track) else None

        cached_status = {
            "playing": is_playing or (current_track is not None),
            "paused": bool(paused) if paused is not None else False,
            "time_pos": time_pos or 0,
            "duration": duration or (current_track.get("duration", 0) if current_track else 0),
            "volume": min(MAX_VOLUME, volume if volume is not None else DEFAULT_VOLUME),
            "title": display_title,
            "artist": display_artist,
            "art": display_art,
            "queue": q_copy,
            "active_sink": curr_sink,
            "sinks": KNOWN_SINKS
        }
    return cached_status

def get_youtube_video_id(query):
    m = re.search(r'(?:v=|\/|youtu\.be\/)([0-9A-Za-z_-]{11})', query)
    return m.group(1) if m else None

def clean_youtube_url(query):
    vid = get_youtube_video_id(query)
    if vid:
        return f"https://www.youtube.com/watch?v={vid}"
    return query

def get_track_metadata(query):
    clean_query = clean_youtube_url(query)
    vid = get_youtube_video_id(clean_query)

    # 1. Fast & ultra-lightweight: Official YouTube oEmbed API (<100ms, 0% CPU, no yt-dlp delay)
    if vid:
        try:
            oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json"
            req = urllib.request.Request(oembed_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    return {
                        "title": data.get("title") or clean_query,
                        "artist": data.get("author_name") or "YouTube",
                        "duration": 0,
                        "art": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                        "url": clean_query
                    }
        except Exception as e:
            try:
                with open("/tmp/ytqueue_debug.log", "a") as f:
                    f.write(f"oEmbed failed for {vid}: {e}\n")
            except Exception:
                pass

    # 2. yt-dlp fallback if search query or oEmbed failed
    try:
        is_url = clean_query.startswith("http://") or clean_query.startswith("https://")
        search_target = clean_query if is_url else f"ytsearch1:{clean_query}"
        cmd = [
            "/usr/local/bin/yt-dlp",
            "--default-search", "ytsearch",
            "-j",
            "--no-playlist",
            search_target
        ]
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=12)
        if p.returncode == 0 and p.stdout:
            for line in p.stdout.splitlines():
                line = line.strip()
                if line.startswith("{"):
                    info = json.loads(line)
                    url = info.get("webpage_url") or info.get("url") or clean_query
                    v_id = info.get("id") or vid
                    art_url = f"https://i.ytimg.com/vi/{v_id}/hqdefault.jpg" if v_id else info.get("thumbnail")
                    return {
                        "title": info.get("title", clean_query),
                        "artist": info.get("uploader") or info.get("channel", "YouTube"),
                        "duration": info.get("duration", 0),
                        "art": art_url,
                        "url": url
                    }
    except Exception:
        pass

    # Default fallback
    art = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if vid else None
    return {
        "title": clean_query,
        "artist": "YouTube",
        "duration": 0,
        "art": art,
        "url": clean_query
    }

def process_and_add_track(target_query):
    global current_track
    try:
        with open("/tmp/ytqueue_debug.log", "a") as f:
            f.write(f"process_and_add_track called with: {target_query}\n")

        clean_url = clean_youtube_url(target_query)
        
        # 1. Fetch metadata immediately (oEmbed takes ~50ms, 0% CPU)
        track_info = get_track_metadata(target_query)
        with open("/tmp/ytqueue_debug.log", "a") as f:
            f.write(f"track_info: {track_info}\n")

        ensure_mpv_running()

        with lock:
            # If no song is currently loaded or playing, start playing immediately
            if current_track is None and len(queue) == 0:
                current_track = track_info
                res = send_mpv_cmd(["loadfile", clean_url])
                with open("/tmp/ytqueue_debug.log", "a") as f:
                    f.write(f"loadfile sent. res: {res}, current_track set to {track_info}\n")
            else:
                queue.append(track_info)
                with open("/tmp/ytqueue_debug.log", "a") as f:
                    f.write(f"appended to queue. queue len: {len(queue)}\n")
    except Exception as e:
        import traceback
        with open("/tmp/ytqueue_debug.log", "a") as f:
            f.write(f"ERROR in process_and_add_track: {e}\n{traceback.format_exc()}\n")

def worker_queue_runner():
    """Lightweight single-queue runner. Sleeps longer when idle to ensure 0% CPU."""
    global current_track
    idle_count = 0
    while True:
        with lock:
            has_queue = len(queue) > 0
            has_current = current_track is not None

        if not has_queue and not has_current:
            # Idle state: sleep 3.0s between checks, 0% CPU
            idle_count += 1
            if idle_count > 10:  # After 30s of pure idle, clean up MPV process
                kill_mpv()
            time.sleep(3.0)
            continue

        idle_count = 0
        ensure_mpv_running()
        time.sleep(1.0)

        idle = get_mpv_prop("idle-active")
        time_pos = get_mpv_prop("time-pos")
        with lock:
            # mpv idle-active is True both before loading and after finishing a track.
            # Only advance or clear if we actually had a track playing that finished (or if queue has waiting tracks)
            if idle is True:
                if len(queue) > 0:
                    current_track = queue.pop(0)
                    send_mpv_cmd(["loadfile", current_track["url"]])
                elif current_track and time_pos is None and current_track.get("_started"):
                    current_track = None
            elif time_pos is not None and current_track:
                current_track["_started"] = True

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            file_path = os.path.join(STATIC_DIR, "index.html")
            if os.path.exists(file_path):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                with open(file_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "index.html not found")
        elif path == "/api/status":
            data = update_status_cache()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
        else:
            self.send_error(404)

    def do_POST(self):
        global current_track
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"

        try:
            payload = json.loads(body)
        except Exception:
            payload = {}

        if path == "/api/add":
            query = payload.get("query", "").strip()
            if query:
                t = threading.Thread(target=process_and_add_track, args=(query,), daemon=True)
                t.start()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))

        elif path == "/api/control":
            action = payload.get("action")
            val = payload.get("value")

            if action == "toggle_play":
                send_mpv_cmd(["cycle", "pause"])
            elif action == "play":
                send_mpv_cmd(["set_property", "pause", False])
            elif action == "pause":
                send_mpv_cmd(["set_property", "pause", True])
            elif action == "stop":
                with lock:
                    queue.clear()
                    current_track = None
                send_mpv_cmd(["stop"])
            elif action == "next":
                with lock:
                    if len(queue) > 0:
                        current_track = queue.pop(0)
                        send_mpv_cmd(["loadfile", current_track["url"]])
                    else:
                        current_track = None
                        send_mpv_cmd(["stop"])
                if val is not None:
                    send_mpv_cmd(["seek", float(val), "absolute"])
            elif action == "seek_back":
                send_mpv_cmd(["seek", -10, "relative"])
            elif action == "volume":
                if val is not None:
                    send_mpv_cmd(["set_property", "volume", max(0, min(MAX_VOLUME, float(val)))])
            elif action == "clear":
                with lock:
                    queue.clear()
            elif action == "remove":
                if val is not None:
                    idx = int(val)
                    with lock:
                        if 0 <= idx < len(queue):
                            queue.pop(idx)
            elif action == "set_sink":
                if val is not None:
                    set_current_sink(str(val))
                    global last_status_poll
                    last_status_poll = 0

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))

    def log_message(self, format, *args):
        return

if __name__ == "__main__":
    t = threading.Thread(target=worker_queue_runner, daemon=True)
    t.start()

    server = ThreadedHTTPServer(("0.0.0.0", PORT), RequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        kill_mpv()
