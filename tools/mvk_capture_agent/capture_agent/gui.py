"""Small operator GUI. Never simulates input into MVKView."""
from __future__ import annotations
import queue
import threading
from .session import CaptureService


def run_gui():
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
    service = CaptureService()
    root = tk.Tk()
    root.title("MVKView Capture Agent 0.4 - bounded popup capture")
    root.geometry("875x580")
    root.minsize(690, 470)
    actions = queue.Queue()
    name = tk.StringVar(value="No target selected")
    config = tk.StringVar(value="")
    consent = tk.BooleanVar(value=False)
    deep = tk.BooleanVar(value=False)
    trace = tk.BooleanVar(value=False)
    arrays = tk.BooleanVar(value=False)
    trace_consent = tk.BooleanVar(value=False)
    state = tk.StringVar(value="Idle - observer not running")
    records = {}

    main = ttk.Frame(root, padding=12)
    main.pack(expand=True, fill="both")
    ttk.Label(main, text="MVKView 1.0.47 - target-bound capture", font=("Segoe UI", 13, "bold")).pack(anchor="w")
    ttk.Label(main, text="No remote upload, no device commands, no debugger breakpoints.").pack(anchor="w", pady=(3, 10))
    targets = ttk.Frame(main)
    targets.pack(fill="x")
    ttk.Button(targets, text="Refresh MVKView windows", command=lambda: refresh()).pack(side="left")
    picker = ttk.Combobox(targets, textvariable=name, width=80, state="readonly")
    picker.pack(side="left", fill="x", expand=True, padx=(8, 0))

    settings = ttk.Frame(main)
    settings.pack(fill="x", pady=8)
    ttk.Label(settings, text="Optional local JSON config:").pack(side="left")
    ttk.Entry(settings, textvariable=config).pack(side="left", padx=8, fill="x", expand=True)
    ttk.Button(settings, text="Browse", command=lambda: select_config()).pack(side="right")
    ttk.Checkbutton(main, text="I authorize local observation of the chosen MVKView window and local evidence storage", variable=consent).pack(anchor="w", pady=4)
    ttk.Checkbutton(main, text="Include explicitly configured read-only memory watches on manual snapshots", variable=deep).pack(anchor="w", pady=2)
    ttk.Checkbutton(main, text="Automatically trace original GetSpectrum with Frida (no x32dbg)", variable=trace).pack(anchor="w", pady=2)
    ttk.Checkbutton(main, text="Also record bounded pre-FFT/Y array candidates (up to 16 MiB)", variable=arrays).pack(anchor="w", pady=2)
    ttk.Checkbutton(main, text="I understand Frida temporarily modifies MVKView process memory and might interrupt execution", variable=trace_consent).pack(anchor="w", pady=3)
    buttons = ttk.Frame(main)
    buttons.pack(fill="x", pady=(8, 7))
    ttk.Button(buttons, text="Start capture", command=lambda: launch("start")).pack(side="left", padx=(0, 8))
    ttk.Button(buttons, text="Capture now", command=lambda: launch("snapshot")).pack(side="left", padx=(0, 8))
    ttk.Button(buttons, text="Stop", command=lambda: launch("stop")).pack(side="left", padx=(0, 8))
    ttk.Button(buttons, text="Export ZIP", command=lambda: launch("export")).pack(side="left", padx=(0, 8))
    ttk.Button(buttons, text="Import x32dbg log", command=lambda: select_debugger()).pack(side="left")
    ttk.Label(main, textvariable=state).pack(fill="x", pady=(1, 4))
    log = tk.Text(main, wrap="word", height=15)
    log.pack(expand=True, fill="both")
    log.insert("end", "Select MVKView.exe, authorize, then Start.\n")
    log.config(state="disabled")

    def append(s):
        log.config(state="normal")
        log.insert("end", str(s) + "\n")
        log.see("end")
        log.config(state="disabled")

    def refresh():
        try:
            found = service.discover()
            records.clear()
            for t in found:
                label = f'PID {t["pid"]}, HWND {t["hwnd"]}, {t.get("name", "")}'
                records[label] = t
            picker["values"] = list(records)
            if found:
                picker.current(0)
            else:
                name.set("No MVKView.exe/Tmvkform found")
            append(f"Discovery: {len(found)} MVKView window(s)")
        except Exception as exc:
            append("Discovery error: " + str(exc))

    def select_config():
        path = filedialog.askopenfilename(title="Optional capture config", filetypes=[("JSON", "*.json")])
        if path:
            config.set(path)

    def select_debugger():
        path = filedialog.askopenfilename(title="Existing x32dbg JSONL/log", filetypes=[("Debugger log", "*.jsonl *.log *.txt")])
        if path:
            launch("import", path)

    busy = False
    def launch(action, path=None):
        nonlocal busy
        if busy:
            return
        if action == "start":
            if not consent.get():
                messagebox.showwarning("Consent", "Please explicitly authorize local capture")
                return
            if name.get() not in records:
                messagebox.showwarning("Target", "Select a discovered original MVKView window")
                return
            if trace.get() and not trace_consent.get():
                messagebox.showwarning("Frida consent", "Frida changes runtime code. Confirm its separate consent checkbox.")
                return
            if arrays.get() and not trace.get():
                messagebox.showwarning("Array capture", "Enable Frida trace before recording arrays")
                return
        busy = True
        state.set("Working: " + action)
        selected = records.get(name.get())
        configured = config.get().strip() or None
        read_watches = deep.get()
        def work():
            try:
                if action == "start":
                    outcome = service.start(acknowledge_local_capture=True,
                                            pid=selected["pid"], config_path=configured,
                                            auto_trace=trace.get(), trace_arrays=arrays.get(),
                                            acknowledge_instrumentation=trace_consent.get())
                elif action == "snapshot":
                    outcome = service.snapshot(include_memory=read_watches)
                elif action == "stop":
                    outcome = service.stop()
                elif action == "export":
                    outcome = service.export()
                elif action == "import":
                    outcome = service.import_debugger(path)
                else:
                    raise ValueError("Invalid action")
                actions.put((action, outcome, None))
            except Exception as exc:
                actions.put((action, None, str(exc)))
        threading.Thread(target=work, name="MVK-GUI-Action", daemon=True).start()

    def poll():
        nonlocal busy
        while True:
            try:
                action, outcome, error = actions.get_nowait()
            except queue.Empty:
                break
            busy = False
            if error:
                append(action + " failed: " + error)
            else:
                append(action + ": " + str(outcome))
            state.set(str(service.status()))
        root.after(350, poll)

    def shutdown():
        try:
            if service.session and service.session.status_label == "capturing":
                service.stop()
        finally:
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", shutdown)
    root.after(350, poll)
    refresh()
    root.mainloop()