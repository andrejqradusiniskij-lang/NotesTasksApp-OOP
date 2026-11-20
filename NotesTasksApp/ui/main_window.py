import queue
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
import customtkinter as ctk

from models.entry import ChecklistTask, Entry, Note, Task
from models.subtask import Subtask
from services.controller import AppController


class EntryDialog(ctk.CTkToplevel):
    """Діалогове вікно створення або редагування нотатки, задачі чи чек-листа."""

    def __init__(self, parent: "MainWindow", controller: AppController, entry: Entry | None = None):
        super().__init__(parent)
        self.parent = parent
        self.controller = controller
        self.entry = entry
        self.title("Редагування запису" if entry else "Новий запис")
        self.geometry("540x620")
        self.grab_set()

        self.kind_var = ctk.StringVar(value=self._detect_kind(entry))
        ctk.CTkLabel(self, text="Тип запису:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=16, pady=(12, 2))
        self.kind_menu = ctk.CTkOptionMenu(
            self,
            values=["Нотатка", "Задача", "Чек-лист"],
            variable=self.kind_var,
            command=lambda _: self._toggle_task_fields(),
        )
        self.kind_menu.pack(fill="x", padx=16)
        if entry is not None:
            self.kind_menu.configure(state="disabled")

        ctk.CTkLabel(self, text="Заголовок *:").pack(anchor="w", padx=16, pady=(8, 2))
        self.title_entry = ctk.CTkEntry(self, placeholder_text="Введіть заголовок...")
        self.title_entry.pack(fill="x", padx=16)
        if entry:
            self.title_entry.insert(0, entry.title)

        ctk.CTkLabel(self, text="Текст / опис:").pack(anchor="w", padx=16, pady=(8, 2))
        self.text_box = ctk.CTkTextbox(self, height=110)
        self.text_box.pack(fill="x", padx=16)
        if isinstance(entry, Note):
            self.text_box.insert("1.0", entry.text)
        elif isinstance(entry, Task):
            self.text_box.insert("1.0", entry.description)

        # Блок параметрів задачі
        self.task_frame = ctk.CTkFrame(self)
        self.task_frame.pack(fill="x", padx=16, pady=8)

        row1 = ctk.CTkFrame(self.task_frame, fg_color="transparent")
        row1.pack(fill="x", padx=8, pady=6)
        ctk.CTkLabel(row1, text="Пріоритет:").pack(side="left")
        self.prio_var = ctk.StringVar(value=entry.priority if isinstance(entry, Task) else "Середній")
        ctk.CTkOptionMenu(row1, values=list(Task.VALID_PRIORITIES), variable=self.prio_var, width=130).pack(side="left", padx=(6, 16))

        ctk.CTkLabel(row1, text="Стан:").pack(side="left")
        self.status_var = ctk.StringVar(value=entry.status if isinstance(entry, Task) else "Нова")
        ctk.CTkOptionMenu(row1, values=list(Task.VALID_STATUSES), variable=self.status_var, width=130).pack(side="left", padx=6)

        row2 = ctk.CTkFrame(self.task_frame, fg_color="transparent")
        row2.pack(fill="x", padx=8, pady=6)
        ctk.CTkLabel(row2, text="Термін (РРРР-ММ-ДД ГГ:ХХ):").pack(side="left")
        self.deadline_entry = ctk.CTkEntry(row2, placeholder_text="2026-12-25 18:00")
        self.deadline_entry.pack(side="left", fill="x", expand=True, padx=6)
        if isinstance(entry, Task) and entry.get_deadline():
            self.deadline_entry.insert(0, entry.get_deadline().strftime(Entry.DATE_FORMAT))

        self.subtask_label = ctk.CTkLabel(self.task_frame, text="Підзадачі (по одній у рядку; [x] — виконана):")
        self.subtask_box = ctk.CTkTextbox(self.task_frame, height=85)
        if isinstance(entry, ChecklistTask):
            lines = [f"{'[x] ' if s.completed else ''}{s.title}" for s in entry.subtasks]
            self.subtask_box.insert("1.0", "\n".join(lines))

        # Вибір тегів
        ctk.CTkLabel(self, text="Теги:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=16, pady=(6, 2))
        self.tags_scroll = ctk.CTkScrollableFrame(self, height=85)
        self.tags_scroll.pack(fill="x", padx=16)
        self.tag_vars: dict[str, ctk.BooleanVar] = {}
        active_tags = set(entry.get_tags()) if entry else set()
        for tag_name in self.controller.tags:
            var = ctk.BooleanVar(value=tag_name in active_tags)
            self.tag_vars[tag_name] = var
            ctk.CTkCheckBox(self.tags_scroll, text=tag_name, variable=var).pack(anchor="w", pady=2)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=14)
        ctk.CTkButton(btn_row, text="Зберегти", command=self._on_save).pack(side="right", padx=6)
        ctk.CTkButton(btn_row, text="Скасувати", fg_color="gray40", command=self.destroy).pack(side="right")

        self._toggle_task_fields()

    @staticmethod
    def _detect_kind(entry: Entry | None) -> str:
        if isinstance(entry, ChecklistTask):
            return "Чек-лист"
        if isinstance(entry, Task):
            return "Задача"
        return "Нотатка"

    def _toggle_task_fields(self) -> None:
        kind = self.kind_var.get()
        if kind == "Нотатка":
            self.task_frame.pack_forget()
        else:
            self.task_frame.pack(fill="x", padx=16, pady=8, before=self.tags_scroll)
            if kind == "Чек-лист":
                self.subtask_label.pack(anchor="w", padx=8, pady=(4, 2))
                self.subtask_box.pack(fill="x", padx=8, pady=(0, 6))
            else:
                self.subtask_label.pack_forget()
                self.subtask_box.pack_forget()

    def _on_save(self) -> None:
        try:
            title = self.title_entry.get()
            text = self.text_box.get("1.0", "end").strip()
            selected_tags = [name for name, var in self.tag_vars.items() if var.get()]
            kind = self.kind_var.get()
            created_at = self.entry.created_at if self.entry else datetime.now()
            entry_id = self.entry.id if self.entry else None

            if kind == "Нотатка":
                obj: Entry = Note(title=title, text=text, created_at=created_at, tags=selected_tags, entry_id=entry_id)
            else:
                dl_raw = self.deadline_entry.get().strip()
                deadline = Entry.parse_datetime(dl_raw) if dl_raw else None
                if kind == "Задача":
                    obj = Task(
                        title=title,
                        description=text,
                        priority=self.prio_var.get(),
                        status=self.status_var.get(),
                        deadline=deadline,
                        created_at=created_at,
                        tags=selected_tags,
                        entry_id=entry_id,
                    )
                else:
                    subtasks: list[Subtask] = []
                    for line in self.subtask_box.get("1.0", "end").splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        if line.lower().startswith("[x]"):
                            subtasks.append(Subtask(line[3:].strip(), completed=True))
                        else:
                            subtasks.append(Subtask(line, completed=False))
                    obj = ChecklistTask(
                        title=title,
                        description=text,
                        priority=self.prio_var.get(),
                        status=self.status_var.get(),
                        deadline=deadline,
                        subtasks=subtasks,
                        created_at=created_at,
                        tags=selected_tags,
                        entry_id=entry_id,
                    )

            if self.entry is None:
                self.controller.add_entry(obj)
            else:
                self.controller.update_entry(obj)
            self.parent.refresh_all()
            self.destroy()
        except Exception as exc:
            messagebox.showerror("Помилка валідації", str(exc), parent=self)


class TagManagerDialog(ctk.CTkToplevel):
    """Вікно керування тегами (створення, редагування, видалення)."""

    def __init__(self, parent: "MainWindow", controller: AppController):
        super().__init__(parent)
        self.parent = parent
        self.controller = controller
        self.title("Керування тегами")
        self.geometry("430x420")
        self.grab_set()

        form = ctk.CTkFrame(self)
        form.pack(fill="x", padx=14, pady=12)
        self.name_entry = ctk.CTkEntry(form, placeholder_text="Назва тегу (напр. Навчання)")
        self.name_entry.pack(side="left", fill="x", expand=True, padx=(8, 6), pady=8)
        self.color_entry = ctk.CTkEntry(form, width=90)
        self.color_entry.insert(0, "#2B7DE9")
        self.color_entry.pack(side="left", padx=4)
        ctk.CTkButton(form, text="Додати", width=80, command=self._add_tag).pack(side="left", padx=(4, 8))

        self.list_frame = ctk.CTkScrollableFrame(self)
        self.list_frame.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        self._render_tags()

    def _render_tags(self) -> None:
        for child in self.list_frame.winfo_children():
            child.destroy()
        for tag in self.controller.tags.values():
            row = ctk.CTkFrame(self.list_frame)
            row.pack(fill="x", pady=3)
            badge = ctk.CTkLabel(row, text="  ", fg_color=tag.color, corner_radius=4, width=22)
            badge.pack(side="left", padx=8, pady=6)
            ctk.CTkLabel(row, text=f"{tag.name} ({tag.color})").pack(side="left", padx=6)
            ctk.CTkButton(
                row,
                text="Видалити",
                width=80,
                fg_color="#B83232",
                hover_color="#8E2424",
                command=lambda n=tag.name: self._delete_tag(n),
            ).pack(side="right", padx=8)

    def _add_tag(self) -> None:
        try:
            self.controller.create_tag(self.name_entry.get(), self.color_entry.get())
            self.name_entry.delete(0, "end")
            self._render_tags()
            self.parent.refresh_all()
        except Exception as exc:
            messagebox.showerror("Помилка", str(exc), parent=self)

    def _delete_tag(self, name: str) -> None:
        try:
            self.controller.delete_tag(name, force=False)
        except ValueError as warn:
            if messagebox.askyesno("Підтвердження", f"{warn}\nВидалити тег і відкріпити його?", parent=self):
                self.controller.delete_tag(name, force=True)
            else:
                return
        self._render_tags()
        self.parent.refresh_all()


class MainWindow(ctk.CTk):
    """Головне вікно застосунку нотаток і задач з тегами."""

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self.title("Менеджер нотаток та задач з тегами (Python 3.14 / CustomTkinter)")
        self.geometry("1180x700")
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.selected_filter_tags: dict[str, ctk.BooleanVar] = {}
        self._build_layout()
        self.refresh_all()
        self.after(100, self._poll_progress_queue)

    def _build_layout(self) -> None:
        # Верхня панель інструментів
        toolbar = ctk.CTkFrame(self)
        toolbar.pack(fill="x", padx=12, pady=(10, 6))

        ctk.CTkButton(toolbar, text="+ Створити запис", command=self._open_create_dialog).pack(side="left", padx=6, pady=8)
        ctk.CTkButton(toolbar, text="Редагувати", command=self._open_edit_dialog).pack(side="left", padx=4)
        ctk.CTkButton(toolbar, text="Видалити", fg_color="#B83232", hover_color="#8E2424", command=self._delete_selected).pack(side="left", padx=4)
        ctk.CTkButton(toolbar, text="Теги", fg_color="#2E7D32", hover_color="#1B5E20", command=self._open_tags_dialog).pack(side="left", padx=10)

        ctk.CTkButton(toolbar, text="Експорт XML (звіт)", command=self._export_xml).pack(side="right", padx=6)
        ctk.CTkButton(toolbar, text="Експорт JSON", command=self._export_json).pack(side="right", padx=4)
        ctk.CTkButton(toolbar, text="Імпорт JSON (фон)", command=self._import_json_bg).pack(side="right", padx=4)

        # Основна область: ліва бічна панель фільтрів + права таблиця
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=4)

        sidebar = ctk.CTkFrame(body, width=250)
        sidebar.pack(side="left", fill="y", padx=(0, 10))
        sidebar.pack_propagate(False)

        ctk.CTkLabel(sidebar, text="Пошук та фільтри", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=12, pady=(12, 6))
        self.search_entry = ctk.CTkEntry(sidebar, placeholder_text="Повнотекстовий пошук...")
        self.search_entry.pack(fill="x", padx=12, pady=4)
        self.search_entry.bind("<KeyRelease>", lambda _: self.refresh_table())

        ctk.CTkLabel(sidebar, text="Пріоритет задачі:").pack(anchor="w", padx=12, pady=(8, 2))
        self.prio_filter = ctk.CTkOptionMenu(
            sidebar,
            values=["Усі", "Високий", "Середній", "Низький"],
            command=lambda _: self.refresh_table(),
        )
        self.prio_filter.pack(fill="x", padx=12)

        ctk.CTkLabel(sidebar, text="Стан задачі:").pack(anchor="w", padx=12, pady=(8, 2))
        self.status_filter = ctk.CTkOptionMenu(
            sidebar,
            values=["Усі", "Нова", "В роботі", "Виконано", "Прострочені"],
            command=lambda _: self.refresh_table(),
        )
        self.status_filter.pack(fill="x", padx=12)

        ctk.CTkLabel(sidebar, text="Сортування:").pack(anchor="w", padx=12, pady=(8, 2))
        self.sort_menu = ctk.CTkOptionMenu(
            sidebar,
            values=["Дата створення (новіші)", "Дата створення (старіші)", "Термін виконання (зрост.)", "Термін виконання (спад.)"],
            command=lambda _: self.refresh_table(),
        )
        self.sort_menu.pack(fill="x", padx=12)

        ctk.CTkLabel(sidebar, text="Фільтр за тегами (AND):").pack(anchor="w", padx=12, pady=(10, 2))
        self.tags_filter_box = ctk.CTkScrollableFrame(sidebar, height=220)
        self.tags_filter_box.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        # Таблиця ttk.Treeview
        table_container = ctk.CTkFrame(body)
        table_container.pack(side="left", fill="both", expand=True)

        columns = ("type", "title", "tags", "priority", "status", "deadline", "created")
        self.tree = ttk.Treeview(table_container, columns=columns, show="headings", selectmode="browse")
        headers = {
            "type": ("Тип", 95),
            "title": ("Зведення / Заголовок", 330),
            "tags": ("Теги", 150),
            "priority": ("Пріоритет", 95),
            "status": ("Стан", 105),
            "deadline": ("Термін", 125),
            "created": ("Створено", 125),
        }
        for col, (text, width) in headers.items():
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="w")

        vsb = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        vsb.pack(side="right", fill="y", padx=(0, 6), pady=8)
        self.tree.bind("<Double-1>", lambda _: self._open_edit_dialog())

        # Нижня панель статусу та індикатор прогресу
        status_bar = ctk.CTkFrame(self)
        status_bar.pack(fill="x", padx=12, pady=(4, 10))

        self.status_label = ctk.CTkLabel(status_bar, text="Готово до роботи")
        self.status_label.pack(side="left", padx=12, pady=6)

        self.progress_bar = ctk.CTkProgressBar(status_bar, width=260)
        self.progress_bar.set(0)
        self.progress_bar.pack(side="right", padx=12, pady=6)

    def refresh_all(self) -> None:
        self._rebuild_tag_filters()
        self.refresh_table()

    def _rebuild_tag_filters(self) -> None:
        prev_selected = {k for k, v in self.selected_filter_tags.items() if v.get()}
        for child in self.tags_filter_box.winfo_children():
            child.destroy()
        self.selected_filter_tags.clear()
        for tag_name in self.controller.tags:
            var = ctk.BooleanVar(value=tag_name in prev_selected)
            self.selected_filter_tags[tag_name] = var
            ctk.CTkCheckBox(
                self.tags_filter_box,
                text=tag_name,
                variable=var,
                command=self.refresh_table,
            ).pack(anchor="w", pady=2)

    def _map_sort_key(self) -> str:
        mapping = {
            "Дата створення (новіші)": "created_desc",
            "Дата створення (старіші)": "created_asc",
            "Термін виконання (зрост.)": "deadline_asc",
            "Термін виконання (спад.)": "deadline_desc",
        }
        return mapping.get(self.sort_menu.get(), "created_desc")

    def refresh_table(self) -> None:
        for row in self.tree.get_children():
            self.tree.delete(row)

        active_tags = [k for k, v in self.selected_filter_tags.items() if v.get()]
        items = self.controller.query_entries(
            search_text=self.search_entry.get(),
            required_tags=active_tags,
            priority_filter=self.prio_filter.get(),
            status_filter=self.status_filter.get(),
            sort_by=self._map_sort_key(),
        )

        # Відображаємо перші 1000 рядків у GUI для миттєвого відгуку при 10 000+ записах
        for entry in items[:1000]:
            if isinstance(entry, ChecklistTask):
                kind_str = "Чек-лист"
            elif isinstance(entry, Task):
                kind_str = "Задача"
            else:
                kind_str = "Нотатка"

            prio = entry.priority if isinstance(entry, Task) else "—"
            status = entry.status if isinstance(entry, Task) else "—"
            if isinstance(entry, Task) and entry.is_overdue():
                status += " (!)"
            dl = entry.get_deadline().strftime(Entry.DATE_FORMAT) if isinstance(entry, Task) and entry.get_deadline() else "—"
            created = entry.created_at.strftime(Entry.DATE_FORMAT)
            tags_str = ", ".join(entry.get_tags()) if entry.get_tags() else "—"

            self.tree.insert(
                "",
                "end",
                iid=entry.id,
                values=(kind_str, entry.summary(), tags_str, prio, status, dl, created),
            )

        bench = self.controller.last_benchmark
        bench_text = ""
        if bench:
            bench_text = (
                f" | Індекс: T1={bench['t1_ms']:.1f} мс, "
                f"T{bench['workers']}={bench['tn_ms']:.1f} мс, S={bench['speedup']:.2f}"
            )
        self.status_label.configure(
            text=f"Показано {min(len(items), 1000)} із {len(items)} знайдених (усього: {len(self.controller.entries)}){bench_text}"
        )

    def _open_create_dialog(self) -> None:
        EntryDialog(self, self.controller, entry=None)

    def _open_edit_dialog(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Увага", "Оберіть запис у таблиці для редагування.")
            return
        entry = self.controller.get_entry_by_id(sel[0])
        if entry:
            EntryDialog(self, self.controller, entry=entry)

    def _delete_selected(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Увага", "Оберіть запис у таблиці для видалення.")
            return
        if messagebox.askyesno("Підтвердження", "Видалити обраний запис?"):
            self.controller.delete_entry(sel[0])
            self.refresh_table()

    def _open_tags_dialog(self) -> None:
        TagManagerDialog(self, self.controller)

    def _import_json_bg(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON файли", "*.json")])
        if not path:
            return
        self.progress_bar.set(0.05)
        self.status_label.configure(text="Запуск фонового імпорту...")
        self.controller.start_background_import(path)

    def _export_json(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON файли", "*.json")])
        if not path:
            return
        try:
            self.controller.export_json(path)
            messagebox.showinfo("Експорт", "Дані успішно збережено у JSON.")
        except Exception as exc:
            messagebox.showerror("Помилка", str(exc))

    def _export_xml(self) -> None:
        if not self.controller.tags:
            messagebox.showwarning("Увага", "Немає жодного тегу для формування звіту.")
            return
        dialog = ctk.CTkInputDialog(
            text=f"Введіть назву тегу ({', '.join(self.controller.tags.keys())}):",
            title="XML-звіт за тегом",
        )
        tag_name = dialog.get_input()
        if not tag_name:
            return
        path = filedialog.asksaveasfilename(defaultextension=".xml", filetypes=[("XML файли", "*.xml")])
        if not path:
            return
        try:
            count = self.controller.export_xml_report(path, tag_name.strip())
            messagebox.showinfo("XML-звіт", f"Звіт сформовано (включено задач: {count}).")
        except Exception as exc:
            messagebox.showerror("Помилка", str(exc))

    def _poll_progress_queue(self) -> None:
        try:
            while True:
                msg_type, *payload = self.controller.progress_queue.get_nowait()
                if msg_type == "progress":
                    ratio, text = payload
                    self.progress_bar.set(ratio)
                    self.status_label.configure(text=text)
                elif msg_type == "done":
                    data = payload[0]
                    self.controller.apply_imported_data(data)
                    self.progress_bar.set(1.0)
                    self.refresh_all()
                elif msg_type == "error":
                    self.progress_bar.set(0.0)
                    self.status_label.configure(text="Помилка імпорту")
                    messagebox.showerror("Помилка імпорту JSON", payload[0])
        except queue.Empty:
            pass
        finally:
            self.after(100, self._poll_progress_queue)
