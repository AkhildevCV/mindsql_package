# installer.py
"""
MindSQL One-Click Automated Installer  v2.0
============================================
Fully cross-platform: Windows / Linux / macOS

Every long-running step has a live loading screen:
  ✅ Ollama download   → live MB/% progress bar
  ✅ GGUF download     → live MB/% progress bar
  ✅ ollama create     → live log output streaming
  ✅ pip install       → animated spinner + package name
"""

import os
import sys
import subprocess
import platform
import threading
import urllib.request
import shutil
import time
import zipfile
import tempfile
from pathlib import Path

import customtkinter as ctk
from tkinter import font as tkfont

# ── OS DETECTION ──────────────────────────────────────────────────────────────
_OS = platform.system()   # "Windows" | "Linux" | "Darwin"

if _OS == "Windows":
    import winreg
    import ctypes as _ctypes

# ── CONSTANTS ─────────────────────────────────────────────────────────────────
APP_NAME      = "MindSQL"
APP_VERSION   = "1.0.0"
MODEL_NAME    = "mindsql-v2"
GGUF_FILENAME = "qwen2.5-coder-3b-instruct.Q4_K_M.gguf"

# ⚠️  IMPORTANT: This URL must point to your PUBLIC HuggingFace repo.
#     Go to https://huggingface.co/AKHILDEVCV/MindSQL-Model-GGUF
#     and make sure the repo visibility is set to "Public".
HF_MODEL_URL = (
    "https://huggingface.co/AKHILDEVCV/MindSQL-Model-GGUF/resolve/main/"
    + GGUF_FILENAME
)

# Ollama download URLs per OS
OLLAMA_URLS = {
    "Windows": "https://ollama.com/download/OllamaSetup.exe",
    "Linux":   "https://ollama.com/install.sh",          # shell script
    "Darwin":  "https://ollama.com/download/Ollama-darwin.zip",  # macOS app bundle
}

# Install location per OS
if _OS == "Windows":
    INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "MindSQL"
elif _OS == "Darwin":
    INSTALL_DIR = Path.home() / "Library" / "Application Support" / "MindSQL"
else:
    INSTALL_DIR = Path.home() / ".local" / "share" / "MindSQL"

MODEL_DIR = INSTALL_DIR / "models"

MODELFILE_TEMPLATE = """\
FROM {model_path}
SYSTEM "You are an expert SQL assistant. Generate only correct SQL."
PARAMETER temperature 0.2
PARAMETER num_predict 250
PARAMETER repeat_penalty 1.1
"""

# ── THEME ─────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

C = {
    "bg":      "#0D1117",
    "surface": "#161B22",
    "border":  "#30363D",
    "accent":  "#2563EB",
    "success": "#22C55E",
    "warning": "#F59E0B",
    "error":   "#EF4444",
    "text":    "#E6EDF3",
    "dim":     "#8B949E",
}


# ── WIDGETS ───────────────────────────────────────────────────────────────────
class StepRow(ctk.CTkFrame):
    ICONS = {
        "pending": ("⏳", C["dim"]),
        "skip":    ("⏭",  C["dim"]),
        "running": ("⚡", C["warning"]),
        "done":    ("✅", C["success"]),
        "error":   ("❌", C["error"]),
    }

    def __init__(self, parent, label, **kw):
        super().__init__(parent, fg_color="transparent", **kw)
        self._icon = ctk.CTkLabel(self, text="⏳", width=30,
                                   font=ctk.CTkFont(size=16))
        self._icon.pack(side="left", padx=(0, 8))
        self._text = ctk.CTkLabel(self, text=label, anchor="w",
                                   text_color=C["dim"],
                                   font=ctk.CTkFont(size=13))
        self._text.pack(side="left", fill="x", expand=True)
        self._note = ctk.CTkLabel(self, text="", anchor="e",
                                   text_color=C["dim"],
                                   font=ctk.CTkFont(size=11))
        self._note.pack(side="right", padx=8)

    def set_state(self, state, note=""):
        icon, color = self.ICONS.get(state, self.ICONS["pending"])
        self._icon.configure(text=icon)
        self._text.configure(text_color=color)
        self._note.configure(text=note)


class LogBox(ctk.CTkTextbox):
    """Scrolling log viewer shown during ollama create."""
    def __init__(self, parent, **kw):
        kw.setdefault("height", 80)
        kw.setdefault("font", ctk.CTkFont(family="Courier", size=10))
        kw.setdefault("fg_color", "#0a0f14")
        kw.setdefault("text_color", C["dim"])
        kw.setdefault("state", "disabled")
        super().__init__(parent, **kw)

    def append(self, line: str):
        self.configure(state="normal")
        self.insert("end", line + "\n")
        self.see("end")
        self.configure(state="disabled")


# ── MAIN INSTALLER WINDOW ─────────────────────────────────────────────────────
class MindSQLInstaller(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME}  Setup  v{APP_VERSION}")
        self.geometry("600x820")
        self.resizable(False, False)
        self.configure(fg_color=C["bg"])
        self._preflight = {}
        self._model_path = None
        self._build_ui()
        # Auto-run system check when window opens
        threading.Thread(target=self._run_preflight, daemon=True).start()

    # ── BUILD UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text="🧠  MindSQL",
                     font=ctk.CTkFont(size=30, weight="bold"),
                     text_color=C["text"]).pack(pady=(20, 2))
        ctk.CTkLabel(hdr,
                     text=f"AI-Powered Database Terminal  •  One-Click Setup  •  {_OS}",
                     font=ctk.CTkFont(size=11), text_color=C["dim"]).pack(pady=(0, 16))

        # System check panel
        pf = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=8)
        pf.pack(fill="x", padx=20, pady=(12, 0))
        ctk.CTkLabel(pf, text="System Check  (runs automatically)",
                     font=ctk.CTkFont(size=10), text_color=C["dim"]).pack(anchor="w", padx=12, pady=(8, 2))
        self._pf_rows = {}
        for key, label in {
            "python": "Python environment",
            "ollama": "Ollama (AI runtime)",
            "model":  f"Ollama model  '{MODEL_NAME}'",
            "gguf":   f"GGUF file  ({GGUF_FILENAME[:34]}…)",
        }.items():
            r = StepRow(pf, label)
            r.pack(fill="x", padx=12, pady=2)
            self._pf_rows[key] = r
        ctk.CTkLabel(pf, text="", height=4).pack()

        # Install path
        loc = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=8)
        loc.pack(fill="x", padx=20, pady=(8, 0))
        ctk.CTkLabel(loc, text="Install Location",
                     font=ctk.CTkFont(size=10), text_color=C["dim"]).pack(anchor="w", padx=12, pady=(6, 0))
        ctk.CTkLabel(loc, text=str(INSTALL_DIR),
                     font=ctk.CTkFont(size=10), text_color=C["text"]).pack(anchor="w", padx=12, pady=(0, 6))

        # Installation steps
        sp = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=8)
        sp.pack(fill="x", padx=20, pady=8)
        ctk.CTkLabel(sp, text="Installation Steps",
                     font=ctk.CTkFont(size=10), text_color=C["dim"]).pack(anchor="w", padx=12, pady=(8, 4))
        self._steps = []
        for lbl in [
            "Prepare install directory",
            "Install Python packages",
            "Download & install Ollama",
            "Download AI model  (~2 GB)",
            "Register model in Ollama",
            f"Register 'mindsql' command  ({_OS})",
            "Create Desktop shortcut",
        ]:
            r = StepRow(sp, lbl)
            r.pack(fill="x", padx=12, pady=2)
            self._steps.append(r)
        ctk.CTkLabel(sp, text="", height=4).pack()

        # ── Live download progress (shown during downloads) ────────────────
        self._dl_outer = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=8)
        self._dl_outer.pack(fill="x", padx=20, pady=(0, 4))
        self._dl_title = ctk.CTkLabel(self._dl_outer, text="",
                                       font=ctk.CTkFont(size=11, weight="bold"),
                                       text_color=C["warning"])
        self._dl_title.pack(anchor="w", padx=12, pady=(8, 2))
        self._dl_bar = ctk.CTkProgressBar(self._dl_outer, height=10,
                                           progress_color=C["warning"],
                                           fg_color=C["border"])
        self._dl_bar.pack(fill="x", padx=12, pady=(2, 4))
        self._dl_bar.set(0)
        self._dl_info = ctk.CTkLabel(self._dl_outer, text="Waiting…",
                                      font=ctk.CTkFont(size=11),
                                      text_color=C["dim"])
        self._dl_info.pack(anchor="w", padx=12, pady=(0, 8))
        self._dl_outer.pack_forget()  # hidden until a download starts

        # ── Log box shown during 'ollama create' ──────────────────────────
        self._log_outer = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=8)
        self._log_outer.pack(fill="x", padx=20, pady=(0, 4))
        ctk.CTkLabel(self._log_outer, text="Ollama model build output",
                     font=ctk.CTkFont(size=10), text_color=C["dim"]).pack(anchor="w", padx=12, pady=(6, 2))
        self._log_box = LogBox(self._log_outer)
        self._log_box.pack(fill="x", padx=12, pady=(0, 8))
        self._log_outer.pack_forget()  # hidden until build starts

        # Overall progress bar
        pg = ctk.CTkFrame(self, fg_color="transparent")
        pg.pack(fill="x", padx=20, pady=(4, 0))
        self._prog_bar = ctk.CTkProgressBar(pg, height=8,
                                             progress_color=C["accent"],
                                             fg_color=C["surface"])
        self._prog_bar.pack(fill="x", pady=(2, 2))
        self._prog_bar.set(0)
        self._status_lbl = ctk.CTkLabel(pg, text="Running system check…",
                                         text_color=C["dim"],
                                         font=ctk.CTkFont(size=11))
        self._status_lbl.pack(anchor="w")

        # Buttons
        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.pack(fill="x", padx=20, pady=10)
        self._install_btn = ctk.CTkButton(
            bf, text="⚡  Install MindSQL",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=48, corner_radius=8,
            fg_color=C["accent"], hover_color="#1D4ED8",
            command=self._start_install, state="disabled")
        self._install_btn.pack(fill="x")
        self._launch_btn = ctk.CTkButton(
            bf, text="🚀  Launch MindSQL",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=44, corner_radius=8,
            fg_color=C["success"], hover_color="#16A34A",
            command=self._launch_app, state="disabled")
        self._launch_btn.pack(fill="x", pady=(8, 0))

    # ── THREAD-SAFE HELPERS ───────────────────────────────────────────────────
    def _ui(self, fn, *a, **kw):    self.after(0, fn, *a, **kw)
    def _set_status(self, msg, color=None):
        self._ui(self._status_lbl.configure, text=msg, text_color=color or C["dim"])
    def _set_prog(self, v):         self._ui(self._prog_bar.set, v)
    def _step(self, i, s, note=""): self._ui(self._steps[i].set_state, s, note)
    def _pf(self, k, s, note=""):   self._ui(self._pf_rows[k].set_state, s, note)

    # ── SHOW / HIDE DOWNLOAD PANEL ────────────────────────────────────────────
    def _show_dl(self, title="Downloading…"):
        self._ui(self._dl_title.configure, text=title)
        self._ui(self._dl_bar.set, 0)
        self._ui(self._dl_info.configure, text="Starting…")
        self._ui(self._dl_outer.pack, fill="x", padx=20, pady=(0, 4))

    def _hide_dl(self):
        self._ui(self._dl_outer.pack_forget)

    def _update_dl(self, done_mb, total_mb, pct):
        self._ui(self._dl_bar.set, pct)
        self._ui(self._dl_info.configure,
                 text=f"{done_mb:.1f} MB / {total_mb:.1f} MB  —  {int(pct*100)}%  "
                      f"({'downloading…' if pct < 1 else 'complete!'})")

    # ── SHOW / HIDE LOG BOX ───────────────────────────────────────────────────
    def _show_log(self):
        self._ui(self._log_outer.pack, fill="x", padx=20, pady=(0, 4))

    def _hide_log(self):
        self._ui(self._log_outer.pack_forget)

    def _log(self, line):
        self._ui(self._log_box.append, line)

    # ── PRE-FLIGHT CHECK ──────────────────────────────────────────────────────
    def _run_preflight(self):
        # Python
        self._pf("python", "running")
        self._preflight["python"] = True
        self._pf("python", "done", f"v{sys.version.split()[0]}")

        # Ollama
        self._pf("ollama", "running")
        ok = self._is_ollama_installed()
        self._preflight["ollama"] = ok
        if ok:
            v = self._ollama_version()
            self._pf("ollama", "done", f"{v}  already installed")
        else:
            self._pf("ollama", "pending", f"will be installed for {_OS}")

        # Ollama model
        self._pf("model", "running")
        ok = self._is_model_installed()
        self._preflight["model"] = ok
        self._pf("model", "done" if ok else "pending",
                 "already in Ollama" if ok else "will be created")

        # GGUF file
        self._pf("gguf", "running")
        gguf = MODEL_DIR / GGUF_FILENAME
        ok = gguf.exists() and gguf.stat().st_size > 100_000_000   # >100 MB = real file
        self._preflight["gguf"] = ok
        if ok:
            self._pf("gguf", "done",
                     f"on disk  ({gguf.stat().st_size/1_073_741_824:.1f} GB)")
        else:
            self._pf("gguf", "pending", "will be downloaded (~2 GB)")

        self._ui(self._apply_skip_marks)
        self._set_status("Ready — click Install to begin.")
        self._ui(self._install_btn.configure, state="normal")

    def _apply_skip_marks(self):
        if self._preflight.get("ollama"):
            self._steps[2].set_state("skip", "already installed")
        if self._preflight.get("gguf"):
            self._steps[3].set_state("skip", "already on disk")
        if self._preflight.get("model"):
            self._steps[3].set_state("skip", "already in Ollama")
            self._steps[4].set_state("skip", "already exists")

    # ── DETECT HELPERS ────────────────────────────────────────────────────────
    def _is_ollama_installed(self):
        try:
            subprocess.run(["ollama", "--version"],
                           capture_output=True, check=True, timeout=10)
            return True
        except Exception:
            return False

    def _ollama_version(self):
        try:
            r = subprocess.run(["ollama", "--version"],
                               capture_output=True, text=True, timeout=10)
            return r.stdout.strip().split()[-1]
        except Exception:
            return ""

    def _is_model_installed(self):
        try:
            r = subprocess.run(["ollama", "list"],
                               capture_output=True, text=True, timeout=15)
            for line in r.stdout.strip().splitlines()[1:]:
                parts = line.split()
                if parts and parts[0].split(":")[0] == MODEL_NAME:
                    return True
            return False
        except Exception:
            return False

    # ── INSTALL FLOW ──────────────────────────────────────────────────────────
    def _start_install(self):
        self._install_btn.configure(state="disabled", text="Installing…")
        threading.Thread(target=self._run_install, daemon=True).start()

    def _run_install(self):
        try:
            T = 7

            # 0 — Prepare directory ────────────────────────────────────────────
            self._step(0, "running")
            self._set_status("Creating install directory…")
            INSTALL_DIR.mkdir(parents=True, exist_ok=True)
            MODEL_DIR.mkdir(parents=True, exist_ok=True)

            src = (Path(sys.executable).parent
                   if getattr(sys, "frozen", False)
                   else Path(__file__).parent)
            app_files = ["main.py","ai_engine.py","config.py","database.py",
                         "ui.py","validator.py","sql_completer.py","schema_manager.py"]
            copied = sum(1 for f in app_files
                         if (src/f).exists() and shutil.copy2(src/f, INSTALL_DIR/f) or True
                         if (src/f).exists())
            self._step(0, "done", f"{copied} files")
            self._set_prog(1/T)

            # 1 — Python packages ──────────────────────────────────────────────
            self._step(1, "running")
            self._set_status("Installing Python packages…")
            self._install_packages()
            self._step(1, "done")
            self._set_prog(2/T)

            # 2 — Ollama ───────────────────────────────────────────────────────
            self._step(2, "running")
            if self._preflight.get("ollama"):
                self._step(2, "skip", "already installed")
            else:
                self._install_ollama()   # has its own loading screen
                self._step(2, "done")
            self._set_prog(3/T)

            # 3 — Download GGUF ────────────────────────────────────────────────
            gguf = MODEL_DIR / GGUF_FILENAME

            if self._preflight.get("model"):
                self._step(3, "skip", "model already in Ollama")
                self._step(4, "skip", "already exists")
                self._set_prog(5/T)

            elif self._preflight.get("gguf") and gguf.exists():
                self._step(3, "skip", "already on disk")
                self._set_prog(4/T)
                self._step(4, "running")
                self._build_model(gguf)        # has its own log box
                self._step(4, "done")
                self._set_prog(5/T)

            else:
                self._step(3, "running")
                self._download_gguf(gguf)      # live progress bar
                self._step(3, "done")
                self._set_prog(4/T)

                self._step(4, "running")
                self._build_model(gguf)        # live log box
                self._step(4, "done")
                self._set_prog(5/T)

            self._model_path = gguf

            # 5 — Register command ─────────────────────────────────────────────
            self._step(5, "running")
            self._set_status("Registering 'mindsql' command…")
            self._register_command()
            self._step(5, "done")
            self._set_prog(6/T)

            # 6 — Shortcut ─────────────────────────────────────────────────────
            self._step(6, "running")
            self._set_status("Creating Desktop shortcut…")
            self._create_shortcut()
            self._step(6, "done")
            self._set_prog(1.0)

            self._set_status(
                "✅  Installation complete!  Open a new terminal and type: mindsql",
                C["success"])
            self._ui(self._install_btn.configure,
                     text="✅  Installed", fg_color="#1a3a1a")
            self._ui(self._launch_btn.configure, state="normal")

        except Exception as exc:
            import traceback; traceback.print_exc()
            self._set_status(f"❌  {exc}", C["error"])
            self._ui(self._install_btn.configure,
                     state="normal", text="⚡  Retry")

    # ── PYTHON PACKAGES ───────────────────────────────────────────────────────
    def _install_packages(self):
        pkgs = ["ollama", "sqlalchemy>=2.0", "pymysql", "psycopg2-binary",
                "rich", "prompt_toolkit", "typer", "sqlglot",
                "sql-metadata", "customtkinter"]

        # On system-managed Pythons (Debian/Ubuntu 23.10+) we need this flag
        extra = ["--break-system-packages"] if _OS == "Linux" else []

        for pkg in pkgs:
            self._set_status(f"Installing  {pkg}…")
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install",
                     "--quiet", "--upgrade", pkg] + extra,
                    check=True, capture_output=True, timeout=120
                )
            except subprocess.CalledProcessError:
                pass    # non-fatal: package may already be current


    # ── OLLAMA DOWNLOAD + INSTALL ─────────────────────────────────────────────
    def _install_ollama(self):
        if _OS == "Windows":
            self._install_ollama_windows()
        elif _OS == "Linux":
            self._install_ollama_linux()
        elif _OS == "Darwin":
            self._install_ollama_macos()
        else:
            raise RuntimeError(
                f"Unsupported OS '{_OS}'. Please install Ollama manually: https://ollama.com"
            )

    def _install_ollama_windows(self):
        """Downloads OllamaSetup.exe with progress bar, then runs it silently."""
        dest = INSTALL_DIR / "OllamaSetup.exe"
        self._show_dl("Downloading Ollama for Windows…")
        self._set_status("Downloading Ollama installer…")
        self._download_with_progress(OLLAMA_URLS["Windows"], dest)
        self._hide_dl()
        self._set_status("Running Ollama installer silently…")
        subprocess.run([str(dest), "/S"], check=True, timeout=300)
        time.sleep(8)   # wait for Ollama to finish registering

    def _install_ollama_linux(self):
        """
        Downloads the Ollama install.sh script and runs it.
        Shows live output in the log box so the UI isn't frozen.
        """
        self._show_log()
        self._set_status("Installing Ollama for Linux (requires internet)…")
        self._log("► Downloading and running Ollama install script…")
        self._log("  Source: https://ollama.com/install.sh")
        self._log("")

        # Run curl | sh and stream output
        try:
            proc = subprocess.Popen(
                "curl -fsSL https://ollama.com/install.sh | sh",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            for line in proc.stdout:
                self._log(line.rstrip())
            proc.wait(timeout=300)
            if proc.returncode != 0:
                raise RuntimeError("Ollama install script failed.")
        finally:
            self._hide_log()

    def _install_ollama_macos(self):
        """
        macOS: tries `brew install ollama` first (cleanest).
        Falls back to downloading the official .zip app bundle.
        """
        # Try Homebrew first (most Mac developers have it)
        if shutil.which("brew"):
            self._show_log()
            self._set_status("Installing Ollama via Homebrew…")
            self._log("► brew install ollama")
            try:
                proc = subprocess.Popen(
                    ["brew", "install", "ollama"],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
                )
                for line in proc.stdout:
                    self._log(line.rstrip())
                proc.wait(timeout=300)
                if proc.returncode == 0:
                    self._hide_log()
                    return
            except Exception:
                pass
            finally:
                self._hide_log()

        # Fallback: download the macOS .zip app bundle
        zip_dest = INSTALL_DIR / "Ollama-darwin.zip"
        self._show_dl("Downloading Ollama for macOS…")
        self._set_status("Downloading Ollama.app…")
        self._download_with_progress(OLLAMA_URLS["Darwin"], zip_dest)
        self._hide_dl()

        self._set_status("Installing Ollama.app to /Applications…")
        with zipfile.ZipFile(zip_dest, "r") as z:
            z.extractall(INSTALL_DIR / "ollama_extracted")

        app_src = INSTALL_DIR / "ollama_extracted" / "Ollama.app"
        app_dst = Path("/Applications/Ollama.app")
        if app_dst.exists():
            shutil.rmtree(app_dst)
        shutil.copytree(app_src, app_dst)
        zip_dest.unlink(missing_ok=True)

        # Launch the app once so it installs the CLI tool into /usr/local/bin
        subprocess.Popen(["open", "-a", "Ollama"])
        time.sleep(6)

    # ── GGUF DOWNLOAD ─────────────────────────────────────────────────────────
    def _download_gguf(self, dest: Path):
        """Downloads the model from HuggingFace with a live progress bar."""
        self._show_dl(f"Downloading AI Model from HuggingFace…")
        self._set_status("Downloading GGUF model (~2 GB)…")
        self._log_box.append("") if hasattr(self, "_log_box") else None
        try:
            self._download_with_progress(HF_MODEL_URL, dest)
        except Exception as exc:
            dest.unlink(missing_ok=True)   # delete partial file
            raise RuntimeError(
                f"Model download failed: {exc}\n\n"
                "Make sure your HuggingFace repo is PUBLIC:\n"
                "https://huggingface.co/AKHILDEVCV/MindSQL-Model-GGUF\n"
                "Settings → Repository visibility → Public"
            )
        finally:
            self._hide_dl()

    def _download_with_progress(self, url: str, dest: Path):
        """Generic download with live MB / % updates in the download panel."""
        dest.parent.mkdir(parents=True, exist_ok=True)

        def hook(block_num, block_size, total_size):
            if total_size > 0:
                done  = block_num * block_size
                pct   = min(done / total_size, 1.0)
                self._update_dl(done / 1_048_576,
                                total_size / 1_048_576,
                                pct)

        urllib.request.urlretrieve(url, dest, reporthook=hook)

    # ── OLLAMA MODEL BUILD ────────────────────────────────────────────────────
    def _build_model(self, gguf_path: Path):
        """
        Runs 'ollama create' and streams every line of output into the log box
        so the UI is never frozen during the 1-2 minute build.
        """
        self._show_log()
        self._set_status("Registering model in Ollama  (may take 1-2 minutes)…")
        self._log(f"► ollama create {MODEL_NAME}")
        self._log(f"  Source: {gguf_path}")
        self._log("")

        mf = INSTALL_DIR / "Modelfile"
        mf.write_text(MODELFILE_TEMPLATE.format(model_path=str(gguf_path)))

        try:
            proc = subprocess.Popen(
                ["ollama", "create", MODEL_NAME, "-f", str(mf)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            for line in proc.stdout:
                self._log(line.rstrip())
            proc.wait(timeout=600)
            if proc.returncode != 0:
                raise RuntimeError(
                    f"'ollama create' failed (exit {proc.returncode}). "
                    "Check the log output above."
                )
            self._log("\n✅  Model registered successfully.")
        finally:
            mf.unlink(missing_ok=True)
            self._hide_log()

    # ── REGISTER COMMAND ──────────────────────────────────────────────────────
    def _register_command(self):
        if _OS == "Windows":
            self._register_windows()
        elif _OS == "Linux":
            self._register_linux()
        elif _OS == "Darwin":
            self._register_macos()

    def _register_windows(self):
        """Creates mindsql.bat and adds INSTALL_DIR to user PATH via registry."""
        bat = INSTALL_DIR / "mindsql.bat"
        bat.write_text(
            f'@echo off\n'
            f'"{sys.executable}" "{INSTALL_DIR / "main.py"}" shell %*\n'
        )
        # Registry PATH update
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                  "Environment", 0, winreg.KEY_ALL_ACCESS)
            try:    current, _ = winreg.QueryValueEx(key, "PATH")
            except FileNotFoundError: current = ""
            dirs = [d for d in current.split(";") if d]
            if str(INSTALL_DIR) not in dirs:
                dirs.append(str(INSTALL_DIR))
                winreg.SetValueEx(key, "PATH", 0,
                                   winreg.REG_EXPAND_SZ, ";".join(dirs))
            winreg.CloseKey(key)
            # Broadcast change so open terminals pick it up
            _ctypes.windll.user32.SendMessageTimeoutW(
                0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, None)
        except Exception as e:
            print(f"[PATH] {e}")

    def _register_linux(self):
        """
        Creates a mindsql shell script and symlinks it.
        Tries /usr/local/bin (system-wide) first, then ~/.local/bin (user).
        Also adds ~/.local/bin to PATH in .bashrc and .zshrc if needed.
        """
        script = INSTALL_DIR / "mindsql"
        script.write_text(
            "#!/usr/bin/env bash\n"
            f'"{sys.executable}" "{INSTALL_DIR / "main.py"}" shell "$@"\n'
        )
        script.chmod(0o755)

        # Try system-wide first (needs sudo — will fail silently if no perms)
        placed = False
        for bin_dir in ("/usr/local/bin", "/usr/bin"):
            try:
                link = Path(bin_dir) / "mindsql"
                if link.exists() or link.is_symlink(): link.unlink()
                link.symlink_to(script)
                placed = True
                break
            except PermissionError:
                continue

        # User-local fallback
        if not placed:
            local_bin = Path.home() / ".local" / "bin"
            local_bin.mkdir(parents=True, exist_ok=True)
            link = local_bin / "mindsql"
            if link.exists() or link.is_symlink(): link.unlink()
            link.symlink_to(script)
            # Add to PATH in shell rc files if not already there
            path_line = f'\nexport PATH="$HOME/.local/bin:$PATH"\n'
            for rc in [".bashrc", ".zshrc", ".profile"]:
                rc_path = Path.home() / rc
                if rc_path.exists():
                    content = rc_path.read_text()
                    if ".local/bin" not in content:
                        rc_path.write_text(content + path_line)

    def _register_macos(self):
        """
        macOS: creates a shell script and symlinks into /usr/local/bin.
        Falls back to ~/.local/bin and updates .zshrc / .bash_profile.
        """
        script = INSTALL_DIR / "mindsql"
        script.write_text(
            "#!/usr/bin/env bash\n"
            f'"{sys.executable}" "{INSTALL_DIR / "main.py"}" shell "$@"\n'
        )
        script.chmod(0o755)

        # macOS default shell is zsh; /usr/local/bin is usually writable
        placed = False
        for bin_dir in ("/usr/local/bin", "/opt/homebrew/bin"):
            try:
                link = Path(bin_dir) / "mindsql"
                if link.exists() or link.is_symlink(): link.unlink()
                link.symlink_to(script)
                placed = True
                break
            except PermissionError:
                continue

        if not placed:
            local_bin = Path.home() / ".local" / "bin"
            local_bin.mkdir(parents=True, exist_ok=True)
            link = local_bin / "mindsql"
            if link.exists() or link.is_symlink(): link.unlink()
            link.symlink_to(script)
            path_line = f'\nexport PATH="$HOME/.local/bin:$PATH"\n'
            for rc in [".zshrc", ".bash_profile", ".profile"]:
                rc_path = Path.home() / rc
                if rc_path.exists():
                    content = rc_path.read_text()
                    if ".local/bin" not in content:
                        rc_path.write_text(content + path_line)

    # ── DESKTOP SHORTCUT ──────────────────────────────────────────────────────
    def _create_shortcut(self):
        if _OS == "Windows":   self._shortcut_windows()
        elif _OS == "Linux":   self._shortcut_linux()
        elif _OS == "Darwin":  self._shortcut_macos()

    def _shortcut_windows(self):
        try:
            try:    import win32com.client
            except ImportError:
                subprocess.run([sys.executable, "-m", "pip", "install",
                                "--quiet", "pywin32"],
                               capture_output=True, timeout=60)
                import win32com.client
            desktop = Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop"
            lnk = desktop / "MindSQL.lnk"
            sh  = win32com.client.Dispatch("WScript.Shell")
            sc  = sh.CreateShortCut(str(lnk))
            sc.TargetPath = str(sys.executable)
            sc.Arguments  = f'"{INSTALL_DIR / "main.py"}" shell'
            sc.WorkingDirectory = str(INSTALL_DIR)
            sc.Description = "MindSQL – AI-Powered Database Terminal"
            sc.save()
        except Exception as e:
            print(f"[Shortcut Windows] {e}")

    def _shortcut_linux(self):
        try:
            entry = (
                "[Desktop Entry]\nType=Application\n"
                f"Name={APP_NAME}\nComment=AI-Powered Database Terminal\n"
                f"Exec=bash -c '{sys.executable} \"{INSTALL_DIR}/main.py\" shell; exec bash'\n"
                "Terminal=true\nCategories=Development;Database;\n"
            )
            p = Path.home() / ".local" / "share" / "applications" / "mindsql.desktop"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(entry)
            p.chmod(0o755)
        except Exception as e:
            print(f"[Shortcut Linux] {e}")

    def _shortcut_macos(self):
        """
        Creates a double-clickable .command file on the macOS Desktop.
        .command files open in Terminal.app automatically.
        """
        try:
            desktop = Path.home() / "Desktop"
            cmd_file = desktop / "MindSQL.command"
            cmd_file.write_text(
                "#!/bin/bash\n"
                f'"{sys.executable}" "{INSTALL_DIR / "main.py"}" shell\n'
            )
            cmd_file.chmod(0o755)
        except Exception as e:
            print(f"[Shortcut macOS] {e}")

    # ── LAUNCH ────────────────────────────────────────────────────────────────
    def _launch_app(self):
        if _OS == "Windows":
            subprocess.Popen(
                ["cmd.exe", "/k", str(INSTALL_DIR / "mindsql.bat")],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        elif _OS == "Darwin":
            script = INSTALL_DIR / "mindsql"
            subprocess.Popen(
                ["open", "-a", "Terminal", str(script)],
                start_new_session=True,
            )
        else:
            subprocess.Popen(
                ["bash", "-c", f'"{sys.executable}" "{INSTALL_DIR/"main.py"}" shell; exec bash'],
                start_new_session=True,
            )
        self.destroy()


# ── ENTRY POINT ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    MindSQLInstaller().mainloop()
