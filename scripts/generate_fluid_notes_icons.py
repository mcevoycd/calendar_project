from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / 'dashboard' / 'static' / 'dashboard' / 'icons'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ICONS = {
    'save': '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline>',
    'delete': '<polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line>',
    'edit': '<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>',
    'close': '<line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line>',
    'pin': '<path d="M9 3l6 6"></path><path d="M12 6l6 6"></path><path d="M9 9l6 6"></path><path d="M12 15v6"></path>',
    'add': '<line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line>',
    'back': '<polyline points="15 18 9 12 15 6"></polyline>',
    'forward': '<polyline points="9 18 15 12 9 6"></polyline>',
    'dashboard': '<path d="M3 11.5 12 4l9 7.5"></path><path d="M5 10.5V20h14v-9.5"></path>',
    'diary': '<rect x="4" y="5" width="16" height="15" rx="2"></rect><path d="M8 3v4M16 3v4M4 9h16"></path>',
    'notes': '<path d="M7 4h8l4 4v12H7z"></path><path d="M15 4v4h4"></path><path d="M10 12h6M10 16h5"></path>',
    'todo': '<path d="M9 6h11M9 12h11M9 18h11"></path><path d="m4 6 1.5 1.5L7.5 5.5"></path><path d="m4 12 1.5 1.5L7.5 11.5"></path><path d="m4 18 1.5 1.5L7.5 17.5"></path>',
    'canvas': '<path d="M4 6h16"></path><path d="M4 12h10"></path><path d="M4 18h7"></path><path d="M18 12h2"></path>',
    'settings': '<path d="M12 3v3"></path><path d="M12 18v3"></path><path d="M3 12h3"></path><path d="M18 12h3"></path><path d="m5.6 5.6 2.1 2.1"></path><path d="m16.3 16.3 2.1 2.1"></path><path d="m18.4 5.6-2.1 2.1"></path><path d="m7.7 16.3-2.1 2.1"></path><circle cx="12" cy="12" r="3.2"></circle>',
    'search': '<circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line>',
    'filter': '<polygon points="3 4 21 4 14 12 14 20 10 18 10 12"></polygon>',
    'category': '<circle cx="6" cy="6" r="3"></circle><circle cx="18" cy="6" r="3"></circle><circle cx="6" cy="18" r="3"></circle><circle cx="18" cy="18" r="3"></circle>',
    'upload': '<path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"></path><polyline points="7 9 12 4 17 9"></polyline><line x1="12" y1="4" x2="12" y2="16"></line>',
    'download': '<path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"></path><polyline points="7 11 12 16 17 11"></polyline><line x1="12" y1="4" x2="12" y2="16"></line>',
}

VARIANTS = {
    'default': '#334155',
    'green': '#34C759',
    'red': '#FF3B30',
    'yellow': '#FFCC00',
    'grey': '#6E6E73',
    'white': '#FFFFFF',
}

SVG_TEMPLATE = '''<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{paths}</svg>\n'''

for icon_name, path_data in ICONS.items():
    for variant_name, color in VARIANTS.items():
        out_file = OUTPUT_DIR / f'{icon_name}_{variant_name}.svg'
        out_file.write_text(SVG_TEMPLATE.format(color=color, paths=path_data), encoding='utf-8')
        print(f'Generated: {out_file.relative_to(BASE_DIR)}')
