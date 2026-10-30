"""Desktop widget window: weather, a pomodoro timer and a Hacker News ticker on a per-pixel transparent window.

Tk provides the window, the event loop and the menu; ui.scene draws everything; ui.layered puts the
result on screen. Left drag moves the window, right click opens the menu, the hover-only × closes it.
"""
import logging
import queue
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from typing import Any, Callable

from focus.pomodoro import Phase, Pomodoro
from news.hackernews import Story, safe_url
from ui import scene as look
from ui import state
from ui.city_dialog import CityDialog, SearchCallback
from ui.formatting import format_temperature, format_wind
from ui.layered import LayeredWindow, virtual_screen
from ui.scene import Scene
from weather import meteocons
from weather.model import Place, Weather

FRAME_MS = 33  # ~30 fps
CLICK_TOLERANCE_PX = 4  # a press that moved further than this is a drag, not a click
log = logging.getLogger(__name__)
PHASE_LABELS = {Phase.FOCUS: "focus", Phase.SHORT_BREAK: "break", Phase.LONG_BREAK: "long break"}


class DeskWidget(tk.Tk):
    def __init__(
        self,
        scale: float,
        place: Place,
        ask_for_place: bool,
        load_weather: Callable[[Place], Weather],
        search_places: Callable[[str], list[Place]],
        load_news: Callable[[], list[Story]],
        pomodoro: Pomodoro,
        weather_refresh_s: int,
        news_refresh_s: int,
        retry_s: int,
        state_file: Path,
    ) -> None:
        super().__init__()
        self._place = place
        self._load_weather = load_weather
        self._search_places = search_places
        self._city_dialog: CityDialog | None = None
        self._load_news = load_news
        self._pomodoro = pomodoro
        self._weather_refresh_ms = weather_refresh_s * 1000
        self._news_refresh_ms = news_refresh_s * 1000
        self._retry_ms = retry_s * 1000
        self._state_file = state_file
        self._scene = Scene(scale, place.name)
        # Results of background work, applied on the UI thread: (callback, value).
        self._ui_queue: queue.Queue[tuple[Callable[[Any], None], Any]] = queue.Queue()
        self._jobs: dict[str, str] = {}
        self._in_flight: set[str] = set()
        self._press_root = (0, 0)
        self._drag_offset = (0, 0)
        self._dragged = False
        self._ignore_next_release = False

        width, height = self._scene.size
        saved = state.load_position(state_file) or (self.winfo_screenwidth() - width - 40, 40)
        x, y = state.visible_position(saved, (width, height), virtual_screen())
        self.overrideredirect(True)  # no title bar and no border
        self.geometry(f"{width}x{height}+{x}+{y}")
        self._window = LayeredWindow(self)
        # Lives on the desktop under open windows; "Always on top" in the menu switches that.
        self._always_on_top = tk.BooleanVar(self, value=False)
        self._window.send_to_bottom()
        self._window.show(self._scene.compose(time.monotonic()))

        self._menu = tk.Menu(self, tearoff=False)
        self._menu.add_command(label="Change city…", command=self._open_city_dialog)
        self._menu.add_command(label="Refresh weather and news", command=self._refresh_all)
        self._menu.add_command(label="Reset pomodoro", command=self._reset_pomodoro)
        self._menu.add_checkbutton(label="Always on top", variable=self._always_on_top,
                                   command=self._apply_stacking)
        self._menu.add_separator()
        self._menu.add_command(label="Close", command=self.destroy)

        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Double-Button-1>", self._on_double_click)
        self.bind("<Button-3>", lambda e: self._menu.tk_popup(e.x_root, e.y_root))
        self.bind("<Motion>", self._on_motion)
        self.bind("<Enter>", self._on_motion)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Escape>", lambda _e: self.destroy())

        self.refresh_weather()
        self.refresh_news()
        self.after(200, self._drain_ui_queue)
        self._frame()
        if ask_for_place:
            self.after(600, self._open_city_dialog)

    # --- frame loop -----------------------------------------------------------------------------

    def _frame(self) -> None:
        # Reschedule first: if anything below raises, the loop must keep running, otherwise
        # the widget silently freezes on its last frame.
        self.after(FRAME_MS, self._frame)
        if self._pomodoro.update():
            self._notify_phase_end()
        self._render_pomodoro()
        self._window.show(self._scene.compose(time.monotonic()))

    def report_callback_exception(self, exc: type, value: BaseException, tb: Any) -> None:
        # Tk's default handler prints to stderr, which does not exist under pythonw.
        log.error("unhandled error in a Tk callback", exc_info=(exc, value, tb))

    # --- background work ------------------------------------------------------------------------

    def refresh_weather(self) -> None:
        place = self._place  # captured now: the result must be matched to the city it was loaded for
        self._run_in_background("weather", lambda: (place, self._load_weather(place)),
                                self._show_weather, self._weather_failed)

    def refresh_news(self) -> None:
        self._run_in_background("news", self._load_news, self._show_news, self._news_failed)

    def _refresh_all(self) -> None:
        self.refresh_weather()
        self.refresh_news()

    def _run_in_background(self, name: str, load: Callable[[], Any], on_success: Callable[[Any], None],
                           on_error: Callable[[Any], None]) -> None:
        self._cancel(name)
        if name in self._in_flight:  # e.g. "Refresh" clicked while a load is still running
            return
        self._in_flight.add(name)

        def finish(callback: Callable[[Any], None]) -> Callable[[Any], None]:
            def apply(value: Any) -> None:
                self._in_flight.discard(name)
                callback(value)
            return apply

        # Network I/O runs in a background thread so the window never freezes. Tkinter is not
        # thread-safe, so the thread only puts the result into a queue; the UI thread applies it.
        def work() -> None:
            try:
                self._ui_queue.put((finish(on_success), load()))
            except Exception as e:  # network or format error: show a status and retry later
                self._ui_queue.put((finish(on_error), e))

        threading.Thread(target=work, daemon=True).start()

    def _drain_ui_queue(self) -> None:
        self.after(200, self._drain_ui_queue)
        while True:
            try:
                callback, value = self._ui_queue.get_nowait()
            except queue.Empty:
                return
            try:
                callback(value)
            except Exception:  # one bad result must not block every later one
                log.exception("failed to apply a background result")

    def _schedule(self, name: str, delay_ms: int, callback: Callable[[], None]) -> None:
        self._cancel(name)
        self._jobs[name] = self.after(delay_ms, callback)

    def _cancel(self, name: str) -> None:
        job = self._jobs.pop(name, None)
        if job:
            self.after_cancel(job)

    # --- weather and news -----------------------------------------------------------------------

    def _show_weather(self, result: tuple[Place, Weather]) -> None:
        place, weather = result
        if place != self._place:  # the city changed while this load was running: drop stale data
            return
        self._scene.set_weather_icons(meteocons.icon_path(meteocons.weather_icon(weather.symbol_code)),
                                      meteocons.icon_path(meteocons.wind_icon(weather.wind_speed_ms)))
        self._scene.temperature = format_temperature(weather.temperature_c)
        self._scene.wind = format_wind(weather.wind_speed_ms)
        self._scene.status, self._scene.status_color = place.name, look.MUTED
        self._schedule("weather", self._weather_refresh_ms, self.refresh_weather)

    def _weather_failed(self, error: Exception) -> None:
        self._scene.status, self._scene.status_color = "offline, retrying…", look.ERROR
        log.warning("weather update failed: %r", error)
        self._schedule("weather", self._retry_ms, self.refresh_weather)

    def _show_news(self, stories: list[Story]) -> None:
        if not stories:  # every item request failed: keep the old headlines and retry soon
            self._news_failed(ValueError("no stories received"))
            return
        self._scene.set_stories([s.title for s in stories], [s.url for s in stories])
        self._schedule("news", self._news_refresh_ms, self.refresh_news)

    def _news_failed(self, error: Exception) -> None:
        log.warning("news update failed: %r", error)  # keep showing the previous headlines
        self._schedule("news", self._retry_ms, self.refresh_news)

    # --- city -----------------------------------------------------------------------------------

    def _open_city_dialog(self) -> None:
        if self._city_dialog is not None and self._city_dialog.winfo_exists():
            self._city_dialog.lift()
            return
        self._city_dialog = CityDialog(self, self._place, self._search_async, self._change_place)

    def _search_async(self, query: str, callback: SearchCallback) -> None:
        self._run_in_background("geocode", lambda: self._search_places(query), callback, callback)

    def _change_place(self, place: Place) -> None:
        self._place = place
        state.save_place(self._state_file, place)
        self._scene.status, self._scene.status_color = place.name, look.MUTED
        self._scene.temperature, self._scene.wind = "…", ""
        self._in_flight.discard("weather")  # a load for the old city may still run; its result is dropped
        self.refresh_weather()

    # --- pomodoro -------------------------------------------------------------------------------

    def _render_pomodoro(self) -> None:
        minutes, seconds = divmod(int(round(self._pomodoro.remaining_s())), 60)
        phase, running = self._pomodoro.phase, self._pomodoro.running
        label = PHASE_LABELS[phase] + ("" if running else " · paused")
        self._scene.timer = f"●  {minutes:02d}:{seconds:02d}   {label}"
        phase_color = look.FOCUS if phase is Phase.FOCUS else look.BREAK
        self._scene.timer_color = phase_color if running else look.MUTED

    def _notify_phase_end(self) -> None:
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except (ImportError, RuntimeError):
            self.bell()

    def _reset_pomodoro(self) -> None:
        self._pomodoro.reset()

    # --- mouse ----------------------------------------------------------------------------------

    def _on_press(self, event: tk.Event) -> None:
        self._press_root = (event.x_root, event.y_root)
        self._drag_offset = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())
        self._dragged = False

    def _on_drag(self, event: tk.Event) -> None:
        px, py = self._press_root
        if abs(event.x_root - px) + abs(event.y_root - py) > CLICK_TOLERANCE_PX:
            self._dragged = True
        if self._dragged:
            dx, dy = self._drag_offset
            self.geometry(f"+{event.x_root - dx}+{event.y_root - dy}")

    def _on_release(self, event: tk.Event) -> None:
        if self._dragged:
            state.save_position(self._state_file, self.winfo_x(), self.winfo_y())
            self._apply_stacking()
            return
        # A double click is press, release, press(double), release: the last release must not act again.
        if self._ignore_next_release:
            self._ignore_next_release = False
            return
        region = self._scene.region_at(event.x, event.y)
        if region == "close":
            self.destroy()
        elif region == "settings":
            x0, _, _, y1 = self._scene.settings_box  # open the menu right under the gear
            self._menu.tk_popup(self.winfo_rootx() + x0, self.winfo_rooty() + y1)
        elif region == "reset":
            self._pomodoro.reset()
        elif region == "timer":
            self._pomodoro.toggle()
        elif region == "ticker":
            url = safe_url(self._scene.url_at(event.x))  # defence in depth: validated again right before use
            if url:
                webbrowser.open(url)

    def _on_double_click(self, event: tk.Event) -> None:
        # The first click already acted (e.g. opened a headline); the second release must not repeat it.
        self._ignore_next_release = True
        if self._scene.region_at(event.x, event.y) == "timer":
            self._pomodoro.reset()

    def _on_motion(self, event: tk.Event) -> None:
        self._scene.hovered = True
        region = self._scene.region_at(event.x, event.y)
        self._scene.hover_region = region
        self._scene.hover_x = event.x if region == "ticker" else None
        self.configure(cursor="hand2" if region else "")

    def _on_leave(self, _event: tk.Event) -> None:
        self._scene.hovered = False
        self._scene.hover_region = None
        self._scene.hover_x = None

    def _apply_stacking(self) -> None:
        on_top = self._always_on_top.get()
        self.attributes("-topmost", on_top)
        if not on_top:
            self._window.send_to_bottom()
