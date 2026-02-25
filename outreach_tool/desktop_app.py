from __future__ import annotations

import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

import pandas as pd

from config import CampaignSettings, load_env
from run_campaign import CampaignStats, process_campaign


class OutreachDesktopApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Cybernara Outreach Tool - One Screen")
        self.root.geometry("980x700")

        load_env()

        self.stop_requested = False
        self.worker_thread: threading.Thread | None = None
        self.log_queue: queue.Queue[tuple[str, str]] = queue.Queue()

        self.file_path_var = tk.StringVar()
        self.verify_var = tk.BooleanVar(value=True)
        self.quality_var = tk.StringVar(value="High")
        self.max_var = tk.IntVar(value=50)
        self.delay_min_var = tk.IntVar(value=300)
        self.delay_max_var = tk.IntVar(value=720)
        self.defer_var = tk.BooleanVar(value=True)
        self.stop_on_credits_var = tk.BooleanVar(value=True)

        self.summary_var = tk.StringVar(value="Total: 0 | Current: 0 | Sent: 0 | Skipped: 0 | Deferred: 0 | Failed: 0")
        self.log_path: Path | None = None

        self._build_ui()
        self.root.after(150, self._drain_queue)

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(container, text="Cybernara Internal Outreach Tool", font=("Arial", 16, "bold"))
        title.pack(anchor="w")
        subtitle = ttk.Label(
            container,
            text="One-screen mode: choose options, start run, monitor logs below, and download/open generated log.",
        )
        subtitle.pack(anchor="w", pady=(0, 10))

        file_row = ttk.Frame(container)
        file_row.pack(fill=tk.X, pady=4)
        ttk.Label(file_row, text="Leads file (CSV/Excel):", width=24).pack(side=tk.LEFT)
        ttk.Entry(file_row, textvariable=self.file_path_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ttk.Button(file_row, text="Browse", command=self._choose_file).pack(side=tk.LEFT)

        options = ttk.LabelFrame(container, text="Campaign options")
        options.pack(fill=tk.X, pady=8)

        row1 = ttk.Frame(options)
        row1.pack(fill=tk.X, padx=8, pady=6)
        ttk.Checkbutton(row1, text="Verification ON", variable=self.verify_var).pack(side=tk.LEFT)
        ttk.Label(row1, text="Quality:").pack(side=tk.LEFT, padx=(14, 4))
        quality_combo = ttk.Combobox(row1, textvariable=self.quality_var, values=["Standard", "High", "Extreme"], width=12, state="readonly")
        quality_combo.pack(side=tk.LEFT)

        row2 = ttk.Frame(options)
        row2.pack(fill=tk.X, padx=8, pady=6)
        ttk.Label(row2, text="Max emails/run (1-50):").pack(side=tk.LEFT)
        ttk.Spinbox(row2, from_=1, to=50, textvariable=self.max_var, width=8).pack(side=tk.LEFT, padx=(4, 16))
        ttk.Label(row2, text="Delay min (sec):").pack(side=tk.LEFT)
        ttk.Spinbox(row2, from_=0, to=86400, textvariable=self.delay_min_var, width=8).pack(side=tk.LEFT, padx=(4, 16))
        ttk.Label(row2, text="Delay max (sec):").pack(side=tk.LEFT)
        ttk.Spinbox(row2, from_=0, to=86400, textvariable=self.delay_max_var, width=8).pack(side=tk.LEFT, padx=(4, 0))

        row3 = ttk.Frame(options)
        row3.pack(fill=tk.X, padx=8, pady=6)
        ttk.Checkbutton(row3, text="Defer outside business hours", variable=self.defer_var).pack(side=tk.LEFT)
        ttk.Checkbutton(row3, text="Stop if Verifalia credits exhausted", variable=self.stop_on_credits_var).pack(
            side=tk.LEFT, padx=(16, 0)
        )

        actions = ttk.Frame(container)
        actions.pack(fill=tk.X, pady=8)
        ttk.Button(actions, text="Start", command=self._start_run).pack(side=tk.LEFT)
        ttk.Button(actions, text="Stop", command=self._stop_run).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(actions, text="Open latest log", command=self._open_log).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Label(container, textvariable=self.summary_var).pack(anchor="w", pady=(2, 8))

        ttk.Label(container, text="Live logs").pack(anchor="w")
        self.log_area = ScrolledText(container, height=24, state=tk.DISABLED)
        self.log_area.pack(fill=tk.BOTH, expand=True)

    def _choose_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Select leads file",
            filetypes=[("Spreadsheet files", "*.csv *.xlsx *.xls"), ("All files", "*.*")],
        )
        if path:
            self.file_path_var.set(path)

    def _append_log(self, line: str) -> None:
        self.log_area.configure(state=tk.NORMAL)
        self.log_area.insert(tk.END, f"{line}\n")
        self.log_area.see(tk.END)
        self.log_area.configure(state=tk.DISABLED)

    def _set_summary(self, stats: CampaignStats) -> None:
        self.summary_var.set(
            f"Total: {stats.total_rows} | Current: {stats.current_row} | Sent: {stats.sent_count} | "
            f"Skipped: {stats.skipped_count} | Deferred: {stats.deferred_count} | Failed: {stats.failed_count}"
        )

    def _start_run(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showwarning("Run in progress", "A campaign is already running.")
            return

        file_path = self.file_path_var.get().strip()
        if not file_path:
            messagebox.showerror("Missing file", "Please select a CSV/Excel leads file.")
            return

        self.stop_requested = False
        self._append_log("Starting campaign...")

        self.worker_thread = threading.Thread(target=self._run_campaign_worker, args=(file_path,), daemon=True)
        self.worker_thread.start()

    def _stop_run(self) -> None:
        self.stop_requested = True
        self._append_log("Stop requested. Will stop gracefully after current step.")

    def _open_log(self) -> None:
        if not self.log_path or not self.log_path.exists():
            messagebox.showinfo("No log yet", "No log file is available yet.")
            return
        messagebox.showinfo("Latest log", f"Log file saved at:\n{self.log_path}")

    def _load_dataframe(self, file_path: str) -> pd.DataFrame:
        suffix = Path(file_path).suffix.lower()
        if suffix in {".xlsx", ".xls"}:
            return pd.read_excel(file_path)
        return pd.read_csv(file_path)

    def _run_campaign_worker(self, file_path: str) -> None:
        try:
            dataframe = self._load_dataframe(file_path)
            settings = CampaignSettings(
                verification_enabled=self.verify_var.get(),
                verification_quality=self.quality_var.get(),
                max_emails_per_run=int(self.max_var.get()),
                delay_min_seconds=int(self.delay_min_var.get()),
                delay_max_seconds=int(self.delay_max_var.get()),
                defer_outside_business_hours=self.defer_var.get(),
                stop_on_verifalia_credits_exhausted=self.stop_on_credits_var.get(),
            )

            def on_progress(stats: CampaignStats, message: str) -> None:
                self.log_queue.put(("progress", message))
                self.log_queue.put(("stats", stats))

            stats, _, log_path, fatal_error = process_campaign(
                dataframe=dataframe,
                settings=settings,
                progress_callback=on_progress,
                should_stop=lambda: self.stop_requested,
            )
            self.log_path = log_path
            self.log_queue.put(("stats", stats))

            if fatal_error:
                self.log_queue.put(("error", fatal_error))
            elif self.stop_requested:
                self.log_queue.put(("info", "Campaign stopped gracefully."))
            else:
                self.log_queue.put(("info", "Campaign completed successfully."))
            self.log_queue.put(("info", f"Log saved: {log_path}"))

        except Exception as exc:  # noqa: BLE001
            self.log_queue.put(("error", str(exc)))

    def _drain_queue(self) -> None:
        while not self.log_queue.empty():
            kind, payload = self.log_queue.get_nowait()
            if kind == "progress":
                self._append_log(str(payload))
            elif kind == "stats":
                self._set_summary(payload)  # type: ignore[arg-type]
            elif kind == "error":
                self._append_log(f"ERROR: {payload}")
            elif kind == "info":
                self._append_log(str(payload))
        self.root.after(150, self._drain_queue)


def main() -> None:
    root = tk.Tk()
    OutreachDesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
