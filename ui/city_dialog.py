"""'Choose your city' dialog: type a name, search, pick one of the matches."""
import tkinter as tk
from tkinter import ttk
from typing import Callable

from weather.model import Place

SearchCallback = Callable[[list[Place] | Exception], None]


class CityDialog(tk.Toplevel):
    def __init__(
        self,
        master: tk.Misc,
        current: Place,
        search_async: Callable[[str, SearchCallback], None],
        on_choose: Callable[[Place], None],
    ) -> None:
        super().__init__(master)
        self._search_async = search_async
        self._on_choose = on_choose
        self._results: list[Place] = []
        self._searching = False

        self.title("Choose your city")
        self.resizable(False, False)
        self.attributes("-topmost", True)  # the widget lives under other windows; its dialog must not

        frame = ttk.Frame(self, padding=14)
        frame.grid(sticky="nsew")
        ttk.Label(frame, text=f"Current: {current.label}").grid(row=0, column=0, columnspan=2, sticky="w")
        self._query = tk.StringVar(self)
        self._entry = ttk.Entry(frame, textvariable=self._query, width=36)
        self._entry.grid(row=1, column=0, sticky="ew", pady=(10, 6))
        self._search_button = ttk.Button(frame, text="Search", command=self._search)
        self._search_button.grid(row=1, column=1, padx=(6, 0), pady=(10, 6))
        self._list = tk.Listbox(frame, height=7, activestyle="dotbox", exportselection=False)
        self._list.grid(row=2, column=0, columnspan=2, sticky="nsew")
        self._status = ttk.Label(frame, text="Type a city name and press Enter.", foreground="#666")
        self._status.grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 10))
        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, columnspan=2, sticky="e")
        self._ok = ttk.Button(buttons, text="OK", command=self._choose, state="disabled")
        self._ok.grid(row=0, column=0, padx=(0, 6))
        ttk.Button(buttons, text="Cancel", command=self.destroy).grid(row=0, column=1)

        self._entry.bind("<Return>", lambda _e: self._search())
        self._list.bind("<<ListboxSelect>>", lambda _e: self._ok.configure(state="normal"))
        self._list.bind("<Double-Button-1>", lambda _e: self._choose())
        self._list.bind("<Return>", lambda _e: self._choose())
        self.bind("<Escape>", lambda _e: self.destroy())

        self._center()
        self.after(50, self._entry.focus_force)

    def _search(self) -> None:
        query = self._query.get().strip()
        if len(query) < 2 or self._searching:
            return
        self._searching = True
        self._search_button.configure(state="disabled")
        self._status.configure(text="Searching…")
        self._search_async(query, self._show_results)

    def _show_results(self, result: list[Place] | Exception) -> None:
        if not self.winfo_exists():  # the dialog was closed while the search was running
            return
        self._searching = False
        self._search_button.configure(state="normal")
        self._list.delete(0, "end")
        self._ok.configure(state="disabled")
        if isinstance(result, Exception):
            self._results = []
            self._status.configure(text="Search failed. Check the internet connection and try again.")
            return
        self._results = result
        for place in result:
            self._list.insert("end", place.label)
        if result:
            self._list.selection_set(0)
            self._list.focus_set()
            self._ok.configure(state="normal")
            self._status.configure(text="Pick your city and press OK.")
        else:
            self._status.configure(text="Nothing found. Try the name in English, e.g. 'Kyiv'.")

    def _choose(self) -> None:
        selection = self._list.curselection()
        if selection:
            self._on_choose(self._results[selection[0]])
            self.destroy()

    def _center(self) -> None:
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_reqwidth()) // 2
        y = (self.winfo_screenheight() - self.winfo_reqheight()) // 3
        self.geometry(f"+{x}+{y}")
