from __future__ import annotations

import queue
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from .config import DEFAULT_GROUPS
from .service import process_pdf_to_excel


class DueClacApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("DueClac System - PDF to Excel Financial Report Converter")
        self.geometry("860x720")
        self.minsize(760, 620)

        self.pdf_path_var = tk.StringVar()
        self.output_path_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Select a PDF and generate the report.")

        self.result_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.worker_thread: threading.Thread | None = None

        self._build_ui()
        self.after(200, self._poll_worker_queue)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        container = ttk.Frame(self, padding=16)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(3, weight=1)
        container.rowconfigure(5, weight=1)

        title_label = ttk.Label(
            container,
            text="DueClac System",
            font=("Segoe UI", 18, "bold"),
        )
        title_label.grid(row=0, column=0, sticky="w")

        description_label = ttk.Label(
            container,
            text=(
                "Upload a text-copyable PDF, review the group list, and export a filtered "
                "Excel due report."
            ),
            wraplength=760,
            justify="left",
        )
        description_label.grid(row=1, column=0, sticky="ew", pady=(6, 16))

        file_frame = ttk.LabelFrame(container, text="Files", padding=12)
        file_frame.grid(row=2, column=0, sticky="ew")
        file_frame.columnconfigure(1, weight=1)

        ttk.Label(file_frame, text="PDF File").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=6)
        ttk.Entry(file_frame, textvariable=self.pdf_path_var).grid(
            row=0, column=1, sticky="ew", pady=6
        )
        self.pdf_button = ttk.Button(file_frame, text="Browse PDF", command=self.select_pdf_file)
        self.pdf_button.grid(row=0, column=2, padx=(8, 0), pady=6)

        ttk.Label(file_frame, text="Excel Output").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=6
        )
        ttk.Entry(file_frame, textvariable=self.output_path_var).grid(
            row=1, column=1, sticky="ew", pady=6
        )
        self.output_button = ttk.Button(file_frame, text="Save As", command=self.select_output_file)
        self.output_button.grid(row=1, column=2, padx=(8, 0), pady=6)

        groups_frame = ttk.LabelFrame(container, text="Known Groups", padding=12)
        groups_frame.grid(row=3, column=0, sticky="nsew", pady=(16, 0))
        groups_frame.columnconfigure(0, weight=1)
        groups_frame.rowconfigure(1, weight=1)

        groups_help = ttk.Label(
            groups_frame,
            text=(
                "Keep one group per line. Add any new group name here before generating "
                "if the PDF uses a new section name."
            ),
            wraplength=760,
            justify="left",
        )
        groups_help.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        self.group_text = ScrolledText(groups_frame, wrap="word", height=12, font=("Consolas", 10))
        self.group_text.grid(row=1, column=0, sticky="nsew")
        self.group_text.insert("1.0", "\n".join(DEFAULT_GROUPS))

        action_frame = ttk.Frame(container)
        action_frame.grid(row=4, column=0, sticky="ew", pady=(16, 0))
        action_frame.columnconfigure(1, weight=1)

        self.generate_button = ttk.Button(
            action_frame,
            text="Generate Excel",
            command=self.start_generation,
        )
        self.generate_button.grid(row=0, column=0, sticky="w")

        self.reset_button = ttk.Button(action_frame, text="Reset", command=self.reset_form)
        self.reset_button.grid(row=0, column=1, sticky="w", padx=(8, 0))

        ttk.Label(action_frame, textvariable=self.status_var).grid(
            row=0, column=2, sticky="e"
        )

        log_frame = ttk.LabelFrame(container, text="Process Log", padding=12)
        log_frame.grid(row=5, column=0, sticky="nsew", pady=(16, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = ScrolledText(log_frame, wrap="word", height=10, state="disabled")
        self.log_text.grid(row=0, column=0, sticky="nsew")

    def select_pdf_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select PDF File",
            filetypes=[("PDF files", "*.pdf")],
        )
        if not file_path:
            return

        self.pdf_path_var.set(file_path)
        if not self.output_path_var.get():
            suggested_output = Path(file_path).with_name(f"{Path(file_path).stem}_due_report.xlsx")
            self.output_path_var.set(str(suggested_output))
        self._log(f"Selected PDF: {file_path}")

    def select_output_file(self) -> None:
        initial_name = "due_report.xlsx"
        current_pdf = self.pdf_path_var.get().strip()
        if current_pdf:
            initial_name = f"{Path(current_pdf).stem}_due_report.xlsx"

        file_path = filedialog.asksaveasfilename(
            title="Save Excel File As",
            defaultextension=".xlsx",
            initialfile=initial_name,
            filetypes=[("Excel files", "*.xlsx")],
        )
        if not file_path:
            return

        self.output_path_var.set(file_path)
        self._log(f"Selected output file: {file_path}")

    def start_generation(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showinfo("DueClac System", "A report is already being generated.")
            return

        pdf_path = self.pdf_path_var.get().strip()
        output_path = self.output_path_var.get().strip()

        if not pdf_path:
            messagebox.showerror("Missing PDF", "Please select a PDF file first.")
            return

        if not Path(pdf_path).exists():
            messagebox.showerror("Invalid PDF", "The selected PDF file does not exist.")
            return

        if not output_path:
            self.select_output_file()
            output_path = self.output_path_var.get().strip()
            if not output_path:
                return

        output_path = self._normalize_output_path(pdf_path, output_path)
        self.output_path_var.set(output_path)

        group_names = self._get_group_names()
        if not group_names:
            messagebox.showerror("Missing Groups", "Please keep at least one group in the group list.")
            return

        self._set_busy_state(True)
        self.status_var.set("Generating...")
        self._log("Starting PDF processing...")

        self.worker_thread = threading.Thread(
            target=self._run_generation,
            args=(pdf_path, output_path, group_names),
            daemon=True,
        )
        self.worker_thread.start()

    def _run_generation(self, pdf_path: str, output_path: str, group_names: list[str]) -> None:
        try:
            report = process_pdf_to_excel(
                pdf_path=pdf_path,
                output_path=output_path,
                group_names=group_names,
            )
            self.result_queue.put(("success", {"report": report, "output_path": output_path}))
        except Exception as exc:  # noqa: BLE001
            error_message = f"{exc}\n\n{traceback.format_exc()}"
            self.result_queue.put(("error", error_message))

    def _poll_worker_queue(self) -> None:
        try:
            status, payload = self.result_queue.get_nowait()
        except queue.Empty:
            self.after(200, self._poll_worker_queue)
            return

        self._set_busy_state(False)

        if status == "success":
            report = payload["report"]
            output_path = payload["output_path"]
            self.status_var.set("Completed")
            self._log(
                "Finished successfully. "
                f"Extracted rows: {report.extracted_rows}, exported rows: {report.exported_rows}, "
                f"total new due: {float(report.total_new_due):,.2f}, total due: {float(report.total_due):,.2f}"
            )
            messagebox.showinfo(
                "DueClac System",
                f"Excel report generated successfully.\n\nSaved to:\n{output_path}",
            )
        else:
            self.status_var.set("Failed")
            self._log("Generation failed. See the error details below.")
            self._log(str(payload))
            messagebox.showerror("DueClac System", str(payload))

        self.after(200, self._poll_worker_queue)

    def reset_form(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showinfo("DueClac System", "Please wait for the current task to finish.")
            return

        self.pdf_path_var.set("")
        self.output_path_var.set("")
        self.status_var.set("Select a PDF and generate the report.")
        self.group_text.delete("1.0", tk.END)
        self.group_text.insert("1.0", "\n".join(DEFAULT_GROUPS))
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state="disabled")

    def _set_busy_state(self, is_busy: bool) -> None:
        state = tk.DISABLED if is_busy else tk.NORMAL
        self.pdf_button.configure(state=state)
        self.output_button.configure(state=state)
        self.generate_button.configure(state=state)
        self.reset_button.configure(state=state)
        self.group_text.configure(state=state)

    def _get_group_names(self) -> list[str]:
        raw_text = self.group_text.get("1.0", tk.END)
        return [line.strip() for line in raw_text.splitlines() if line.strip()]

    def _normalize_output_path(self, pdf_path: str, output_path: str) -> str:
        pdf_file = Path(pdf_path)
        candidate = Path(output_path).expanduser()
        default_name = f"{pdf_file.stem}_due_report.xlsx"

        if output_path.endswith(("\\", "/")):
            candidate = candidate / default_name
        elif candidate.exists() and candidate.is_dir():
            candidate = candidate / default_name
        elif not candidate.suffix:
            candidate = candidate.with_suffix(".xlsx")
        elif candidate.suffix.lower() != ".xlsx":
            candidate = candidate.with_suffix(".xlsx")

        if str(candidate) != output_path:
            self._log(f"Adjusted output path to: {candidate}")

        return str(candidate)

    def _log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")


def run_app() -> None:
    app = DueClacApp()
    app.mainloop()
