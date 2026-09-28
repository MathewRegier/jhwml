"""JHWML - Mod Launcher — desktop installer for friends who do not have Python or Node."""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import threading
import traceback


import tkinter as tk
from tkinter import filedialog, ttk

if getattr(sys, 'frozen', False):
    BUNDLE = pathlib.Path(sys._MEIPASS)
    sys.path.insert(0, str(BUNDLE / 'tools'))
    sys.path.insert(0, str(BUNDLE))
else:
    BUNDLE = pathlib.Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(BUNDLE / 'tools'))

from packager import find_happy_wheels, install, looks_like_game, project_root  # noqa: E402
from launcher_update import apply_and_restart, check_for_update, download_update  # noqa: E402
from launcher_version import NAME, VERSION  # noqa: E402
from mod_store import DEFAULT_CATALOG_URL, sync_mods  # noqa: E402

INK = '#f3ead6'
MUTED = '#b7c0b6'
STEEL = '#121916'
RAIL = '#161e1b'
CARD = '#141c19'
CORAL = '#fd7f7c'
MINT = '#c8e6c0'
LINE = '#3b4a44'
PATH_BG = '#0d1210'
STEPS = ('welcome', 'locate', 'mods', 'install', 'done')
STEP_LABELS = ('Welcome', 'Find the game', 'Choose mods', 'Install', 'Ready')
CREDITS = 'Created by Jimbob · Discord jimbob1111'


def log_path() -> pathlib.Path:
    root = pathlib.Path(os.environ.get('LOCALAPPDATA') or pathlib.Path.home() / 'AppData' / 'Local')
    folder = root / 'HappyWheelsModLauncher'
    folder.mkdir(parents=True, exist_ok=True)
    return folder / 'launcher.log'


def write_log(text: str) -> None:
    try:
        path = log_path()
        existing = path.read_text(encoding='utf-8') if path.exists() else ''
        path.write_text(existing + text + '\n', encoding='utf-8')
    except OSError:
        pass


class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f'{NAME} {VERSION}')
        icon = BUNDLE / 'installer' / 'icon.ico'
        if icon.is_file():
            try:
                self.iconbitmap(default=str(icon))
            except Exception:
                try:
                    self.iconbitmap(str(icon))
                except Exception:
                    pass
        png = BUNDLE / 'installer' / 'icon.png'
        if png.is_file():
            try:
                self._icon_photo = tk.PhotoImage(file=str(png))
                self.iconphoto(True, self._icon_photo)
            except Exception:
                pass
        self.configure(bg=STEEL)
        self.minsize(880, 600)
        self.geometry('980x680')
        self.game_path = tk.StringVar()
        self.game_status = tk.StringVar()
        self.install_status = tk.StringVar(value='Starting…')
        self.store_status = tk.StringVar(value='Checking the online mod library…')
        self.update_status = tk.StringVar(value='Checking for launcher updates…')
        self.done_path = tk.StringVar()
        self.step = 'welcome'
        self.mod_vars: list[tuple[dict, tk.BooleanVar]] = []
        self.catalog_url = DEFAULT_CATALOG_URL
        self.pages: dict[str, tk.Frame] = {}
        self.step_labels: list[tk.Label] = []
        self._update_info: dict | None = None
        self._update_path: pathlib.Path | None = None
        self._build()
        self.after(50, self._detect)
        self.after(80, self._check_launcher_update)

    def _build(self) -> None:
        root = tk.Frame(self, bg=STEEL)
        root.pack(fill='both', expand=True)
        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(0, weight=1)

        rail = tk.Frame(root, bg=RAIL, width=250, padx=22, pady=28)
        rail.grid(row=0, column=0, sticky='nsw')
        rail.grid_propagate(False)

        stamp = tk.Label(
            rail, text=f'VERSION {VERSION}', fg=CORAL, bg=RAIL,
            font=('Georgia', 9, 'bold'), bd=2, relief='solid', highlightthickness=0,
            padx=10, pady=8,
        )
        stamp.configure(highlightbackground=CORAL)
        stamp.pack(anchor='w')

        tk.Label(rail, text='JHWML', fg=INK, bg=RAIL, font=('Georgia', 22, 'bold')).pack(anchor='w', pady=(18, 0))
        tk.Label(rail, text='Mod Launcher', fg=CORAL, bg=RAIL, font=('Georgia', 12)).pack(anchor='w', pady=(2, 6))
        tk.Label(rail, text=f'v{VERSION}', fg=MINT, bg=RAIL, font=('Georgia', 11, 'bold')).pack(anchor='w', pady=(0, 16))

        for index, label in enumerate(STEP_LABELS, start=1):
            row = tk.Label(
                rail, text=f'{index:02}  {label}', fg=MUTED, bg=RAIL,
                font=('Georgia', 11), anchor='w',
            )
            row.pack(fill='x', pady=6)
            self.step_labels.append(row)

        tk.Label(
            rail,
            text=CREDITS,
            fg=MINT, bg=RAIL, font=('Georgia', 9, 'bold'), wraplength=200, justify='left',
        ).pack(side='bottom', anchor='w')
        tk.Label(
            rail,
            text='Keep this launcher. It updates itself and can re-patch the game after a Steam update.',
            fg='#8b968e', bg=RAIL, font=('Georgia', 9), wraplength=200, justify='left',
        ).pack(side='bottom', anchor='w', pady=(0, 10))

        stage = tk.Frame(root, bg=STEEL, padx=42, pady=34)
        stage.grid(row=0, column=1, sticky='nsew')
        stage.grid_rowconfigure(0, weight=1)
        stage.grid_columnconfigure(0, weight=1)

        self.pages['update'] = self._page_update(stage)
        self.pages['welcome'] = self._page_welcome(stage)
        self.pages['locate'] = self._page_locate(stage)
        self.pages['mods'] = self._page_mods(stage)
        self.pages['install'] = self._page_install(stage)
        self.pages['done'] = self._page_done(stage)
        self.show('welcome')

    def _heading(self, parent: tk.Widget, title: str, lede: str) -> None:
        tk.Label(parent, text=title, fg=INK, bg=STEEL, font=('Georgia', 28, 'bold'), justify='left', wraplength=620).pack(anchor='w')
        tk.Label(parent, text=lede, fg=MUTED, bg=STEEL, font=('Georgia', 12), justify='left', wraplength=620).pack(anchor='w', pady=(8, 22))

    def _card(self, parent: tk.Widget) -> tk.Frame:
        card = tk.Frame(parent, bg=CARD, highlightbackground=LINE, highlightthickness=1, padx=16, pady=16)
        card.pack(fill='x')
        return card

    def _actions(self, parent: tk.Widget) -> tk.Frame:
        bar = tk.Frame(parent, bg=STEEL)
        bar.pack(side='bottom', fill='x', pady=(22, 0))
        return bar

    def _button(self, parent: tk.Widget, text: str, command, primary: bool = False) -> tk.Button:
        if primary:
            button = tk.Button(
                parent, text=text, command=command, bg=CORAL, fg='#2a1210',
                activebackground='#ff9b97', activeforeground='#2a1210',
                font=('Georgia', 12, 'bold'), relief='flat', padx=16, pady=10, cursor='hand2',
            )
        else:
            button = tk.Button(
                parent, text=text, command=command, bg=STEEL, fg='#d7eee6',
                activebackground='#24312c', activeforeground=INK,
                font=('Georgia', 12, 'bold'), relief='solid', bd=1, padx=16, pady=10, cursor='hand2',
            )
        button.pack(side='left', padx=(0, 10))
        return button

    def _page_welcome(self, parent: tk.Widget) -> tk.Frame:
        page = tk.Frame(parent, bg=STEEL)
        self._heading(
            page,
            'Install mods\ninto Happy Wheels.',
            'Close Happy Wheels first, then continue.',
        )
        note = self._card(page)
        tk.Label(
            note,
            text='Built for Happy Wheels 1.99.2 by Jimbob.\n\nKeep this launcher and open it for future mod or launcher updates.\n\nIf the game ever updates, open this launcher again. It will update itself, then you can press Install to re-patch Happy Wheels.',
            fg='#9aa79e', bg=CARD, font=('Georgia', 11), justify='left', wraplength=600,
        ).pack(anchor='w')
        self._button(self._actions(page), 'Continue', lambda: self.show('locate'), primary=True)
        return page

    def _page_locate(self, parent: tk.Widget) -> tk.Frame:
        page = tk.Frame(parent, bg=STEEL)
        self._heading(
            page,
            'Where is Happy Wheels?',
            'We look in the usual Steam folders first. If your library is on another drive, point us to the folder that contains Happy Wheels.exe.',
        )
        card = self._card(page)
        tk.Label(card, text='GAME FOLDER', fg=MINT, bg=CARD, font=('Georgia', 9, 'bold')).pack(anchor='w')
        row = tk.Frame(card, bg=CARD)
        row.pack(fill='x', pady=(8, 0))
        tk.Entry(
            row, textvariable=self.game_path, state='readonly', readonlybackground=PATH_BG,
            fg=INK, font=('Consolas', 11), relief='flat',
        ).pack(side='left', fill='x', expand=True, ipady=8, padx=(0, 10))
        tk.Button(
            row, text='Browse', command=self.browse_game, bg=CARD, fg='#d7eee6',
            font=('Georgia', 11, 'bold'), relief='solid', bd=1, padx=12, pady=6, cursor='hand2',
        ).pack(side='left')
        tk.Label(card, textvariable=self.game_status, fg=MINT, bg=CARD, font=('Georgia', 11), wraplength=560, justify='left').pack(anchor='w', pady=(10, 0))
        actions = self._actions(page)
        self._button(actions, 'Back', lambda: self.show('welcome'))
        self._button(actions, 'Continue', self.go_mods, primary=True)
        return page

    def _page_mods(self, parent: tk.Widget) -> tk.Frame:
        page = tk.Frame(parent, bg=STEEL)
        self._heading(page, 'Install a mod?', 'Choose what to install. Open this launcher again later for new or updated mods.')
        tk.Label(page, textvariable=self.store_status, fg=MINT, bg=STEEL, font=('Georgia', 11), wraplength=620, justify='left').pack(anchor='w', pady=(0, 12))
        self.mod_list = tk.Frame(page, bg=STEEL)
        self.mod_list.pack(fill='both', expand=True)
        actions = self._actions(page)
        self._button(actions, 'Back', lambda: self.show('locate'))
        self._button(actions, 'Check again', self.refresh_library)
        self._button(actions, 'Install', self.start_install, primary=True)
        return page

    def _page_install(self, parent: tk.Widget) -> tk.Frame:
        page = tk.Frame(parent, bg=STEEL)
        self._heading(page, 'Installing', 'This takes a minute. Do not close the window or open the modded game yet.')
        card = self._card(page)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Mod.Horizontal.TProgressbar', troughcolor=PATH_BG, background=CORAL, bordercolor=LINE, lightcolor=CORAL, darkcolor=CORAL)
        self.bar = ttk.Progressbar(card, style='Mod.Horizontal.TProgressbar', maximum=100, mode='determinate')
        self.bar.pack(fill='x')
        tk.Label(card, textvariable=self.install_status, fg=MINT, bg=CARD, font=('Georgia', 11), wraplength=560, justify='left').pack(anchor='w', pady=(10, 0))
        return page

    def _page_update(self, parent: tk.Widget) -> tk.Frame:
        page = tk.Frame(parent, bg=STEEL)
        self._heading(
            page,
            'Update available.',
            'A newer launcher is ready. Install it now? The download stays in this window.',
        )
        card = self._card(page)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Mod.Horizontal.TProgressbar', troughcolor=PATH_BG, background=CORAL, bordercolor=LINE, lightcolor=CORAL, darkcolor=CORAL)
        self.update_bar = ttk.Progressbar(card, style='Mod.Horizontal.TProgressbar', maximum=100, mode='determinate')
        self.update_bar.pack(fill='x')
        tk.Label(card, textvariable=self.update_status, fg=MINT, bg=CARD, font=('Georgia', 11), wraplength=560, justify='left').pack(anchor='w', pady=(10, 0))
        actions = self._actions(page)
        self._update_yes = self._button(actions, 'Yes, install update', self._accept_self_update, primary=True)
        self._update_no = self._button(actions, 'No, not now', self._decline_self_update)
        return page

    def _page_done(self, parent: tk.Widget) -> tk.Frame:
        page = tk.Frame(parent, bg=STEEL)
        tk.Label(page, text='OK', fg=CORAL, bg=STEEL, font=('Georgia', 42, 'bold')).pack(anchor='w')
        self._heading(
            page,
            'Ready to play.',
            'Keep this launcher and open it for future mod or launcher updates. If Happy Wheels updates, open the launcher again so it can update itself and re-patch the game.\n\nCreated by Jimbob · Discord jimbob1111',
        )
        tk.Label(page, textvariable=self.done_path, fg='#9aa79e', bg=STEEL, font=('Consolas', 10), wraplength=620, justify='left').pack(anchor='w')
        actions = self._actions(page)
        self._button(actions, 'Play', self.play, primary=True)
        self._button(actions, 'Open folder', self.open_folder)
        return page

    def show(self, name: str) -> None:
        self.step = name
        for page in self.pages.values():
            page.grid_forget()
        self.pages[name].grid(row=0, column=0, sticky='nsew')
        index = STEPS.index(name) if name in STEPS else 0
        for i, label in enumerate(self.step_labels):
            label.configure(fg=INK if i <= index else MUTED)

    def _check_launcher_update(self) -> None:
        def run():
            try:
                info = check_for_update(VERSION)
                if info:
                    self.after(0, lambda: self._offer_self_update(info))
            except Exception:
                write_log(traceback.format_exc())

        threading.Thread(target=run, daemon=True).start()

    def _offer_self_update(self, info: dict) -> None:
        if self.step in ('install', 'done'):
            return
        self._update_info = info
        notes = info.get('notes') or ''
        extra = (' ' + notes) if notes else ''
        self.update_status.set(f'{NAME} v{info["version"]} is available.{extra}\nInstall this update now?')
        self.update_bar['value'] = 0
        self._update_yes.configure(state='normal')
        self._update_no.configure(state='normal')
        self.show('update')
        threading.Thread(target=self._prefetch_update, args=(info,), daemon=True).start()

    def _prefetch_update(self, info: dict) -> None:
        try:
            path = download_update(info)
            self._update_path = path
            self.after(0, lambda: self.update_bar.configure(value=40) if self.step == 'update' else None)
        except Exception:
            write_log(traceback.format_exc())

    def _decline_self_update(self) -> None:
        self.show('welcome')

    def _accept_self_update(self) -> None:
        info = self._update_info
        if not info:
            self.show('welcome')
            return
        self._update_yes.configure(state='disabled')
        self._update_no.configure(state='disabled')
        self.update_bar['value'] = 20
        self.update_status.set(f'Downloading v{info["version"]}…')

        def run():
            try:
                if not getattr(sys, 'frozen', False):
                    raise RuntimeError('This is a source build, so it cannot replace an EXE.')
                path = self._update_path or download_update(info)
                self.after(0, lambda: self._apply_self_update(path, info))
            except Exception as error:
                write_log(traceback.format_exc())
                self.after(0, lambda: self._self_update_failed(str(error)))

        threading.Thread(target=run, daemon=True).start()

    def _apply_self_update(self, path: pathlib.Path, info: dict) -> None:
        self.update_bar['value'] = 90
        self.update_status.set(f'Installing v{info["version"]} and restarting…')
        try:
            self.withdraw()
            apply_and_restart(path)
        except Exception as error:
            write_log(traceback.format_exc())
            self.deiconify()
            self._self_update_failed(str(error))

    def _self_update_failed(self, error: str) -> None:
        self.update_bar['value'] = 0
        self.update_status.set('Could not install the update: ' + error + '\nYou can keep using this launcher.')
        self._update_yes.configure(state='normal')
        self._update_no.configure(state='normal')

    def _detect(self) -> None:
        try:
            found = find_happy_wheels()
            self.game_path.set(str(found) if found else '')
            self.game_status.set('Found your Steam Happy Wheels folder.' if found else 'We could not find it automatically.')
            self.refresh_library()
        except Exception as error:
            write_log(traceback.format_exc())
            self.game_status.set('Could not scan for Happy Wheels: ' + str(error))

    def _installed_mods_dir(self) -> pathlib.Path | None:
        path = self.game_path.get()
        if not path:
            return None
        return pathlib.Path(path) / 'mods'

    def refresh_library(self) -> None:
        self.store_status.set('Checking the online mod library…')
        installed = self._installed_mods_dir()

        def run():
            try:
                catalog = sync_mods(
                    self.catalog_url,
                    bundled=project_root() / 'mods',
                    installed=installed,
                    progress=lambda message: self.after(0, lambda m=message: self.store_status.set(m)),
                )
                self.after(0, lambda: self._library_ready(catalog))
            except Exception as error:
                write_log(traceback.format_exc())
                self.after(0, lambda: self._library_ready([], str(error)))

        threading.Thread(target=run, daemon=True).start()

    def _library_ready(self, catalog: list[dict], error: str = '') -> None:
        if error:
            self.store_status.set('Could not check the online library: ' + error)
        elif any(mod.get('status') in ('new', 'update') for mod in catalog):
            self.store_status.set('Found new or updated mods. They will be copied when you press Install.')
        elif catalog:
            self.store_status.set('Mod library is up to date.')
        else:
            self.store_status.set('No mods were found online or in this launcher.')
        self._render_mods(catalog)

    def _render_mods(self, catalog: list[dict]) -> None:
        for child in self.mod_list.winfo_children():
            child.destroy()
        self.mod_vars = []
        if not catalog:
            tk.Label(self.mod_list, text='No mods were found.', fg='#9aa79e', bg=STEEL, font=('Georgia', 11)).pack(anchor='w')
            return
        for mod in catalog:
            chosen = tk.BooleanVar(value=True)
            self.mod_vars.append((mod, chosen))
            card = tk.Frame(self.mod_list, bg=CARD, highlightbackground=LINE, highlightthickness=1, padx=14, pady=12)
            card.pack(fill='x', pady=(0, 10))
            tk.Checkbutton(
                card, variable=chosen, bg=CARD, activebackground=CARD, selectcolor=PATH_BG,
                fg=CORAL, activeforeground=CORAL, highlightthickness=0,
            ).pack(side='left', padx=(0, 12))
            body = tk.Frame(card, bg=CARD)
            body.pack(side='left', fill='x', expand=True)
            title = mod['name'] + (f'  ·  v{mod["version"]}' if mod.get('version') else '')
            tk.Label(body, text=title, fg=INK, bg=CARD, font=('Georgia', 16, 'bold')).pack(anchor='w')
            if mod.get('badge'):
                tk.Label(body, text=mod['badge'], fg=CORAL if mod.get('status') in ('new', 'update') else MINT, bg=CARD, font=('Georgia', 10, 'bold')).pack(anchor='w')
            extra = (mod.get('description') or '') + (('  ·  ' + mod['author']) if mod.get('author') else '')
            if extra.strip():
                tk.Label(body, text=extra, fg=MUTED, bg=CARD, font=('Georgia', 11), wraplength=520, justify='left').pack(anchor='w')

    def browse_game(self) -> None:
        initial = self.game_path.get() or str(pathlib.Path.home())
        path = filedialog.askdirectory(parent=self, title='Select the Happy Wheels folder', initialdir=initial)
        if not path:
            return
        self.game_path.set(path)
        if looks_like_game(pathlib.Path(path)):
            self.game_status.set('Using the folder you chose.')
            self.refresh_library()
        else:
            self.game_status.set('That folder does not look like Happy Wheels. Choose the one with Happy Wheels.exe.')

    def go_mods(self) -> None:
        path = self.game_path.get()
        if not path or not looks_like_game(pathlib.Path(path)):
            self.game_status.set('Choose the folder that contains Happy Wheels.exe.')
            return
        self.refresh_library()
        self.show('mods')

    def start_install(self) -> None:
        source = self.game_path.get()
        mods = [mod['id'] for mod, chosen in self.mod_vars if chosen.get()]
        self.install_status.set('Starting…')
        self.bar['value'] = 4
        self.show('install')

        def run():
            try:
                game = install(
                    pathlib.Path(source),
                    enabled_ids=mods,
                    progress=lambda percent, message: self.after(0, lambda p=percent, m=message: self._progress(p, m)),
                )
                self.after(0, lambda: self._install_done(True, '', str(game)))
            except Exception as error:
                write_log(traceback.format_exc())
                self.after(0, lambda: self._install_done(False, str(error), source))

        threading.Thread(target=run, daemon=True).start()

    def _progress(self, percent: int, message: str) -> None:
        self.bar['value'] = percent
        self.install_status.set(message)

    def _install_done(self, ok: bool, error: str, dest: str) -> None:
        if not ok:
            self.install_status.set(error or 'Install failed.')
            return
        self.done_path.set(dest)
        self.show('done')

    def play(self) -> None:
        exe = pathlib.Path(self.game_path.get()) / 'Happy Wheels.exe'
        if exe.exists():
            subprocess.Popen([str(exe)], cwd=str(exe.parent))

    def open_folder(self) -> None:
        folder = pathlib.Path(self.game_path.get())
        if folder.exists():
            os.startfile(folder)  # type: ignore[attr-defined]


def main() -> None:
    try:
        if sys.platform == 'win32':
            try:
                from ctypes import windll
                windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                pass
        app = Launcher()
        app.mainloop()
    except Exception:
        write_log(traceback.format_exc())
        raise


if __name__ == '__main__':
    sys.excepthook = lambda *_args: write_log(traceback.format_exc())
    main()
