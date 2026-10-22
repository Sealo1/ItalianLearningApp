import csv
import json
import random
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.parse import quote, unquote


LEGACY_DATA_FILE = Path(__file__).with_name("italian_english_flashcards.json")
CSV_DIRECTORY = Path(__file__).with_name("flashcard_sets")


class FlashcardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Flashcards")
        self.root.geometry("920x700")
        self.root.minsize(740, 600)
        self.root.configure(background="#F3F6F2")

        self.sets = self.load_sets()
        self.current_set_index = 0
        self.learn_index = 0
        self.learn_flipped = False
        self.test_deck = []
        self.test_index = 0
        self.test_score = 0
        self.test_answer_count = 0
        self.test_answered = False
        self.test_running = False

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#F3F6F2")
        style.configure("TLabel", background="#F3F6F2", foreground="#20352E")
        style.configure("Title.TLabel", background="#173F35", foreground="#FFFFFF",
                        font=("Segoe UI", 19, "bold"))
        style.configure("Card.TLabel", background="#FFFFFF", foreground="#173F35",
                        font=("Segoe UI", 23, "bold"), padding=28)
        style.configure("TButton", background="#173F35", foreground="#FFFFFF", padding=(10, 6))
        style.map("TButton", background=[("active", "#28614F"), ("disabled", "#AAB8B1")])
        style.configure("TNotebook", background="#F3F6F2", borderwidth=0)
        style.configure("TNotebook.Tab", background="#DDE8E0", foreground="#20352E",
                        padding=(14, 8))
        style.map("TNotebook.Tab", background=[("selected", "#E6B44A")])
        style.configure("Treeview", background="#FFFFFF", fieldbackground="#FFFFFF",
                        foreground="#20352E", rowheight=28)
        style.map("Treeview", background=[("selected", "#B8D8C4")],
                  foreground=[("selected", "#173F35")])
        style.configure("Correct.TLabel", foreground="#26734D", font=("Segoe UI", 10, "bold"))
        style.configure("Incorrect.TLabel", foreground="#B3483C", font=("Segoe UI", 10, "bold"))

        header = ttk.Frame(root, padding=(20, 18, 20, 14), style="Header.TFrame")
        style.configure("Header.TFrame", background="#173F35")
        header.pack(fill="x")
        ttk.Label(header, text="Flashcards", style="Title.TLabel").pack(side="left")

        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill="both", expand=True, padx=20, pady=(0, 18))

        self.manage_tab = ttk.Frame(self.tabs, padding=16)
        self.learn_tab = ttk.Frame(self.tabs, padding=16)
        self.test_tab = ttk.Frame(self.tabs, padding=16)
        self.tabs.add(self.manage_tab, text="My sets")
        self.tabs.add(self.learn_tab, text="Learn")
        self.tabs.add(self.test_tab, text="Test")

        self.build_manage_tab()
        self.build_learn_tab()
        self.build_test_tab()
        self.refresh_set_options()
        self.refresh_cards()
        self.show_learning_card()
        if not any(CSV_DIRECTORY.glob("*.csv")):
            self.save_sets()

    def default_set(self):
        return {
            "name": "Italian / English",
            "front_label": "English",
            "back_label": "Italian",
            "file_name": "Italian - English",
            "cards": [],
        }

    def load_sets(self):
        csv_files = sorted(CSV_DIRECTORY.glob("*.csv")) if CSV_DIRECTORY.exists() else []
        if csv_files:
            loaded_sets = []
            for csv_path in csv_files:
                try:
                    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
                        reader = csv.reader(file)
                        headers = next(reader, None)
                        if not headers or len(headers) != 2 or not all(label.strip() for label in headers):
                            raise ValueError("The first row must contain two non-empty column titles.")
                        cards = []
                        for row_number, row in enumerate(reader, start=2):
                            if not row or (len(row) == 2 and not any(value.strip() for value in row)):
                                continue
                            if len(row) != 2 or not all(value.strip() for value in row):
                                raise ValueError(f"Row {row_number} must contain two non-empty values.")
                            cards.append({"front": row[0], "back": row[1]})
                    loaded_sets.append(
                        {
                            "name": unquote(csv_path.stem),
                            "front_label": headers[0].strip(),
                            "back_label": headers[1].strip(),
                            "file_name": csv_path.stem,
                            "cards": cards,
                        }
                    )
                except (OSError, csv.Error, ValueError) as error:
                    messagebox.showwarning("Could not load CSV set", f"{csv_path.name}: {error}")
            return loaded_sets or [self.default_set()]

        try:
            with LEGACY_DATA_FILE.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            return [self.default_set()]
        except (OSError, json.JSONDecodeError) as error:
            messagebox.showwarning("Could not load cards", str(error))
            return [self.default_set()]

        if isinstance(data, list):
            if any(
                not isinstance(card, dict)
                or not isinstance(card.get("english"), str)
                or not isinstance(card.get("italian"), str)
                for card in data
            ):
                messagebox.showwarning("Could not load cards", "The saved deck has an invalid format.")
                return [self.default_set()]
            migrated = self.default_set()
            migrated["cards"] = [
                {"front": card["english"], "back": card["italian"]} for card in data
            ]
            migrated_sets = [migrated]
        elif not isinstance(data, dict) or not isinstance(data.get("sets"), list):
            messagebox.showwarning("Could not load cards", "The saved deck has an invalid format.")
            return [self.default_set()]
        else:
            migrated_sets = []
            for card_set in data["sets"]:
                if (
                    not isinstance(card_set, dict)
                    or not all(isinstance(card_set.get(key), str) for key in
                               ("name", "front_label", "back_label"))
                    or not isinstance(card_set.get("cards"), list)
                    or any(
                        not isinstance(card, dict)
                        or not isinstance(card.get("front"), str)
                        or not isinstance(card.get("back"), str)
                        for card in card_set["cards"]
                    )
                ):
                    messagebox.showwarning("Could not load cards", "The saved sets have an invalid format.")
                    return [self.default_set()]
                migrated_sets.append(
                    {
                        "name": card_set["name"],
                        "front_label": card_set["front_label"],
                        "back_label": card_set["back_label"],
                        "cards": card_set["cards"],
                    }
                )

        used_file_names = []
        for card_set in migrated_sets:
            card_set["file_name"] = self.make_file_name(card_set["name"], used_file_names)
            used_file_names.append(card_set["file_name"])
        if migrated_sets:
            self.save_sets(migrated_sets)
            return migrated_sets
        return [self.default_set()]

    def make_file_name(self, name, other_file_names=(), ignore_file_name=None):
        base_name = quote(name.strip(), safe=" ()_-") or "Flashcards"
        reserved = {file_name.casefold() for file_name in other_file_names}
        candidate = base_name
        suffix = 2
        while candidate.casefold() in reserved or (
            (CSV_DIRECTORY / f"{candidate}.csv").exists()
            and candidate.casefold() not in reserved
            and candidate.casefold() != (ignore_file_name or "").casefold()
        ):
            candidate = f"{base_name} ({suffix})"
            suffix += 1
        return candidate

    def save_sets(self, sets=None):
        sets_to_save = self.sets if sets is None else sets
        try:
            CSV_DIRECTORY.mkdir(parents=True, exist_ok=True)
            for card_set in sets_to_save:
                csv_path = CSV_DIRECTORY / f"{card_set['file_name']}.csv"
                with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
                    writer = csv.writer(file, lineterminator="\n")
                    writer.writerow((card_set["front_label"], card_set["back_label"]))
                    writer.writerows((card["front"], card["back"]) for card in card_set["cards"])
        except OSError as error:
            messagebox.showerror("Could not save CSV flashcards", str(error))
            return False
        return True

    def build_manage_tab(self):
        set_toolbar = ttk.Frame(self.manage_tab)
        set_toolbar.pack(fill="x", pady=(0, 12))
        ttk.Label(set_toolbar, text="Set").pack(side="left", padx=(0, 8))
        self.current_set_var = tk.StringVar()
        self.set_picker = ttk.Combobox(
            set_toolbar, textvariable=self.current_set_var, state="readonly", width=28
        )
        self.set_picker.pack(side="left", padx=(0, 8))
        self.set_picker.bind("<<ComboboxSelected>>", self.change_current_set)
        ttk.Button(set_toolbar, text="New set", command=self.add_set).pack(side="left")
        ttk.Button(set_toolbar, text="Rename", command=self.rename_set).pack(side="left", padx=6)
        ttk.Button(set_toolbar, text="Delete set", command=self.delete_set).pack(side="left")
        ttk.Button(set_toolbar, text="Import CSV", command=self.import_csv_set).pack(
            side="left", padx=(6, 0)
        )

        toolbar = ttk.Frame(self.manage_tab)
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Button(toolbar, text="Add card", command=self.add_card).pack(side="left")
        ttk.Button(toolbar, text="Edit selected", command=self.edit_selected).pack(side="left", padx=8)
        ttk.Button(toolbar, text="Delete selected", command=self.delete_selected).pack(side="left")

        listing = ttk.Frame(self.manage_tab)
        listing.pack(fill="both", expand=True)
        self.card_tree = ttk.Treeview(
            listing,
            columns=("front", "back"),
            show="headings",
            selectmode="browse",
        )
        self.card_tree.heading("front", text="Front")
        self.card_tree.heading("back", text="Back")
        self.card_tree.column("front", width=340, anchor="w")
        self.card_tree.column("back", width=340, anchor="w")
        scrollbar = ttk.Scrollbar(listing, orient="vertical", command=self.card_tree.yview)
        self.card_tree.configure(yscrollcommand=scrollbar.set)
        self.card_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    @property
    def current_set(self):
        return self.sets[self.current_set_index]

    def refresh_set_options(self):
        names = [card_set["name"] for card_set in self.sets]
        self.set_picker.configure(values=names)
        self.current_set_var.set(self.current_set["name"])
        self.card_tree.heading("front", text=self.current_set["front_label"])
        self.card_tree.heading("back", text=self.current_set["back_label"])
        if hasattr(self, "learn_set_picker"):
            self.learn_set_picker.configure(values=names)
        self.learn_direction_picker.configure(
            values=(self.current_set["front_label"], self.current_set["back_label"])
        )
        self.learn_direction.set(self.current_set["front_label"])
        if hasattr(self, "test_set_listbox"):
            self.test_set_listbox.delete(0, tk.END)
            for card_set in self.sets:
                count = len(card_set["cards"])
                self.test_set_listbox.insert(tk.END, f"{card_set['name']} ({count} cards)")
            self.test_set_listbox.selection_set(self.current_set_index)

    def change_current_set(self, _event=None):
        name = self.current_set_var.get()
        self.current_set_index = next(
            index for index, card_set in enumerate(self.sets) if card_set["name"] == name
        )
        self.learn_index = 0
        self.learn_flipped = False
        self.refresh_set_options()
        self.refresh_cards()

    def add_set(self):
        self.open_set_editor()

    def import_csv_set(self):
        source_path = filedialog.askopenfilename(
            title="Import flashcard set",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
        )
        if not source_path:
            return
        source_path = Path(source_path)
        try:
            with source_path.open("r", encoding="utf-8-sig", newline="") as file:
                reader = csv.reader(file)
                headers = next(reader, None)
                if not headers or len(headers) != 2 or not all(label.strip() for label in headers):
                    raise ValueError("The first row must contain two non-empty column titles.")
                cards = []
                for row_number, row in enumerate(reader, start=2):
                    if not row or (len(row) == 2 and not any(value.strip() for value in row)):
                        continue
                    if len(row) != 2 or not all(value.strip() for value in row):
                        raise ValueError(f"Row {row_number} must contain two non-empty values.")
                    cards.append({"front": row[0], "back": row[1]})
        except (OSError, csv.Error, ValueError) as error:
            messagebox.showerror("Could not import CSV", str(error))
            return

        base_name = source_path.stem.strip() or "Imported set"
        name = base_name
        suffix = 2
        existing_names = {card_set["name"].casefold() for card_set in self.sets}
        while name.casefold() in existing_names:
            name = f"{base_name} ({suffix})"
            suffix += 1
        used_file_names = (card_set["file_name"] for card_set in self.sets)
        self.sets.append(
            {
                "name": name,
                "front_label": headers[0].strip(),
                "back_label": headers[1].strip(),
                "file_name": self.make_file_name(name, used_file_names),
                "cards": cards,
            }
        )
        self.current_set_index = len(self.sets) - 1
        self.learn_index = 0
        self.learn_flipped = False
        if not self.save_sets():
            self.sets.pop()
            self.current_set_index = max(0, len(self.sets) - 1)
            return
        self.refresh_set_options()
        self.refresh_cards()

    def rename_set(self):
        self.open_set_editor(self.current_set_index)

    def delete_set(self):
        if len(self.sets) == 1:
            messagebox.showinfo("Keep one set", "The last set cannot be deleted.")
            return
        if not messagebox.askyesno(
            "Delete set", f"Delete '{self.current_set['name']}' and all its flashcards?"
        ):
            return
        removed_set = self.sets.pop(self.current_set_index)
        self.current_set_index = min(self.current_set_index, len(self.sets) - 1)
        self.learn_index = 0
        if not self.save_sets():
            self.sets.insert(self.current_set_index, removed_set)
            return
        try:
            (CSV_DIRECTORY / f"{removed_set['file_name']}.csv").unlink(missing_ok=True)
        except OSError as error:
            messagebox.showwarning("Could not remove CSV file", str(error))
        self.refresh_set_options()
        self.refresh_cards()

    def open_set_editor(self, index=None):
        existing = self.sets[index] if index is not None else None
        dialog = tk.Toplevel(self.root)
        dialog.title("Rename set" if existing else "Create a set")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.grab_set()

        content = ttk.Frame(dialog, padding=18)
        content.pack(fill="both", expand=True)
        fields = (
            ("Set name", existing["name"] if existing else ""),
            ("Front label", existing["front_label"] if existing else "Front"),
            ("Back label", existing["back_label"] if existing else "Back"),
        )
        variables = []
        for row, (label, value) in enumerate(fields):
            variable = tk.StringVar(value=value)
            variables.append(variable)
            ttk.Label(content, text=label).grid(row=row * 2, column=0, sticky="w", pady=(0, 4))
            entry = ttk.Entry(content, textvariable=variable, width=38)
            entry.grid(row=row * 2 + 1, column=0, sticky="ew", pady=(0, 10))
            if row == 0:
                name_entry = entry

        def save():
            name, front_label, back_label = (variable.get().strip() for variable in variables)
            if not name or not front_label or not back_label:
                messagebox.showerror("Missing information", "Fill in all three fields.", parent=dialog)
                return
            if front_label.casefold() == back_label.casefold():
                messagebox.showerror("Labels must differ", "Choose a different label for each side.", parent=dialog)
                return
            if any(
                other_index != index and card_set["name"].casefold() == name.casefold()
                for other_index, card_set in enumerate(self.sets)
            ):
                messagebox.showerror("Name already used", "Choose a unique set name.", parent=dialog)
                return
            if existing:
                old_name = existing["name"]
                old_file_name = existing["file_name"]
                other_file_names = (
                    card_set["file_name"]
                    for other_index, card_set in enumerate(self.sets)
                    if other_index != index
                )
                existing.update(
                    name=name,
                    front_label=front_label,
                    back_label=back_label,
                    file_name=self.make_file_name(
                        name, other_file_names, ignore_file_name=old_file_name
                    ),
                )
            else:
                self.sets.append(
                    {
                        "name": name,
                        "front_label": front_label,
                        "back_label": back_label,
                        "file_name": self.make_file_name(
                            name, (card_set["file_name"] for card_set in self.sets)
                        ),
                        "cards": [],
                    }
                )
                self.current_set_index = len(self.sets) - 1
            self.learn_index = 0
            self.learn_flipped = False
            if not self.save_sets():
                if existing:
                    existing.update(
                        name=old_name,
                        front_label=fields[1][1],
                        back_label=fields[2][1],
                        file_name=old_file_name,
                    )
                else:
                    self.sets.pop()
                    self.current_set_index = max(0, len(self.sets) - 1)
                return
            if existing and old_file_name != existing["file_name"]:
                try:
                    (CSV_DIRECTORY / f"{old_file_name}.csv").unlink(missing_ok=True)
                except OSError as error:
                    messagebox.showwarning("Could not remove old CSV file", str(error))
            self.refresh_set_options()
            self.refresh_cards()
            dialog.destroy()

        buttons = ttk.Frame(content)
        buttons.grid(row=6, column=0, sticky="e", pady=(4, 0))
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Save", command=save).pack(side="left")
        name_entry.focus_set()
        dialog.bind("<Return>", lambda _event: save())

    def refresh_cards(self):
        self.card_tree.delete(*self.card_tree.get_children())
        for index, card in enumerate(self.current_set["cards"]):
            self.card_tree.insert(
                "", "end", iid=str(index), values=(card["front"], card["back"])
            )
        self.show_learning_card()

    def selected_card_index(self):
        selection = self.card_tree.selection()
        return int(selection[0]) if selection else None

    def add_card(self):
        self.open_card_editor()

    def edit_selected(self):
        index = self.selected_card_index()
        if index is None:
            messagebox.showinfo("Select a card", "Choose a card to edit.")
            return
        self.open_card_editor(index)

    def delete_selected(self):
        index = self.selected_card_index()
        if index is None:
            messagebox.showinfo("Select a card", "Choose a card to delete.")
            return
        if not messagebox.askyesno("Delete card", "Delete this flashcard?"):
            return
        del self.current_set["cards"][index]
        self.save_sets()
        self.learn_index = min(self.learn_index, max(0, len(self.current_set["cards"]) - 1))
        self.refresh_cards()

    def open_card_editor(self, index=None):
        card = self.current_set["cards"][index] if index is not None else {"front": "", "back": ""}
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit flashcard" if index is not None else "Add flashcard")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.grab_set()

        content = ttk.Frame(dialog, padding=18)
        content.pack(fill="both", expand=True)
        front_var = tk.StringVar(value=card["front"])
        back_var = tk.StringVar(value=card["back"])
        ttk.Label(content, text=self.current_set["front_label"]).grid(
            row=0, column=0, sticky="w", pady=(0, 5)
        )
        front_entry = ttk.Entry(content, textvariable=front_var, width=42)
        front_entry.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(content, text=self.current_set["back_label"]).grid(
            row=2, column=0, sticky="w", pady=(0, 5)
        )
        back_entry = ttk.Entry(content, textvariable=back_var, width=42)
        back_entry.grid(row=3, column=0, sticky="ew")

        def save():
            front = front_var.get()
            back = back_var.get()
            if not front.strip() or not back.strip():
                messagebox.showerror("Missing information", "Enter both sides of the card.", parent=dialog)
                return
            new_card = {"front": front, "back": back}
            if index is None:
                self.current_set["cards"].append(new_card)
            else:
                self.current_set["cards"][index] = new_card
            self.save_sets()
            self.refresh_cards()
            self.refresh_set_options()
            dialog.destroy()

        buttons = ttk.Frame(content)
        buttons.grid(row=4, column=0, sticky="e", pady=(16, 0))
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Save", command=save).pack(side="left")
        front_entry.focus_set()
        dialog.bind("<Return>", lambda _event: save())

    def build_learn_tab(self):
        controls = ttk.Frame(self.learn_tab)
        controls.pack(fill="x", pady=(0, 16))
        ttk.Label(controls, text="Set").pack(side="left", padx=(0, 6))
        self.learn_set_picker = ttk.Combobox(
            controls, textvariable=self.current_set_var, state="readonly", width=24
        )
        self.learn_set_picker.pack(side="left", padx=(0, 14))
        self.learn_set_picker.bind("<<ComboboxSelected>>", self.change_current_set)
        ttk.Label(controls, text="Show first:").pack(side="left")
        self.learn_direction = tk.StringVar()
        self.learn_direction_picker = ttk.Combobox(
            controls,
            textvariable=self.learn_direction,
            values=("Front", "Back"),
            state="readonly",
            width=18,
        )
        self.learn_direction_picker.pack(side="left", padx=8)
        self.learn_direction_picker.bind(
            "<<ComboboxSelected>>", lambda _event: self.show_learning_card()
        )

        self.learn_counter = tk.StringVar()
        ttk.Label(controls, textvariable=self.learn_counter).pack(side="right")
        self.learn_text = tk.StringVar()
        self.learn_label = ttk.Label(
            self.learn_tab,
            textvariable=self.learn_text,
            style="Card.TLabel",
            anchor="center",
            justify="center",
            relief="groove",
        )
        self.learn_label.pack(fill="both", expand=True, pady=(0, 16))

        navigation = ttk.Frame(self.learn_tab)
        navigation.pack(fill="x")
        self.previous_button = ttk.Button(
            navigation, text="Previous", command=lambda: self.move_learning(-1)
        )
        self.previous_button.pack(side="left")
        self.flip_button = ttk.Button(navigation, text="Flip card", command=self.flip_card)
        self.flip_button.pack(side="left", expand=True)
        self.next_button = ttk.Button(navigation, text="Next", command=lambda: self.move_learning(1))
        self.next_button.pack(side="right")

    def show_learning_card(self):
        if not hasattr(self, "learn_text"):
            return
        cards = self.current_set["cards"]
        if not cards:
            self.learn_counter.set("0 cards")
            self.learn_text.set("Add a flashcard to start learning.")
            self.flip_button.configure(state="disabled")
            self.previous_button.configure(state="disabled")
            self.next_button.configure(state="disabled")
            return

        self.learn_index = min(self.learn_index, len(cards) - 1)
        card = cards[self.learn_index]
        side = "front" if self.learn_direction.get() == self.current_set["front_label"] else "back"
        if self.learn_flipped:
            side = "back" if side == "front" else "front"
        self.learn_counter.set(
            f"{self.current_set['name']}  ·  Card {self.learn_index + 1} of {len(cards)}"
        )
        self.learn_text.set(card[side])
        self.flip_button.configure(text="Show front" if self.learn_flipped else "Flip card", state="normal")
        self.previous_button.configure(state="normal" if self.learn_index > 0 else "disabled")
        self.next_button.configure(
            state="normal" if self.learn_index < len(cards) - 1 else "disabled"
        )

    def flip_card(self):
        self.learn_flipped = not self.learn_flipped
        self.show_learning_card()

    def move_learning(self, offset):
        self.learn_index = min(
            max(self.learn_index + offset, 0), max(0, len(self.current_set["cards"]) - 1)
        )
        self.learn_flipped = False
        self.show_learning_card()

    def build_test_tab(self):
        controls = ttk.Frame(self.test_tab)
        controls.pack(fill="x", pady=(0, 18))
        ttk.Label(controls, text="Direction").pack(side="left")
        self.test_direction = tk.StringVar(value="Front to back")
        self.test_direction_picker = ttk.Combobox(
            controls,
            textvariable=self.test_direction,
            values=("Front to back", "Back to front"),
            state="readonly",
            width=18,
        )
        self.test_direction_picker.pack(side="left", padx=8)

        self.test_progress = tk.StringVar(value="Ready")
        ttk.Label(controls, textvariable=self.test_progress).pack(side="right")
        ttk.Label(self.test_tab, text="Sets included in test").pack(anchor="w", pady=(0, 5))
        set_list_frame = ttk.Frame(self.test_tab)
        set_list_frame.pack(fill="x", pady=(0, 14))
        self.test_set_listbox = tk.Listbox(
            set_list_frame,
            height=4,
            selectmode=tk.EXTENDED,
            exportselection=False,
            background="#FFFFFF",
            foreground="#20352E",
            selectbackground="#E6B44A",
            selectforeground="#173F35",
            borderwidth=1,
            relief="solid",
        )
        set_scrollbar = ttk.Scrollbar(
            set_list_frame, orient="vertical", command=self.test_set_listbox.yview
        )
        self.test_set_listbox.configure(yscrollcommand=set_scrollbar.set)
        self.test_set_listbox.pack(side="left", fill="x", expand=True)
        set_scrollbar.pack(side="right", fill="y")

        self.test_question = tk.StringVar(value="Start a test when you're ready.")
        ttk.Label(
            self.test_tab,
            textvariable=self.test_question,
            style="Card.TLabel",
            anchor="center",
            justify="center",
            relief="groove",
        ).pack(fill="both", expand=True, pady=(0, 16))

        answer_area = ttk.Frame(self.test_tab)
        answer_area.pack(fill="x")
        ttk.Label(answer_area, text="Your answer").pack(anchor="w", pady=(0, 5))
        self.answer_var = tk.StringVar()
        self.answer_entry = ttk.Entry(answer_area, textvariable=self.answer_var, state="disabled")
        self.answer_entry.pack(fill="x")
        self.answer_entry.bind("<Return>", self.handle_test_action)
        self.test_feedback = tk.StringVar()
        self.test_feedback_label = ttk.Label(
            self.test_tab, textvariable=self.test_feedback, wraplength=700
        )
        self.test_feedback_label.pack(anchor="w", pady=(12, 4))
        test_buttons = ttk.Frame(self.test_tab)
        test_buttons.pack(fill="x", pady=(8, 0))
        self.end_test_button = ttk.Button(
            test_buttons, text="End test", command=self.end_test, state="disabled"
        )
        self.end_test_button.pack(side="left")
        self.test_action_button = ttk.Button(
            test_buttons, text="Start test", command=self.begin_test
        )
        self.test_action_button.pack(side="right")

    def begin_test(self):
        selected_indices = self.test_set_listbox.curselection()
        if not selected_indices:
            messagebox.showinfo("Choose sets", "Select at least one set for the test.")
            return
        self.test_deck = []
        for set_index in selected_indices:
            card_set = self.sets[set_index]
            for card in card_set["cards"]:
                self.test_deck.append(
                    {
                        **card,
                        "set_name": card_set["name"],
                        "front_label": card_set["front_label"],
                        "back_label": card_set["back_label"],
                    }
                )
        if not self.test_deck:
            messagebox.showinfo("No flashcards", "The selected sets do not contain any cards.")
            return
        random.shuffle(self.test_deck)
        self.test_index = 0
        self.test_score = 0
        self.test_answer_count = 0
        self.test_running = True
        self.test_direction_picker.configure(state="disabled")
        self.test_set_listbox.configure(state=tk.DISABLED)
        self.end_test_button.configure(state="normal")
        self.test_action_button.configure(text="Check answer", command=self.handle_test_action)
        self.answer_entry.configure(state="normal")
        self.show_test_card()

    def show_test_card(self):
        self.test_answered = False
        self.answer_var.set("")
        self.test_feedback.set("")
        self.test_progress.set(f"Card {self.test_index + 1} of {len(self.test_deck)}")
        card = self.test_deck[self.test_index]
        source = "front" if self.test_direction.get() == "Front to back" else "back"
        label = card[f"{source}_label"]
        self.test_question.set(f"{card['set_name']}  ·  {label}\n{card[source]}")
        self.test_action_button.configure(text="Check answer")
        self.answer_entry.configure(state="normal")
        self.answer_entry.focus_set()

    def handle_test_action(self, _event=None):
        if not self.test_running:
            return
        if not self.test_answered:
            card = self.test_deck[self.test_index]
            target = "back" if self.test_direction.get() == "Front to back" else "front"
            expected = card[target]
            self.test_answer_count += 1
            if self.answer_var.get().casefold() == expected.casefold():
                self.test_score += 1
                self.test_feedback.set("Correct.")
                self.test_feedback_label.configure(style="Correct.TLabel")
            else:
                self.test_feedback.set(f"Spelling does not match. Correct answer: {expected}")
                self.test_feedback_label.configure(style="Incorrect.TLabel")
                retry_position = min(self.test_index + 7, len(self.test_deck))
                self.test_deck.insert(retry_position, card.copy())
            self.test_answered = True
            self.answer_entry.configure(state="disabled")
            last_card = self.test_index == len(self.test_deck) - 1
            self.test_action_button.configure(text="Finish test" if last_card else "Next card")
            return

        if self.test_index == len(self.test_deck) - 1:
            self.finish_test()
        else:
            self.test_index += 1
            self.show_test_card()

    def end_test(self):
        if self.test_running:
            self.finish_test(ended=True)

    def finish_test(self, ended=False):
        self.test_running = False
        self.test_direction_picker.configure(state="readonly")
        self.test_set_listbox.configure(state=tk.NORMAL)
        self.end_test_button.configure(state="disabled")
        self.test_question.set("Test ended" if ended else "Test complete")
        self.test_progress.set(f"Score: {self.test_score} / {self.test_answer_count}")
        if ended:
            self.test_feedback.set("Test stopped.")
        else:
            self.test_feedback.set(
                "All answers matched."
                if self.test_score == self.test_answer_count
                else "Review the cards you missed."
            )
        self.test_feedback_label.configure(
            style="Correct.TLabel"
            if self.test_score == self.test_answer_count
            else "Incorrect.TLabel"
        )
        self.answer_var.set("")
        self.answer_entry.configure(state="disabled")
        self.test_action_button.configure(text="Test again", command=self.begin_test)


def main():
    root = tk.Tk()
    FlashcardApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()