"""
Power Plays Asset Fetcher — Desktop GUI v2
Double-click to launch. Requires asset_fetcher.py in the same folder.
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk
import subprocess
import queue


class AssetFetcherGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Power Plays — Asset Fetcher v5")
        self.root.geometry("820x700")
        self.root.minsize(700, 550)
        self.root.configure(bg="#1a1a2e")
        self.process = None
        self.output_queue = queue.Queue()
        self.polling = False

        self.bg = "#1a1a2e"
        self.card_bg = "#16213e"
        self.accent = "#e94560"
        self.accent_hover = "#ff6b81"
        self.text_color = "#eaeaea"
        self.muted = "#8892a8"
        self.input_bg = "#0f3460"
        self.success = "#4ecca3"
        self.border = "#2a2a4a"

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Card.TFrame", background=self.card_bg)
        style.configure("Main.TFrame", background=self.bg)
        style.configure("Title.TLabel", background=self.bg, foreground=self.text_color, font=("Segoe UI", 18, "bold"))
        style.configure("Subtitle.TLabel", background=self.bg, foreground=self.muted, font=("Segoe UI", 10))
        style.configure("CardTitle.TLabel", background=self.card_bg, foreground=self.text_color, font=("Segoe UI", 11, "bold"))
        style.configure("Input.TLabel", background=self.card_bg, foreground=self.text_color, font=("Segoe UI", 10))
        self.build_ui()

    def build_ui(self):
        main = ttk.Frame(self.root, style="Main.TFrame")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        ttk.Label(main, text="⚡ Power Plays Asset Fetcher", style="Title.TLabel").pack(anchor="w")
        ttk.Label(main, text="Drop in a script, grab your assets. v5 — full project support.", style="Subtitle.TLabel").pack(anchor="w", pady=(2, 15))

        # Script selection
        sc = ttk.Frame(main, style="Card.TFrame")
        sc.pack(fill=tk.X, pady=(0, 10))
        si = ttk.Frame(sc, style="Card.TFrame")
        si.pack(fill=tk.X, padx=15, pady=12)
        ttk.Label(si, text="📄 Script File", style="CardTitle.TLabel").pack(anchor="w")
        fr = ttk.Frame(si, style="Card.TFrame")
        fr.pack(fill=tk.X, pady=(6, 0))
        self.script_var = tk.StringVar()
        tk.Entry(fr, textvariable=self.script_var, font=("Consolas", 10), bg=self.input_bg, fg=self.text_color, insertbackground=self.text_color, relief="flat", bd=0, highlightthickness=1, highlightbackground=self.border, highlightcolor=self.accent).pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6)
        tk.Button(fr, text="Browse", font=("Segoe UI", 9, "bold"), bg=self.accent, fg="white", relief="flat", cursor="hand2", activebackground=self.accent_hover, activeforeground="white", bd=0, padx=16, pady=4, command=self.browse_file).pack(side=tk.RIGHT, padx=(8, 0))

        # Settings
        stc = ttk.Frame(main, style="Card.TFrame")
        stc.pack(fill=tk.X, pady=(0, 10))
        sti = ttk.Frame(stc, style="Card.TFrame")
        sti.pack(fill=tk.X, padx=15, pady=12)
        ttk.Label(sti, text="⚙️ Settings", style="CardTitle.TLabel").pack(anchor="w")
        sr = ttk.Frame(sti, style="Card.TFrame")
        sr.pack(fill=tk.X, pady=(8, 0))

        for label_text, var_name, default, from_, to_ in [("Images per query", "images_per_var", "3", 1, 10), ("Videos per query", "videos_per_var", "1", 1, 5)]:
            f = ttk.Frame(sr, style="Card.TFrame")
            f.pack(side=tk.LEFT, padx=(0, 25))
            ttk.Label(f, text=label_text, style="Input.TLabel").pack(anchor="w")
            var = tk.StringVar(value=default)
            setattr(self, var_name, var)
            tk.Spinbox(f, from_=from_, to=to_, textvariable=var, width=5, font=("Consolas", 11), bg=self.input_bg, fg=self.text_color, buttonbackground=self.border, relief="flat", bd=0, highlightthickness=1, highlightbackground=self.border, highlightcolor=self.accent, insertbackground=self.text_color).pack(anchor="w", pady=(3, 0))

        of = ttk.Frame(sr, style="Card.TFrame")
        of.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(of, text="Output folder", style="Input.TLabel").pack(anchor="w")
        self.output_var = tk.StringVar(value="assets")
        tk.Entry(of, textvariable=self.output_var, font=("Consolas", 10), bg=self.input_bg, fg=self.text_color, insertbackground=self.text_color, relief="flat", bd=0, highlightthickness=1, highlightbackground=self.border, highlightcolor=self.accent).pack(fill=tk.X, pady=(3, 0), ipady=4)

        # Buttons
        br = ttk.Frame(main, style="Main.TFrame")
        br.pack(fill=tk.X, pady=(0, 10))
        self.dry_run_btn = tk.Button(br, text="🔍  Dry Run", font=("Segoe UI", 11), bg=self.input_bg, fg=self.text_color, relief="flat", cursor="hand2", activebackground=self.border, activeforeground=self.text_color, bd=0, padx=20, pady=8, command=self.run_dry)
        self.dry_run_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.run_btn = tk.Button(br, text="⚡  Fetch Assets", font=("Segoe UI", 11, "bold"), bg=self.accent, fg="white", relief="flat", cursor="hand2", activebackground=self.accent_hover, activeforeground="white", bd=0, padx=20, pady=8, command=self.run_fetch)
        self.run_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.stop_btn = tk.Button(br, text="⏹  Stop", font=("Segoe UI", 11), bg="#333", fg=self.muted, relief="flat", cursor="hand2", activebackground="#444", activeforeground=self.text_color, bd=0, padx=20, pady=8, command=self.stop_process, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT)
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = tk.Label(br, textvariable=self.status_var, font=("Segoe UI", 9), bg=self.bg, fg=self.muted, anchor="e")
        self.status_label.pack(side=tk.RIGHT)

        # Log
        lh = ttk.Frame(main, style="Main.TFrame")
        lh.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(lh, text="Output", style="Subtitle.TLabel").pack(side=tk.LEFT)
        tk.Button(lh, text="Clear", font=("Segoe UI", 8), bg=self.bg, fg=self.muted, relief="flat", cursor="hand2", activebackground=self.bg, activeforeground=self.text_color, bd=0, command=self.clear_log).pack(side=tk.RIGHT)
        self.log = scrolledtext.ScrolledText(main, font=("Consolas", 9), bg="#0d1117", fg="#c9d1d9", insertbackground=self.text_color, relief="flat", bd=0, highlightthickness=1, highlightbackground=self.border, wrap=tk.WORD, height=12)
        self.log.pack(fill=tk.BOTH, expand=True)
        self.log.tag_configure("success", foreground=self.success)
        self.log.tag_configure("error", foreground=self.accent)
        self.log.tag_configure("info", foreground="#58a6ff")
        self.log.tag_configure("header", foreground=self.text_color, font=("Consolas", 9, "bold"))

        btr = ttk.Frame(main, style="Main.TFrame")
        btr.pack(fill=tk.X, pady=(8, 0))
        tk.Button(btr, text="📂  Open Assets Folder", font=("Segoe UI", 9), bg=self.card_bg, fg=self.muted, relief="flat", cursor="hand2", activebackground=self.border, activeforeground=self.text_color, bd=0, padx=12, pady=5, command=self.open_assets_folder).pack(side=tk.LEFT)

    def browse_file(self):
        path = filedialog.askopenfilename(title="Select a Power Plays script", filetypes=[("All supported", "*.md *.txt *.docx"), ("Markdown", "*.md"), ("Word", "*.docx"), ("Text", "*.txt")])
        if path:
            self.script_var.set(path)

    def get_fetcher_path(self):
        for loc in [os.path.join(os.path.dirname(os.path.abspath(__file__)), "asset_fetcher.py"), os.path.join(os.getcwd(), "asset_fetcher.py")]:
            if os.path.exists(loc):
                return loc
        return None

    def get_command(self, dry_run=False):
        script = self.script_var.get().strip()
        if not script:
            self.log_message("⚠ Please select a script file first.\n", "error")
            return None
        if not os.path.exists(script):
            self.log_message(f"⚠ File not found: {script}\n", "error")
            return None
        fetcher_path = self.get_fetcher_path()
        if not fetcher_path:
            self.log_message(f"⚠ Cannot find asset_fetcher.py\n  Looked in: {os.path.dirname(os.path.abspath(__file__))}\n", "error")
            return None
        self.log_message(f"  Using: {fetcher_path}\n", "info")
        cmd = [sys.executable, "-u", fetcher_path, "--script", script, "--images-per", self.images_per_var.get(), "--videos-per", self.videos_per_var.get(), "--output", self.output_var.get()]
        if dry_run:
            cmd.append("--dry-run")
        return cmd

    def run_dry(self):
        cmd = self.get_command(dry_run=True)
        if cmd: self.execute(cmd, "Dry run")

    def run_fetch(self):
        cmd = self.get_command(dry_run=False)
        if cmd: self.execute(cmd, "Fetching assets")

    def execute(self, cmd, label):
        self.set_running(True, label)
        self.log_message(f"\n{'─'*60}\n", "info")
        self.log_message(f"  {label}...\n", "header")
        self.log_message(f"{'─'*60}\n\n", "info")

        def run_in_thread():
            try:
                kwargs = {}
                if sys.platform == 'win32':
                    kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, cwd=os.path.dirname(os.path.abspath(__file__)), env={**os.environ, 'PYTHONUNBUFFERED': '1', 'PYTHONIOENCODING': 'utf-8'}, encoding='utf-8', errors='replace', **kwargs)
                for line in iter(self.process.stdout.readline, ''):
                    if line:
                        self.output_queue.put(line)
                self.process.stdout.close()
                self.process.wait()
            except Exception as e:
                self.output_queue.put(f"Error launching script: {e}\n")
            self.output_queue.put(None)

        threading.Thread(target=run_in_thread, daemon=True).start()
        self.polling = True
        self.poll_output()

    def poll_output(self):
        if not self.polling: return
        try:
            for _ in range(50):
                line = self.output_queue.get_nowait()
                if line is None:
                    self.polling = False
                    self.set_running(False, "Done")
                    self.log_message("\n✅ Finished!\n", "success")
                    return
                if "✓" in line or "Download complete" in line:
                    self.log_message(line, "success")
                elif "✗" in line or "Error" in line or "ERROR" in line:
                    self.log_message(line, "error")
                elif "──" in line or "📄" in line or "Extracted" in line or "Done" in line:
                    self.log_message(line, "header")
                elif "🔍" in line or "🎬" in line or "📰" in line or "📝" in line or "📋" in line or "📁" in line:
                    self.log_message(line, "info")
                else:
                    self.log_message(line)
        except queue.Empty:
            pass
        if self.polling:
            self.root.after(100, self.poll_output)

    def stop_process(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.log_message("\n⏹ Stopped by user.\n", "error")
        self.polling = False
        self.set_running(False, "Stopped")

    def set_running(self, running, label=""):
        if running:
            self.run_btn.config(state=tk.DISABLED); self.dry_run_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL, fg=self.accent)
            self.status_var.set(f"⏳ {label}..."); self.status_label.config(fg=self.accent)
        else:
            self.run_btn.config(state=tk.NORMAL); self.dry_run_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED, fg=self.muted)
            color = self.success if "Done" in label else self.muted
            self.status_var.set(f"✅ {label}" if "Done" in label else label)
            self.status_label.config(fg=color)

    def log_message(self, text, tag=None):
        self.log.insert(tk.END, text, tag); self.log.see(tk.END)

    def clear_log(self):
        self.log.delete(1.0, tk.END)

    def open_assets_folder(self):
        folder = self.output_var.get()
        if not os.path.isabs(folder):
            folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), folder)
        if os.path.exists(folder):
            if sys.platform == 'win32': os.startfile(folder)
            else: subprocess.run(['open', folder])
        else:
            self.log_message(f"⚠ Folder doesn't exist yet: {folder}\n  Run a fetch first.\n", "error")


if __name__ == "__main__":
    root = tk.Tk()
    AssetFetcherGUI(root)
    root.mainloop()
