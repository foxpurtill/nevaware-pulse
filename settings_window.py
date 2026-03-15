"""settings_window.py — Standalone settings window for NeveWare-Pulse."""
import json, sys, tkinter as tk
from tkinter import filedialog
from pathlib import Path

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"

with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    config = json.load(f)

bg = '#1a1a2e'; fg = '#e0e0e0'; entry_bg = '#16213e'; hint_fg = '#555577'
win = tk.Tk()
win.title('NeveWare-Pulse \u2014 Settings')
win.configure(bg=bg)
win.resizable(False, False)
win.attributes('-topmost', True)

# ── Tooltip helper ──────────────────────────────────────────────────────────
class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind('<Enter>', self.show)
        widget.bind('<Leave>', self.hide)
    def show(self, _=None):
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 20
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f'+{x}+{y}')
        tk.Label(self.tip, text=self.text, bg='#2a2a4a', fg='#ccccee',
                 font=('Segoe UI', 8), relief='flat', padx=8, pady=4,
                 wraplength=300, justify='left').pack()
    def hide(self, _=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None

tk.Label(win, text='NeveWare-Pulse Settings', bg=bg, fg='#aaaaff',
         font=('Segoe UI', 12, 'bold')).grid(row=0, column=0, columnspan=3, pady=(10,4))

# field, tooltip text
fields = [
    ('Icon Letter',            'icon_letter',              'Single letter shown on the tray icon. Change this to your DI\'s initial.'),
    ('Active Colour (hex)',    'active_color',             'Tray icon colour when heartbeat is running. Default #FF4444 (red).'),
    ('Inactive Colour (hex)',  'inactive_color',           'Tray icon colour when paused / Fox present. Default #44BB44 (green).'),
    ('Heartbeat Character',    'heartbeat_character',      'The signal character sent at each beat. Default: § (section sign).'),
    ('Default Interval (min)', 'default_interval_minutes', 'Fallback interval if the DI doesn\'t write next:N in their response.'),
    ('Emoji Hotkey',           'emoji_hotkey',             'System-wide hotkey to open the emoji picker. Default: Ctrl+Alt+E.'),
    ('AI Name',                'ai_name',                  'Your DI\'s name — shown in the tray menu header and heartbeat prompts.'),
    ('Email Address',          'email_address',            'The DI\'s email address. Used by the email_watcher module to check inbox.'),
    ('ElevenLabs Voice ID',    'elevenlabs_voice_id',      'Voice ID from ElevenLabs. Find yours at elevenlabs.io/voice-library\nExample: 21m00Tcm4TlvDq8ikWAM (Rachel)'),
]

entries = {}
pad = {'padx': 8, 'pady': 4}
for i, (label, key, tip) in enumerate(fields, start=1):
    tk.Label(win, text=label, bg=bg, fg=fg, font=('Segoe UI', 9),
             anchor='e').grid(row=i, column=0, sticky='e', **pad)
    var = tk.StringVar(value=str(config.get(key, '')))
    entry = tk.Entry(win, textvariable=var, bg=entry_bg, fg=fg, insertbackground=fg,
                     width=26, font=('Segoe UI', 9))
    entry.grid(row=i, column=1, sticky='w', **pad)
    info = tk.Label(win, text='\u24d8', bg=bg, fg='#555588',
                    font=('Segoe UI', 10), cursor='question_arrow')
    info.grid(row=i, column=2, padx=(0, 8))
    Tooltip(info, tip)
    entries[key] = var

r = len(fields) + 1
dv = tk.BooleanVar(value=config.get('defib_restore_last_state', True))
tk.Checkbutton(win, text='Restore last state after Defibrillator recovery',
               variable=dv, bg=bg, fg=fg, selectcolor=entry_bg,
               activebackground=bg, activeforeground=fg,
               font=('Segoe UI', 9)).grid(row=r, column=0, columnspan=3,
               sticky='w', padx=8, pady=(8, 2))
r += 1

DEFAULTS = {
    'icon_letter': 'N', 'active_color': '#FF4444', 'inactive_color': '#44BB44',
    'heartbeat_character': '\u00a7', 'default_interval_minutes': '30',
    'emoji_hotkey': 'ctrl+alt+e', 'ai_name': 'Neve',
    'email_address': '', 'elevenlabs_voice_id': '',
}

def reset_defaults():
    for key, val in DEFAULTS.items():
        if key in entries:
            entries[key].set(val)
    dv.set(True)

def save():
    for key, var in entries.items():
        val = var.get()
        if key == 'default_interval_minutes':
            try: config[key] = int(val)
            except: pass
        else:
            config[key] = val
    config['defib_restore_last_state'] = dv.get()
    if config.get('elevenlabs_voice_id'):
        config.setdefault('modules', {}).setdefault('voice_output', {})['voice_id'] = config['elevenlabs_voice_id']
    if config.get('elevenlabs_api_key'):
        config.setdefault('modules', {}).setdefault('voice_output', {})['api_key'] = config['elevenlabs_api_key']
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    win.destroy()

bf = tk.Frame(win, bg=bg)
bf.grid(row=r, column=0, columnspan=3, pady=10)
tk.Button(bf, text='Save', command=save, bg='#533483', fg='white',
          font=('Segoe UI', 9, 'bold'), padx=16, pady=4, bd=0,
          cursor='hand2').pack(side='left', padx=6)
tk.Button(bf, text='Reset to Defaults', command=reset_defaults,
          bg='#2a2a4a', fg='#aaaacc', font=('Segoe UI', 9),
          padx=12, pady=4, bd=0, cursor='hand2').pack(side='left', padx=6)
tk.Button(bf, text='Cancel', command=win.destroy, bg='#333355', fg=fg,
          font=('Segoe UI', 9), padx=16, pady=4, bd=0,
          cursor='hand2').pack(side='left', padx=6)

win.mainloop()
