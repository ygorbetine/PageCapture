"""
Page Capture 1.9 - capture pages one by one (simple or scroll-and-stitch mode) and build a PDF.
By Ygor Betine - Becine Tools. For personal use, with apps that allow screen capture.

Install:
    pip install mss pyautogui pillow numpy opencv-python pynput img2pdf
    (optional, to read the book title by OCR)  pip install pytesseract  + the Tesseract program

Hotkeys while capturing:  F9 = pause / resume   |   ESC = stop
"""
import base64
import ctypes
import io
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import filedialog

import cv2
import mss
import numpy as np
import pyautogui
from PIL import Image, ImageDraw, ImageOps, ImageTk
from pynput import keyboard

try:
    import winsound
except ImportError:  # not on Windows
    winsound = None

try:
    import ctypes.wintypes
except (ImportError, ValueError):
    pass

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # real pixel coordinates
except Exception:
    pass

pyautogui.PAUSE = 0
pyautogui.FAILSAFE = True  # mouse to the top-left corner also aborts

VERSION = "1.9"
AUTHOR = "Ygor Betine"
SUITE = "Becine Tools"

# ---------- brand palette ----------
NAVY = "#23305E"
PURPLE = "#7E217A"
PURPLE_LT = "#A64AA1"  # lighter tint of the brand purple (outlines, focus)
LIGHT = "#E8E8E8"
YELLOW = "#F6FF54"     # detail only (slider knob, check mark)
BLACK = "#000000"
INPUT_BG = "#141B38"   # darkened navy for fields
LINE = "#4A5A94"
MUTED = "#A9AEC4"
DIM = "#6E7490"

SCALE = [1.0]
LANG = ["en"]

# ---------- translations (English, Portuguese) ----------
TXT = {
    "subtitle": ("Capture book pages straight into a PDF", "Capture páginas de livros direto em PDF"),
    "hint_keys": ("F9 pause · ESC stop", "F9 pausar · ESC parar"),
    "folders": ("FOLDERS", "PASTAS"),
    "temp_images": ("Temp folder", "Pasta temp."),
    "pdf_folder": ("PDF folder", "Pasta dos PDFs"),
    "doc_name": ("Document name", "Documento"),
    "name_hint": ("Leave the document name empty to use the window title or, if there is none, the title read "
                  "from the first page.",
                  "Deixe o nome do documento vazio para usar o título da janela ou, se não houver, o título "
                  "lido na primeira página."),
    "log_name_page": ('Document name read from the first page: "{name}"', 'Nome do documento lido na primeira página: "{name}"'),
    "log_name_fallback": ('Could not read a title from the first page; using "{name}"',
                          'Não consegui ler um título na primeira página; usando "{name}"'),
    "log_project": ("Project folder: {dir}", "Pasta do projeto: {dir}"),
    "no_project": ("No project found. Type a document name or capture something first.",
                   "Nenhum projeto encontrado. Digite um nome de documento ou capture algo primeiro."),
    "from_window": ("From window", "Da janela"),
    "ocr_title": ("OCR title", "OCR título"),
    "capture": ("CAPTURE", "CAPTURA"),
    "show_log": ("Show log", "Mostrar log"),
    "hide_log": ("Hide log", "Ocultar log"),
    "mode": ("Mode", "Modo"),
    "simple": ("Simple", "Simples"),
    "scroll": ("Scroll", "Rolagem"),
    "start_page": ("Start at page", "Pág. inicial"),
    "pages": ("Pages (0 = to the end)", "Páginas (0 = até o fim)"),
    "delay": ("Delay (s)", "Espera (s)"),
    "key": ("Next-page key", "Tecla próx. pág."),
    "scroll_step": ("Scroll step", "Passo rolagem"),
    "max_steps": ("Max scroll steps", "Máx. de passos"),
    "threshold": ("Match threshold", "Limiar junção"),
    "strict": ("Strict", "Rígido"),
    "balanced": ("Balanced", "Equilibrado"),
    "flexible": ("Flexible", "Flexível"),
    "explain": (
        "How alike the end of one screenshot and the start of the next must look to count as the same page. "
        "Higher = stricter: if they differ too much, the app assumes the page turned and stops there, so "
        "nothing from the next page gets in (a very high value can cut long pages short). "
        "Lower = more forgiving: it keeps scrolling through soft or blurry pages, but may let part of the "
        "next page in. 0.90 works for most books.",
        "O quão parecidos o fim de um print e o começo do próximo precisam ser para valerem como a mesma "
        "página. Mais alto = mais rígido: se forem diferentes demais, o app entende que a página virou e para "
        "ali, sem deixar nada da próxima página entrar (um valor muito alto pode cortar páginas longas). "
        "Mais baixo = mais tolerante: continua rolando em páginas suaves ou borradas, mas pode deixar entrar "
        "um pedaço da próxima página. 0,90 funciona na maioria dos livros."),
    "options": ("OPTIONS", "OPÇÕES"),
    "opt_pdf": ("Build the PDF when finished", "Gerar o PDF ao terminar"),
    "opt_end": ("Stop when the page stops changing", "Parar quando a página parar de mudar"),
    "opt_gap": ("Scroll mode: stop at the dark gap between pages",
                "Modo rolagem: parar na faixa escura entre páginas"),
    "opt_clean": ("Delete temp images after building the PDF", "Apagar imagens temp. após gerar o PDF"),
    "select_region": ("Select region", "Selecionar região"),
    "region_btn": ("Region  {w}×{h}", "Região  {w}×{h}"),
    "make_pdf": ("Make PDF now", "Gerar PDF agora"),
    "start": ("Start  ▶", "Iniciar  ▶"),
    "status_idle": ("Pick the page area, then press Start. You get 5 seconds to click the reader window.",
                    "Escolha a área da página e clique em Iniciar. Você tem 5 segundos para clicar na janela do leitor."),
    "need_region": ("Select the capture region first, then press Start.",
                    "Selecione a região de captura primeiro e depois clique em Iniciar."),
    "region_status": ("Region set at ({x}, {y}). Press Start when ready.",
                      "Região definida em ({x}, {y}). Clique em Iniciar quando estiver pronto."),
    "overlay_region": ("Drag to select the page area   ·   ESC to cancel",
                       "Arraste para selecionar a área da página   ·   ESC para cancelar"),
    "overlay_title": ("Drag over the book title   ·   ESC to cancel",
                      "Arraste sobre o título do livro   ·   ESC para cancelar"),
    "panel_title": ("Capture", "Captura"),
    "pause": ("Pause  (F9)", "Pausar  (F9)"),
    "resume": ("Resume  (F9)", "Continuar  (F9)"),
    "stop": ("Stop  (ESC)", "Parar  (ESC)"),
    "page_n": ("Page {n}", "Página {n}"),
    "log_title": ("Live log", "Log em tempo real"),
    "clear": ("Clear", "Limpar"),
    "close": ("Close", "Fechar"),
    "d_fields_t": ("Check the fields", "Confira os campos"),
    "d_fields": ("Please check the numbers: start page, pages, delay and scroll values.",
                 "Confira os números: página inicial, páginas, espera e valores de rolagem."),
    "d_region_t": ("Region needed", "Região necessária"),
    "d_region": ("Select the capture region first. The app reads the title of the window behind it.",
                 "Selecione a região de captura primeiro. O app lê o título da janela que está atrás dela."),
    "d_notitle_t": ("No book title found", "Título do livro não encontrado"),
    "d_notitle": ('The window title is just "{title}". Try "OCR title" or type the name.',
                  'O título da janela é apenas "{title}". Tente "OCR título" ou digite o nome.'),
    "empty": ("empty", "vazio"),
    "d_ocr_t": ("OCR not available", "OCR indisponível"),
    "ocr_pkg": ("OCR needs the pytesseract package and the Tesseract program.\n\npip install pytesseract\n"
                "Tesseract for Windows: github.com/UB-Mannheim/tesseract/wiki",
                "O OCR precisa do pacote pytesseract e do programa Tesseract.\n\npip install pytesseract\n"
                "Tesseract para Windows: github.com/UB-Mannheim/tesseract/wiki"),
    "ocr_tess": ("Tesseract is not installed.\nTesseract for Windows: github.com/UB-Mannheim/tesseract/wiki",
                 "O Tesseract não está instalado.\nTesseract para Windows: github.com/UB-Mannheim/tesseract/wiki"),
    "d_nothing_t": ("Nothing recognised", "Nada reconhecido"),
    "d_nothing": ("Could not read a title there. Try a tighter area or type the name.",
                  "Não consegui ler um título ali. Tente uma área mais justa ou digite o nome."),
    "pdf_building": ("Building PDF...", "Gerando PDF..."),
    "pdf_saved": ("PDF saved to:\n{pdf}", "PDF salvo em:\n{pdf}"),
    "pdf_none": ("There are no images in the temp folder.", "Não há imagens na pasta temporária."),
    "pdf_fail": ("Could not build the PDF:\n{err}", "Não foi possível gerar o PDF:\n{err}"),
    "log_pdf_temp": ("Building PDF from the temp folder...", "Gerando PDF a partir da pasta temporária..."),
    "d_tempfull_t": ("Temp folder not empty", "A pasta temporária não está vazia"),
    "d_tempfull": ("The temp folder already has {n} images.\n\nDelete them and start fresh, or keep them "
                   "(they will be overwritten from page 1)?",
                   "A pasta temporária já tem {n} imagens.\n\nApagar e começar do zero, ou manter "
                   "(elas serão sobrescritas a partir da página 1)?"),
    "b_delstart": ("Delete & start", "Apagar e iniciar"),
    "b_keep": ("Keep", "Manter"),
    "b_cancel": ("Cancel", "Cancelar"),
    "log_deleted": ("Deleted {n} old images from the temp folder", "Apagadas {n} imagens antigas da pasta temporária"),
    "log_name": ('PDF name: "{name}"', 'Nome do PDF: "{name}"'),
    "log_name_none": (" (no book title found)", " (título do livro não encontrado)"),
    "log_name_win": ('PDF name from the window title: "{name}"', 'Nome do PDF a partir do título da janela: "{name}"'),
    "log_name_ocr": ('PDF name from OCR: "{name}"', 'Nome do PDF a partir do OCR: "{name}"'),
    "log_hk_ok": ("Hotkeys active: F9 pause / resume, ESC stop (work with any window focused)",
                  "Atalhos ativos: F9 pausa / continua, ESC para (funcionam com qualquer janela em foco)"),
    "log_hk_no": ("Global hotkeys unavailable: use the panel buttons",
                  "Atalhos globais indisponíveis: use os botões do painel"),
    "log_hid_ok": ("Control windows are hidden from screen captures",
                   "As janelas de controle ficam ocultas das capturas de tela"),
    "log_hid_no": ("This Windows version cannot hide the control windows from captures; "
                   "they were moved away from the region",
                   "Esta versão do Windows não consegue ocultar as janelas de controle das capturas; "
                   "elas foram afastadas da região"),
    "log_start": ("Start: page {n}, mode {mode}, key '{key}', delay {delay}s{extra}",
                  "Início: página {n}, modo {mode}, tecla '{key}', espera {delay}s{extra}"),
    "log_extra": (", threshold {th:.2f}, page gap {gap}", ", limiar {th:.2f}, faixa entre páginas {gap}"),
    "on": ("on", "ligada"),
    "off": ("off", "desligada"),
    "countdown": ("Click the reader window. Starting in {s}s...", "Clique na janela do leitor. Começando em {s}s..."),
    "log_capturing": ("Capturing page {n}", "Capturando a página {n}"),
    "log_same": ("Page {n} looks identical to the previous one ({k}/2)",
                 "A página {n} parece idêntica à anterior ({k}/2)"),
    "captured": ("Captured page {n}  ({saved}{total})", "Página {n} capturada  ({saved}{total})"),
    "total_of": (" of {p}", " de {p}"),
    "log_saved": ("Saved page {n} ({w}x{h})", "Página {n} salva ({w}x{h})"),
    "log_finished": ("Finished ({reason}), {saved} page(s) captured", "Finalizado ({reason}), {saved} página(s) capturada(s)"),
    "log_error": ("Error: {e}", "Erro: {e}"),
    "paused_status": ("Paused (next: page {n}). Press F9 to resume.", "Pausado (próxima: página {n}). Pressione F9 para continuar."),
    "log_paused": ("Paused", "Pausado"),
    "log_resumed": ("Resumed", "Retomado"),
    "log_stop": ("Stop requested", "Parada solicitada"),
    "log_region": ("Region set: {w}x{h} at ({x}, {y})", "Região definida: {w}x{h} em ({x}, {y})"),
    "log_open_fail": ("Could not open the log: {e}", "Não foi possível abrir o log: {e}"),
    "t_done": ("All done", "Concluído"),
    "m_done": ("Captured {saved} pages {span}.", "{saved} páginas capturadas {span}."),
    "span": ("(pages {a}–{b})", "(páginas {a}–{b})"),
    "t_early": ("Finished early", "Terminou antes do previsto"),
    "m_early": ("The page stopped changing, so the book probably ended.\nCaptured {saved} pages{plan} {span}.",
                "A página parou de mudar, então o livro provavelmente acabou.\n{saved} páginas capturadas{plan} {span}."),
    "plan": (" of {p} planned", " de {p} previstas"),
    "t_err": ("Something went wrong", "Algo deu errado"),
    "m_err": ("The capture stopped because of an error:\n{err}", "A captura parou por causa de um erro:\n{err}"),
    "t_stopped": ("Capture stopped", "Captura interrompida"),
    "m_stopped": ("Last saved page: {last}.\nTo continue, go to page {next} in the reader and press Start.",
                  "Última página salva: {last}.\nPara continuar, vá para a página {next} no leitor e clique em Iniciar."),
    "pdf_to": ("\n\nPDF saved to:\n{pdf}", "\n\nPDF salvo em:\n{pdf}"),
    "cp_trim": ("  trimmed {n}px of page gap at the top", "  removidos {n}px de faixa entre páginas no topo"),
    "cp_gap": ("  page gap found at {n}px: the page ends here", "  faixa entre páginas em {n}px: a página termina aqui"),
    "cp_nomatch": ("  scroll {step}: no overlap (score {s:.2f}, needs {t:.2f}): the page changed, stopping here "
                   "without adding it",
                   "  rolagem {step}: sem sobreposição (nota {s:.2f}, precisa de {t:.2f}): a página mudou, "
                   "parando aqui sem adicioná-la"),
    "cp_match": ("  scroll {step}: overlap score {s:.2f}, +{a}px", "  rolagem {step}: nota de sobreposição {s:.2f}, +{a}px"),
    "cp_end": ("  end of page reached after {step} scroll(s)", "  fim da página após {step} rolagem(ns)"),
    "default_name": ("captures", "capturas"),
    "export": ("Export", "Exportar"),
    "compression": ("Compression", "Compressão"),
    "comp_off": ("Off", "Nenhuma"),
    "comp_light": ("Light", "Leve"),
    "comp_balanced": ("Medium", "Média"),
    "comp_strong": ("Strong", "Forte"),
    "log_comp": ("PDF compression: {level} (JPEG quality {q}, max width {w})",
                 "Compressão do PDF: {level} (qualidade JPEG {q}, largura máx. {w})"),
    "log_comp_off": ("PDF compression: off (page images kept lossless)",
                     "Compressão do PDF: desligada (imagens das páginas sem perdas)"),
    "orig_width": ("original", "original"),
    "pdf_compressing": ("Compressing pages for the PDF ({i}/{n})...", "Comprimindo as páginas do PDF ({i}/{n})..."),
    "pdf_size": ("Size: {size} MB (page images: {orig} MB)", "Tamanho: {size} MB (imagens das páginas: {orig} MB)"),
    "log_export_title": ("Export log", "Exportar log"),
    "log_to": ("\n\nLog:\n{path}", "\n\nLog:\n{path}"),
    "log_file_saved": ("Log saved: {path}", "Log salvo: {path}"),
    "source": ("Source", "Origem"),
    "src_region": ("Screen region", "Região da tela"),
    "src_window": ("Window", "Janela"),
    "select_window": ("Select window", "Selecionar janela"),
    "window_btn": ("Window: {t}", "Janela: {t}"),
    "overlay_window": ("Click the window to capture   ·   right click or ESC to cancel",
                       "Clique na janela a capturar   ·   botão direito ou ESC para cancelar"),
    "need_window": ("Select the window first, then press Start.", "Selecione a janela primeiro e depois clique em Iniciar."),
    "window_status": ('Window selected: "{title}". Press Start when ready.',
                      'Janela selecionada: "{title}". Clique em Iniciar quando estiver pronto.'),
    "log_window": ('Window set: "{title}"', 'Janela definida: "{title}"'),
    "log_src_window": ('Source: window "{title}" (the control windows never appear in the frames)',
                       'Origem: janela "{title}" (as janelas de controle nunca aparecem nos quadros)'),
    "log_src_region": ("Source: screen region", "Origem: região da tela"),
    "win_black": ("The window returned a black image. It may block window capture, or its content is not "
                  "being rendered right now.",
                  "A janela retornou uma imagem preta. Ela pode bloquear a captura de janela, ou seu conteúdo "
                  "não está sendo renderizado agora."),
    "win_min": ("The window is minimized. Restore it and try again.", "A janela está minimizada. Restaure-a e tente de novo."),
    "win_gone": ("The window was closed or cannot be captured.", "A janela foi fechada ou não pode ser capturada."),
    "cp_resized": ("  the window size changed during the scroll; ending this page",
                   "  o tamanho da janela mudou durante a rolagem; encerrando esta página"),
}


def t(name, /, **kw):
    s = TXT[name][0 if LANG[0] == "en" else 1]
    return s.format(**kw) if kw else s


def U(n):
    """Scale a layout size (designed for 96 dpi) to the current screen."""
    return int(round(n * SCALE[0]))


def F(px, bold=False, semibold=False):
    return ("Segoe UI Semibold" if semibold else "Segoe UI", -U(px), "bold" if bold else "normal")


# ---------- settings (language and window position are remembered) ----------
def settings_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "BecineTools", "PageCapture", "settings.json")


def load_settings():
    try:
        with open(settings_path(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_settings(data):
    try:
        os.makedirs(os.path.dirname(settings_path()), exist_ok=True)
        with open(settings_path(), "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


# ---------- monitors ----------
def virtual_screen(win):
    """(x, y, w, h) of the whole desktop, spanning every monitor."""
    try:
        u = ctypes.windll.user32
        return u.GetSystemMetrics(76), u.GetSystemMetrics(77), u.GetSystemMetrics(78), u.GetSystemMetrics(79)
    except Exception:
        return 0, 0, win.winfo_screenwidth(), win.winfo_screenheight()


def monitor_bounds(win, x, y):
    """Work area (left, top, right, bottom) of the monitor that contains the point."""
    if sys.platform == "win32":
        try:
            u = ctypes.windll.user32

            class MonitorInfo(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.wintypes.DWORD), ("rcMonitor", ctypes.wintypes.RECT),
                            ("rcWork", ctypes.wintypes.RECT), ("dwFlags", ctypes.wintypes.DWORD)]

            u.MonitorFromPoint.argtypes = [ctypes.wintypes.POINT, ctypes.wintypes.DWORD]
            u.MonitorFromPoint.restype = ctypes.c_void_p
            u.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MonitorInfo)]
            mi = MonitorInfo()
            mi.cbSize = ctypes.sizeof(MonitorInfo)
            hmon = u.MonitorFromPoint(ctypes.wintypes.POINT(int(x), int(y)), 2)  # nearest monitor
            if hmon and u.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                r = mi.rcWork
                return r.left, r.top, r.right, r.bottom
        except Exception:
            pass
    return 0, 0, win.winfo_screenwidth(), win.winfo_screenheight()


# ---------- background / drawing helpers ----------
_bg_src = None


def bg_image(w, h, cards=()):
    """Brand gradient stretched to w x h, with translucent dark cards on top."""
    global _bg_src
    if _bg_src is None:
        _bg_src = Image.open(io.BytesIO(base64.b64decode(BG_B64))).convert("RGB")
    img = _bg_src.resize((w, h), Image.LANCZOS).convert("RGBA")
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for x1, y1, x2, y2 in cards:
        d.rounded_rectangle((x1, y1, x2, y2), radius=U(14), fill=(0, 0, 0, 118),
                            outline=(232, 232, 232, 34), width=1)
    return ImageTk.PhotoImage(Image.alpha_composite(img, overlay).convert("RGB"))


def rr_points(x1, y1, x2, y2, r):
    return [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
            x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]


def round_rect(c, x1, y1, x2, y2, r, **kw):
    return c.create_polygon(rr_points(x1, y1, x2, y2, r), smooth=True, **kw)


STYLES = {
    "primary": dict(fill=PURPLE, hover="#9A2E96", fg=LIGHT, outline=PURPLE_LT),
    "secondary": dict(fill="#2A3A70", hover="#35498C", fg=LIGHT, outline=LINE),
    "disabled": dict(fill="#2B1D33", hover="#2B1D33", fg=DIM, outline="#43324D"),
}


class Btn:
    def __init__(self, c, x, y, w, h, text, cmd, kind="secondary", size=13):
        s = STYLES[kind]
        self.c, self.cmd, self.s, self.kind = c, cmd, s, kind
        self.enabled = True
        tag = f"btn{id(self)}"
        self.shape = round_rect(c, x, y, x + w, y + h, U(10), fill=s["fill"], outline=s["outline"],
                                width=1, tags=tag)
        self.text = c.create_text(x + w / 2, y + h / 2, text=text, fill=s["fg"], font=F(size, True), tags=tag)
        c.tag_bind(tag, "<Enter>", self._enter)
        c.tag_bind(tag, "<Leave>", self._leave)
        c.tag_bind(tag, "<Button-1>", lambda e: self.cmd())

    def _enter(self, _):
        self.c.itemconfig(self.shape, fill=self.s["hover"])
        self.c.config(cursor="hand2" if self.enabled else "")

    def _leave(self, _):
        self.c.itemconfig(self.shape, fill=self.s["fill"])
        self.c.config(cursor="")

    def set_enabled(self, on, kind="secondary"):
        """Disabled buttons look dimmed; clicking them still calls cmd (so it can explain why)."""
        self.enabled = on
        self.s = STYLES[kind if on else "disabled"]
        self.c.itemconfig(self.shape, fill=self.s["fill"], outline=self.s["outline"])
        self.c.itemconfig(self.text, fill=self.s["fg"])

    def flash(self):
        self.c.itemconfig(self.shape, outline=LIGHT, width=2)
        self.c.after(700, lambda: self.c.itemconfig(self.shape, outline=self.s["outline"], width=1))

    def set_text(self, t_):
        self.c.itemconfig(self.text, text=t_)


class Check:
    def __init__(self, c, x, y, text, var):
        self.c, self.var = c, var
        tag = f"chk{id(self)}"
        self.box = round_rect(c, x, y, x + U(20), y + U(20), U(6), fill=INPUT_BG, outline=LINE, tags=tag)
        self.tick = c.create_text(x + U(10), y + U(10), text="✓", fill=YELLOW, font=F(14, True),
                                  state="hidden", tags=tag)
        c.create_text(x + U(32), y + U(10), anchor="w", text=text, fill=LIGHT, font=F(13), tags=tag)
        c.tag_bind(tag, "<Button-1>", self.toggle)
        c.tag_bind(tag, "<Enter>", lambda e: c.config(cursor="hand2"))
        c.tag_bind(tag, "<Leave>", lambda e: c.config(cursor=""))
        self.refresh()

    def toggle(self, _=None):
        self.var.set(not self.var.get())
        self.refresh()

    def refresh(self):
        on = self.var.get()
        self.c.itemconfig(self.box, fill=PURPLE if on else INPUT_BG, outline=PURPLE_LT if on else LINE)
        self.c.itemconfig(self.tick, state="normal" if on else "hidden")


class Segmented:
    def __init__(self, c, x, y, w, h, options, var, on_change=None, size=13):
        self.c, self.var, self.on_change, self.options, self.parts = c, var, on_change, options, []
        round_rect(c, x, y, x + w, y + h, U(10), fill=INPUT_BG, outline=LINE)
        seg = w / len(options)
        for i, (label, value) in enumerate(options):
            sx, tag = x + i * seg, f"seg{id(self)}_{i}"
            rect = round_rect(c, sx + U(3), y + U(3), sx + seg - U(3), y + h - U(3), U(8),
                              fill=INPUT_BG, outline="", tags=tag)
            txt = c.create_text(sx + seg / 2, y + h / 2, text=label, fill=MUTED, font=F(size, True), tags=tag)
            c.tag_bind(tag, "<Button-1>", lambda e, v=value: self.select(v))
            c.tag_bind(tag, "<Enter>", lambda e: c.config(cursor="hand2"))
            c.tag_bind(tag, "<Leave>", lambda e: c.config(cursor=""))
            self.parts.append((value, rect, txt))
        self.refresh()

    def select(self, value):
        self.var.set(value)
        self.refresh()
        if self.on_change:
            self.on_change()

    def refresh(self):
        for value, rect, txt in self.parts:
            on = self.var.get() == value
            self.c.itemconfig(rect, fill=PURPLE if on else INPUT_BG)
            self.c.itemconfig(txt, fill=LIGHT if on else MUTED)


class Slider:
    """Horizontal slider drawn on the canvas, with a value read-out on the right."""

    def __init__(self, c, x, y, w, lo, hi, var, step=0.01, describe=None):
        self.c, self.x, self.y, self.w = c, x, y, w
        self.lo, self.hi, self.var, self.step, self.describe = lo, hi, var, step, describe
        self.enabled = True
        tag = f"sld{id(self)}"
        self.hh = U(5)  # half height of the track
        self.track = round_rect(c, x, y - self.hh, x + w, y + self.hh, self.hh, fill=INPUT_BG, outline=LINE, tags=tag)
        self.fill = c.create_polygon(rr_points(x, y, x + 1, y, 1), smooth=True, fill=PURPLE, outline="", tags=tag)
        self.knob = c.create_oval(0, 0, 0, 0, fill=YELLOW, outline=LIGHT, width=1, tags=tag)
        self.value_txt = c.create_text(x + w + U(16), y, anchor="w", fill=LIGHT, font=F(13, True))
        c.tag_bind(tag, "<Button-1>", self._set_from_event)
        c.tag_bind(tag, "<B1-Motion>", self._set_from_event)
        c.tag_bind(tag, "<Enter>", lambda e: c.config(cursor="hand2" if self.enabled else ""))
        c.tag_bind(tag, "<Leave>", lambda e: c.config(cursor=""))
        self.refresh()

    def _set_from_event(self, e):
        if not self.enabled:
            return
        frac = min(1.0, max(0.0, (self.c.canvasx(e.x) - self.x) / self.w))
        val = self.lo + frac * (self.hi - self.lo)
        self.var.set(round(round(val / self.step) * self.step, 4))
        self.refresh()

    def set_enabled(self, on):
        self.enabled = on
        self.refresh()

    def refresh(self):
        frac = (self.var.get() - self.lo) / (self.hi - self.lo)
        frac = min(1.0, max(0.0, frac))
        cx = self.x + frac * self.w
        r = U(9)
        fx = max(cx, self.x + 2 * self.hh)
        self.c.coords(self.fill, *rr_points(self.x, self.y - self.hh + 1, fx, self.y + self.hh - 1, self.hh - 1))
        self.c.coords(self.knob, cx - r, self.y - r, cx + r, self.y + r)
        self.c.itemconfig(self.fill, fill=PURPLE if self.enabled else DIM)
        self.c.itemconfig(self.knob, fill=YELLOW if self.enabled else DIM, outline=LIGHT if self.enabled else LINE)
        txt = f"{self.var.get():.2f}"
        if LANG[0] == "pt":
            txt = txt.replace(".", ",")
        if self.describe:
            txt += "  " + self.describe(self.var.get())
        self.c.itemconfig(self.value_txt, text=txt, fill=LIGHT if self.enabled else DIM)


# ---------- window helpers ----------
def center(win, w, h, ref=(0, 0)):
    L, T, R, B = monitor_bounds(win, *ref)
    win.geometry(f"{w}x{h}+{L + (R - L - w) // 2}+{max(T, T + (B - T - h) // 2 - U(20))}")


def no_activate(win):
    """Make a window non-activating: clicking it keeps the focus on the reader app."""
    try:
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        ex = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex | 0x08000000 | 0x80)
    except Exception:
        pass


def hide_from_capture(win):
    """Exclude this window from screenshots / screen recordings (Windows 10 2004+). True on success."""
    try:
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        return bool(ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x11))  # WDA_EXCLUDEFROMCAPTURE
    except Exception:
        return False


def place_outside(win, w, h, region, avoid=(), near=None):
    """Put a window on the monitor of the capture region (or of `near`), away from the region and
    from the `avoid` rects. Returns the (x, y, w, h) rect."""
    if region:
        ref = (region["left"] + region["width"] // 2, region["top"] + region["height"] // 2)
    elif near:
        ref = (near[0] + near[2] // 2, near[1] + near[3] // 2)
    else:
        ref = (0, 0)
    L, T, R, B = monitor_bounds(win, *ref)
    m = U(10)
    cands = [(R - w - m, B - h - m), (L + m, B - h - m), (R - w - m, T + m), (L + m, T + m),
             (R - w - m, (T + B - h) // 2), (L + m, (T + B - h) // 2)]
    if near:  # prefer the space right / left of a reference window
        side = [(near[0] + near[2] + m, near[1]), (near[0] - w - m, near[1])]
        cands = [(x, max(T, min(y, B - h - m))) for x, y in side if L <= x and x + w <= R] + cands
    rects = list(avoid)
    if region:
        rects.append((region["left"], region["top"], region["width"], region["height"]))

    def hit(r, x, y):
        return not (x + w <= r[0] or x >= r[0] + r[2] or y + h <= r[1] or y >= r[1] + r[3])

    pos = next((p for p in cands if not any(hit(r, *p) for r in rects)), cands[0])
    win.geometry(f"+{pos[0]}+{pos[1]}")
    return (pos[0], pos[1], w, h)


_DIALOG = [None]


def dialog(root, title, message, buttons):
    """Themed dialog. buttons = [(label, kind)]. Returns the clicked index (None if closed)."""
    if _DIALOG[0] is not None and _DIALOG[0].winfo_exists():
        _DIALOG[0].lift()
        return None
    result = [None]
    top = tk.Toplevel(root)
    _DIALOG[0] = top
    top.title(title)
    top.resizable(False, False)
    top.attributes("-topmost", True)
    W = U(460)
    c = tk.Canvas(top, width=W, height=U(200), highlightthickness=0, bd=0, bg=BLACK)
    c.pack()
    c.create_text(U(28), U(26), anchor="nw", text=title, fill=LIGHT, font=F(17, semibold=True), width=W - U(56))
    t2 = c.create_text(U(28), U(64), anchor="nw", text=message, fill=LIGHT, font=F(13), width=W - U(56))
    top.update_idletasks()
    H = c.bbox(t2)[3] + U(28) + U(40) + U(26)
    c.config(height=H)
    img = bg_image(W, H, [(U(10), U(10), W - U(10), H - U(10))])
    bgid = c.create_image(0, 0, image=img, anchor="nw")
    c.tag_lower(bgid)
    c.image = img

    def pick(i):
        result[0] = i
        top.destroy()

    x = W - U(28)
    for i in range(len(buttons) - 1, -1, -1):
        label, kind = buttons[i]
        w = max(U(96), len(label) * U(9) + U(40))
        x -= w
        Btn(c, x, H - U(26) - U(40), w, U(40), label, lambda i=i: pick(i), kind)
        x -= U(10)
    ref = (root.winfo_rootx() + root.winfo_width() // 2, root.winfo_rooty() + root.winfo_height() // 2) \
        if root.state() == "normal" else (0, 0)
    center(top, W, H, ref)
    top.protocol("WM_DELETE_WINDOW", top.destroy)
    top.update()
    top.lift()
    top.focus_force()
    root.wait_window(top)
    _DIALOG[0] = None
    return result[0]


def beep(kind):
    if winsound:
        winsound.MessageBeep({"ok": winsound.MB_ICONASTERISK, "warn": winsound.MB_ICONEXCLAMATION,
                              "err": winsound.MB_ICONHAND}[kind])


# ---------- capture ----------
def grab(region):
    with mss.mss() as sct:
        shot = sct.grab(region)
        return np.array(Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX"))


def select_region(root, hint):
    """Overlay across ALL monitors: drag to choose a region. Right click or ESC cancels."""
    result = {}
    vx, vy, vw, vh = virtual_screen(root)
    win = tk.Toplevel(root)
    win.overrideredirect(True)
    win.attributes("-alpha", 0.35, "-topmost", True)
    win.geometry(f"{vw}x{vh}{vx:+d}{vy:+d}")
    win.configure(bg=BLACK, cursor="crosshair")
    canvas = tk.Canvas(win, bg=BLACK, highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    win.update_idletasks()
    ref = (root.winfo_rootx() + 10, root.winfo_rooty() + 10)
    L, T, R, B = monitor_bounds(win, *ref)
    canvas.create_text((L + R) // 2 - vx, T - vy + U(48), fill=LIGHT, font=F(20, True), text=hint)
    state = {}

    def down(e):
        state["x"], state["y"], state["cx"], state["cy"] = e.x_root, e.y_root, e.x, e.y
        state["rect"] = canvas.create_rectangle(e.x, e.y, e.x, e.y, outline=LIGHT, width=2)

    def move(e):
        if "rect" in state:
            canvas.coords(state["rect"], state["cx"], state["cy"], e.x, e.y)

    def up(e):
        if "x" in state:
            x1, x2 = sorted((state["x"], e.x_root))
            y1, y2 = sorted((state["y"], e.y_root))
            if x2 - x1 > 10 and y2 - y1 > 10:
                result.update(left=x1, top=y1, width=x2 - x1, height=y2 - y1)
        win.destroy()

    canvas.bind("<ButtonPress-1>", down)
    canvas.bind("<B1-Motion>", move)
    canvas.bind("<ButtonRelease-1>", up)
    canvas.bind("<Button-3>", lambda e: win.destroy())
    win.bind("<Escape>", lambda e: win.destroy())
    win.focus_force()
    root.wait_window(win)
    return result or None


def append_scroll(acc, prev, new, thresh, strip=80, tol=20.0):
    """Join `new` to `acc` only if it is the same page scrolled. Returns (acc, added_rows, score, matched).
    matched is False when the page changed (page turn): nothing is added and the caller must stop."""
    h = new.shape[0]
    strip = min(strip, h // 4)
    res = cv2.matchTemplate(new, prev[-strip:], cv2.TM_CCOEFF_NORMED)
    _, score, _, loc = cv2.minMaxLoc(res)
    if not np.isfinite(score) or score < thresh:
        return acc, 0, float(score) if np.isfinite(score) else 0.0, False
    shift = (h - strip) - loc[1]  # how many rows the content moved up
    if shift < 0:
        return acc, 0, score, False
    if shift > 0:  # the whole overlap must agree, not just the strip (a page turn can fool the strip)
        a = prev[shift:].astype(np.int16)
        b = new[:h - shift].astype(np.int16)
        if np.abs(a - b).mean() > tol:
            return acc, 0, score, False
    fresh = new[loc[1] + strip:]
    return (np.vstack([acc, fresh]) if len(fresh) > 2 else acc), len(fresh), score, True


MIN_GAP = 12  # rows of dark band that count as the gap between two pages


def gap_runs(img, min_run=MIN_GAP):
    """Full-width, flat, dark bands (the gap between pages in continuous view): [(start, end)]."""
    g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(np.float32)
    uni = (g.std(axis=1) < 3.0) & (g.mean(axis=1) < 45)
    runs, i, n = [], 0, len(uni)
    while i < n:
        if uni[i]:
            j = i
            while j < n and uni[j]:
                j += 1
            if j - i >= min_run:
                runs.append((i, j))
            i = j
        else:
            i += 1
    return runs


def capture_page(target, scroll_amount, max_steps, thresh, gap, log, delay=0.4, preview=None):
    first = target.grab()
    if first is None:
        raise RuntimeError(t("win_gone"))
    acc = prev = first
    if gap:
        runs = gap_runs(acc, 3)
        if runs and runs[0][0] == 0:  # the frame starts inside the gap of the previous page
            acc = acc[runs[0][1]:]
            log(t("cp_trim", n=runs[0][1]))
            if acc.shape[0] < 10:
                acc = first
        runs = gap_runs(acc)
        if runs:
            log(t("cp_gap", n=runs[0][0]))
            return acc[:runs[0][0]]
    if preview:
        preview(acc)
    for step in range(1, max_steps + 1):
        pyautogui.moveTo(*target.center())
        pyautogui.scroll(-scroll_amount)
        time.sleep(delay)
        new = target.grab()
        if new is None or new.shape != first.shape:
            log(t("cp_resized"), "warn")
            break
        old_len = acc.shape[0]
        acc, added, score, ok = append_scroll(acc, prev, new, thresh)
        if not ok:  # the page turned (or the content is not the same): do not join it
            log(t("cp_nomatch", step=step, s=score, t=thresh), "warn")
            break
        log(t("cp_match", step=step, s=score, a=added))
        if preview:
            preview(acc)
        if gap and added > 2:
            off = max(0, old_len - 3 * MIN_GAP)
            runs = gap_runs(acc[off:])
            if runs:
                cut = off + runs[0][0]
                log(t("cp_gap", n=cut))
                return acc[:cut]
        if added <= 2:  # nothing new = end of page
            log(t("cp_end", step=step))
            break
        prev = new
    return acc


# ---------- files ----------
def app_dir():
    """Program folder: next to the .exe when packaged, next to the .py otherwise."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def root_dir():
    """Root folder of the program. When the .exe sits in dist\\, the root is the folder above it,
    so nothing is ever saved inside dist."""
    base = app_dir()
    if getattr(sys, "frozen", False) and os.path.basename(base).lower() == "dist":
        return os.path.dirname(base)
    return base


def list_pages(folder):
    """List [(number, path)] of the page_NNN.png images, in order."""
    out = []
    if os.path.isdir(folder):
        for f in os.listdir(folder):
            m = re.fullmatch(r"page_(\d+)\.png", f)
            if m:
                out.append((int(m.group(1)), os.path.join(folder, f)))
    return sorted(out)


# JPEG quality and maximum page width in pixels (0 = keep the original width)
COMPRESSION = {"off": None, "light": (90, 0), "balanced": (80, 2000), "strong": (62, 1400)}


def build_pdf(temp, out_dir, name, clean, level="off", progress=None):
    """Build <out_dir>/<name>.pdf from the page images of a project.
    level: off = lossless page images; light / balanced / strong = JPEG pages, strong also shrinks wide pages.
    Returns (pdf_path, bytes_of_the_page_images), or (None, 0) when there is nothing to export."""
    pages = list_pages(temp)
    if not pages:
        return None, 0
    os.makedirs(out_dir, exist_ok=True)
    pdf = os.path.join(out_dir, name + ".pdf")
    paths = [p for _, p in pages]
    orig = sum(os.path.getsize(p) for p in paths)
    profile = COMPRESSION.get(level)
    work, files = None, paths
    try:
        if profile:
            quality, max_w = profile
            work = tempfile.mkdtemp(prefix="page_capture_")
            files = []
            for i, path in enumerate(paths, 1):
                im = Image.open(path).convert("RGB")
                if max_w and im.width > max_w:
                    im = im.resize((max_w, max(1, round(im.height * max_w / im.width))), Image.LANCZOS)
                jpg = os.path.join(work, f"{i:05d}.jpg")
                im.save(jpg, "JPEG", quality=quality, optimize=True)  # img2pdf embeds JPEGs without re-encoding
                files.append(jpg)
                if progress:
                    progress(i, len(paths))
        try:
            import img2pdf
            with open(pdf, "wb") as f:
                f.write(img2pdf.convert(files))
        except ImportError:  # fallback, uses more memory
            imgs = [Image.open(p).convert("RGB") for p in files]
            imgs[0].save(pdf, save_all=True, append_images=imgs[1:])
    finally:
        if work:
            shutil.rmtree(work, ignore_errors=True)
    if clean:
        for p in paths:
            os.remove(p)
    return pdf, orig


# ---------- book name helpers ----------
_API = []


def _api():
    """user32 / gdi32 with explicit argument types (handles are pointer sized on 64-bit Windows)."""
    if not _API:
        u, g, W, vp = ctypes.windll.user32, ctypes.windll.gdi32, ctypes.wintypes, ctypes.c_void_p
        u.GetClientRect.argtypes = [W.HWND, ctypes.POINTER(W.RECT)]
        u.GetWindowRect.argtypes = [W.HWND, ctypes.POINTER(W.RECT)]
        u.ClientToScreen.argtypes = [W.HWND, ctypes.POINTER(W.POINT)]
        u.GetWindowDC.argtypes, u.GetWindowDC.restype = [W.HWND], vp
        u.ReleaseDC.argtypes = [W.HWND, vp]
        u.PrintWindow.argtypes = [W.HWND, vp, ctypes.c_uint]
        for name in ("IsWindow", "IsIconic", "IsWindowVisible", "SetForegroundWindow", "GetWindowTextLengthW"):
            getattr(u, name).argtypes = [W.HWND]
        u.GetWindowTextW.argtypes = [W.HWND, ctypes.c_wchar_p, ctypes.c_int]
        u.GetWindowThreadProcessId.argtypes = [W.HWND, ctypes.POINTER(W.DWORD)]
        g.CreateCompatibleDC.argtypes, g.CreateCompatibleDC.restype = [vp], vp
        g.CreateCompatibleBitmap.argtypes, g.CreateCompatibleBitmap.restype = [vp, ctypes.c_int, ctypes.c_int], vp
        g.SelectObject.argtypes, g.SelectObject.restype = [vp, vp], vp
        g.DeleteObject.argtypes = [vp]
        g.DeleteDC.argtypes = [vp]
        g.GetDIBits.argtypes = [vp, vp, ctypes.c_uint, ctypes.c_uint, vp, vp, ctypes.c_uint]
        _API.extend([u, g])
    return _API


def window_text(hwnd):
    if sys.platform != "win32":
        return ""
    u, _ = _api()
    n = u.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    u.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def find_window_at(x, y):
    """Topmost visible, titled window (not ours) that contains the point: (hwnd, title) or None."""
    if sys.platform != "win32":
        return None
    u, _ = _api()
    W, pid, found = ctypes.wintypes, os.getpid(), []
    proc_t = ctypes.WINFUNCTYPE(ctypes.c_bool, W.HWND, W.LPARAM)

    def cb(hwnd, _):
        if not u.IsWindowVisible(hwnd) or u.IsIconic(hwnd):
            return True
        owner = W.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid:
            return True
        try:  # skip cloaked (hidden UWP / other virtual desktop) windows
            cloaked = ctypes.c_int(0)
            dw = ctypes.windll.dwmapi.DwmGetWindowAttribute
            dw.argtypes = [W.HWND, W.DWORD, ctypes.c_void_p, W.DWORD]
            dw(hwnd, 14, ctypes.byref(cloaked), 4)
            if cloaked.value:
                return True
        except Exception:
            pass
        r = W.RECT()
        u.GetWindowRect(hwnd, ctypes.byref(r))
        if r.left <= x < r.right and r.top <= y < r.bottom:
            title = window_text(hwnd)
            if title:
                found.append((hwnd, title))
                return False
        return True

    u.EnumWindows(proc_t(cb), 0)
    return found[0] if found else None


def window_title_at(x, y):
    hit = find_window_at(x, y)
    return hit[1] if hit else None


def window_client_rect(hwnd):
    """Client area (the content, without title bar and borders) in screen coordinates."""
    if sys.platform != "win32":
        return None
    u, _ = _api()
    W = ctypes.wintypes
    cr, pt = W.RECT(), W.POINT(0, 0)
    if not u.GetClientRect(hwnd, ctypes.byref(cr)):
        return None
    u.ClientToScreen(hwnd, ctypes.byref(pt))
    return dict(left=pt.x, top=pt.y, width=cr.right, height=cr.bottom)


class BitmapInfoHeader(ctypes.Structure):
    _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32), ("biHeight", ctypes.c_int32),
                ("biPlanes", ctypes.c_uint16), ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
                ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
                ("biClrImportant", ctypes.c_uint32)]


def grab_window(hwnd):
    """Pixels of the window content, even if other windows cover it (PrintWindow). None on failure."""
    if sys.platform != "win32":
        return None
    u, g = _api()
    W = ctypes.wintypes
    wr, cr, pt = W.RECT(), W.RECT(), W.POINT(0, 0)
    if not (u.GetWindowRect(hwnd, ctypes.byref(wr)) and u.GetClientRect(hwnd, ctypes.byref(cr))):
        return None
    u.ClientToScreen(hwnd, ctypes.byref(pt))
    w, h = wr.right - wr.left, wr.bottom - wr.top
    if w <= 0 or h <= 0 or cr.right <= 0 or cr.bottom <= 0:
        return None
    hdc = u.GetWindowDC(hwnd)
    mem = g.CreateCompatibleDC(hdc)
    bmp = g.CreateCompatibleBitmap(hdc, w, h)
    old = g.SelectObject(mem, bmp)
    try:
        if not u.PrintWindow(hwnd, mem, 2):  # PW_RENDERFULLCONTENT
            return None
        bi = BitmapInfoHeader(ctypes.sizeof(BitmapInfoHeader), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(w * h * 4)
        if not g.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bi), 0):
            return None
    finally:
        g.SelectObject(mem, old)
        g.DeleteObject(bmp)
        g.DeleteDC(mem)
        u.ReleaseDC(hwnd, hdc)
    arr = np.frombuffer(buf, np.uint8).reshape(h, w, 4)[:, :, [2, 1, 0]]
    x0, y0 = pt.x - wr.left, pt.y - wr.top
    return np.ascontiguousarray(arr[y0:y0 + cr.bottom, x0:x0 + cr.right])


def select_window(root, hint):
    """Overlay across all monitors: the window under the cursor is outlined, a click picks it.
    Returns {"hwnd", "title"} or None."""
    result = {}
    vx, vy, vw, vh = virtual_screen(root)
    win = tk.Toplevel(root)
    win.overrideredirect(True)
    win.attributes("-alpha", 0.35, "-topmost", True)
    win.geometry(f"{vw}x{vh}{vx:+d}{vy:+d}")
    win.configure(bg=BLACK, cursor="hand2")
    canvas = tk.Canvas(win, bg=BLACK, highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    win.update_idletasks()
    L, T, R, B = monitor_bounds(win, root.winfo_rootx() + 10, root.winfo_rooty() + 10)
    canvas.create_text((L + R) // 2 - vx, T - vy + U(48), fill=LIGHT, font=F(20, True), text=hint)
    state = {"hwnd": None, "items": []}

    def hover(e):
        hit = find_window_at(e.x_root, e.y_root)
        hwnd = hit[0] if hit else None
        if hwnd == state["hwnd"]:
            return
        state["hwnd"] = hwnd
        for i in state["items"]:
            canvas.delete(i)
        state["items"] = []
        r = window_client_rect(hwnd) if hwnd else None
        if r:
            x1, y1 = r["left"] - vx, r["top"] - vy
            state["items"].append(canvas.create_rectangle(x1, y1, x1 + r["width"], y1 + r["height"],
                                                          outline=LIGHT, width=3))
            state["items"].append(canvas.create_text(x1 + U(12), y1 + U(12), anchor="nw", fill=LIGHT,
                                                     font=F(15, True), text=hit[1][:60]))

    def click(e):
        hit = find_window_at(e.x_root, e.y_root)
        if hit:
            result.update(hwnd=hit[0], title=hit[1])
        win.destroy()

    canvas.bind("<Motion>", hover)
    canvas.bind("<ButtonPress-1>", click)
    canvas.bind("<Button-3>", lambda e: win.destroy())
    win.bind("<Escape>", lambda e: win.destroy())
    win.focus_force()
    root.wait_window(win)
    return result or None


class RegionTarget:
    """What to capture: a fixed rectangle of the screen."""
    is_window = False

    def __init__(self, region):
        self.region = region

    def rect(self):
        return self.region

    def grab(self):
        return grab(self.region)

    def center(self):
        r = self.region
        return r["left"] + r["width"] // 2, r["top"] + r["height"] // 2

    def check(self):
        pass

    def focus(self):
        pass


class WindowTarget:
    """What to capture: the content of one window, whatever is on top of it (even on another monitor)."""
    is_window = True

    def __init__(self, hwnd):
        self.hwnd = hwnd

    def rect(self):
        return window_client_rect(self.hwnd)

    def grab(self):
        return grab_window(self.hwnd)

    def center(self):
        r = self.rect()
        return r["left"] + r["width"] // 2, r["top"] + r["height"] // 2

    def check(self):
        u, _ = _api()
        if not u.IsWindow(self.hwnd):
            raise RuntimeError(t("win_gone"))
        if u.IsIconic(self.hwnd):
            raise RuntimeError(t("win_min"))
        frame = self.grab()
        if frame is None:
            raise RuntimeError(t("win_gone"))
        if frame.max() < 5:
            raise RuntimeError(t("win_black"))

    def focus(self):
        try:
            _api()[0].SetForegroundWindow(self.hwnd)
        except Exception:
            pass


def book_name(title):
    """Turn a window title or OCR text into a safe file name; None if it is just the app name."""
    if not title:
        return None
    s = re.sub(r"\s*[-–—|]\s*(Amazon\s*)?Kindle(\s*for\s*PC)?\s*$", "", title, flags=re.I)
    s = re.sub(r"^\s*(Amazon\s*)?Kindle(\s*for\s*PC)?\s*[-–—|:]\s*", "", s, flags=re.I)
    s = re.sub(r'[\\/:*?"<>|]+', " ", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    if not s or s.lower() in ("kindle", "amazon kindle", "kindle for pc"):
        return None
    return s[:120]


def _tesseract():
    try:
        import pytesseract
    except ImportError:
        raise RuntimeError(t("ocr_pkg"))
    for p in (r"C:\Program Files\Tesseract-OCR\tesseract.exe", r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"):
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            break
    return pytesseract


def ocr_title(region):
    pytesseract = _tesseract()
    img = Image.fromarray(grab(region)).convert("L")
    img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
    if np.mean(np.array(img)) < 128:  # light text on dark background
        img = ImageOps.invert(img)
    try:
        text = pytesseract.image_to_string(img, config="--psm 7")
    except pytesseract.TesseractNotFoundError:
        raise RuntimeError(t("ocr_tess"))
    return " ".join(text.split())


def title_from_page(img):
    """Best guess of the book title on the first page (cover): the tallest line of text in its upper part,
    joined with neighbouring lines of similar size. None if nothing readable."""
    try:
        pt = _tesseract()
        from pytesseract import Output
    except RuntimeError:
        return None
    gray = Image.fromarray(img).convert("L")
    if max(gray.size) > 1600:  # keep the OCR fast
        k = 1600 / max(gray.size)
        gray = gray.resize((int(gray.width * k), int(gray.height * k)), Image.LANCZOS)
    if np.mean(np.array(gray)) < 110:  # light text on a dark cover
        gray = ImageOps.invert(gray)
    try:
        d = pt.image_to_data(gray, output_type=Output.DICT)
    except Exception:
        return None
    lines = {}
    for i, word in enumerate(d["text"]):
        word = word.strip()
        try:
            conf = float(d["conf"][i])
        except (ValueError, TypeError):
            continue
        if word and conf >= 50:
            key = (d["block_num"][i], d["par_num"][i], d["line_num"][i])
            lines.setdefault(key, []).append((d["left"][i], word, d["height"][i], d["top"][i]))
    cand = []
    for ws in lines.values():
        ws.sort()
        text = " ".join(w for _, w, _, _ in ws)
        top = min(x[3] for x in ws)
        if sum(c.isalpha() for c in text) >= 3 and top <= gray.height * 0.7:
            cand.append((top, float(np.median([x[2] for x in ws])), text))
    if not cand:
        return None
    cand.sort()
    best = max(cand, key=lambda c: c[1])
    lo = hi = cand.index(best)
    while lo > 0 and hi - lo < 3 and cand[lo - 1][1] >= 0.75 * best[1] and cand[lo][0] - cand[lo - 1][0] <= 2.5 * best[1]:
        lo -= 1
    while hi < len(cand) - 1 and hi - lo < 3 and cand[hi + 1][1] >= 0.75 * best[1] \
            and cand[hi + 1][0] - cand[hi][0] <= 2.5 * best[1]:
        hi += 1
    return book_name(" ".join(c[2] for c in cand[lo:hi + 1]))


def latest_project(root):
    """Name of the most recently written project folder (one that holds page images) under root."""
    best, best_t = None, -1.0
    if os.path.isdir(root):
        for d in os.listdir(root):
            pages = list_pages(os.path.join(root, d))
            if pages:
                mt = max(os.path.getmtime(p) for _, p in pages)
                if mt > best_t:
                    best, best_t = d, mt
    return best


def unique_project(temp_root, out_root, name):
    """A project name that does not collide with an existing project (never overwrites another book)."""
    cand, i = name, 2
    while os.path.exists(os.path.join(temp_root, cand)) or os.path.exists(os.path.join(out_root, cand)):
        cand = f"{name} ({i})"
        i += 1
    return cand


# ---------- global hotkeys (work even when another window has the focus) ----------
class Hotkeys(threading.Thread):
    """F9 / ESC through RegisterHotKey, handled by Windows itself (no keyboard hook needed)."""

    def __init__(self, on_f9, on_esc):
        super().__init__(daemon=True)
        self.on_f9, self.on_esc = on_f9, on_esc
        self.ready = threading.Event()
        self.registered = False
        self.tid = None

    def run(self):
        if sys.platform != "win32":
            self.ready.set()
            return
        u = ctypes.windll.user32
        self.tid = ctypes.windll.kernel32.GetCurrentThreadId()
        ok1 = u.RegisterHotKey(None, 1, 0x4000, 0x78)  # F9, MOD_NOREPEAT
        ok2 = u.RegisterHotKey(None, 2, 0x4000, 0x1B)  # ESC
        self.registered = bool(ok1 and ok2)
        self.ready.set()
        msg = ctypes.wintypes.MSG()
        while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == 0x0312:  # WM_HOTKEY
                (self.on_f9 if msg.wParam == 1 else self.on_esc)()
        u.UnregisterHotKey(None, 1)
        u.UnregisterHotKey(None, 2)

    def stop(self):
        if self.tid and sys.platform == "win32":
            ctypes.windll.user32.PostThreadMessageW(self.tid, 0x0012, 0, 0)  # WM_QUIT


# ---------- floating windows: non-activating and hidden from the screenshots ----------
class Panel(tk.Toplevel):
    """The capture window: preview, progress, controls and (expandable) live log, all in one window."""
    COLORS = {"info": LIGHT, "warn": "#D9A6D6", "err": "#FF9AA8"}

    def __init__(self, app, region):
        super().__init__(app.root)
        self.app = app
        self.title(t("panel_title"))
        self.attributes("-topmost", True)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", app.request_stop)
        self.W, self.H0, self.H1 = U(440), U(232), U(424)  # collapsed / with the log open
        W = self.W
        self.show_log = app.log_visible
        H = self.H1 if self.show_log else self.H0
        self.c = c = tk.Canvas(self, width=W, height=H, highlightthickness=0, bd=0, bg=BLACK)
        c.pack()
        self.bg_item = c.create_image(0, 0, anchor="nw")
        self._draw_bg(H)

        # live preview of the page being captured
        round_rect(c, U(20), U(20), U(170), U(192), U(10), fill=INPUT_BG, outline=LINE)
        self.thumb = None
        self.thumb_item = c.create_image(U(95), U(106), anchor="center")
        self.caption = c.create_text(U(95), U(208), text="", fill=MUTED, font=F(11))

        x0, cw = U(190), U(230)
        self.text = c.create_text(x0, U(20), anchor="nw", width=cw, text="", fill=LIGHT, font=F(12))
        self.bar_y, self.bar_h, self.x0, self.cw = U(92), U(8), x0, cw
        round_rect(c, x0, self.bar_y, x0 + cw, self.bar_y + self.bar_h, U(4), fill=INPUT_BG, outline=LINE)
        self.fill = c.create_polygon(rr_points(x0, self.bar_y, x0 + 2, self.bar_y + self.bar_h, 1),
                                     smooth=True, fill=PURPLE, outline="")
        self.count = c.create_text(x0 + cw, U(112), anchor="e", text="", fill=MUTED, font=F(11))
        self.pause_btn = Btn(c, x0, U(130), U(112), U(38), t("pause"), app.toggle_pause, size=12)
        Btn(c, x0 + U(118), U(130), U(112), U(38), t("stop"), app.request_stop, size=12)
        self.log_btn = Btn(c, x0, U(178), cw, U(36), t("hide_log") if self.show_log else t("show_log"),
                           app.toggle_log, size=12)

        # live log, inside this same window
        self.log_text = tk.Text(c, bg=INPUT_BG, fg=LIGHT, insertbackground=LIGHT, relief="flat", bd=U(6),
                                highlightthickness=1, highlightbackground=LINE, highlightcolor=LINE,
                                font=("Consolas", -U(12)), wrap="word", state="disabled",
                                selectbackground=PURPLE, selectforeground=LIGHT)
        for lvl, col in self.COLORS.items():
            self.log_text.tag_config(lvl, foreground=col)
        self.log_item = c.create_window(U(20), U(236), window=self.log_text, anchor="nw",
                                        width=W - U(40), height=U(170),
                                        state="normal" if self.show_log else "hidden")
        for line, lvl in app.log_buf:
            self._insert(line, lvl)

        self.update_idletasks()
        no_activate(self)
        self.hidden = hide_from_capture(self)
        self.rect = place_outside(self, W, H, region)

    def _draw_bg(self, H):
        self.bg = bg_image(self.W, H, [(U(6), U(6), self.W - U(6), H - U(6))])
        self.c.itemconfig(self.bg_item, image=self.bg)
        self.c.tag_lower(self.bg_item)

    def set_log(self, show):
        """Open / close the log area; the window grows or shrinks and stays on screen."""
        if show == self.show_log:
            return
        self.show_log = show
        H = self.H1 if show else self.H0
        self.c.config(height=H)
        self._draw_bg(H)
        self.c.itemconfig(self.log_item, state="normal" if show else "hidden")
        x, y = self.winfo_x(), self.winfo_y()
        L, T, R, B = monitor_bounds(self, x + self.W // 2, y + H // 2)
        if y + H > B:
            y = max(T, B - H - U(10))
        self.geometry(f"{self.W}x{H}+{x}+{y}")
        self.rect = (x, y, self.W, H)
        self.log_btn.set_text(t("hide_log") if show else t("show_log"))

    def _insert(self, line, level):
        self.log_text.config(state="normal")
        self.log_text.insert("end", line + "\n", level)
        self.log_text.config(state="disabled")
        self.log_text.see("end")

    def append(self, line, level):
        self._insert(line, level)

    def clear(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    def set_text(self, s):
        self.c.itemconfig(self.text, text=s)

    def set_preview(self, im, caption=None):
        self.thumb = ImageTk.PhotoImage(im)
        self.c.itemconfig(self.thumb_item, image=self.thumb)
        if caption is not None:
            self.c.itemconfig(self.caption, text=caption)

    def set_progress(self, done, total):
        frac = min(1.0, done / total) if total else 0
        fx = self.x0 + max(U(8), frac * self.cw)
        self.c.coords(self.fill, *rr_points(self.x0, self.bar_y, fx, self.bar_y + self.bar_h, U(4)))
        self.c.itemconfig(self.count, text=f"{done} / {total}" if total else str(done))


class LogWindow(tk.Toplevel):
    COLORS = {"info": LIGHT, "warn": "#D9A6D6", "err": "#FF9AA8"}

    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.title(t("log_title"))
        self.attributes("-topmost", True)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", app.toggle_log)
        self.W, self.H = U(500), U(320)
        W, H = self.W, self.H
        c = tk.Canvas(self, width=W, height=H, highlightthickness=0, bd=0, bg=BLACK)
        c.pack()
        self.bg = bg_image(W, H, [(U(6), U(6), W - U(6), H - U(6))])
        c.create_image(0, 0, image=self.bg, anchor="nw")
        c.create_text(U(20), U(24), anchor="w", text=t("log_title"), fill=LIGHT, font=F(15, semibold=True))
        self.text = tk.Text(c, bg=INPUT_BG, fg=LIGHT, insertbackground=LIGHT, relief="flat", bd=U(6),
                            highlightthickness=1, highlightbackground=LINE, highlightcolor=LINE,
                            font=("Consolas", -U(12)), wrap="word", state="disabled",
                            selectbackground=PURPLE, selectforeground=LIGHT)
        for lvl, col in self.COLORS.items():
            self.text.tag_config(lvl, foreground=col)
        c.create_window(U(18), U(44), window=self.text, anchor="nw", width=W - U(36), height=H - U(44) - U(62))
        Btn(c, W - U(18) - U(90), H - U(50), U(90), U(32), t("close"), app.toggle_log, size=12)
        Btn(c, W - U(18) - U(190), H - U(50), U(90), U(32), t("export"), app.export_log, size=12)
        Btn(c, W - U(18) - U(290), H - U(50), U(90), U(32), t("clear"), app.clear_log, size=12)
        for line, lvl in app.log_buf:
            self._insert(line, lvl)
        self.update_idletasks()
        no_activate(self)
        self.hidden = hide_from_capture(self)

    def place(self, region, avoid=(), near=None):
        place_outside(self, self.W, self.H, region, avoid, near)

    def _insert(self, line, level):
        self.text.config(state="normal")
        self.text.insert("end", line + "\n", level)
        self.text.config(state="disabled")
        self.text.see("end")

    def append(self, line, level):
        self._insert(line, level)

    def clear(self):
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.config(state="disabled")


# ---------- main app ----------
class App:
    LW, LH = 560, 996  # logical window size

    def __init__(self, root):
        self.root = root
        self.settings = load_settings()
        LANG[0] = self.settings.get("lang", "en") if self.settings.get("lang") in ("en", "pt") else "en"
        sh = root.winfo_screenheight()
        SCALE[0] = max(0.8, min(root.winfo_fpixels("1i") / 96, (sh - 90) / self.LH))
        W, H = U(self.LW), U(self.LH)
        root.title(f"Page Capture {VERSION}")
        root.resizable(False, False)
        root.configure(bg=BLACK)
        self.restore_position(W, H)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.region = None
        self.window = None
        self.target = None
        self.panel = None
        self.log_win = None
        self.log_visible = True  # the log opens automatically; the button hides / shows it
        self.log_buf = []
        self.session_lines = []  # lines of the current capture session (saved to log.txt)
        self.hk = None
        self.hk_ok = False
        self.running = False
        self.status_msg = t("status_idle")
        self.stop = threading.Event()
        self.paused = threading.Event()
        self.vars = {
            "temp": tk.StringVar(value=os.path.join(root_dir(), "temp_captures")),
            "out": tk.StringVar(value=os.path.join(root_dir(), "exports")),
            "name": tk.StringVar(value=""),
            "start": tk.StringVar(value="1"),
            "pages": tk.StringVar(value="50"),
            "delay": tk.StringVar(value="1.0"),
            "key": tk.StringVar(value="right"),
            "source": tk.StringVar(value="region"),
            "mode": tk.StringVar(value="simple"),
            "scroll": tk.StringVar(value="300"),
            "steps": tk.StringVar(value="15"),
            "thresh": tk.DoubleVar(value=0.90),
            "compress": tk.StringVar(value="off"),
            "pdf": tk.BooleanVar(value=True),
            "end": tk.BooleanVar(value=True),
            "gap": tk.BooleanVar(value=True),
            "clean": tk.BooleanVar(value=False),
            "lang": tk.StringVar(value=LANG[0]),
        }
        self.name_auto = False  # True while the name box holds a name the app detected (not typed)
        self._setting_name = False
        self.vars["name"].trace_add("write", self._name_edited)
        self.c = None
        self.build_ui()
        keyboard.Listener(on_press=self.on_key).start()  # fallback when RegisterHotKey is unavailable
        self.root.after(300, self.apply_log)

    # --- window position (remembers the monitor) ---
    def restore_position(self, W, H):
        s = self.settings
        vx, vy, vw, vh = virtual_screen(self.root)
        if "win_x" in s and "win_y" in s:
            x, y = int(s["win_x"]), int(s["win_y"])
            cx, cy = x + W // 2, y + H // 2
            if vx <= cx < vx + vw and vy <= cy < vy + vh:  # that monitor is still connected
                self.root.geometry(f"{W}x{H}{x:+d}{y:+d}")
                return
        center(self.root, W, H)

    def save_state(self):
        data = dict(self.settings)
        data["lang"] = LANG[0]
        try:
            data["win_x"], data["win_y"] = self.root.winfo_x(), self.root.winfo_y()
        except tk.TclError:
            pass
        self.settings = data
        save_settings(data)

    def on_close(self):
        self.save_state()
        self.stop.set()
        if self.hk:
            self.hk.stop()
        self.root.destroy()

    # --- UI construction (rebuilt when the language changes) ---
    def build_ui(self):
        v = self.vars
        W, H = U(self.LW), U(self.LH)
        cards = [(20, 92, 540, 246), (20, 260, 540, 606), (20, 620, 540, 818), (20, 892, 540, 960)]
        self.c = c = tk.Canvas(self.root, width=W, height=H, highlightthickness=0, bd=0, bg=BLACK)
        c.pack()
        self.bg = bg_image(W, H, [tuple(U(n) for n in card) for card in cards])
        c.create_image(0, 0, image=self.bg, anchor="nw")

        # header
        c.create_text(U(28), U(36), anchor="w", text="Page Capture", fill=LIGHT, font=F(30, semibold=True))
        c.create_text(U(30), U(68), anchor="w", text=t("subtitle"), fill=MUTED, font=F(13))
        Segmented(c, U(436), U(16), U(104), U(28), [("EN", "en"), ("PT", "pt")], v["lang"],
                  self.change_lang, size=12)
        c.create_text(U(540), U(60), anchor="e", text=t("hint_keys"), fill=MUTED, font=F(12))
        c.create_text(U(540), U(78), anchor="e", text=f"v{VERSION}", fill=DIM, font=F(11))

        # folders card
        self.section(t("folders"), 36, 106)
        self.field(t("temp_images"), "temp", 36, 150, 126, 320)
        Btn(c, U(478), U(126), U(38), U(30), "…", lambda: self.pick_dir("temp"), size=15)
        self.field(t("pdf_folder"), "out", 36, 150, 164, 320)
        Btn(c, U(478), U(164), U(38), U(30), "…", lambda: self.pick_dir("out"), size=15)
        _, name_entry = self.field(t("doc_name"), "name", 36, 150, 202, 170)
        name_entry.bind("<FocusIn>", lambda ev: self.c.itemconfig(self.status_item, text=t("name_hint")))
        name_entry.bind("<FocusOut>", lambda ev: self.c.itemconfig(self.status_item, text=self.status_msg))
        Btn(c, U(328), U(202), U(104), U(30), t("from_window"), self.name_from_window, size=11)
        Btn(c, U(440), U(202), U(76), U(30), t("ocr_title"), self.name_from_ocr, size=11)

        # capture card
        self.section(t("capture"), 36, 274)
        self.log_btn = Btn(c, U(416), U(262), U(100), U(26),
                           t("hide_log") if self.log_visible else t("show_log"), self.toggle_log, size=11)
        c.create_text(U(36), U(311), anchor="w", text=t("source"), fill=LIGHT, font=F(13))
        Segmented(c, U(150), U(294), U(240), U(34), [(t("src_region"), "region"), (t("src_window"), "window")],
                  v["source"], self.update_source, size=12)
        c.create_text(U(36), U(351), anchor="w", text=t("mode"), fill=LIGHT, font=F(13))
        Segmented(c, U(150), U(334), U(210), U(34), [(t("simple"), "simple"), (t("scroll"), "scroll")],
                  v["mode"], self.update_mode)
        self.field(t("start_page"), "start", 36, 150, 380, 80)
        self.field(t("pages"), "pages", 262, 436, 380, 80)
        self.field(t("delay"), "delay", 36, 150, 420, 80)
        self.field(t("key"), "key", 262, 436, 420, 80)
        self.scroll_fields = [
            self.field(t("scroll_step"), "scroll", 36, 150, 460, 80),
            self.field(t("max_steps"), "steps", 262, 436, 460, 80),
        ]
        self.thresh_label = c.create_text(U(36), U(514), anchor="w", text=t("threshold"), fill=LIGHT, font=F(13))
        self.thresh_slider = Slider(c, U(150), U(514), U(240), 0.50, 0.99, v["thresh"], 0.01,
                                    describe=self.describe_thresh)
        self.thresh_note = c.create_text(U(36), U(538), anchor="nw", width=U(488), text=t("explain"),
                                         fill=MUTED, font=F(11))

        # options card
        self.section(t("options"), 36, 634)
        c.create_text(U(36), U(670), anchor="w", text=t("compression"), fill=LIGHT, font=F(13))
        Segmented(c, U(150), U(654), U(370), U(32),
                  [(t("comp_off"), "off"), (t("comp_light"), "light"), (t("comp_balanced"), "balanced"),
                   (t("comp_strong"), "strong")], v["compress"], size=12)
        Check(c, U(36), U(700), t("opt_pdf"), v["pdf"])
        Check(c, U(36), U(728), t("opt_end"), v["end"])
        Check(c, U(36), U(756), t("opt_gap"), v["gap"])
        Check(c, U(36), U(784), t("opt_clean"), v["clean"])

        # actions
        self.region_btn = Btn(c, U(20), U(834), U(170), U(46), self.target_btn_text(), self.pick_target)
        Btn(c, U(200), U(834), U(170), U(46), t("make_pdf"), self.pdf_now)
        self.start_btn = Btn(c, U(380), U(834), U(160), U(46), t("start"), self.start, kind="primary", size=14)
        self.start_btn.set_enabled(self.target_ready(), "primary")  # needs a region / window first

        # status + signature
        self.status_item = c.create_text(U(36), U(906), anchor="nw", width=U(488), fill=LIGHT, font=F(13),
                                         text=self.status_msg)
        c.create_text(W // 2, U(978), text=f"{AUTHOR}  ·  {SUITE}", fill=MUTED, font=F(12, True))
        self.update_mode()

    def _name_edited(self, *_):
        if not self._setting_name:
            self.name_auto = False

    def set_name(self, name, auto):
        self._setting_name = True
        self.vars["name"].set(name)
        self._setting_name = False
        self.name_auto = auto

    def change_lang(self):
        LANG[0] = self.vars["lang"].get()
        self.save_state()
        self.root.after_idle(self.rebuild)

    def rebuild(self):
        self.c.destroy()
        self.status_msg = t("status_idle") if not self.running and self.status_msg in (
            TXT["status_idle"][0], TXT["status_idle"][1]) else self.status_msg
        self.build_ui()
        if self.log_win:  # reopen the log in the new language
            self.log_win.destroy()
            self.log_win = None
            self.apply_log()

    # --- layout helpers ---
    def describe_thresh(self, val):
        return t("strict") if val >= 0.95 else t("balanced") if val >= 0.85 else t("flexible")

    def section(self, text, x, y):
        self.c.create_text(U(x), U(y), anchor="w", text=text, fill=MUTED, font=F(11, True))

    def field(self, label, key, lx, ex, y, w):
        lab = self.c.create_text(U(lx), U(y + 15), anchor="w", text=label, fill=LIGHT, font=F(13))
        e = tk.Entry(self.c, textvariable=self.vars[key], bg=INPUT_BG, fg=LIGHT, insertbackground=LIGHT,
                     relief="flat", bd=U(6), highlightthickness=1, highlightbackground=LINE,
                     highlightcolor=PURPLE_LT, font=F(13), selectbackground=PURPLE, selectforeground=LIGHT,
                     disabledbackground=INPUT_BG, disabledforeground=DIM)
        self.c.create_window(U(ex), U(y), window=e, anchor="nw", width=U(w), height=U(30))
        return lab, e

    def update_mode(self):
        on = self.vars["mode"].get() == "scroll"
        for lab, e in self.scroll_fields:
            e.config(state="normal" if on else "disabled")
            self.c.itemconfig(lab, fill=LIGHT if on else DIM)
        self.c.itemconfig(self.thresh_label, fill=LIGHT if on else DIM)
        self.c.itemconfig(self.thresh_note, fill=MUTED if on else DIM)
        self.thresh_slider.set_enabled(on)

    # --- helpers ---
    def ui(self, fn, *a):
        self.root.after(0, fn, *a)

    def set_status(self, msg):
        def _set():
            self.status_msg = msg
            self.c.itemconfig(self.status_item, text=msg)
            if self.panel:
                self.panel.set_text(msg)
        self.ui(_set)

    def log(self, msg, level="info"):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"

        def _add():
            self.log_buf.append((line, level))
            self.session_lines.append(line)
            del self.log_buf[:-2000]
            for sink in (self.log_win, self.panel):
                if sink:
                    sink.append(line, level)
        self.ui(_add)

    def export_log(self):
        """Save everything in the log window to a .txt file of your choice."""
        path = filedialog.asksaveasfilename(
            parent=self.root, title=t("log_export_title"), defaultextension=".txt",
            initialdir=self.vars["out"].get() if os.path.isdir(self.vars["out"].get()) else None,
            initialfile="page-capture-log.txt", filetypes=[("Text", "*.txt")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(line for line, _ in self.log_buf) + "\n")
            self.log(t("log_file_saved", path=path))
        except OSError as e:
            self.log(t("log_error", e=e), "err")

    def save_session_log(self, cfg):
        """Append this session's log to log.txt inside the project's export folder. Returns the path or None."""
        if not self.session_lines:
            return None
        if cfg.get("pending_name"):  # nothing was captured, so there is no project folder
            folder, fname = cfg["out_root"], f"log {time.strftime('%Y-%m-%d %H.%M.%S')}.txt"
        else:
            folder, fname = cfg["out"], "log.txt"
        try:
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, fname)
            head = f"=== Page Capture {VERSION} · {cfg['name']} · {time.strftime('%Y-%m-%d %H:%M:%S')} ==="
            with open(path, "a", encoding="utf-8") as f:
                f.write(head + "\n" + "\n".join(self.session_lines) + "\n\n")
            return path
        except OSError:
            return None

    def clear_log(self):
        self.log_buf.clear()
        for sink in (self.log_win, self.panel):
            if sink:
                sink.clear()

    def preview(self, img, caption=None):
        """Send a thumbnail of the frame being captured to the control panel."""
        im = Image.fromarray(img)
        im.thumbnail((U(142), U(164)), Image.BILINEAR)
        self.ui(lambda: self.panel.set_preview(im, caption) if self.panel else None)

    def main_rect(self):
        r = self.root
        if r.state() != "normal":
            return None
        return (r.winfo_rootx(), r.winfo_rooty(), r.winfo_width(), r.winfo_height())

    # --- capture target: screen region or window ---
    def target_ready(self):
        if self.vars["source"].get() == "window":
            return bool(self.window)
        return bool(self.region)

    def target_btn_text(self):
        if self.vars["source"].get() == "window":
            if self.window:
                name = self.window["title"]
                return t("window_btn", t=name if len(name) <= 14 else name[:13] + "…")
            return t("select_window")
        if self.region:
            return t("region_btn", w=self.region["width"], h=self.region["height"])
        return t("select_region")

    def update_source(self):
        self.region_btn.set_text(self.target_btn_text())
        self.start_btn.set_enabled(self.target_ready(), "primary")

    def target_rect(self):
        """Screen rect of what is being captured (the control windows keep away from it)."""
        if self.vars["source"].get() == "window" and self.window:
            return window_client_rect(self.window["hwnd"]) or self.region
        return self.region

    def make_target(self):
        if self.vars["source"].get() == "window":
            return WindowTarget(self.window["hwnd"])
        return RegionTarget(self.region)

    def pick_target(self):
        if self.vars["source"].get() == "window":
            self.pick_window()
        else:
            self.pick_region()

    def pick_window(self):
        self.root.withdraw()
        time.sleep(0.3)
        res = select_window(self.root, t("overlay_window"))
        self.root.deiconify()
        if res:
            self.window = res
            self.update_source()
            self.log(t("log_window", title=res["title"]))
            self.status_msg = t("window_status", title=res["title"])
            self.c.itemconfig(self.status_item, text=self.status_msg)

    def refresh_log_buttons(self):
        txt = t("hide_log") if self.log_visible else t("show_log")
        self.log_btn.set_text(txt)
        if self.panel:
            self.panel.log_btn.set_text(txt)

    def apply_log(self):
        """One log, shown where it gets in nobody's way: inside the capture window while capturing,
        beside the main window otherwise."""
        if self.running and self.panel:
            if self.log_win:
                self.log_win.destroy()
                self.log_win = None
            self.panel.set_log(self.log_visible)
        elif self.log_visible and not self.log_win:
            try:
                self.log_win = LogWindow(self)
            except Exception as e:
                self.log_visible = False
                self.set_status(t("log_open_fail", e=e))
            else:
                main = self.main_rect()
                self.log_win.place(None, [main] if main else [], near=main)
        elif not self.log_visible and self.log_win:
            self.log_win.destroy()
            self.log_win = None
        self.refresh_log_buttons()

    def toggle_log(self):
        self.log_visible = not self.log_visible
        self.apply_log()

    def alert(self, title, msg):
        dialog(self.root, title, msg, [("OK", "primary")])

    def on_key(self, k):  # fallback, only used when RegisterHotKey is unavailable
        if not self.running or self.hk_ok:
            return
        if k == keyboard.Key.esc:
            self.request_stop()
        elif k == keyboard.Key.f9:
            self.ui(self.toggle_pause)

    def request_stop(self):
        if self.running and not self.stop.is_set():
            self.log(t("log_stop"))
        self.stop.set()

    def toggle_pause(self):
        if not self.running:
            return
        if self.paused.is_set():
            self.paused.clear()
            self.log(t("log_resumed"))
            if self.panel:
                self.panel.pause_btn.set_text(t("pause"))
        else:
            self.paused.set()
            self.log(t("log_paused"))
            if self.panel:
                self.panel.pause_btn.set_text(t("resume"))

    def pick_dir(self, key):
        d = filedialog.askdirectory()
        if d:
            self.vars[key].set(os.path.normpath(d))

    def pick_region(self):
        self.root.withdraw()
        time.sleep(0.3)
        reg = select_region(self.root, t("overlay_region"))
        self.root.deiconify()
        if reg:
            self.region = reg
            self.update_source()
            self.log(t("log_region", w=reg["width"], h=reg["height"], x=reg["left"], y=reg["top"]))
            self.status_msg = t("region_status", x=reg["left"], y=reg["top"])
            self.c.itemconfig(self.status_item, text=self.status_msg)

    def region_center(self):
        r = self.region
        return r["left"] + r["width"] // 2, r["top"] + r["height"] // 2

    def auto_name(self):
        """Book name from the title of the window behind the capture region (None if unknown)."""
        if self.vars["source"].get() == "window" and self.window:
            return book_name(window_text(self.window["hwnd"]))
        if not self.region:
            return None
        return book_name(window_title_at(*self.region_center()))

    def name_from_window(self):
        if self.vars["source"].get() == "window" and self.window:
            title = window_text(self.window["hwnd"])
        elif not self.region:
            self.alert(t("d_region_t"), t("d_region"))
            return
        else:
            title = window_title_at(*self.region_center())
        name = book_name(title)
        if name:
            self.set_name(name, False)
            self.log(t("log_name_win", name=name))
        else:
            self.alert(t("d_notitle_t"), t("d_notitle", title=title or t("empty")))

    def name_from_ocr(self):
        self.root.withdraw()
        time.sleep(0.3)
        reg = select_region(self.root, t("overlay_title"))
        self.root.deiconify()
        if not reg:
            return
        try:
            name = book_name(ocr_title(reg))
        except RuntimeError as e:
            self.alert(t("d_ocr_t"), str(e))
            return
        if name:
            self.set_name(name, False)
            self.log(t("log_name_ocr", name=name))
        else:
            self.alert(t("d_nothing_t"), t("d_nothing"))

    def parse(self):
        v = {k: x.get() for k, x in self.vars.items()}
        try:
            cfg = dict(
                temp_root=v["temp"], out_root=v["out"], name=book_name(v["name"]) or "",
                start=int(v["start"]), pages=int(v["pages"]),
                delay=float(v["delay"].replace(",", ".")), key=v["key"].strip() or "right", mode=v["mode"],
                scroll=int(v["scroll"]), steps=int(v["steps"]), thresh=float(v["thresh"]),
                pdf=v["pdf"], end=v["end"], gap=v["gap"], clean=v["clean"], compress=v["compress"])
            assert cfg["start"] >= 1 and cfg["pages"] >= 0
            return cfg
        except (ValueError, AssertionError):
            self.alert(t("d_fields_t"), t("d_fields"))
            return None

    # --- one folder per project (named after the document) ---
    def assign_project(self, cfg, name):
        cfg["name"] = name
        cfg["temp"] = os.path.join(cfg["temp_root"], name)  # page images of this project
        cfg["out"] = os.path.join(cfg["out_root"], name)    # its PDF

    def resolve_name(self, cfg):
        """(name, read_from_first_page). A typed name wins, then the window title; otherwise the name is
        read from the first captured page. A name detected earlier is reused when resuming."""
        if cfg["name"] and not self.name_auto:
            return cfg["name"], False
        found = self.auto_name()
        if found:
            self.set_name(found, True)
            self.log(t("log_name_win", name=found))
            return found, False
        if cfg["name"] and self.name_auto and cfg["start"] > 1:
            return cfg["name"], False
        return "", True

    def finish_naming(self, cfg, img):
        """Runs after the first page: read the title from it and move the project to its final folder."""
        cfg["pending_name"] = False
        found = title_from_page(img)
        name = found or f"{t('default_name')} {time.strftime('%Y-%m-%d %H.%M')}"
        self.log(t("log_name_page", name=name) if found else t("log_name_fallback", name=name),
                 "info" if found else "warn")
        name = unique_project(cfg["temp_root"], cfg["out_root"], name)
        new_temp = os.path.join(cfg["temp_root"], name)
        try:
            os.rename(cfg["temp"], new_temp)
            cfg["temp"] = new_temp
        except OSError as e:  # keep the working folder; the PDF still gets the final name
            self.log(t("log_error", e=e), "warn")
        cfg["name"] = name
        cfg["out"] = os.path.join(cfg["out_root"], name)
        self.log(t("log_project", dir=cfg["out"]))
        self.ui(lambda: self.set_name(name, True))

    def export_pdf(self, cfg):
        """Build the project's PDF (compressed if chosen). Returns (pdf_path or None, size line or "")."""
        level = cfg.get("compress", "off")
        q = COMPRESSION.get(level)
        if q:
            w = f"{q[1]}px" if q[1] else t("orig_width")
            self.log(t("log_comp", level=t("comp_" + level).lower(), q=q[0], w=w))
        else:
            self.log(t("log_comp_off"))
        pdf, orig = build_pdf(cfg["temp"], cfg["out"], cfg["name"], cfg["clean"], level,
                              progress=lambda i, n: self.set_status(t("pdf_compressing", i=i, n=n)))
        info = ""
        if pdf:
            info = t("pdf_size", size=f"{os.path.getsize(pdf) / 1048576:.1f}", orig=f"{orig / 1048576:.1f}")
            self.log(info)
        return pdf, info

    # --- actions ---
    def pdf_now(self):
        cfg = self.parse()
        if not cfg:
            return
        name = cfg["name"] or self.auto_name() or latest_project(cfg["temp_root"])
        if not name:
            self.alert("PDF", t("no_project"))
            return
        self.assign_project(cfg, name)

        def work():
            self.set_status(t("pdf_building"))
            self.log(t("log_pdf_temp"))
            try:
                pdf, info = self.export_pdf(cfg)
                msg = (t("pdf_saved", pdf=pdf) + "\n" + info) if pdf else t("pdf_none")
                self.log(msg.replace("\n", " "))
            except Exception as e:
                msg = t("pdf_fail", err=e)
                self.log(msg.replace("\n", " "), "err")
            self.set_status(msg.replace("\n", " "))
            self.ui(lambda: self.alert("PDF", msg))

        threading.Thread(target=work, daemon=True).start()

    def start(self):
        self.session_lines = []
        if not self.target_ready():  # blocked: no region / window, no capture
            self.status_msg = t("need_window") if self.vars["source"].get() == "window" else t("need_region")
            self.c.itemconfig(self.status_item, text=self.status_msg)
            self.region_btn.flash()
            return
        cfg = self.parse()
        if not cfg:
            return
        name, pending = self.resolve_name(cfg)
        self.assign_project(cfg, "_untitled_" + time.strftime("%Y%m%d_%H%M%S") if pending else name)
        cfg["pending_name"] = pending
        os.makedirs(cfg["temp"], exist_ok=True)
        existing = list_pages(cfg["temp"])
        if cfg["start"] == 1 and existing:
            ans = dialog(self.root, t("d_tempfull_t"), t("d_tempfull", n=len(existing)),
                         [(t("b_delstart"), "primary"), (t("b_keep"), "secondary"), (t("b_cancel"), "secondary")])
            if ans in (None, 2):
                return
            if ans == 0:
                for _, p in existing:
                    os.remove(p)
                self.log(t("log_deleted", n=len(existing)))
        self.stop.clear()
        self.paused.clear()
        self.running = True
        self.root.withdraw()
        self.target = self.make_target()
        self.panel = Panel(self, self.target_rect())
        self.apply_log()  # the log moves into the capture window
        if self.target.is_window:
            self.log(t("log_src_window", title=self.window["title"]))
        else:
            self.log(t("log_src_region"))
            hidden = self.panel.hidden
            self.log(t("log_hid_ok") if hidden else t("log_hid_no"), "info" if hidden else "warn")
        self.hk = Hotkeys(lambda: self.ui(self.toggle_pause), self.request_stop)
        self.hk.start()
        self.hk.ready.wait(1.0)
        self.hk_ok = self.hk.registered
        self.log(t("log_hk_ok") if self.hk_ok else t("log_hk_no"), "info" if self.hk_ok else "warn")
        self.panel.set_progress(0, cfg["pages"])
        if not pending:
            self.log(t("log_project", dir=cfg["out"]))
        threading.Thread(target=self.run, args=(cfg,), daemon=True).start()

    def wait_if_paused(self, n):
        shown = False
        while self.paused.is_set() and not self.stop.is_set():
            if not shown:
                self.set_status(t("paused_status", n=n))
                shown = True
            time.sleep(0.2)

    def run(self, cfg):
        n = cfg["start"]
        saved, same, last = 0, 0, None
        reason, err, pdf = "stopped", "", None
        try:
            extra = t("log_extra", th=cfg["thresh"], gap=t("on") if cfg["gap"] else t("off")) \
                if cfg["mode"] == "scroll" else ""
            self.log(t("log_start", n=n, mode=cfg["mode"], key=cfg["key"], delay=cfg["delay"], extra=extra))
            tgt = self.target
            tgt.check()  # window mode: still there, not minimized, not black
            for s in range(5, 0, -1):  # time to focus the reader window
                if self.stop.is_set():
                    break
                self.set_status(t("countdown", s=s))
                time.sleep(1)
            tgt.focus()
            while not self.stop.is_set():
                if cfg["pages"] and saved >= cfg["pages"]:
                    reason = "count"
                    break
                self.wait_if_paused(n)
                if self.stop.is_set():
                    break
                self.log(t("log_capturing", n=n))
                cap = t("page_n", n=n)
                if cfg["mode"] == "scroll":
                    img = capture_page(tgt, cfg["scroll"], cfg["steps"], cfg["thresh"], cfg["gap"],
                                       self.log, preview=lambda a: self.preview(a, cap))
                else:
                    img = tgt.grab()
                    if img is None:
                        raise RuntimeError(t("win_gone"))
                    self.preview(img, cap)
                if cfg["end"] and last is not None and last.shape == img.shape \
                        and np.mean(cv2.absdiff(last, img)) < 0.5:
                    same += 1
                    self.log(t("log_same", n=n, k=same), "warn")
                    if same >= 2:  # the page did not change after 2 tries
                        reason = "end"
                        break
                    pyautogui.press(cfg["key"])
                    time.sleep(cfg["delay"])
                    continue
                same, last = 0, img
                Image.fromarray(img).save(os.path.join(cfg["temp"], f"page_{n:03d}.png"))
                saved += 1
                n += 1
                total = t("total_of", p=cfg["pages"]) if cfg["pages"] else ""
                self.set_status(t("captured", n=n - 1, saved=saved, total=total))
                self.log(t("log_saved", n=n - 1, w=img.shape[1], h=img.shape[0]))
                self.ui(lambda s=saved: self.panel.set_progress(s, cfg["pages"]) if self.panel else None)
                if cfg.get("pending_name"):
                    self.finish_naming(cfg, img)
                if cfg["pages"] and saved >= cfg["pages"]:
                    reason = "count"
                    break
                pyautogui.press(cfg["key"])
                time.sleep(cfg["delay"])
            if cfg["pdf"] and list_pages(cfg["temp"]):
                self.set_status(t("pdf_building"))
                self.log(t("pdf_building"))
                pdf, cfg["pdf_info"] = self.export_pdf(cfg)
                self.log(t("pdf_saved", pdf=pdf).replace("\n", " "))
        except Exception as e:
            reason, err = "error", str(e)
            self.log(t("log_error", e=e), "err")
        if cfg.get("pending_name") and not list_pages(cfg["temp"]):
            try:
                os.rmdir(cfg["temp"])  # nothing was captured: do not leave an empty working folder
            except OSError:
                pass
        self.log(t("log_finished", reason=reason, saved=saved))
        self.ui(self.finish, reason, cfg, n, saved, pdf, err)

    def finish(self, reason, cfg, next_n, saved, pdf, err):
        self.running = False
        self.paused.clear()
        if self.hk:
            self.hk.stop()
            self.hk, self.hk_ok = None, False
        if self.panel:
            self.panel.destroy()
            self.panel = None
        self.root.deiconify()
        self.root.update_idletasks()
        self.apply_log()  # the log goes back beside the main window
        self.vars["start"].set(str(next_n))  # ready to continue
        first, last = cfg["start"], next_n - 1
        span = t("span", a=first, b=last) if saved else ""
        if reason == "count":
            title, kind = t("t_done"), "ok"
            msg = t("m_done", saved=saved, span=span)
        elif reason == "end":
            plan = t("plan", p=cfg["pages"]) if cfg["pages"] else ""
            title, kind = t("t_early"), "warn"
            msg = t("m_early", saved=saved, plan=plan, span=span)
        elif reason == "error":
            title, kind, msg = t("t_err"), "err", t("m_err", err=err)
        else:
            title, kind = t("t_stopped"), "ok"
            msg = t("m_stopped", last=last, next=next_n)
        if pdf:
            msg += t("pdf_to", pdf=pdf)
            if cfg.get("pdf_info"):
                msg += "\n" + cfg["pdf_info"]
        log_path = self.save_session_log(cfg)
        if log_path:
            msg += t("log_to", path=log_path)
        self.status_msg = f"{title}. " + msg.split("\n")[0]
        self.c.itemconfig(self.status_item, text=self.status_msg)
        beep(kind)
        self.root.attributes("-topmost", True)
        self.alert(title, msg)
        self.root.attributes("-topmost", False)


# ---------- embedded background (brand gradient) ----------
BG_B64 = (
    "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"
)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
