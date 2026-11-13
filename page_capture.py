"""
Page Capture 2.2 - capture pages one by one (simple or scroll-and-stitch mode) and build a PDF, CBZ or ZIP.
By Ygor Betine - Becine Tools. For personal use, with apps that allow screen capture.

Install:
    pip install mss pyautogui pillow numpy opencv-python pynput img2pdf pypdf
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
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
import zipfile
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog

import cv2
import mss
import numpy as np
import pyautogui
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageTk
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

VERSION = "2.3"
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
ZOOM = 1.15  # the whole interface is drawn 15% larger than its 1000 x 640 design

# ---------- translations (English, Portuguese) ----------
TXT = {
    "subtitle": ("Capture book pages straight into a PDF", "Capture páginas de livros direto em PDF"),
    "hint_keys": ("F9 pause · ESC stop", "F9 pausar · ESC parar"),
    "folders": ("FOLDERS", "PASTAS"),
    "temp_images": ("Temp folder", "Pasta temporária"),
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
    "pages": ("Pages (0 = to the end)", "Páginas (0 = até fim)"),
    "delay": ("Delay (s)", "Espera (s)"),
    "key": ("Next-page key", "Tecla próx. pág."),
    "scroll_step": ("Scroll step", "Passo rolagem"),
    "max_steps": ("Max scroll steps", "Máx. de passos"),
    "threshold": ("Match threshold", "Limiar de junção"),
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
    "opt_pdf": ("Create the file when finished", "Gerar o arquivo ao terminar"),
    "opt_end": ("Stop if the page does not change", "Parar se a página não mudar"),
    "opt_gap": ("Scroll: stop at the dark gap", "Rolagem: parar na faixa escura"),
    "opt_clean": ("Delete temp images at the end", "Apagar imagens temp. no fim"),
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
    "ocr_skip": ("Tesseract not found: building the PDF without searchable text. "
                 "Install it to enable it: github.com/UB-Mannheim/tesseract/wiki",
                 "Tesseract não encontrado: gerando o PDF sem texto pesquisável. "
                 "Instale para ativar: github.com/UB-Mannheim/tesseract/wiki"),
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
    "cp_nogap": ("  page gap detection skipped: the page fills the whole width, so a gap cannot be told apart "
                 "from dark artwork",
                 "  detecção da faixa entre páginas ignorada: a página ocupa toda a largura, então a faixa não se "
                 "distingue de uma arte escura"),
    "cp_end": ("  end of page reached after {step} scroll(s)", "  fim da página após {step} rolagem(ns)"),
    "default_name": ("captures", "capturas"),
    "upd_checking": ("Checking for updates...", "Verificando atualizações..."),
    "upd_check_t": ("Updates", "Atualizações"),
    "upd_title": ("New version available", "Nova versão disponível"),
    "upd_msg": ("Version {new} is available. You are using {cur}.", "A versão {new} está disponível. Você está usando a {cur}."),
    "upd_download": ("Download", "Baixar"),
    "upd_notes": ("What's new", "Novidades"),
    "upd_later": ("Later", "Depois"),
    "upd_none_t": ("Up to date", "Atualizado"),
    "upd_none": ("You are on the latest version ({cur}).", "Você está na versão mais recente ({cur})."),
    "upd_fail": ("Could not check for updates right now. Check your internet connection.",
                 "Não foi possível verificar atualizações agora. Confira sua conexão com a internet."),
    "tab_capture": ("Capture", "Capturar"),
    "tab_projects": ("Projects", "Projetos"),
    "tab_compress": ("Compress", "Comprimir"),
    "cp_title": ("Compress a PDF", "Comprimir um PDF"),
    "cp_hint": ("Recompresses the images inside any PDF. Text, links and bookmarks are kept. Nothing is captured. "
                "You can also drag a PDF onto this window.",
                "Recomprime as imagens de qualquer PDF. Texto, links e marcadores são mantidos. Nada é capturado. "
                "Você também pode arrastar um PDF para esta janela."),
    "cp_pick": ("Choose PDF…", "Escolher PDF…"),
    "cp_pick_title": ("Choose the PDF to compress", "Escolha o PDF para comprimir"),
    "cp_none": ("No file chosen yet.", "Nenhum arquivo escolhido ainda."),
    "cp_info": ("{pages} pages · {size} MB", "{pages} páginas · {size} MB"),
    "comp_extreme": ("Maximum", "Máxima"),
    "cp_gray": ("Convert to grayscale (smaller)", "Converter para tons de cinza (menor)"),
    "cp_split": ("Split into two documents", "Dividir em dois documentos"),
    "cp_split_one": ("The PDF has only one page, so it cannot be split.", "O PDF tem só uma página e não pode ser dividido."),
    "cp_part": ("part", "parte"),
    "cp_done_split": ("Done: {a} MB → {b} MB (−{pct}%), split in two:\n{p1}\n{p2}",
                      "Pronto: {a} MB → {b} MB (−{pct}%), dividido em dois:\n{p1}\n{p2}"),
    "cp_est": ("Estimate: ≈ {size} MB (−{pct}%)", "Estimativa: ≈ {size} MB (−{pct}%)"),
    "cp_est_split": ("Estimate: ≈ {size} MB in total, ≈ {half} MB per file (−{pct}%)",
                     "Estimativa: ≈ {size} MB no total, ≈ {half} MB por arquivo (−{pct}%)"),
    "cp_finishing": ("Finishing: writing the file…", "Finalizando: gravando o arquivo…"),
    "cp_est_wait": ("Estimating…", "Calculando estimativa…"),
    "cp_est_none": ("Estimate: little or no reduction expected", "Estimativa: pouca ou nenhuma redução esperada"),
    "cp_level": ("Compression level", "Nível de compressão"),
    "cp_save_as": ("Save as", "Salvar como"),
    "cp_change": ("Change…", "Alterar…"),
    "cp_run": ("Compress", "Comprimir"),
    "cp_running": ("Compressing page {i} of {n}…", "Comprimindo página {i} de {n}…"),
    "cp_done": ("Done: {a} MB → {b} MB (−{pct}%)\n{path}", "Pronto: {a} MB → {b} MB (−{pct}%)\n{path}"),
    "cp_nogain": ("This PDF could not get any smaller at this level (its images are already small or it has no images). "
                  "No file was created.",
                  "Este PDF não ficou menor neste nível (as imagens já são pequenas ou ele não tem imagens). "
                  "Nenhum arquivo foi criado."),
    "cp_fail": ("Could not compress the PDF:\n{err}", "Não foi possível comprimir o PDF:\n{err}"),
    "cp_locked": ("The PDF is password-protected.", "O PDF está protegido por senha."),
    "cp_open": ("Open file", "Abrir arquivo"),
    "cp_folder": ("Open folder", "Abrir pasta"),
    "cp_need_file": ("Choose a PDF first.", "Escolha um PDF primeiro."),
    "cp_status": ("Compress tab: pick a PDF, choose the level and press Compress.",
                  "Aba Comprimir: escolha um PDF, o nível e clique em Comprimir."),
    "output": ("Output", "Saída"),
    "doc_name_full": ("Document name", "Nome do documento"),
    "ph_name": ("Empty: window title or 1st page", "Vazio: título da janela ou 1ª pág."),
    "nothing_selected": ("Nothing selected yet", "Nada selecionado ainda"),
    "chip_region": ("Screen region", "Região da tela"),
    "preset_none": ("No preset", "Sem predefinição"),
    "ask_preset_t": ("Save preset", "Salvar predefinição"),
    "ask_preset": ("Preset name", "Nome da predefinição"),
    "log_preset": ('Preset saved: "{name}"', 'Predefinição salva: "{name}"'),
    "th_short": ("How alike two screenshots must be to be joined.", "Quão parecidos dois prints precisam ser para serem unidos."),
    "how_works": ("How it works", "Como funciona"),
    "opt_ocr": ("Searchable PDF (OCR)", "PDF pesquisável (OCR)"),
    "projects": ("Projects", "Projetos"),
    "new_capture": ("New capture", "Nova captura"),
    "search": ("Search project", "Buscar projeto"),
    "flt_all": ("All", "Todos"),
    "flt_going": ("In progress", "Em andamento"),
    "flt_pdf": ("With PDF", "Com PDF"),
    "details": ("Details", "Detalhes"),
    "open_folder": ("Open folder", "Abrir pasta"),
    "open_pdf": ("Open PDF", "Abrir PDF"),
    "continue": ("Continue", "Continuar"),
    "gen_pdf": ("Generate PDF", "Gerar PDF"),
    "gen_pdf_project": ("Export project", "Exportar projeto"),
    "pages_h": ("Pages", "Páginas"),
    "export_h": ("Export", "Exportar"),
    "mark_hint": ("Click: mark to redo · double-click: enlarge", "Clique: marcar para refazer · duplo clique: ampliar"),
    "recapture": ("Recapture marked ({n})", "Recapturar marcadas ({n})"),
    "from_page": ("From page", "Da página"),
    "to_page": ("To page", "Até a página"),
    "ph_title": ("Title (optional)", "Título (opcional)"),
    "ph_author": ("Author (optional)", "Autor (opcional)"),
    "proj_meta": ("{c} of {p} pages captured", "{c} de {p} páginas capturadas"),
    "proj_meta2": ("{c} pages captured", "{c} páginas capturadas"),
    "next_page": ("next: page {n}", "próxima: pág. {n}"),
    "n_pages": ("{n} pages", "{n} páginas"),
    "of_total": ("{c} of {p}", "{c} de {p}"),
    "pdf_row": ("PDF {size} MB", "PDF {size} MB"),
    "lvl_off": ("lossless", "sem perdas"),
    "no_pdf_yet": ("No PDF yet", "Nenhum PDF ainda"),
    "select_project": ("Select a project", "Selecione um projeto"),
    "no_projects": ("No projects yet. Start a capture and it will show up here.",
                    "Nenhum projeto ainda. Faça uma captura e ele aparece aqui."),
    "status_projects": ("{n} projects · {k} with PDF · exports in {path}", "{n} projetos · {k} com PDF · exports em {path}"),
    "menu_open_temp": ("Open images folder", "Abrir pasta das imagens"),
    "menu_delete_temp": ("Delete temp images", "Apagar imagens temporárias"),
    "d_deltemp_t": ("Delete temp images", "Apagar imagens temporárias"),
    "d_deltemp": ('Delete the {n} temp images of "{name}"? The PDF is kept.',
                  'Apagar as {n} imagens temporárias de "{name}"? O PDF é mantido.'),
    "d_nomark_t": ("Nothing marked", "Nada marcado"),
    "d_nomark": ("Mark the pages you want to redo first.", "Marque primeiro as páginas que deseja refazer."),
    "recap_go": ("Recapture: go to page {n} in the reader and press Start.",
                 "Recaptura: vá para a página {n} no leitor e clique em Iniciar."),
    "recap_next": ("Recapture: go to page {n} in the reader and press Start. {left} section(s) left.",
                   "Recaptura: vá para a página {n} no leitor e clique em Iniciar. Faltam {left} trecho(s)."),
    "recap_done": ("Recapture finished. Generate the PDF again in Projects.",
                   "Recaptura concluída. Gere o PDF de novo em Projetos."),
    "t_recap": ("Recapture", "Recaptura"),
    "continue_msg": ('Continuing "{name}": go to page {n} in the reader and press Start.',
                     'Continuando "{name}": vá para a página {n} no leitor e clique em Iniciar.'),
    "pdf_ocr": ("Reading the text of the pages (OCR) {i}/{n}...", "Lendo o texto das páginas (OCR) {i}/{n}..."),
    "ocr_pypdf": ("The searchable PDF needs the pypdf package: pip install pypdf",
                  "O PDF pesquisável precisa do pacote pypdf: pip install pypdf"),
    "log_ocr": ("Searchable PDF: the text of each page is read with OCR (slower)",
                "PDF pesquisável: o texto de cada página é lido por OCR (mais lento)"),
    "d_range_t": ("Check the page range", "Confira o intervalo de páginas"),
    "d_range": ("The range needs two page numbers, the first not greater than the last.",
                "O intervalo precisa de dois números de página, com o primeiro não maior que o último."),
    "exp_none": ("There are no captured pages in that project or range.",
                 "Não há páginas capturadas nesse projeto ou intervalo."),
    "pg_abbr": ("p", "pág. "),
    "export": ("Export", "Exportar"),
    "compression": ("Compression", "Compressão"),
    "comp_off": ("Off", "Sem"),
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
    # ---- 2.2 ----
    "crop": ("Trim borders", "Recortar bordas"),
    "crop_none": ("None", "Nenhum"),
    "crop_auto": ("Auto", "Auto"),
    "crop_manual": ("Manual", "Manual"),
    "crop_t": ("Trim borders", "Recortar bordas"),
    "crop_hint": ("Drag over the area to keep. It is used on every page.",
                  "Arraste sobre a área que deve ficar. Vale para todas as páginas."),
    "crop_reset": ("Whole page", "Página inteira"),
    "crop_need": ("Pick a window or region first (or capture a page) to see a sample page.",
                  "Escolha uma janela ou região antes (ou capture uma página) para ver uma página de exemplo."),
    "format": ("Format", "Formato"),
    "adjust": ("Image adjust", "Ajuste da imagem"),
    "adj_original": ("Original", "Original"),
    "adj_sharp": ("Sharper", "Nítida"),
    "adj_gray": ("Gray", "Cinza"),
    "adj_bw": ("B&W", "P&B"),
    "opt_dups": ("Skip repeated pages", "Pular páginas repetidas"),
    "folders_btn": ("Output folders…", "Pastas de saída…"),
    "folders_t": ("Output folders", "Pastas de saída"),
    "more_opts": ("More options ▸", "Mais opções ▸"),
    "exp_opts_t": ("Export options", "Opções de exportação"),
    "opt_bookmarks": ("Create bookmarks in the PDF", "Criar marcadores no PDF"),
    "bk_summary": ("{n} bookmarks: page {pages}", "{n} marcadores: pág. {pages}"),
    "bk_none": ("No bookmarks yet (add them when viewing a page)", "Nenhum marcador ainda (crie ao ver uma página)"),
    "review_n": ("Review ({n})", "Revisar ({n})"),
    "review_none": ("No repeated pages found.", "Nenhuma página repetida encontrada."),
    "gen_file_project": ("Export project", "Exportar projeto"),
    "lg_bookmark": ("bookmark", "marcador"),
    "lg_repeated": ("repeated", "repetida"),
    "open_file": ("Open file", "Abrir arquivo"),
    "file_saved": ("File saved to:\n{pdf}", "Arquivo salvo em:\n{pdf}"),
    "pv_title": ("Page {n}", "Página {n}"),
    "pv_marked": ("Marked to redo", "Marcada para refazer"),
    "pv_same": ("Same as page {m} ({p}%)", "Igual à pág. {m} ({p}%)"),
    "pv_del_dup": ("Delete this repeated page", "Excluir esta repetida"),
    "pv_mark": ("Mark to redo", "Marcar para refazer"),
    "pv_unmark": ("Unmark", "Desmarcar"),
    "pv_bookmark": ("Bookmark (optional)", "Marcador (opcional)"),
    "pv_insert": ("Insert page after…", "Inserir página depois…"),
    "pv_insert_pick": ("Pick the image(s) to insert", "Escolha a(s) imagem(ns) a inserir"),
    "pv_move": ("Move to", "Mover para"),
    "pv_delete": ("Delete page", "Excluir página"),
    "pv_del_q": ("Delete page {n}? The next pages move up one position.",
                 "Excluir a página {n}? As próximas sobem uma posição."),
    "pv_close": ("Close", "Fechar"),
    "pv_prev": ("‹ Previous", "‹ Anterior"),
    "pv_next": ("Next ›", "Próxima ›"),
    "pv_of": ("{n} of {t}", "{n} de {t}"),
    "menu_rename": ("Rename", "Renomear"),
    "ask_rename_t": ("Rename project", "Renomear projeto"),
    "ask_rename": ("New name for the project", "Novo nome do projeto"),
    "rename_exists": ("A project with this name already exists.", "Já existe um projeto com esse nome."),
    "rename_fail": ("Could not rename: {err}", "Não foi possível renomear: {err}"),
    "log_renamed": ('Project renamed: "{old}" -> "{new}"', 'Projeto renomeado: "{old}" -> "{new}"'),
    "eta": ("{t} left", "faltam {t}"),
    "eta_min": ("~{n} min", "~{n} min"),
    "eta_sec": ("~{n} s", "~{n} s"),
    "log_dup": ("Page {n} repeats the previous one: skipped ({k})", "Página {n} repete a anterior: pulada ({k})"),
    "notice_dup": ("Page {n} repeated: skipped", "Página {n} repetida: pulada"),
    "upd_now": ("Update now", "Atualizar agora"),
    "upd_auto": ("The app closes, updates itself and opens again.", "O app fecha, se atualiza e abre de novo sozinho."),
    "upd_prog_t": ("Updating to {new}", "Atualizando para {new}"),
    "upd_s1": ("Downloading the new version", "Baixando a nova versão"),
    "upd_s2": ("Preparing the files", "Preparando os arquivos"),
    "upd_s3": ("Restarting the app", "Reiniciando o app"),
    "upd_dont": ("Do not close this window.", "Não feche esta janela."),
    "upd_err": ("The update failed: {err}", "A atualização falhou: {err}"),
    "upd_nopy": ("Python was not found, so the app cannot rebuild itself. Install Python (python.org, tick \"Add python.exe to PATH\") "
                 "or update by downloading the zip.",
                 "O Python não foi encontrado, então o app não consegue se reconstruir. Instale o Python (python.org, marque "
                 "\"Add python.exe to PATH\") ou atualize baixando o zip."),
    "upd_noasset": ("This release has no zip to install. The release page will open.",
                    "Esta versão não tem um zip para instalar. A página da versão vai abrir."),
    "upd_busy": ("Finish or stop the capture before updating.", "Termine ou pare a captura antes de atualizar."),
}


def t(name, /, **kw):
    s = TXT[name][0 if LANG[0] == "en" else 1]
    return s.format(**kw) if kw else s


def U(n):
    """Scale a layout size (designed for 96 dpi) to the current screen."""
    return int(round(n * SCALE[0]))


FONT = ["Segoe UI", "Segoe UI", "Segoe UI"]  # bold / body / black; the bundled Panamera replaces them when it loads


def load_fonts(root):
    """Load the bundled Panamera family for this program only (nothing is installed on the PC) and use it
    for the whole interface. If it cannot be loaded, the interface keeps Segoe UI."""
    folder = os.path.join(getattr(sys, "_MEIPASS", None) or app_dir(), "fonts")
    if sys.platform == "win32" and os.path.isdir(folder):
        try:
            add = ctypes.windll.gdi32.AddFontResourceExW
            add.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
            for name in sorted(os.listdir(folder)):
                if name.lower().endswith((".ttf", ".otf")):
                    add(os.path.join(folder, name), 0x10, None)  # FR_PRIVATE: visible to this program only
        except Exception:
            pass
    families = set(tkfont.families(root))
    if "Panamera" in families:
        FONT[0] = "Panamera"
        FONT[1] = "Panamera Medium" if "Panamera Medium" in families else "Panamera"
        FONT[2] = "Panamera Black" if "Panamera Black" in families else "Panamera"


def FB(px, underline=False):
    """Panamera Black, used for the version number."""
    return (FONT[2], -U(px + 1), "underline" if underline else "normal")


def apply_icon(root):
    """Window / taskbar icon (PageCapture.ico sits next to the program or inside the packaged exe)."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("BecineTools.PageCapture")
    except Exception:
        pass
    for base in (getattr(sys, "_MEIPASS", None), app_dir(), root_dir()):
        path = os.path.join(base, "PageCapture.ico") if base else None
        if path and os.path.isfile(path):
            try:
                root.iconbitmap(default=path)
            except tk.TclError:
                pass
            return


def F(px, bold=False, semibold=False):
    """Interface font: Panamera Medium for text, Panamera Bold for buttons and headings (one size up)."""
    if bold or semibold:
        return (FONT[0], -U(px + 1), "bold")
    return (FONT[1], -U(px + 1), "normal")


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
                            outline=(232, 232, 232, 88), width=2)
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
        tag = self.tag = f"btn{id(self)}"
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


def enable_file_drop(win, callback):
    """Let files be dragged from Explorer onto the window (Windows, no extra package). callback(list_of_paths)."""
    try:
        from ctypes import wintypes as wt
        user32, shell32 = ctypes.windll.user32, ctypes.windll.shell32
        hwnd = user32.GetParent(win.winfo_id())
        proc_t = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
        user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
        user32.CallWindowProcW.restype = ctypes.c_ssize_t
        user32.SetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_void_p]
        user32.SetWindowLongPtrW.restype = ctypes.c_void_p
        shell32.DragQueryFileW.argtypes = [ctypes.c_void_p, wt.UINT, wt.LPWSTR, wt.UINT]
        shell32.DragFinish.argtypes = [ctypes.c_void_p]
        old, pending = [None], []

        def proc(h, msg, wp, lp):
            if msg == 0x233:  # WM_DROPFILES
                files = []
                for i in range(shell32.DragQueryFileW(wp, 0xFFFFFFFF, None, 0)):
                    buf = ctypes.create_unicode_buffer(1024)
                    shell32.DragQueryFileW(wp, i, buf, 1024)
                    files.append(buf.value)
                shell32.DragFinish(wp)
                pending.append(files)  # no Tk calls in here: Tk picks them up from its own timer below
                return 0
            return user32.CallWindowProcW(old[0], h, msg, wp, lp)

        win._drop_proc = proc_t(proc)  # keep a reference or it gets garbage-collected
        old[0] = user32.SetWindowLongPtrW(hwnd, -4, ctypes.cast(win._drop_proc, ctypes.c_void_p))
        shell32.DragAcceptFiles(hwnd, True)

        def poll():
            while pending:
                callback(pending.pop(0))
            win.after(150, poll)
        win.after(150, poll)
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


MIN_GAP = 12           # rows of reader background that count as the gap between two pages
SETTLE_TIMEOUT = 1.2   # seconds to wait for a scroll to show up before deciding the page cannot scroll further


def reader_background(img):
    """Colour of the reader's dark background, read from the left and right edge columns of the frame.
    None when the page fills the whole width or the edges are not flat: then a gap cannot be told apart
    from dark artwork, so gap detection stays off (it must never cut a page that has black areas)."""
    means = []
    for side in (img[:, :3], img[:, -3:]):
        side = side.reshape(-1, 3).astype(np.float32)
        if side.std(axis=0).max() > 4.0:
            return None
        means.append(side.mean(axis=0))
    if np.abs(means[0] - means[1]).max() > 6.0:
        return None
    bg = (means[0] + means[1]) / 2
    return bg if bg.mean() < 60 else None


def gap_runs(img, bg, min_run=MIN_GAP):
    """Full-width flat bands with exactly the reader background colour: [(start, end)]."""
    f = img.astype(np.float32)
    uni = (f.mean(axis=2).std(axis=1) < 3.0) & (np.abs(f.mean(axis=1) - bg).max(axis=1) <= 8.0)
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


def _same(a, b):
    return a.shape == b.shape and cv2.absdiff(a, b).mean() < 0.3


def settle(target, prev, delay):
    """Grab the frame after a scroll, once it stops changing (animations, lazy-loaded images).
    If nothing has moved yet, keep waiting up to SETTLE_TIMEOUT before concluding that the page cannot
    scroll any further, instead of deciding on the first frame."""
    t0 = time.time()
    time.sleep(delay)
    last = None
    while True:
        cur = target.grab()
        if cur is None:
            return None
        waited = time.time() - t0
        if last is not None and _same(last, cur):
            if not _same(prev, cur) or waited >= SETTLE_TIMEOUT:
                return cur
        if waited >= SETTLE_TIMEOUT + 3.0:  # still moving after a long time: take what we have
            return cur
        last = cur
        time.sleep(0.15)


def capture_page(target, scroll_amount, max_steps, thresh, gap, log, delay=0.4, preview=None):
    first = target.grab()
    if first is None:
        raise RuntimeError(t("win_gone"))
    acc = prev = first
    bg = reader_background(first) if gap else None
    if gap and bg is None:
        log(t("cp_nogap"))
    if bg is not None:
        runs = gap_runs(acc, bg, 3)
        if runs and runs[0][0] == 0:  # the frame starts inside the gap of the previous page
            acc = acc[runs[0][1]:]
            log(t("cp_trim", n=runs[0][1]))
            if acc.shape[0] < 10:
                acc = first
        runs = gap_runs(acc, bg)
        if runs:
            log(t("cp_gap", n=runs[0][0]))
            return acc[:runs[0][0]]
    if preview:
        preview(acc)
    for step in range(1, max_steps + 1):
        pyautogui.moveTo(*target.center())
        pyautogui.scroll(-scroll_amount)
        new = settle(target, prev, delay)
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
        if bg is not None and added > 2:
            off = max(0, old_len - 3 * MIN_GAP)
            runs = gap_runs(acc[off:], bg)
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
COMPRESSION = {"off": None, "light": (90, 0), "balanced": (80, 2000), "strong": (62, 1400), "extreme": (45, 1000)}
FORMATS = {"pdf": ".pdf", "cbz": ".cbz", "zip": ".zip"}


def split_pdf(src, dst1, dst2):
    """Split a PDF into two documents at the middle page (bookmarks of each half are kept)."""
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(src)
    n = len(reader.pages)
    if n < 2:
        raise RuntimeError(t("cp_split_one"))
    mid = (n + 1) // 2
    for dst, rng in ((dst1, (0, mid)), (dst2, (mid, n))):
        w = PdfWriter()
        w.append(reader, pages=rng)
        with open(dst, "wb") as f:
            w.write(f)
    return mid, n - mid


def _page_images(page):
    """Image XObjects of a page (also inside form XObjects), found from the resources: no content-stream parsing."""
    out, seen = [], set()

    def walk(res, depth):
        try:
            xobjs = res["/XObject"].get_object()
        except Exception:
            return
        for name in list(xobjs.keys()):
            try:
                xo = xobjs[name].get_object()
                ref = getattr(xo, "indirect_reference", None)
                idn = ref.idnum if ref is not None else id(xo)
                if idn in seen:
                    continue
                seen.add(idn)
                sub = xo.get("/Subtype")
                if sub == "/Image":
                    out.append(xo)
                elif sub == "/Form" and depth < 4 and "/Resources" in xo:
                    walk(xo["/Resources"].get_object(), depth + 1)
            except Exception:
                continue

    try:
        if "/Resources" in page:
            walk(page["/Resources"].get_object(), 0)
    except Exception:
        pass
    return out


def _decode_image(xo):
    """PIL image of an image XObject."""
    from pypdf.generic._image_xobject import _xobj_to_image
    return _xobj_to_image(xo)[2]


def _recompressible(xo):
    """True for images we re-encode as JPEG: colour / gray, no transparency, not 1-bit, not JBIG2 / CCITT."""
    if "/SMask" in xo or "/Mask" in xo or xo.get("/ImageMask"):
        return False
    if xo.get("/BitsPerComponent") == 1:
        return False
    filt = str(xo.get("/Filter"))
    return "JBIG2" not in filt and "CCITT" not in filt


def _shrink_image(pil, max_w, gray):
    """Same image changes compress_pdf makes: gray / RGB and a maximum width."""
    if pil.mode == "1":
        return None
    if gray:
        pil = pil.convert("L")
    elif pil.mode not in ("RGB", "L"):
        pil = pil.convert("RGB")
    if max_w and pil.width > max_w:
        pil = pil.resize((max_w, max(1, round(pil.height * max_w / pil.width))), Image.LANCZOS)
    return pil


def _xmp_bytes(path):
    """Bytes taken by XMP metadata streams stored in the file (what strip_hidden_data removes). A plain byte search
    for '/Subtype /XML' objects up to their 'endstream', whether compressed or not: fast even for hundreds of MB."""
    import mmap
    total = 0
    try:
        with open(path, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            seen = set()
            for pat in (b"/Subtype/XML", b"/Subtype /XML"):
                pos = 0
                while True:
                    a = mm.find(pat, pos)
                    if a < 0:
                        break
                    pos = a + len(pat)
                    e = mm.find(b"endstream", a)
                    if e < 0:
                        break
                    if (a, e) not in seen:
                        seen.add((a, e))
                        total += e - a
    except (OSError, ValueError):
        pass
    return total


def estimate_size(src, level, gray=False, samples=10):
    """Estimate the size in bytes of src after compress_pdf(): the hidden data that gets removed is counted
    exactly, and the images are estimated by re-encoding a sample picked by weight (heavy images dominate)."""
    from pypdf import PdfReader
    quality, max_w = COMPRESSION.get(level) or COMPRESSION["balanced"]
    reader = PdfReader(src)
    if reader.is_encrypted and not reader.decrypt(""):
        raise RuntimeError(t("cp_locked"))
    total = os.path.getsize(src)
    seen, imgs = set(), []
    for page in reader.pages:
        for xo in _page_images(page):
            try:
                idn = xo.indirect_reference.idnum
                if idn in seen:
                    continue
                seen.add(idn)
                if _recompressible(xo):
                    imgs.append((len(xo._data), xo))
            except Exception:
                continue
    hidden = _xmp_bytes(src)
    weight = sum(w for w, _ in imgs)
    ratio = 1.0
    if imgs:
        # systematic sampling over the cumulative weight: every sample point stands for the same number of bytes
        picks, acc, j = [], 0, 0
        for item in imgs:
            acc += item[0]
            while j < samples and acc >= (j + 0.5) * weight / samples:
                picks.append(item)
                j += 1
        done, ratios = {}, []
        for w, xo in picks:
            if id(xo) not in done:
                try:
                    pil = _shrink_image(_decode_image(xo), max_w, gray)
                    buf = io.BytesIO()
                    pil.save(buf, "JPEG", quality=quality)
                    done[id(xo)] = min(1.0, buf.tell() / w)  # an image that would grow is left as it is
                except Exception:
                    done[id(xo)] = None
            if done[id(xo)] is not None:
                ratios.append(done[id(xo)])
        if ratios:
            ratio = sum(ratios) / len(ratios)
    return max(total * 0.02, total - hidden - weight * (1 - ratio))


def strip_hidden_data(writer):
    """Drop editor leftovers that can weigh tens of MB: XMP metadata hanging from images / pages / forms and the
    Photoshop / Illustrator private data (PieceInfo). The document's own small metadata stays."""
    seen, removed = set(), [0]

    def walk(o, is_catalog=False):
        try:
            o = o.get_object() if hasattr(o, "get_object") else o
        except Exception:
            return
        if id(o) in seen:
            return
        seen.add(id(o))
        if hasattr(o, "keys"):
            if "/PieceInfo" in o:
                del o["/PieceInfo"]
                removed[0] += 1
            if "/Metadata" in o:
                try:
                    md = o["/Metadata"].get_object()
                    if o.get("/Type") != "/Catalog" or len(getattr(md, "_data", b"")) > 200_000:
                        del o["/Metadata"]
                        removed[0] += 1
                except Exception:
                    pass
            for k in list(o.keys()):
                if k not in ("/Parent", "/P"):
                    walk(o[k])
        elif isinstance(o, list):
            for v in o:
                walk(v)

    for obj in list(getattr(writer, "_objects", [])):
        if obj is not None:
            walk(obj)
    return removed[0]


def compress_pdf(src, dst, level, progress=None, gray=False):
    """Recompress the images of any PDF (text, links and bookmarks are kept). Returns the new size in bytes."""
    from pypdf import PdfReader, PdfWriter
    from pypdf._page import ImageFile
    quality, max_w = COMPRESSION.get(level) or COMPRESSION["balanced"]
    reader = PdfReader(src)
    if reader.is_encrypted and not reader.decrypt(""):
        raise RuntimeError(t("cp_locked"))
    writer = PdfWriter(clone_from=reader)
    stripped = strip_hidden_data(writer)
    seen, n = set(), len(writer.pages)
    for i, page in enumerate(writer.pages, 1):
        for xo in _page_images(page):
            try:  # one image we cannot decode (JBIG2, ...) must not stop the others on the page
                ref = getattr(xo, "indirect_reference", None)
                key = ref.idnum if ref is not None else None
                if key is None or key in seen:
                    continue
                seen.add(key)
                if not _recompressible(xo):  # transparency, 1-bit scans, JBIG2 / CCITT: leave them untouched
                    continue
                pil = _shrink_image(_decode_image(xo), max_w, gray)
                if pil is None:
                    continue
                buf = io.BytesIO()
                pil.save(buf, "JPEG", quality=quality)
                if buf.tell() >= len(getattr(xo, "_data", b"")):  # would not get smaller: keep the original
                    continue
                ImageFile(name="image.jpg", data=b"", image=pil, indirect_reference=ref).replace(pil, quality=quality)
            except Exception:
                continue  # an image we cannot handle stays as it was
        try:
            page.compress_content_streams()
        except Exception:
            pass
        if progress:
            progress(i, n)
    try:
        writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)
    except Exception:
        pass
    if progress:
        progress(-1, n)  # finishing: writing the file
    if stripped:
        # the removed data is still stored as unreachable objects: copy only what is reachable into a fresh file
        buf = io.BytesIO()
        writer.write(buf)
        buf.seek(0)
        writer = PdfWriter(clone_from=PdfReader(buf))
    with open(dst, "wb") as f:
        writer.write(f)
    return os.path.getsize(dst)


def add_bookmarks(pdf, items):
    """Add outline entries [(page index from 0, title)] to a finished PDF."""
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(pdf)
    writer = PdfWriter()
    writer.append(reader)
    if reader.metadata:
        writer.add_metadata({k: v for k, v in reader.metadata.items() if isinstance(v, str)})
    for idx, title in items:
        writer.add_outline_item(title, idx)
    tmp = pdf + ".tmp"
    with open(tmp, "wb") as f:
        writer.write(f)
    os.replace(tmp, pdf)


def build_pdf(temp, out_dir, name, clean, level="off", progress=None, first=None, last=None, title=None,
              author=None, ocr=False, lang="eng", fmt="pdf", crop="none", box=None, adjust="original",
              bookmarks=None, skip=()):
    """Build <out_dir>/<name>.pdf (or .cbz / .zip) from the page images of a project (optionally only pages
    first..last). level: off = lossless page images; light / balanced / strong = JPEG pages, strong also shrinks
    wide pages. crop / adjust: trim borders and adjust the images. ocr: searchable PDF. bookmarks: {page: title}
    added to the PDF outline. skip: page numbers left out (repeated pages).
    Returns (file_path, bytes_of_the_page_images), or (None, 0) when there is nothing to export."""
    pages = [(n, p) for n, p in list_pages(temp)
             if (first is None or n >= first) and (last is None or n <= last) and n not in skip]
    if not pages:
        return None, 0
    os.makedirs(out_dir, exist_ok=True)
    fmt = fmt if fmt in FORMATS else "pdf"
    target = os.path.join(out_dir, name + FORMATS[fmt])
    paths = [p for _, p in pages]
    orig = sum(os.path.getsize(p) for p in paths)
    profile = COMPRESSION.get(level)
    processed = crop != "none" or adjust != "original"

    def prepare(path):
        """Page image after trimming / adjusting / shrinking. Returns (PIL image, extension)."""
        im = Image.open(path)
        im = im.convert("RGB") if im.mode not in ("RGB", "L") else im
        im = process_image(im, crop, box, adjust)
        if profile:
            quality, max_w = profile
            if max_w and im.width > max_w:
                im = im.resize((max_w, max(1, round(im.height * max_w / im.width))), Image.LANCZOS)
            return im, ".jpg", dict(format="JPEG", quality=quality, optimize=True)
        return im, ".png", dict(format="PNG")

    if fmt in ("cbz", "zip"):  # a comic-book / plain archive with the page images inside
        with zipfile.ZipFile(target, "w", zipfile.ZIP_STORED) as z:
            for i, path in enumerate(paths, 1):
                if profile or processed:
                    im, ext, kw = prepare(path)
                    buf = io.BytesIO()
                    im.save(buf, **kw)
                    z.writestr(f"{i:03d}{ext}", buf.getvalue())
                else:
                    z.write(path, f"{i:03d}.png")
                if progress:
                    progress("compressing", i, len(paths))
        if clean:
            for p in paths:
                os.remove(p)
        return target, orig

    pdf = target
    work, files = None, paths
    try:
        if profile or processed:
            work = tempfile.mkdtemp(prefix="page_capture_")
            files = []
            for i, path in enumerate(paths, 1):
                im, ext, kw = prepare(path)
                out = os.path.join(work, f"{i:05d}{ext}")
                im.save(out, **kw)  # img2pdf embeds JPEGs without re-encoding
                files.append(out)
                if progress:
                    progress("compressing", i, len(paths))
        if ocr:
            pytesseract = _tesseract()
            try:
                from pypdf import PdfReader, PdfWriter
            except ImportError:
                raise RuntimeError(t("ocr_pypdf"))
            writer = PdfWriter()
            for i, path in enumerate(files, 1):
                try:
                    data = pytesseract.image_to_pdf_or_hocr(path, extension="pdf", lang=lang)
                except pytesseract.TesseractNotFoundError:
                    raise RuntimeError(t("ocr_tess"))
                except pytesseract.TesseractError:  # language pack missing: fall back to English
                    data = pytesseract.image_to_pdf_or_hocr(path, extension="pdf", lang="eng")
                writer.add_page(PdfReader(io.BytesIO(data)).pages[0])
                if progress:
                    progress("ocr", i, len(files))
            meta = {}
            if title:
                meta["/Title"] = title
            if author:
                meta["/Author"] = author
            if meta:
                writer.add_metadata(meta)
            with open(pdf, "wb") as f:
                writer.write(f)
        else:
            try:
                import img2pdf
                with open(pdf, "wb") as f:
                    f.write(img2pdf.convert(files, title=title or None, author=author or None))
            except ImportError:  # fallback, uses more memory
                imgs = [Image.open(p).convert("RGB") for p in files]
                imgs[0].save(pdf, save_all=True, append_images=imgs[1:])
        if bookmarks:
            items = [(i, str(bookmarks[str(n)])) for i, (n, _) in enumerate(pages) if str(bookmarks.get(str(n), "")).strip()]
            if items:
                try:
                    add_bookmarks(pdf, items)
                except ImportError:
                    pass
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
    data = os.path.join(getattr(sys, "_MEIPASS", None) or app_dir(), "tessdata")  # languages that ship with the program
    if os.path.isdir(data):
        os.environ["TESSDATA_PREFIX"] = data
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


def unique_file(path):
    """path, or 'name (2).ext', 'name (3).ext'... when it already exists."""
    base, ext = os.path.splitext(path)
    n, cand = 2, path
    while os.path.exists(cand):
        cand = f"{base} ({n}){ext}"
        n += 1
    return cand


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
        self.show_log = app.log_capture
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
        self.count = c.create_text(x0, U(112), anchor="w", text="", fill=MUTED, font=F(11))
        self.eta = c.create_text(x0 + cw, U(112), anchor="e", text="", fill=YELLOW, font=F(11, True))
        self.notice = c.create_text(x0, U(78), anchor="w", text="", fill=YELLOW, font=F(11, True))
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

    def set_notice(self, s):
        self.c.itemconfig(self.notice, text=fit_text(s, F(11, True), self.cw))

    def set_progress(self, done, total, eta=None):
        frac = min(1.0, done / total) if total else 0
        self.c.itemconfig(self.eta, text=t("eta", t=eta_text(eta)) if eta is not None else "")
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


def mb(nbytes):
    """Size in MB with the decimal separator of the chosen language."""
    s = f"{nbytes / 1048576:.1f}"
    return s.replace(".", ",") if LANG[0] == "pt" else s


def fit_text(text, font, max_w):
    """Trim text with an ellipsis so it fits max_w pixels."""
    f = tkfont.Font(font=font)
    if f.measure(text) <= max_w:
        return text
    while text and f.measure(text + "…") > max_w:
        text = text[:-1]
    return text.rstrip() + "…"


def open_path(path):
    """Open a file or folder with the system's default program."""
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


def add_placeholder(entry, var, text):
    """Grey hint text inside an Entry while it is empty and not focused."""
    lab = tk.Label(entry, text=text, bg=INPUT_BG, fg="#9AA0BA", font=F(13), anchor="w", cursor="xterm")
    state = {"focus": False}

    def refresh(*_):
        try:
            if var.get() or state["focus"]:
                lab.place_forget()
            else:
                lab.place(x=U(7), rely=0.5, anchor="w")
        except tk.TclError:  # the entry is gone
            pass

    def on_focus(flag):
        def _f(_e):
            state["focus"] = flag
            refresh()
        return _f

    tid = var.trace_add("write", refresh)

    def drop(_e):
        try:
            var.trace_remove("write", tid)
        except (tk.TclError, ValueError):
            pass

    entry.bind("<FocusIn>", on_focus(True), add="+")
    entry.bind("<FocusOut>", on_focus(False), add="+")
    entry.bind("<Destroy>", drop, add="+")
    lab.bind("<Button-1>", lambda e: entry.focus_set())
    refresh()


class DropDown:
    """Closed box showing the current choice; a click opens a themed menu."""

    def __init__(self, c, x, y, w, h, get_options, get_value, on_pick, size=12):
        self.c, self.get_options, self.on_pick, self.size, self.w = c, get_options, on_pick, size, w
        tag = f"dd{id(self)}"
        self.x, self.y, self.h = x, y, h
        round_rect(c, x, y, x + w, y + h, U(8), fill=INPUT_BG, outline=LINE, tags=tag)
        self.text = c.create_text(x + U(10), y + h / 2, anchor="w", fill=LIGHT, font=F(size), tags=tag, text="")
        cx, cy = x + w - U(14), y + h / 2
        c.create_line(cx - U(4), cy - U(2), cx, cy + U(2), cx + U(4), cy - U(2), fill=MUTED, width=2, tags=tag)
        c.tag_bind(tag, "<Button-1>", self._open)
        c.tag_bind(tag, "<Enter>", lambda e: c.config(cursor="hand2"))
        c.tag_bind(tag, "<Leave>", lambda e: c.config(cursor=""))
        self.set_text(get_value())

    def set_text(self, s):
        self.c.itemconfig(self.text, text=fit_text(s, F(self.size), self.w - U(34)))

    def _open(self, _e):
        m = tk.Menu(self.c, tearoff=0, bg=INPUT_BG, fg=LIGHT, activebackground=PURPLE, activeforeground=LIGHT,
                    bd=0, relief="flat", font=F(self.size))
        for opt in self.get_options():
            m.add_command(label=opt, command=lambda o=opt: self.on_pick(o))
        try:
            m.tk_popup(self.c.winfo_rootx() + self.x, self.c.winfo_rooty() + self.y + self.h)
        finally:
            m.grab_release()


class TabBar:
    """The two section tabs in the header (Capture / Projects, with a project counter)."""

    def __init__(self, c, cx, cy, tabs, current, on_change):
        self.c, self.tabs, self.on_change, self.current = c, tabs, on_change, current
        font = tkfont.Font(font=F(14, True))
        pad, pill_w, gap = U(18), U(30), U(4)
        widths = [font.measure(label) + 2 * pad + (pill_w if key == "projects" else 0) for key, label in tabs]
        total = sum(widths) + gap * (len(tabs) - 1) + U(6)
        h = U(40)
        x0, y0 = cx - total / 2, cy - h / 2
        round_rect(c, x0, y0, x0 + total, y0 + h, U(12), fill="#10162F", outline=LINE)
        self.rects, self.texts, self.count_txt = {}, {}, None
        x = x0 + U(3)
        for (key, label), w in zip(tabs, widths):
            tag = f"tab{id(self)}_{key}"
            self.rects[key] = round_rect(c, x, y0 + U(3), x + w, y0 + h - U(3), U(9), fill="#10162F", outline="", tags=tag)
            self.texts[key] = c.create_text(x + pad, cy, anchor="w", text=label, fill=MUTED, font=F(14, True), tags=tag)
            if key == "projects":
                px = x + pad + font.measure(label) + U(8)
                round_rect(c, px, cy - U(10), px + U(22), cy + U(10), U(10), fill="#4A4F70", outline="", tags=tag)
                self.count_txt = c.create_text(px + U(11), cy, text="0", fill=LIGHT, font=F(12, True), tags=tag)
            c.tag_bind(tag, "<Button-1>", lambda e, k=key: self.on_change(k))
            c.tag_bind(tag, "<Enter>", lambda e: c.config(cursor="hand2"))
            c.tag_bind(tag, "<Leave>", lambda e: c.config(cursor=""))
            x += w + gap
        self.set(current)

    def set(self, key):
        self.current = key
        for k in self.rects:
            on = k == key
            self.c.itemconfig(self.rects[k], fill=PURPLE if on else "#10162F")
            self.c.itemconfig(self.texts[k], fill=LIGHT if on else MUTED)

    def set_count(self, key, n):
        if self.count_txt:
            self.c.itemconfig(self.count_txt, text=str(n) if n < 100 else "99+")


def ask_text(root, title, label, initial=""):
    """Themed one-line prompt. Returns the text, or None if cancelled."""
    result = [None]
    top = tk.Toplevel(root)
    top.title(title)
    top.resizable(False, False)
    top.attributes("-topmost", True)
    W, H = U(420), U(210)
    c = tk.Canvas(top, width=W, height=H, highlightthickness=0, bd=0, bg=BLACK)
    c.pack()
    img = bg_image(W, H, [(U(10), U(10), W - U(10), H - U(10))])
    c.create_image(0, 0, image=img, anchor="nw")
    c.image = img
    c.create_text(U(28), U(26), anchor="nw", text=title, fill=LIGHT, font=F(17, semibold=True))
    c.create_text(U(28), U(64), anchor="nw", text=label, fill="#C8CBDB", font=F(12))
    var = tk.StringVar(value=initial)
    e = tk.Entry(c, textvariable=var, bg=INPUT_BG, fg=LIGHT, insertbackground=LIGHT, relief="flat", bd=U(6),
                 highlightthickness=1, highlightbackground=LINE, highlightcolor=PURPLE_LT, font=F(13),
                 selectbackground=PURPLE, selectforeground=LIGHT)
    c.create_window(U(28), U(86), window=e, anchor="nw", width=W - U(56), height=U(34))

    def ok():
        result[0] = var.get().strip() or None
        top.destroy()

    Btn(c, W - U(28) - U(100), H - U(26) - U(40), U(100), U(40), "OK", ok, "primary")
    Btn(c, W - U(28) - U(210), H - U(26) - U(40), U(100), U(40), t("b_cancel"), top.destroy, "secondary")
    e.bind("<Return>", lambda _e: ok())
    e.bind("<Escape>", lambda _e: top.destroy())
    center(top, W, H, (root.winfo_rootx() + root.winfo_width() // 2, root.winfo_rooty() + root.winfo_height() // 2)
           if root.state() == "normal" else (0, 0))
    top.update()
    top.lift()
    e.focus_force()
    e.select_range(0, "end")
    root.wait_window(top)
    return result[0]


# ---------- projects: one folder per document, with a small project.json ----------
def load_meta(temp_dir):
    try:
        with open(os.path.join(temp_dir, "project.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_meta(temp_dir, meta):
    try:
        os.makedirs(temp_dir, exist_ok=True)
        with open(os.path.join(temp_dir, "project.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)
    except OSError:
        pass


def project_info(temp_root, out_root, name):
    temp, out = os.path.join(temp_root, name), os.path.join(out_root, name)
    pages = list_pages(temp)
    nums = [n for n, _ in pages]
    meta = load_meta(temp)
    pdf = os.path.join(out, name + ".pdf")
    if not os.path.isfile(pdf) and os.path.isdir(out):  # e.g. a page-range, searchable or .cbz / .zip copy
        others = [os.path.join(out, f) for f in os.listdir(out) if f.lower().endswith(tuple(FORMATS.values()))]
        if others:
            pdf = max(others, key=os.path.getmtime)
    has_pdf = os.path.isfile(pdf)
    times = [os.path.getmtime(p) for _, p in pages] + ([os.path.getmtime(pdf)] if has_pdf else [])
    pdf_meta = meta.get("pdf") or {}
    return dict(
        name=name, temp=temp, out=out, pages=nums, captured=len(nums), last=max(nums) if nums else 0,
        planned=int(meta.get("planned", 0) or 0), mtime=max(times) if times else 0,
        pdf=pdf if has_pdf else None, pdf_size=os.path.getsize(pdf) if has_pdf else 0,
        pdf_level=pdf_meta.get("compress"), marked=sorted(int(m) for m in meta.get("marked", [])),
        bookmarks={int(k): v for k, v in (meta.get("bookmarks") or {}).items()})


def scan_projects(temp_root, out_root):
    """Every project found in the temp and export folders, newest first."""
    names = set()
    for base in (temp_root, out_root):
        if os.path.isdir(base):
            for d in os.listdir(base):
                if os.path.isdir(os.path.join(base, d)) and not d.startswith("_untitled_"):
                    names.add(d)
    infos = [project_info(temp_root, out_root, n) for n in names]
    return sorted([i for i in infos if i["captured"] or i["pdf"]], key=lambda i: i["mtime"], reverse=True)


def in_progress(info):
    """True while a project still has pages to capture (when the planned total is known)."""
    return bool(info["planned"]) and info["last"] < info["planned"]


def page_runs(pages):
    """[(first, count)] for consecutive page numbers: [2, 3, 4, 16, 17] -> [(2, 3), (16, 2)]."""
    runs = []
    for n in sorted(pages):
        if runs and n == runs[-1][0] + runs[-1][1]:
            runs[-1][1] += 1
        else:
            runs.append([n, 1])
    return [(a, b) for a, b in runs]


# ---------- presets and remembered fields ----------
PRESET_KEYS = ("mode", "delay", "scroll", "steps", "thresh", "end", "gap", "compress", "ocr", "format", "adjust",
               "crop", "dups")
BUILTIN_PRESETS = {
    "Artbook · rolagem": dict(mode="scroll", delay="1.0", scroll="300", steps="15", thresh=0.90, end=True,
                              gap=True, compress="off", ocr=False),
    "Texto · simples": dict(mode="simple", delay="0.8", scroll="300", steps="15", thresh=0.90, end=True,
                            gap=True, compress="balanced", ocr=False),
}
FIELD_KEYS = ("temp", "out", "pages", "delay", "key", "source", "mode", "scroll", "steps", "thresh", "pdf",
              "end", "gap", "clean", "compress", "ocr", "author", "format", "adjust", "crop", "crop_box", "dups",
              "bookmarks")


# ---------- updates: a newer release on GitHub ----------
REPO = "ygorbetine/PageCapture"
RELEASES_URL = f"https://github.com/{REPO}/releases"


def version_tuple(tag):
    """'v2.1' / '2.1.0' -> (2, 1, 0): only the numbers count."""
    return tuple(int(n) for n in re.findall(r"\d+", str(tag))) or (0,)


def check_update(timeout=6):
    """Latest published release as dict(tag, url, asset), or None when GitHub cannot be reached.
    First the public API (it also gives the .zip link); if that is refused (hourly limit) the
    /releases/latest redirect, which gives the tag without any limit."""
    ua = {"User-Agent": f"PageCapture/{VERSION}"}
    try:
        req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases/latest",
                                     headers={**ua, "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8"))
        tag = d.get("tag_name") or ""
        if tag:
            asset = next((a.get("browser_download_url") for a in d.get("assets", [])
                          if str(a.get("name", "")).lower().endswith(".zip")), None)
            return dict(tag=tag, url=d.get("html_url") or f"{RELEASES_URL}/tag/{tag}", asset=asset)
    except Exception:
        pass
    try:
        with urllib.request.urlopen(urllib.request.Request(f"{RELEASES_URL}/latest", headers=ua),
                                    timeout=timeout) as r:
            final = r.geturl()
        m = re.search(r"/releases/tag/([^/?#]+)", final)
        if m:
            return dict(tag=urllib.parse.unquote(m.group(1)), url=final, asset=None)
    except Exception:
        pass
    return None


# ---------- images: trim borders, adjust ----------
def auto_crop_box(arr, tol=28, pad=6):
    """(left, top, right, bottom) of the page content inside plain borders (reader bars, margins).
    None when the borders are not a plain colour or nothing sensible is found."""
    h, w = arr.shape[:2]
    if h < 40 or w < 40:
        return None
    edge = np.concatenate([arr[:3].reshape(-1, 3), arr[-3:].reshape(-1, 3),
                           arr[:, :3].reshape(-1, 3), arr[:, -3:].reshape(-1, 3)]).astype(np.int16)
    if edge.std(axis=0).max() > 40:  # the edges are not one flat colour: nothing to trim
        return None
    bg = np.median(edge, axis=0)
    diff = np.abs(arr.astype(np.int16) - bg).max(axis=2) > tol
    rows = np.where(diff.mean(axis=1) > 0.004)[0]
    cols = np.where(diff.mean(axis=0) > 0.004)[0]
    if not len(rows) or not len(cols):
        return None
    top, bottom = max(0, int(rows[0]) - pad), min(h, int(rows[-1]) + 1 + pad)
    left, right = max(0, int(cols[0]) - pad), min(w, int(cols[-1]) + 1 + pad)
    if (bottom - top) * (right - left) < 0.35 * h * w:  # would cut away most of the page: not a border
        return None
    return left, top, right, bottom


def parse_box(s):
    """'l,t,r,b' (fractions of the page, saved by the manual crop) -> [l, t, r, b] or None."""
    try:
        v = [float(x) for x in str(s).split(",")]
        if len(v) == 4 and 0 <= v[0] < v[2] <= 1 and 0 <= v[1] < v[3] <= 1:
            return v
    except ValueError:
        pass
    return None


def process_image(im, crop="none", box=None, adjust="original"):
    """Trim the borders (auto / manual box) and adjust a page image (sharper, gray, black and white)."""
    if crop == "auto":
        b = auto_crop_box(np.asarray(im.convert("RGB")))
        if b:
            im = im.crop(b)
    elif crop == "manual" and box:
        w, h = im.size
        im = im.crop((round(box[0] * w), round(box[1] * h), round(box[2] * w), round(box[3] * h)))
    if adjust == "sharp":
        im = im.convert("RGB").filter(ImageFilter.UnsharpMask(radius=1.6, percent=130, threshold=3))
    elif adjust == "gray":
        im = ImageOps.grayscale(im)
    elif adjust == "bw":
        g = np.asarray(ImageOps.grayscale(im))
        im = Image.fromarray(cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                   cv2.THRESH_BINARY, 31, 12))
    return im


# ---------- repeated pages ----------
def _small(gray):
    return cv2.resize(gray, (64, 64), interpolation=cv2.INTER_AREA).astype(np.float32)


def sig_equal(a, b):
    d = np.abs(a - b)
    return bool(d.mean() < 1.5 and (d > 30).mean() < 0.004)


def sig_percent(a, b):
    return int(round(100 - float(np.abs(a - b).mean()) / 255 * 100))


def array_sig(img_rgb):
    return _small(cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY))


def same_page(a, b):
    """True when two captured frames (RGB arrays) show the same page."""
    return sig_equal(array_sig(a), array_sig(b))


_SIGS = {}


def page_sig(path):
    """Small gray signature of a page image (cached while the file does not change)."""
    try:
        st = os.stat(path)
        key = (path, st.st_mtime_ns, st.st_size)
        if key not in _SIGS:
            g = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_GRAYSCALE)  # also works with accents in the path
            _SIGS[key] = _small(g) if g is not None else None
        return _SIGS[key]
    except OSError:
        return None


def find_duplicates(pages):
    """{page: previous page it repeats} for consecutive pages that look the same."""
    out, prev = {}, None
    for n, p in pages:
        s = page_sig(p)
        if prev is not None and s is not None and prev[1] is not None and sig_equal(prev[1], s):
            out[n] = prev[0]
        prev = (n, s)
    return out


# ---------- managing the pages of a project ----------
def reorder_pages(temp, order):
    """Rebuild page_001..N.png from `order`: page numbers (int) already in the project or image file
    paths (str) to insert. Pages that are not listed are deleted. Returns {old number: new number}."""
    stash = {}
    for n, p in list_pages(temp):
        tmp = os.path.join(temp, f"_move_{n:05d}.png")
        os.replace(p, tmp)
        stash[n] = tmp
    mapping = {}
    for new_n, item in enumerate(order, 1):
        dst = os.path.join(temp, f"page_{new_n:03d}.png")
        if isinstance(item, int):
            os.replace(stash.pop(item), dst)
            mapping[item] = new_n
        else:
            Image.open(item).convert("RGB").save(dst)
    for tmp in stash.values():
        try:
            os.remove(tmp)
        except OSError:
            pass
    return mapping


def remap_meta(meta, mapping):
    """Move the marks and bookmarks of a project to the new page numbers."""
    meta["marked"] = sorted({mapping[int(m)] for m in meta.get("marked", []) if int(m) in mapping})
    meta["bookmarks"] = {str(mapping[int(k)]): v for k, v in (meta.get("bookmarks") or {}).items()
                         if int(k) in mapping}
    return meta


# ---------- updates that install themselves ----------
UPDATE_FILES = ("page_capture.py", "Installer.bat", "PageCapture.ico")


def download_file(url, dest, progress=None, cancel=None, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": f"PageCapture/{VERSION}"})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            if cancel is not None and cancel.is_set():
                raise RuntimeError("cancelled")
            chunk = r.read(65536)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)


def find_release_root(folder):
    """Folder (inside an extracted zip) that holds page_capture.py."""
    for base, _dirs, files in os.walk(folder):
        if "page_capture.py" in files:
            return base
    return None


def release_version(root):
    try:
        with open(os.path.join(root, "page_capture.py"), encoding="utf-8") as f:
            m = re.search(r'^VERSION = "([^"]+)"', f.read(), re.M)
        return m.group(1) if m else None
    except OSError:
        return None


def apply_update_files(src, dest, backup):
    """Copy the new program files over the old ones; the old ones are kept in `backup` and put back on failure."""
    os.makedirs(backup, exist_ok=True)
    jobs = [(n, os.path.join(src, n), os.path.join(dest, n)) for n in UPDATE_FILES]
    for sub in ("fonts", "tessdata"):
        sf = os.path.join(src, sub)
        if os.path.isdir(sf):
            jobs += [(sub + "/" + f, os.path.join(sf, f), os.path.join(dest, sub, f)) for f in os.listdir(sf)]
    done = []
    try:
        for rel, s, d in jobs:
            if not os.path.isfile(s):
                continue
            os.makedirs(os.path.dirname(d), exist_ok=True)
            if os.path.isfile(d):
                b = os.path.join(backup, rel.replace("/", "__"))
                shutil.copy2(d, b)
                done.append((d, b))
            else:
                done.append((d, None))
            shutil.copy2(s, d)
    except Exception:
        for d, b in done:
            try:
                shutil.copy2(b, d) if b else os.remove(d)
            except OSError:
                pass
        raise


def updater_script(root, exe, tag, backup_exe):
    """Batch file that waits for the app to close, rebuilds it with Installer.bat and opens it again.
    If the build fails the previous program is put back."""
    name = os.path.basename(exe)
    return "\r\n".join([
        "@echo off",
        "chcp 65001 >nul",
        "title Page Capture - updating",
        f"echo Updating Page Capture to {tag}. This takes a few minutes, please wait...",
        ":wait",
        f'tasklist /fi "imagename eq {name}" 2>nul | find /i "{name}" >nul',
        "if not errorlevel 1 (",
        "    timeout /t 1 /nobreak >nul",
        "    goto wait",
        ")",
        f'copy /y "{exe}" "{backup_exe}" >nul 2>nul',
        f'call "{os.path.join(root, "Installer.bat")}" /auto',
        "if errorlevel 1 (",
        "    echo.",
        "    echo The update failed. Putting the previous version back...",
        f'    copy /y "{backup_exe}" "{exe}" >nul',
        "    pause",
        ")",
        f'start "" "{exe}"',
        "exit",
        ""])


def eta_text(seconds):
    s = max(0, int(seconds))
    return t("eta_sec", n=max(5, round(s / 5) * 5)) if s < 60 else t("eta_min", n=max(1, round(s / 60)))


# ---------- extra windows: page viewer, manual crop, options, folders, update progress ----------
def new_window(root, title, W, H, cards):
    """Themed fixed-size window with the brand background. Returns (window, canvas); sizes in design units."""
    top = tk.Toplevel(root)
    top.title(title)
    top.resizable(False, False)
    top.attributes("-topmost", True)
    c = tk.Canvas(top, width=U(W), height=U(H), highlightthickness=0, bd=0, bg=BLACK)
    c.pack()
    img = bg_image(U(W), U(H), [tuple(U(v) for v in card) for card in cards])
    c.create_image(0, 0, image=img, anchor="nw")
    c.image = img
    ref = (root.winfo_rootx() + root.winfo_width() // 2, root.winfo_rooty() + root.winfo_height() // 2) \
        if root.state() == "normal" else (0, 0)
    center(top, U(W), U(H), ref)
    return top, c


def small_entry(c, var, x, y, w, h=32, numeric=False):
    e = tk.Entry(c, textvariable=var, bg=INPUT_BG, fg=LIGHT, insertbackground=LIGHT, relief="flat", bd=U(6),
                 highlightthickness=1, highlightbackground=LINE, highlightcolor=PURPLE_LT, font=F(13),
                 selectbackground=PURPLE, selectforeground=LIGHT)
    c.create_window(U(x), U(y), window=e, anchor="nw", width=U(w), height=U(h), tags="dyn")
    return e


class PageViewer(tk.Toplevel):
    """One page of a project in a big view, with the actions that change the pages of the project."""
    W, H = 800, 560

    def __init__(self, app, info, n):
        super().__init__(app.root)
        self.app, self.temp, self.name = app, info["temp"], info["name"]
        self.resizable(False, False)
        self.attributes("-topmost", True)
        W, H = U(self.W), U(self.H)
        self.c = tk.Canvas(self, width=W, height=H, highlightthickness=0, bd=0, bg=BLACK)
        self.c.pack()
        self.bg = bg_image(W, H, [tuple(U(v) for v in card) for card in ((16, 16, 536, 544), (552, 16, 784, 544))])
        self.c.create_image(0, 0, image=self.bg, anchor="nw")
        self.widgets, self.photo, self.n = [], None, n
        ref = (app.root.winfo_rootx() + app.root.winfo_width() // 2, app.root.winfo_rooty() + app.root.winfo_height() // 2)
        center(self, W, H, ref)
        self.bind("<Left>", lambda e: self.step(-1) if e.widget is self else None)
        self.bind("<Right>", lambda e: self.step(1) if e.widget is self else None)
        self.bind("<Escape>", lambda e: self.destroy())
        self.reload(n)
        self.focus_force()

    # --- data ---
    def reload(self, n):
        self.pages = list_pages(self.temp)
        if not self.pages:
            self.destroy()
            return
        self.nums = [p[0] for p in self.pages]
        self.n = n if n in self.nums else min(self.nums, key=lambda k: abs(k - n))
        self.dups = find_duplicates(self.pages)
        self.draw()

    def step(self, d):
        i = self.nums.index(self.n) + d
        if 0 <= i < len(self.nums):
            self.n = self.nums[i]
            self.draw()

    def meta(self):
        return load_meta(self.temp)

    # --- drawing ---
    def add_btn(self, x, y, w, h, text, cmd, kind="secondary", size=12):
        b = Btn(self.c, U(x), U(y), U(w), U(h), text, cmd, kind, size)
        self.c.addtag_withtag("dyn", b.tag)
        return b

    def pill(self, x, y, text, fill, outline, fg):
        c = self.c
        w = tkfont.Font(font=F(12, True)).measure(text) + U(22)
        c.create_polygon(rr_points(U(x), U(y), U(x) + w, U(y) + U(24), U(12)), smooth=True, fill=fill, outline=outline,
                         tags="dyn")
        c.create_text(U(x) + w / 2, U(y + 12), text=text, fill=fg, font=F(12, True), tags="dyn")

    def draw(self):
        c, n = self.c, self.n
        c.delete("dyn")
        for w in self.widgets:
            try:
                w.destroy()
            except tk.TclError:
                pass
        self.widgets = []
        self.title(t("pv_title", n=n) + " · " + self.name)
        path = dict(self.pages)[n]
        im = Image.open(path).convert("RGB")
        im.thumbnail((U(480), U(446)), Image.LANCZOS)
        self.photo = ImageTk.PhotoImage(im)
        cx, cy = U(276), U(254)
        c.create_image(cx, cy, image=self.photo, tags="dyn")
        c.create_rectangle(cx - im.width // 2, cy - im.height // 2, cx + im.width // 2, cy + im.height // 2,
                           outline=LINE, tags="dyn")
        i = self.nums.index(n)
        pb = self.add_btn(128, 494, 110, 32, t("pv_prev"), lambda: self.step(-1))
        nb = self.add_btn(314, 494, 110, 32, t("pv_next"), lambda: self.step(1))
        pb.set_enabled(i > 0)
        nb.set_enabled(i < len(self.nums) - 1)
        c.create_text(U(276), U(510), text=t("pv_of", n=i + 1, t=len(self.nums)), fill=MUTED, font=F(13), tags="dyn")

        # right column
        meta = self.meta()
        marked = n in {int(m) for m in meta.get("marked", [])}
        c.create_text(U(572), U(44), anchor="w", text=t("pv_title", n=n).upper(), fill=LIGHT, font=F(12, True), tags="dyn")
        c.create_line(U(572), U(62), U(764), U(62), fill=PURPLE_LT, width=max(2, U(2)), tags="dyn")
        y = 74
        if marked:
            self.pill(572, y, t("pv_marked"), "#3C1A3E", PURPLE_LT, LIGHT)
            y += 30
        dup = self.dups.get(n)
        if dup:
            a, b = page_sig(path), page_sig(dict(self.pages)[dup])
            pct = sig_percent(a, b) if a is not None and b is not None else 99
            self.pill(572, y, t("pv_same", m=dup, p=pct), "#2B2C14", YELLOW, YELLOW)
            y += 30
            self.add_btn(572, y, 192, 30, t("pv_del_dup"), self.delete_page)
            y += 38
        self.add_btn(572, y, 192, 30, t("pv_unmark") if marked else t("pv_mark"), self.toggle_mark)
        y += 40
        c.create_text(U(572), U(y + 8), anchor="w", text=t("pv_bookmark"), fill="#C8CBDB", font=F(12), tags="dyn")
        self.bk_var = tk.StringVar(value=str((meta.get("bookmarks") or {}).get(str(n), "")))
        e = small_entry(c, self.bk_var, 572, y + 21, 192)
        e.bind("<Return>", lambda _e: self.save_bookmark())
        e.bind("<FocusOut>", lambda _e: self.save_bookmark())
        self.widgets.append(e)
        y += 62
        self.add_btn(572, y, 192, 30, t("pv_insert"), self.insert_after)
        y += 38
        c.create_text(U(572), U(y + 15), anchor="w", text=t("pv_move"), fill="#C8CBDB", font=F(12), tags="dyn")
        self.mv_var = tk.StringVar(value=str(n))
        e2 = small_entry(c, self.mv_var, 660, y, 56, 30)
        self.widgets.append(e2)
        self.add_btn(724, y, 40, 30, "OK", self.move_page)
        self.add_btn(572, 470, 192, 30, t("pv_delete"), self.delete_page)
        self.add_btn(572, 506, 192, 30, t("pv_close"), self.destroy, kind="primary")

    # --- actions ---
    def toggle_mark(self):
        meta = self.meta()
        marked = {int(m) for m in meta.get("marked", [])} ^ {self.n}
        meta["marked"] = sorted(marked)
        save_meta(self.temp, meta)
        self.app.pages_changed()
        self.draw()

    def save_bookmark(self):
        try:
            text = self.bk_var.get().strip()
        except (tk.TclError, AttributeError):
            return
        meta = self.meta()
        bk = dict(meta.get("bookmarks") or {})
        if text == str(bk.get(str(self.n), "")):
            return
        if text:
            bk[str(self.n)] = text
        else:
            bk.pop(str(self.n), None)
        meta["bookmarks"] = bk
        save_meta(self.temp, meta)
        self.app.pages_changed()

    def apply(self, order, focus=None):
        """Rebuild the page files from `order`, keep marks and bookmarks with their pages."""
        mapping = reorder_pages(self.temp, order)
        save_meta(self.temp, remap_meta(self.meta(), mapping))
        self.app.pages_changed()
        self.reload(mapping.get(focus, self.n) if focus is not None else self.n)

    def delete_page(self):
        n = self.n
        if dialog(self.app.root, t("pv_delete"), t("pv_del_q", n=n),
                  [(t("pv_delete"), "primary"), (t("b_cancel"), "secondary")]) != 0:
            return
        self.apply([m for m in self.nums if m != n], focus=None)

    def insert_after(self):
        paths = filedialog.askopenfilenames(parent=self, title=t("pv_insert_pick"),
                                            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.webp"), ("*", "*.*")])
        if not paths:
            return
        i = self.nums.index(self.n)
        self.apply(self.nums[:i + 1] + [str(p) for p in paths] + self.nums[i + 1:], focus=self.n)

    def move_page(self):
        try:
            to = int(self.mv_var.get())
            assert 1 <= to <= len(self.nums)
        except (ValueError, AssertionError):
            self.app.alert(t("d_range_t"), t("d_range"))
            return
        order = [m for m in self.nums if m != self.n]
        order.insert(to - 1, self.n)
        self.apply(order, focus=self.n)


class CropDialog:
    """Drag over a sample page: the part inside the rectangle is kept on every page. run() -> [l, t, r, b] as
    fractions of the page, or None when cancelled."""

    def __init__(self, root, img, box=None):
        self.root, self.img, self.box, self.result = root, img, box, None

    def run(self):
        W, H = 720, 580
        top, c = new_window(self.root, t("crop_t"), W, H, [(10, 10, 710, 570)])
        c.create_text(U(28), U(26), anchor="nw", text=t("crop_t"), fill=LIGHT, font=F(17, semibold=True))
        c.create_text(U(28), U(58), anchor="nw", text=t("crop_hint"), fill="#C8CBDB", font=F(12))
        im = self.img.copy()
        im.thumbnail((U(664), U(404)), Image.LANCZOS)
        photo = ImageTk.PhotoImage(im)
        ox, oy = U(28) + (U(664) - im.width) // 2, U(88)
        c.create_image(ox, oy, image=photo, anchor="nw")
        c.photo = photo
        w, h = im.width, im.height
        rect = [0.0, 0.0, 1.0, 1.0] if not self.box else list(self.box)
        state = {"start": None}

        def draw():
            c.delete("ov")
            x1, y1, x2, y2 = ox + rect[0] * w, oy + rect[1] * h, ox + rect[2] * w, oy + rect[3] * h
            for a in ((ox, oy, ox + w, y1), (ox, y2, ox + w, oy + h), (ox, y1, x1, y2), (x2, y1, ox + w, y2)):
                if a[2] > a[0] and a[3] > a[1]:
                    c.create_rectangle(*a, fill=BLACK, stipple="gray50", outline="", tags="ov")
            c.create_rectangle(x1, y1, x2, y2, outline=YELLOW, width=2, tags="ov")

        def clamp(e):
            return (min(1.0, max(0.0, (c.canvasx(e.x) - ox) / w)), min(1.0, max(0.0, (c.canvasy(e.y) - oy) / h)))

        def down(e):
            state["start"] = clamp(e)

        def move(e):
            if state["start"]:
                x, y = clamp(e)
                sx, sy = state["start"]
                rect[:] = [min(sx, x), min(sy, y), max(sx, x), max(sy, y)]
                draw()

        def ok():
            if rect[2] - rect[0] > 0.05 and rect[3] - rect[1] > 0.05:
                self.result = list(rect)
            top.destroy()

        def reset():
            rect[:] = [0.0, 0.0, 1.0, 1.0]
            draw()

        c.bind("<ButtonPress-1>", down)
        c.bind("<B1-Motion>", move)
        c.bind("<ButtonRelease-1>", move)
        Btn(c, U(28), U(H - 26 - 40), U(150), U(40), t("crop_reset"), reset, "secondary")
        Btn(c, U(W - 28 - 100), U(H - 26 - 40), U(100), U(40), "OK", ok, "primary")
        Btn(c, U(W - 28 - 210), U(H - 26 - 40), U(100), U(40), t("b_cancel"), top.destroy, "secondary")
        draw()
        top.update()
        top.lift()
        self.root.wait_window(top)
        return self.result


class UpdateWindow(tk.Toplevel):
    """Progress of a self-installing update: download, prepare the files, restart."""

    def __init__(self, root, tag):
        super().__init__(root)
        self.title(t("upd_prog_t", new=tag))
        self.resizable(False, False)
        self.attributes("-topmost", True)
        W, H = U(480), U(330)
        self.c = c = tk.Canvas(self, width=W, height=H, highlightthickness=0, bd=0, bg=BLACK)
        c.pack()
        self.bg = bg_image(W, H, [(U(10), U(10), W - U(10), H - U(10))])
        c.create_image(0, 0, image=self.bg, anchor="nw")
        c.create_text(U(30), U(28), anchor="nw", text=t("upd_prog_t", new=tag), fill=LIGHT, font=F(18, semibold=True))
        self.dots, self.labels = [], []
        for i, key in enumerate(("upd_s1", "upd_s2", "upd_s3")):
            y = U(84 + i * 32)
            d = c.create_oval(U(30), y - U(10), U(50), y + U(10), fill=INPUT_BG, outline=LINE)
            tx = c.create_text(U(40), y, text=str(i + 1), fill=LIGHT, font=F(11, True))
            lb = c.create_text(U(62), y, anchor="w", text=t(key), fill=MUTED, font=F(14))
            self.dots.append((d, tx))
            self.labels.append(lb)
        self.bx, self.bw, self.by = U(30), U(420), U(196)
        round_rect(c, self.bx, self.by, self.bx + self.bw, self.by + U(10), U(5), fill=INPUT_BG, outline=LINE)
        self.fill = c.create_polygon(rr_points(self.bx, self.by, self.bx + 2, self.by + U(10), 1), smooth=True,
                                     fill=PURPLE, outline="")
        c.create_text(U(30), U(226), anchor="w", text=t("upd_dont"), fill=MUTED, font=F(12))
        self.cancel_cmd = lambda: None
        self.cancel_btn = Btn(c, W - U(30) - U(110), H - U(28) - U(40), U(110), U(40), t("b_cancel"), self._cancel)
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        center(self, W, H, (root.winfo_rootx() + root.winfo_width() // 2, root.winfo_rooty() + root.winfo_height() // 2)
               if root.state() == "normal" else (0, 0))
        self.step(0)

    def _cancel(self):
        self.cancel_cmd()

    def step(self, i):
        for k, (d, tx) in enumerate(self.dots):
            done, now = k < i, k == i
            self.c.itemconfig(d, fill=PURPLE if done else INPUT_BG, outline=PURPLE_LT if done else (YELLOW if now else LINE))
            self.c.itemconfig(tx, text="✓" if done else str(k + 1), fill=YELLOW if now else LIGHT)
            self.c.itemconfig(self.labels[k], fill=LIGHT if (done or now) else MUTED)
        self.progress(0 if i == 0 else 1)
        if i >= 2:
            self.cancel_btn.set_enabled(False)

    def progress(self, frac):
        frac = min(1.0, max(0.0, frac))
        self.c.coords(self.fill, *rr_points(self.bx, self.by, self.bx + max(U(10), frac * self.bw), self.by + U(10), U(5)))


# ---------- main app ----------
class App:
    LW, LH = 1000, 640  # logical window size
    BAR_BOTTOM = 574    # bottom edge of the status bar; the signature is centred below it

    def __init__(self, root):
        self.root = root
        self.settings = load_settings()
        load_fonts(root)
        apply_icon(root)
        LANG[0] = self.settings.get("lang", "en") if self.settings.get("lang") in ("en", "pt") else "en"
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        SCALE[0] = max(0.7, min(root.winfo_fpixels("1i") / 96 * ZOOM, (sh - 90) / self.LH, (sw - 40) / self.LW))
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
        self.log_visible = False  # the standalone log starts closed; the button shows / hides it
        self.log_capture = True   # while capturing, the log is open inside the capture window
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
            "ocr": tk.BooleanVar(value=False),
            "pfrom": tk.StringVar(value="1"),
            "pto": tk.StringVar(value=""),
            "title": tk.StringVar(value=""),
            "author": tk.StringVar(value=""),
            "format": tk.StringVar(value="pdf"),
            "adjust": tk.StringVar(value="original"),
            "crop": tk.StringVar(value="none"),
            "crop_box": tk.StringVar(value=""),
            "dups": tk.BooleanVar(value=False),
            "bookmarks": tk.BooleanVar(value=True),
            "cp_level": tk.StringVar(value="balanced"),
            "cp_gray": tk.BooleanVar(value=False),
            "cp_split": tk.BooleanVar(value=False),
        }
        self.cp_src, self.cp_out, self.cp_info, self.cp_result, self.cp_busy = "", "", "", "", False
        self.cp_done_path = ""
        self.cp_est_cache, self.cp_est_token, self.cp_est_item = {}, None, None
        for k in ("cp_level", "cp_gray", "cp_split"):
            self.vars[k].trace_add("write", self.cp_estimate)
        self.apply_fields(self.settings.get("fields", {}))  # remembered from the last session
        self.name_auto = False  # True while the name box holds a name the app detected (not typed)
        self._setting_name = False
        self.vars["name"].trace_add("write", self._name_edited)
        self.c = None
        self.tab = "capture"
        self.projects, self.sel_name = [], None
        self.list_offset, self.page_offset = 0, 0
        self.proj_filter = "all"
        self.proj_search = tk.StringVar(value="")
        self.proj_search.trace_add("write", self.on_search)
        self.preset_name = ""
        self.recap_active, self.recap_runs = False, []
        self.update_info = None  # set when a newer release is found: the version number turns yellow
        self._dups, self._dups_busy, self._crop_segs = {}, set(), []
        self.regions, self._cur_widgets = {}, []
        self.region_btn = self.start_btn = None
        self.name_btns = []
        self.refresh_projects(draw=False)
        self.build_ui()
        keyboard.Listener(on_press=self.on_key).start()  # fallback when RegisterHotKey is unavailable
        self.root.after(300, self.apply_log)
        self.root.after(2500, self.start_update_check)

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
        data["fields"] = self.collect_fields()
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
        self.c = c = tk.Canvas(self.root, width=W, height=H, highlightthickness=0, bd=0, bg=BLACK)
        c.pack()
        self.regions = {}
        self._cur_widgets = []
        self.bg_item = c.create_image(0, 0, anchor="nw")
        self.set_cards([])

        # header: title, section tabs, language and hints
        c.create_text(U(22), U(30), anchor="w", text="Page Capture", fill=LIGHT, font=F(28, semibold=True))
        c.create_text(U(24), U(56), anchor="w", text=t("subtitle"), fill=MUTED, font=F(13))
        self.tabbar = TabBar(c, U(500), U(36), [("capture", t("tab_capture")), ("projects", t("tab_projects")), ("compress", t("tab_compress"))],
                             self.tab, self.switch_tab)
        self.tabbar.set_count("projects", len(self.projects))
        Segmented(c, U(874), U(14), U(104), U(28), [("EN", "en"), ("BR", "pt")], v["lang"], self.change_lang, size=12)
        ver_font = FB(13, underline=True)  # clicking it checks for updates (or installs the one it found)
        self.ver_item = c.create_text(U(978), U(58), anchor="e", text=f"v{VERSION}",
                                      fill=YELLOW if self.update_info else MUTED, font=ver_font, tags="verlink")
        vw = tkfont.Font(font=ver_font).measure(f"v{VERSION}")
        c.create_text(U(978) - vw - U(8), U(58), anchor="e", text=f"{t('hint_keys')} ·", fill=MUTED, font=F(12))
        c.tag_bind("verlink", "<Button-1>", lambda e: self.version_click())
        c.tag_bind("verlink", "<Enter>", lambda e: c.config(cursor="hand2"))
        c.tag_bind("verlink", "<Leave>", lambda e: c.config(cursor=""))

        # signature: centred between the bottom bar and the end of the window
        c.create_text(W // 2, U((self.BAR_BOTTOM + self.LH) / 2), text=f"{AUTHOR}  ·  {SUITE}", fill=MUTED,
                      font=F(12, True))
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            c.bind(seq, self.on_wheel)
        self.render_tab()
        if not getattr(self.root, "_drop_proc", None):  # once: the window can be rebuilt (language change)
            self.root.update_idletasks()
            enable_file_drop(self.root, self.on_files_dropped)

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

    # --- drawing helpers ---
    def describe_thresh(self, val):
        return t("strict") if val >= 0.95 else t("balanced") if val >= 0.85 else t("flexible")

    def set_cards(self, cards):
        W, H = U(self.LW), U(self.LH)
        self.bg = bg_image(W, H, [tuple(U(n) for n in card) for card in cards])
        self.c.itemconfig(self.bg_item, image=self.bg)

    def draw_region(self, name, builder):
        """Draw `builder` as a named region: everything it creates is removed together on the next redraw."""
        self.clear_region(name)
        before = set(self.c.find_all())
        self._cur_widgets = []
        builder()
        self.regions[name] = ([i for i in self.c.find_all() if i not in before], self._cur_widgets)

    def clear_region(self, name):
        items, widgets = self.regions.pop(name, ([], []))
        for w in widgets:
            try:
                w.destroy()
            except tk.TclError:
                pass
        for i in items:
            self.c.delete(i)

    def card_title(self, x1, top, x2, text, step=None, tall=False):
        """Numbered title with a purple rule under it. Returns the y of the rule."""
        c = self.c
        cy = top + 18 + (15 if tall else 11)
        tx = x1 + 20
        if step is not None:
            c.create_oval(U(x1 + 20), U(cy - 11), U(x1 + 42), U(cy + 11), fill=PURPLE, outline=PURPLE_LT)
            c.create_text(U(x1 + 31), U(cy), text=str(step), fill=LIGHT, font=F(12, True))
            tx = x1 + 52
        c.create_text(U(tx), U(cy), anchor="w", text=text.upper(), fill=LIGHT, font=F(12, True))
        y = top + (59 if tall else 51)
        c.create_line(U(x1 + 20), U(y), U(x2 - 20), U(y), fill=PURPLE_LT, width=max(2, U(2)))
        return y

    def entry(self, var, x, y, w, h=32, ph=None):
        e = tk.Entry(self.c, textvariable=var, bg=INPUT_BG, fg=LIGHT, insertbackground=LIGHT, relief="flat",
                     bd=U(6), highlightthickness=1, highlightbackground=LINE, highlightcolor=PURPLE_LT,
                     font=F(13), selectbackground=PURPLE, selectforeground=LIGHT, disabledbackground=INPUT_BG,
                     disabledforeground=DIM)
        self.c.create_window(U(x), U(y), window=e, anchor="nw", width=U(w), height=U(h))
        self._cur_widgets.append(e)
        if ph:
            add_placeholder(e, var, ph)
        return e

    def field_above(self, label, key, x, y, w, ph=None, h=32):
        lab = self.c.create_text(U(x), U(y + 8), anchor="w", text=label, fill="#C8CBDB", font=F(12))
        return lab, self.entry(self.vars[key], x, y + 21, w, h, ph)

    # --- tabs ---
    def cards_capture(self):
        return [(22, 72, 314, 512), (330, 72, 670, 512), (686, 72, 978, 512), (22, 526, 684, 574)]

    def cards_projects(self):
        return [(22, 72, 462, 512), (478, 72, 978, 512), (22, 526, 846, 574)]

    def render_tab(self):
        for name in list(self.regions):
            self.clear_region(name)
        self.region_btn = self.start_btn = None
        self.name_btns = []
        if self.tab == "compress":
            self.set_cards([(22, 72, 978, 512), (22, 526, 846, 574)])
            self.draw_region("tab", self.build_compress)
        elif self.tab == "projects":
            self.refresh_projects(draw=False)
            self.set_cards(self.cards_projects())
            self.draw_region("tab", self.build_projects_static)
            self.draw_region("list", self.draw_list)
            self.draw_region("detail", self.draw_detail)
        else:
            self.set_cards(self.cards_capture())
            self.draw_region("tab", self.build_capture)
            self.update_mode()
            self.update_source()

    def switch_tab(self, key):
        if self.running or key == self.tab:
            return
        self.tab = key
        self.tabbar.set(key)
        self.render_tab()

    # --- Compress tab ---
    def build_compress(self):
        c, v = self.c, self.vars
        self.card_title(22, 72, 978, t("cp_title"), None, tall=True)
        c.create_text(U(42), U(144), anchor="nw", width=U(900), text=t("cp_hint"), fill=MUTED, font=F(13))
        Btn(c, U(42), U(184), U(170), U(38), t("cp_pick"), self.cp_pick, kind="primary", size=13)
        shown = os.path.basename(self.cp_src) if self.cp_src else t("cp_none")
        c.create_text(U(228), U(196), anchor="w", text=fit_text(shown, F(14, True), U(720)), fill=LIGHT, font=F(14, True))
        if self.cp_info:
            c.create_text(U(228), U(216), anchor="w", text=self.cp_info, fill=MUTED, font=F(12))
        c.create_text(U(42), U(268), anchor="w", text=t("cp_level"), fill="#C8CBDB", font=F(12))
        Segmented(c, U(42), U(282), U(560), U(40),
                  [(t("comp_light"), "light"), (t("comp_balanced"), "balanced"), (t("comp_strong"), "strong"),
                   (t("comp_extreme"), "extreme")], v["cp_level"], size=12)
        self.cp_est_item = c.create_text(U(958), U(268), anchor="e", text="", fill=YELLOW, font=F(12, True))
        self.cp_estimate()
        Check(c, U(626), U(284), t("cp_gray"), v["cp_gray"])
        Check(c, U(626), U(308), t("cp_split"), v["cp_split"])
        c.create_text(U(42), U(346), anchor="w", text=t("cp_save_as"), fill="#C8CBDB", font=F(12))
        round_rect(c, U(42), U(360), U(840), U(394), U(10), fill=INPUT_BG, outline=LINE)
        c.create_text(U(56), U(377), anchor="w", text=fit_text(self.cp_out or "—", F(12), U(770)), fill=LIGHT, font=F(12))
        Btn(c, U(852), U(360), U(106), U(34), t("cp_change"), self.cp_change_out, size=12)
        self.cp_run_btn = Btn(c, U(808), U(446), U(150), U(46), t("cp_run"), self.cp_run, kind="primary", size=14)
        self.cp_run_btn.set_enabled(bool(self.cp_src) and not self.cp_busy, "primary")
        if self.cp_result:
            c.create_text(U(42), U(408), anchor="nw", width=U(740), text=self.cp_result, fill=LIGHT, font=F(13))
        if self.cp_done_path:
            Btn(c, U(42), U(476), U(130), U(28), t("cp_open"), lambda: open_path(self.cp_done_path), size=12)
            Btn(c, U(182), U(476), U(130), U(28), t("cp_folder"),
                lambda: open_path(os.path.dirname(self.cp_done_path)), size=12)
        self.build_bar(True)
        if not self.cp_busy:
            c.itemconfig(self.status_item, text=t("cp_status"))

    def cp_estimate(self, *_):
        """Show the expected size after compression (sampled in the background; cached per file / options)."""
        if not getattr(self, "cp_est_item", None) or self.tab != "compress":
            return
        v = self.vars
        key = (self.cp_src, v["cp_level"].get(), v["cp_gray"].get())

        def show(text):
            try:
                self.c.itemconfig(self.cp_est_item, text=text)
            except tk.TclError:
                pass

        if not self.cp_src:
            show("")
            return
        before = os.path.getsize(self.cp_src) if os.path.isfile(self.cp_src) else 0
        if key in self.cp_est_cache:
            show(self.cp_est_text(self.cp_est_cache[key], before))
            return
        show(t("cp_est_wait"))
        self.cp_est_token = tok = object()

        def work():
            try:
                size = estimate_size(*key)
            except Exception:
                size = None
            self.ui(done, size)

        def done(size):
            if tok is not self.cp_est_token:  # the user changed something meanwhile
                return
            if size is None:
                show("")
                return
            self.cp_est_cache[key] = size
            show(self.cp_est_text(size, before))
        threading.Thread(target=work, daemon=True).start()

    def cp_est_text(self, size, before):
        ratio = size / before if before else 1
        if ratio > 0.97:
            return t("cp_est_none")
        pct = round((1 - ratio) * 100)
        if self.vars["cp_split"].get():
            return t("cp_est_split", size=mb(size), half=mb(size / 2), pct=pct)
        return t("cp_est", size=mb(size), pct=pct)

    def cp_pick(self):
        if self.cp_busy:
            return
        path = filedialog.askopenfilename(parent=self.root, title=t("cp_pick_title"), filetypes=[("PDF", "*.pdf")])
        if path:
            self.cp_set_src(path)

    def on_files_dropped(self, files):
        """A file was dragged onto the window: a PDF goes straight to the Compress tab."""
        pdfs = [f for f in files if f.lower().endswith(".pdf")]
        if not pdfs or self.running or self.cp_busy:
            return
        self.tab = "compress"
        self.tabbar.set("compress")
        self.cp_set_src(pdfs[0])
        self.root.lift()

    def cp_set_src(self, path):
        self.cp_src, self.cp_result, self.cp_done_path = path, "", ""
        try:
            from pypdf import PdfReader
            pages = len(PdfReader(path).pages)
        except Exception:
            pages = "?"
        self.cp_info = t("cp_info", pages=pages, size=mb(os.path.getsize(path)))
        out_dir = self.vars["out"].get()
        os.makedirs(out_dir, exist_ok=True)
        stem = os.path.splitext(os.path.basename(path))[0]
        self.cp_out = unique_file(os.path.join(out_dir, stem + " (" + t("cp_run").lower() + ").pdf"))
        self.render_tab()

    def cp_change_out(self):
        path = filedialog.asksaveasfilename(
            parent=self.root, title=t("cp_save_as"), defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
            initialdir=os.path.dirname(self.cp_out) if self.cp_out else None,
            initialfile=os.path.basename(self.cp_out) if self.cp_out else "")
        if path:
            self.cp_out = path
            self.render_tab()

    def cp_run(self):
        if self.cp_busy:
            return
        if not self.cp_src:
            self.alert(t("cp_title"), t("cp_need_file"))
            return
        src, dst, level = self.cp_src, self.cp_out, self.vars["cp_level"].get()
        gray, split = self.vars["cp_gray"].get(), self.vars["cp_split"].get()
        if os.path.abspath(src) == os.path.abspath(dst):
            dst = unique_file(os.path.splitext(dst)[0] + " (2).pdf")
            self.cp_out = dst
        self.cp_busy, self.cp_result, self.cp_done_path = True, "", ""
        self.cp_run_btn.set_enabled(False, "primary")
        threading.Thread(target=self.cp_worker, args=(src, dst, level, gray, split), daemon=True).start()

    def cp_worker(self, src, dst, level, gray=False, split=False):
        tmp = dst + ".part"
        try:
            os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
            before = os.path.getsize(src)
            after = compress_pdf(src, tmp, level,
                                 progress=lambda i, n: self.set_status(t("cp_running", i=i, n=n) if i >= 0 else t("cp_finishing")),
                                 gray=gray)
            if split:
                base = os.path.splitext(dst)[0]
                p1 = unique_file(f"{base} ({t('cp_part')} 1).pdf")
                p2 = unique_file(f"{base} ({t('cp_part')} 2).pdf")
                split_pdf(tmp if after < before else src, p1, p2)  # a PDF that did not shrink is split as it was
                os.remove(tmp)
                total = os.path.getsize(p1) + os.path.getsize(p2)
                pct = max(0, round((1 - total / before) * 100))
                result, path = t("cp_done_split", a=mb(before), b=mb(total), pct=pct, p1=os.path.basename(p1), p2=os.path.basename(p2)), p1
            elif after >= before:
                os.remove(tmp)
                result, path = t("cp_nogain"), ""
            else:
                os.replace(tmp, dst)
                pct = round((1 - after / before) * 100)
                result, path = t("cp_done", a=mb(before), b=mb(after), pct=pct, path=dst), dst
            self.log(result.replace("\n", " "))
        except Exception as e:
            result, path = t("cp_fail", err=e), ""
            self.log(result.replace("\n", " "), "err")
            try:
                os.remove(tmp)
            except OSError:
                pass
        self.ui(self.cp_finish, result, path)

    def cp_finish(self, result, path):
        self.cp_busy, self.cp_result, self.cp_done_path = False, result, path
        beep("ok" if path else "warn")
        if self.tab == "compress":
            self.render_tab()
            self.set_status(result.split("\n")[0])

    def build_bar(self, wide):
        """Bottom bar: status, log toggle and (on the Capture tab) Start."""
        c = self.c
        x2 = 846 if wide else 684
        self.status_item = c.create_text(U(38), U(550), anchor="w", width=U(x2 - 22 - 32), fill=LIGHT,
                                         font=F(13), text=self.status_msg)
        self.log_btn = Btn(c, U(858 if wide else 696), U(526), U(120), U(48),
                           t("hide_log") if self.log_visible else t("show_log"), self.toggle_log, size=13)
        if not wide:
            self.start_btn = Btn(c, U(828), U(526), U(150), U(48), t("start"), self.start, kind="primary", size=14)
            self.start_btn.set_enabled(self.target_ready(), "primary")  # needs a region / window first

    # --- Capture tab ---
    def build_capture(self):
        c, v = self.c, self.vars

        # 1 · Source
        self.card_title(22, 72, 314, t("source"), 1)
        Segmented(c, U(42), U(136), U(252), U(38), [(t("src_region"), "region"), (t("src_window"), "window")],
                  v["source"], self.update_source, size=12)
        self.region_btn = Btn(c, U(42), U(186), U(252), U(36), self.target_btn_text(), self.pick_target)
        round_rect(c, U(42), U(234), U(294), U(269), U(10), fill="#10162F", outline=LINE)
        c.create_rectangle(U(54), U(243), U(70), U(257), outline=LIGHT, width=2)
        c.create_line(U(54), U(247), U(70), U(247), fill=LIGHT, width=2)
        self.chip_name = c.create_text(U(80), U(251), anchor="w", fill=LIGHT, font=F(13, True), text="")
        self.chip_size = c.create_text(U(282), U(251), anchor="e", fill=MUTED, font=F(12), text="")
        self.field_above(t("doc_name_full"), "name", 42, 281, 252, ph=t("ph_name"))
        self.name_btns = [
            Btn(c, U(42), U(346), U(122), U(30), t("from_window"), lambda: self.need_target(self.name_from_window), size=12),
            Btn(c, U(172), U(346), U(122), U(30), t("ocr_title"), lambda: self.need_target(self.name_from_ocr), size=12),
        ]
        c.create_text(U(42), U(396), anchor="w", text=t("crop"), fill="#C8CBDB", font=F(12))
        self._crop_segs = [Segmented(c, U(42), U(409), U(252), U(38),
                                     [(t("crop_none"), "none"), (t("crop_auto"), "auto"), (t("crop_manual"), "manual")],
                                     v["crop"], self.on_crop_change, size=12)]

        # 2 · Capture
        yl = self.card_title(330, 72, 670, t("capture"), 2, tall=True)
        self.preset_dd = DropDown(c, U(464), U(90), U(150), U(30), self.preset_names, self.preset_label,
                                  self.apply_preset)
        save = Btn(c, U(620), U(90), U(30), U(30), "", self.save_preset)
        cx, cy = U(635), U(105)  # floppy-disk icon
        for item in (c.create_polygon(cx - U(6), cy - U(6), cx + U(3), cy - U(6), cx + U(6), cy - U(3), cx + U(6),
                                      cy + U(6), cx - U(6), cy + U(6), fill="", outline=LIGHT, width=2),
                     c.create_rectangle(cx - U(3), cy - U(6), cx + U(2), cy - U(2), outline=LIGHT, width=1),
                     c.create_rectangle(cx - U(3), cy + U(1), cx + U(3), cy + U(6), outline=LIGHT, width=1)):
            c.addtag_withtag(save.tag, item)
        c.create_text(U(350), U(163), anchor="w", text=t("mode"), fill="#C8CBDB", font=F(12))
        Segmented(c, U(450), U(144), U(200), U(38), [(t("simple"), "simple"), (t("scroll"), "scroll")],
                  v["mode"], self.update_mode, size=12)
        self.field_above(t("start_page"), "start", 350, 194, 144)
        self.field_above(t("pages"), "pages", 506, 194, 144)
        self.field_above(t("delay"), "delay", 350, 257, 144)
        self.field_above(t("key"), "key", 506, 257, 144)
        self.scroll_fields = [self.field_above(t("scroll_step"), "scroll", 350, 320, 144),
                              self.field_above(t("max_steps"), "steps", 506, 320, 144)]
        self.thresh_label = c.create_text(U(350), U(393), anchor="w", text=t("threshold"), fill=LIGHT, font=F(13))
        self.thresh_slider = Slider(c, U(350), U(418), U(300), 0.50, 0.99, v["thresh"], 0.01,
                                    describe=self.describe_thresh)
        c.coords(self.thresh_slider.value_txt, U(650), U(393))
        c.itemconfig(self.thresh_slider.value_txt, anchor="e")
        self.thresh_note = c.create_text(U(350), U(432), anchor="nw", width=U(300), text=t("th_short"),
                                         fill=MUTED, font=F(12))
        how = f"how{id(self)}"
        c.create_oval(U(350), U(475), U(364), U(489), outline=LIGHT, width=2, tags=how)
        c.create_line(U(357), U(479), U(357), U(479), U(357), U(484), fill=LIGHT, width=2, tags=how)
        c.create_text(U(372), U(482), anchor="w", text=t("how_works"), fill=LIGHT,
                      font=(FONT[0], -U(13), "bold underline"), tags=how)
        c.tag_bind(how, "<Button-1>", lambda e: dialog(self.root, t("threshold"), t("explain"), [("OK", "primary")]))
        c.tag_bind(how, "<Enter>", lambda e: c.config(cursor="hand2"))
        c.tag_bind(how, "<Leave>", lambda e: c.config(cursor=""))

        # 3 · Output
        self.card_title(686, 72, 978, t("output"), 3)
        c.create_text(U(706), U(151), anchor="w", text=t("format"), fill="#C8CBDB", font=F(12))
        Segmented(c, U(782), U(134), U(176), U(34), [("PDF", "pdf"), ("CBZ", "cbz"), ("ZIP", "zip")],
                  v["format"], size=12)
        c.create_text(U(706), U(185), anchor="w", text=t("compression"), fill="#C8CBDB", font=F(12))
        Segmented(c, U(706), U(196), U(252), U(36),
                  [(t("comp_off"), "off"), (t("comp_light"), "light"), (t("comp_balanced"), "balanced"),
                   (t("comp_strong"), "strong")], v["compress"], size=11)
        c.create_text(U(706), U(257), anchor="w", text=t("adjust"), fill="#C8CBDB", font=F(12))
        self.adjust_dd = DropDown(c, U(826), U(242), U(132), U(30), self.adjust_names, self.adjust_label,
                                  self.pick_adjust)
        for y, text, key in ((284, t("opt_pdf"), "pdf"), (310, t("opt_end"), "end"), (336, t("opt_gap"), "gap"),
                             (362, t("opt_dups"), "dups"), (388, t("opt_ocr"), "ocr"), (414, t("opt_clean"), "clean")):
            Check(c, U(706), U(y), text, v[key])
        Btn(c, U(706), U(448), U(252), U(34), t("folders_btn"), self.folders_dialog, size=12)

        self.build_bar(False)

    def need_target(self, fn):
        """Buttons that depend on the source stay dimmed until a region / window is chosen."""
        if not self.target_ready():
            self.status_msg = t("need_window") if self.vars["source"].get() == "window" else t("need_region")
            self.c.itemconfig(self.status_item, text=self.status_msg)
            if self.region_btn:
                self.region_btn.flash()
            return
        fn()

    def refresh_chip(self):
        """The little box under the source button: what is selected right now."""
        if not getattr(self, "chip_name", None) or self.tab != "capture":
            return
        src = self.vars["source"].get()
        if src == "window" and self.window:
            name = self.window["title"]
            r = window_client_rect(self.window["hwnd"])
            size = f"{r['width']} × {r['height']}" if r else ""
        elif src == "region" and self.region:
            name, size = t("chip_region"), f"{self.region['width']} × {self.region['height']}"
        else:
            name, size = t("nothing_selected"), ""
        self.c.itemconfig(self.chip_name, text=fit_text(name, F(13, True), U(190 if size else 250)),
                          fill=LIGHT if size or name != t("nothing_selected") else DIM)
        self.c.itemconfig(self.chip_size, text=size)

    def update_mode(self):
        if self.tab != "capture" or not getattr(self, "scroll_fields", None):
            return
        on = self.vars["mode"].get() == "scroll"
        for lab, e in self.scroll_fields:
            e.config(state="normal" if on else "disabled")
            self.c.itemconfig(lab, fill="#C8CBDB" if on else DIM)
        self.c.itemconfig(self.thresh_label, fill=LIGHT if on else DIM)
        self.c.itemconfig(self.thresh_note, fill=MUTED if on else DIM)
        self.thresh_slider.set_enabled(on)

    # --- presets and remembered fields ---
    def preset_names(self):
        user = [n for n in self.settings.get("presets", {}) if n not in BUILTIN_PRESETS]
        return list(BUILTIN_PRESETS) + user + [t("preset_none")]

    def preset_label(self):
        return self.preset_name or t("preset_none")

    def apply_preset(self, name):
        if name == t("preset_none"):
            self.preset_name = ""
            self.preset_dd.set_text(name)
            return
        data = BUILTIN_PRESETS.get(name) or self.settings.get("presets", {}).get(name)
        if not data:
            return
        for k in PRESET_KEYS:
            if k in data:
                try:
                    self.vars[k].set(data[k])
                except (tk.TclError, ValueError):
                    pass
        self.preset_name = name
        self.render_tab()  # the toggles and segments pick up the new values

    def save_preset(self):
        name = ask_text(self.root, t("ask_preset_t"), t("ask_preset"), self.preset_name)
        if not name:
            return
        presets = dict(self.settings.get("presets", {}))
        presets[name] = {k: self.vars[k].get() for k in PRESET_KEYS}
        self.settings["presets"] = presets
        save_settings(self.settings)
        self.preset_name = name
        self.preset_dd.set_text(name)
        self.log(t("log_preset", name=name))

    def collect_fields(self):
        out = {}
        for k in FIELD_KEYS:
            try:
                out[k] = self.vars[k].get()
            except tk.TclError:
                pass
        return out

    def apply_fields(self, data):
        for k in FIELD_KEYS:
            if k in data:
                try:
                    self.vars[k].set(data[k])
                except (tk.TclError, ValueError):
                    pass
        if self.vars["compress"].get() not in COMPRESSION:
            self.vars["compress"].set("off")
        if self.vars["source"].get() not in ("region", "window"):
            self.vars["source"].set("region")
        if self.vars["mode"].get() not in ("simple", "scroll"):
            self.vars["mode"].set("simple")

    # --- image adjust, trim borders, folders, export options ---
    ADJ = ("original", "sharp", "gray", "bw")

    def adjust_names(self):
        return [t("adj_" + k) for k in self.ADJ]

    def adjust_label(self):
        return t("adj_" + self.vars["adjust"].get())

    def pick_adjust(self, label):
        for k in self.ADJ:
            if t("adj_" + k) == label:
                self.vars["adjust"].set(k)
        self.adjust_dd.set_text(self.adjust_label())

    def refresh_crop_segs(self):
        for sg in list(self._crop_segs):
            try:
                sg.refresh()
            except tk.TclError:
                self._crop_segs.remove(sg)

    def crop_sample(self):
        """A page to draw the manual crop on: the first page of the project, otherwise a live grab of the source."""
        info = self.current_project() if self.tab == "projects" else None
        if not info:
            name = book_name(self.vars["name"].get())
            if name:
                info = next((p for p in self.projects if p["name"] == name), None)
        if info and info["pages"]:
            return Image.open(list_pages(info["temp"])[0][1]).convert("RGB")
        if self.target_ready():
            try:
                arr = self.make_target().grab()
                if arr is not None:
                    return Image.fromarray(arr)
            except Exception:
                pass
        return None

    def on_crop_change(self):
        """Manual: draw the area to keep over a sample page. Auto / None need nothing."""
        if self.vars["crop"].get() != "manual":
            return
        img = self.crop_sample()
        old = parse_box(self.vars["crop_box"].get())
        if img is None:
            self.vars["crop"].set("none")
            self.alert(t("crop_t"), t("crop_need"))
        else:
            box = CropDialog(self.root, img, old).run()
            if box:
                self.vars["crop_box"].set(",".join(f"{x:.4f}" for x in box))
            elif not old:
                self.vars["crop"].set("none")
        self.refresh_crop_segs()

    def folders_dialog(self):
        top, c = new_window(self.root, t("folders_t"), 560, 300, [(10, 10, 550, 290)])
        top.attributes("-topmost", False)
        top.transient(self.root)
        c.create_text(U(28), U(26), anchor="nw", text=t("folders_t"), fill=LIGHT, font=F(17, semibold=True))
        for y, label, key in ((72, t("pdf_folder"), "out"), (140, t("temp_images"), "temp")):
            c.create_text(U(28), U(y + 8), anchor="w", text=label, fill="#C8CBDB", font=F(12))
            small_entry(c, self.vars[key], 28, y + 21, 444, 34)
            Btn(c, U(480), U(y + 21), U(52), U(34), "…", lambda k=key: self.pick_dir(k, top), size=15)
        Btn(c, U(560 - 28 - 100), U(300 - 26 - 40), U(100), U(40), "OK", top.destroy, "primary")
        top.update()
        top.lift()
        self.root.wait_window(top)
        self.refresh_projects(draw=False)

    def export_options(self):
        info = self.current_project()
        v = self.vars
        keys = ("adjust", "crop", "crop_box", "ocr", "bookmarks", "dups", "title", "author")
        snap = {k: v[k].get() for k in keys}
        dups = (self.get_dups(info) if info else None)
        if dups is None and info:
            dups = find_duplicates(list_pages(info["temp"]))
        dups = dups or {}
        W, H = 560, 500
        top, c = new_window(self.root, t("exp_opts_t"), W, H, [(10, 10, 550, 490)])
        c.create_text(U(30), U(26), anchor="nw", text=t("exp_opts_t"), fill=LIGHT, font=F(17, semibold=True))
        c.create_text(U(30), U(76), anchor="w", text=t("adjust"), fill="#C8CBDB", font=F(12))
        Segmented(c, U(30), U(88), U(500), U(36), [(t("adj_" + k), k) for k in self.ADJ], v["adjust"], size=12)
        c.create_text(U(30), U(146), anchor="w", text=t("crop"), fill="#C8CBDB", font=F(12))
        self._crop_segs = [Segmented(c, U(30), U(158), U(500), U(36),
                                     [(t("crop_none"), "none"), (t("crop_auto"), "auto"), (t("crop_manual"), "manual")],
                                     v["crop"], self.on_crop_change, size=12)]
        Check(c, U(30), U(214), t("opt_ocr"), v["ocr"])
        Check(c, U(30), U(246), t("opt_bookmarks"), v["bookmarks"])
        marks = sorted(info["bookmarks"]) if info else []
        summary = t("bk_summary", n=len(marks), pages=" · ".join(str(m) for m in marks)) if marks else t("bk_none")
        c.create_text(U(62), U(278), anchor="w", text=fit_text(summary, F(12), U(460)), fill=MUTED, font=F(12))
        Check(c, U(30), U(304), t("opt_dups"), v["dups"])
        Btn(c, U(400), U(300), U(130), U(30), t("review_n", n=len(dups)), lambda: self.review_dups(info), size=12)
        for x, key, ph in ((30, "title", t("ph_title")), (290, "author", t("ph_author"))):
            e = small_entry(c, v[key], x, 362, 240)
            add_placeholder(e, v[key], ph)
        done = {"ok": False}

        def ok():
            done["ok"] = True
            top.destroy()

        Btn(c, U(W - 28 - 100), U(H - 26 - 40), U(100), U(40), "OK", ok, "primary")
        Btn(c, U(W - 28 - 210), U(H - 26 - 40), U(100), U(40), t("b_cancel"), top.destroy, "secondary")
        top.update()
        top.lift()
        self.root.wait_window(top)
        if not done["ok"]:
            for k, val in snap.items():
                v[k].set(val)
        self._crop_segs = []
        self.render_tab()

    def review_dups(self, info):
        pages = list_pages(info["temp"]) if info else []
        dups = find_duplicates(pages)
        if not dups:
            self.alert(t("exp_opts_t"), t("review_none"))
            return
        self.open_viewer(min(dups))

    def get_dups(self, info):
        """{page: repeated page} of a project; computed in the background (None until ready)."""
        key = info["name"]
        stamp = (tuple(info["pages"]), info["mtime"])
        cached = self._dups.get(key)
        if cached and cached[0] == stamp:
            return cached[1]
        if key not in self._dups_busy:
            self._dups_busy.add(key)

            def work():
                d = find_duplicates(list_pages(info["temp"]))
                self._dups[key] = (stamp, d)
                self._dups_busy.discard(key)
                self.ui(self._dups_ready, key)

            threading.Thread(target=work, daemon=True).start()
        return cached[1] if cached else None

    def _dups_ready(self, key):
        if self.tab == "projects" and self.sel_name == key and self.c is not None:
            try:
                self.draw_region("detail", self.draw_detail)
            except tk.TclError:
                pass

    def pages_changed(self):
        """A page was marked / bookmarked / moved / deleted from the viewer: refresh the project."""
        self.refresh_projects()

    def open_viewer(self, n):
        info = self.current_project()
        if info and info["pages"]:
            PageViewer(self, info, n)

    def rename_project(self, info):
        new = ask_text(self.root, t("ask_rename_t"), t("ask_rename"), info["name"])
        new = book_name(new) if new else None
        if not new or new == info["name"]:
            return
        tr, orr = self.vars["temp"].get(), self.vars["out"].get()
        new_temp, new_out = os.path.join(tr, new), os.path.join(orr, new)
        if new.lower() != info["name"].lower() and (os.path.exists(new_temp) or os.path.exists(new_out)):
            self.alert(t("ask_rename_t"), t("rename_exists"))
            return
        try:
            if os.path.isdir(info["temp"]):
                os.rename(info["temp"], new_temp)
            if os.path.isdir(info["out"]):
                os.rename(info["out"], new_out)
                for f in os.listdir(new_out):  # the exported files carry the project name
                    if f.startswith(info["name"]):
                        os.rename(os.path.join(new_out, f), os.path.join(new_out, new + f[len(info["name"]):]))
        except OSError as e:
            self.alert(t("ask_rename_t"), t("rename_fail", err=e))
            self.refresh_projects()
            return
        if self.sel_name == info["name"]:
            self.sel_name = new
        if self.vars["name"].get() == info["name"]:
            self.set_name(new, False)
        self.log(t("log_renamed", old=info["name"], new=new))
        self.refresh_projects()

    # --- Projects tab ---
    def build_projects_static(self):
        c = self.c
        self.card_title(22, 72, 462, t("projects"), None, tall=True)
        Btn(c, U(332), U(90), U(110), U(30), "+  " + t("new_capture"), self.new_capture, kind="primary", size=12)
        self.entry(self.proj_search, 42, 144, 262, 34, t("search"))
        self.filter_dd = DropDown(c, U(314), U(144), U(128), U(34), self.filter_names, self.filter_label,
                                  self.pick_filter)
        self.card_title(478, 72, 978, t("details"), None, tall=True)
        self.open_btn = Btn(c, U(848), U(90), U(110), U(30), t("open_folder"), self.open_current_folder, size=12)
        self.build_bar(True)
        total = len(self.projects)
        with_pdf = sum(1 for p in self.projects if p["pdf"])
        c.itemconfig(self.status_item, text=t("status_projects", n=total, k=with_pdf, path=self.vars["out"].get()))

    def filter_names(self):
        return [t("flt_all"), t("flt_going"), t("flt_pdf")]

    def filter_label(self):
        return {"all": t("flt_all"), "going": t("flt_going"), "pdf": t("flt_pdf")}[self.proj_filter]

    def pick_filter(self, label):
        self.proj_filter = {t("flt_all"): "all", t("flt_going"): "going", t("flt_pdf"): "pdf"}[label]
        self.filter_dd.set_text(label)
        self.list_offset = 0
        self.draw_region("list", self.draw_list)

    def on_search(self, *_):
        if self.tab == "projects" and self.c is not None:
            self.list_offset = 0
            try:
                self.draw_region("list", self.draw_list)
            except tk.TclError:
                pass

    def filtered_projects(self):
        q = self.proj_search.get().strip().lower()
        out = []
        for p in self.projects:
            if q and q not in p["name"].lower():
                continue
            if self.proj_filter == "going" and not in_progress(p):
                continue
            if self.proj_filter == "pdf" and not p["pdf"]:
                continue
            out.append(p)
        return out

    def refresh_projects(self, draw=True):
        self.projects = scan_projects(self.vars["temp"].get(), self.vars["out"].get())
        if self.sel_name and not any(p["name"] == self.sel_name for p in self.projects):
            self.sel_name = None
        if getattr(self, "tabbar", None) is not None:
            self.tabbar.set_count("projects", len(self.projects))
        if draw and self.tab == "projects":
            self.draw_region("list", self.draw_list)
            self.draw_region("detail", self.draw_detail)

    def current_project(self):
        return next((p for p in self.projects if p["name"] == self.sel_name), None)

    def select_project(self, name):
        self.sel_name, self.page_offset = name, 0
        info = self.current_project()
        self.vars["pfrom"].set("1")
        self.vars["pto"].set(str(info["last"]) if info else "")
        self.vars["title"].set("")
        self.draw_region("list", self.draw_list)
        self.draw_region("detail", self.draw_detail)

    def on_wheel(self, e):
        if self.tab != "projects" or e.x > U(470):
            return
        up = getattr(e, "num", 0) == 4 or getattr(e, "delta", 0) > 0
        n = len(self.filtered_projects())
        off = max(0, min(max(0, n - 4), self.list_offset + (-1 if up else 1)))
        if off != self.list_offset:
            self.list_offset = off
            self.draw_region("list", self.draw_list)

    @staticmethod
    def level_label(level):
        if level in ("light", "balanced", "strong"):
            return t("comp_" + level).lower()
        return t("lvl_off") if level == "off" else ""

    def draw_list(self):
        c = self.c
        items = self.filtered_projects()
        if not items:
            c.create_text(U(242), U(300), width=U(340), justify="center", text=t("no_projects"), fill=MUTED,
                          font=F(13))
            return
        off = min(self.list_offset, max(0, len(items) - 4))
        self.list_offset = off
        for k, info in enumerate(items[off:off + 4]):
            self.draw_row(info, 190 + 72 * k)
        if len(items) > 4:  # slim scrollbar
            h = 282 * 4 / len(items)
            y0 = 190 + (282 - h) * off / (len(items) - 4)
            round_rect(c, U(446), U(y0), U(450), U(y0 + h), U(2), fill=LINE, outline="")

    def draw_row(self, info, y):
        c = self.c
        sel = info["name"] == self.sel_name
        tag = f"row{abs(hash(info['name']))}"
        round_rect(c, U(42), U(y), U(442), U(y + 66), U(12), fill="#2A1236" if sel else "#10162F",
                   outline=PURPLE_LT if sel else "#3A3F5C", width=2 if sel else 1, tags=tag)
        round_rect(c, U(54), U(y + 7), U(98), U(y + 59), U(6), fill=INPUT_BG, outline=LINE, tags=tag)
        c.create_polygon(U(68), U(y + 20), U(80), U(y + 20), U(86), U(y + 26), U(86), U(y + 46), U(68), U(y + 46),
                         fill="", outline=MUTED, width=2, tags=tag)
        c.create_text(U(110), U(y + 17), anchor="w", fill=LIGHT, font=F(14, True), tags=tag,
                      text=fit_text(info["name"], F(14, True), U(182)))
        when = time.strftime("%d/%m, %H:%M", time.localtime(info["mtime"])) if info["mtime"] else ""
        going = in_progress(info)
        meta = (f"{when} · " + t("next_page", n=info["last"] + 1)) if going else \
            (t("n_pages", n=info["captured"]) + (f" · {when}" if when else "") if info["captured"] else when)
        c.create_text(U(110), U(y + 35), anchor="w", fill=MUTED, font=F(12), tags=tag,
                      text=fit_text(meta, F(12), U(182)))
        if going:
            round_rect(c, U(110), U(y + 49), U(180), U(y + 55), U(3), fill=INPUT_BG, outline=LINE, tags=tag)
            frac = max(0.05, min(1.0, info["captured"] / info["planned"]))
            round_rect(c, U(110), U(y + 49), U(110 + 70 * frac), U(y + 55), U(3), fill=PURPLE, outline="", tags=tag)
            c.create_text(U(188), U(y + 52), anchor="w", fill=MUTED, font=F(12), tags=tag,
                          text=t("of_total", c=info["captured"], p=info["planned"]))
        elif info["pdf"]:
            c.create_line(U(110), U(y + 53), U(114), U(y + 57), U(121), U(y + 48), fill=MUTED, width=2, tags=tag)
            lvl = self.level_label(info["pdf_level"])
            kind = os.path.splitext(info["pdf"])[1][1:].upper() or "PDF"
            txt = t("pdf_row", size=mb(info["pdf_size"])).replace("PDF", kind, 1) + (f" · {lvl}" if lvl else "")
            c.create_text(U(128), U(y + 52), anchor="w", fill=MUTED, font=F(12), tags=tag,
                          text=fit_text(txt, F(12), U(160)))
        else:
            c.create_text(U(110), U(y + 52), anchor="w", fill=MUTED, font=F(12), tags=tag, text=t("no_pdf_yet"))
        if going:
            label, fn, kind = t("continue"), (lambda i=info: self.continue_project(i)), "primary"
        elif info["pdf"]:
            label = t("open_pdf") if info["pdf"].lower().endswith(".pdf") else t("open_file")
            fn, kind = (lambda i=info: open_path(i["pdf"])), "secondary"
        else:
            label, fn, kind = t("gen_pdf"), (lambda i=info: self.export_project(i)), "primary"
        Btn(c, U(298), U(y + 18), U(96), U(30), label, fn, kind=kind, size=12)
        Btn(c, U(400), U(y + 18), U(30), U(30), "···", lambda i=info: self.row_menu(i), size=14)
        c.tag_bind(tag, "<Button-1>", lambda e, n=info["name"]: self.select_project(n))

    def row_menu(self, info):
        m = tk.Menu(self.c, tearoff=0, bg=INPUT_BG, fg=LIGHT, activebackground=PURPLE, activeforeground=LIGHT,
                    bd=0, relief="flat", font=F(12))
        m.add_command(label=t("menu_rename"), command=lambda: self.rename_project(info))
        m.add_command(label=t("open_folder"),
                      command=lambda: open_path(info["out"] if os.path.isdir(info["out"]) else info["temp"]))
        m.add_command(label=t("menu_open_temp"), command=lambda: open_path(info["temp"]),
                      state="normal" if os.path.isdir(info["temp"]) else "disabled")
        m.add_command(label=t("gen_pdf"), command=lambda: self.export_project(info),
                      state="normal" if info["captured"] else "disabled")
        m.add_separator()
        m.add_command(label=t("menu_delete_temp"), command=lambda: self.delete_temp(info),
                      state="normal" if info["captured"] else "disabled")
        try:
            m.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())
        finally:
            m.grab_release()

    def draw_detail(self):
        c = self.c
        info = self.current_project()
        if getattr(self, "open_btn", None):
            self.open_btn.set_enabled(bool(info), "secondary")
        if not info:
            c.create_text(U(728), U(290), text=t("select_project"), fill=MUTED, font=F(13))
            return
        total = max(info["last"], info["planned"])
        c.create_text(U(498), U(152), anchor="w", fill=LIGHT, font=F(16, semibold=True),
                      text=fit_text(info["name"], F(16, semibold=True), U(460)))
        meta = t("proj_meta", c=info["captured"], p=total) if info["planned"] else t("proj_meta2", c=info["captured"])
        if in_progress(info):
            meta += " · " + t("next_page", n=info["last"] + 1)
        c.create_text(U(498), U(174), anchor="w", fill=MUTED, font=F(12), text=meta)

        # left column: pages (click to mark the bad ones, double-click to enlarge)
        c.create_text(U(498), U(204), anchor="w", text=t("pages_h"), fill="#C8CBDB", font=F(11, True))
        c.create_text(U(498), U(218), anchor="nw", width=U(222), text=t("mark_hint"), fill=MUTED, font=F(12))
        have, marked, per = set(info["pages"]), set(info["marked"]), 15
        dups = self.get_dups(info) or {}
        off = min(self.page_offset, max(0, ((total - 1) // per) * per)) if total else 0
        self.page_offset = off
        for idx in range(per):
            n = off + idx + 1
            if n > total:
                break
            x, y = 498 + (idx % 5) * 45.25, 254 + (idx // 5) * 40
            tag = f"tile{n}"
            if n in marked:
                fill, outline, width, fg = "#3C1A3E", PURPLE_LT, 2, LIGHT
            elif n in have:
                fill, outline, width, fg = INPUT_BG, LINE, 1, LIGHT
            else:
                fill, outline, width, fg = "#0D1127", "#2A2F4A", 1, DIM
            round_rect(c, U(x), U(y), U(x + 39), U(y + 34), U(7), fill=fill, outline=outline, width=width, tags=tag)
            c.create_text(U(x + 19.5), U(y + 17), text=str(n), fill=fg, font=F(12, True), tags=tag)
            if n in info["bookmarks"]:
                c.create_oval(U(x + 30), U(y + 4), U(x + 36), U(y + 10), fill=YELLOW, outline="", tags=tag)
            if n in dups:
                c.create_text(U(x + 7), U(y + 27), text="=", fill=YELLOW, font=F(11, True), tags=tag)
            if n in have:
                c.tag_bind(tag, "<Button-1>", lambda e, k=n: self.toggle_mark(k))
                c.tag_bind(tag, "<Double-Button-1>", lambda e, k=n: self.open_viewer(k))
                c.tag_bind(tag, "<Enter>", lambda e: c.config(cursor="hand2"))
                c.tag_bind(tag, "<Leave>", lambda e: c.config(cursor=""))
        if total > per:
            Btn(c, U(498), U(372), U(30), U(26), "‹", lambda: self.page_step(-per), size=14)
            Btn(c, U(688), U(372), U(30), U(26), "›", lambda: self.page_step(per), size=14)
            c.create_text(U(608), U(385), text=f"{off + 1}–{min(off + per, total)} / {total}", fill=MUTED, font=F(12))
        Btn(c, U(498), U(408), U(220), U(30), t("recapture", n=len(marked)), self.recapture_marked, size=12)
        lx = U(498)
        for glyph, label in (("●", t("lg_bookmark")), ("=", t("lg_repeated"))):
            c.create_text(lx, U(452), anchor="w", text=glyph, fill=YELLOW, font=F(11, True))
            lx += tkfont.Font(font=F(11, True)).measure(glyph) + U(6)
            c.create_text(lx, U(452), anchor="w", text=label, fill=MUTED, font=F(11))
            lx += tkfont.Font(font=F(11)).measure(label) + U(18)

        # right column: export (range, format, compression, more options)
        c.create_text(U(738), U(204), anchor="w", text=t("export_h"), fill="#C8CBDB", font=F(11, True))
        self.field_above(t("from_page"), "pfrom", 738, 220, 105)
        self.field_above(t("to_page"), "pto", 853, 220, 105)
        c.create_text(U(738), U(297), anchor="w", text=t("format"), fill="#C8CBDB", font=F(12))
        Segmented(c, U(812), U(282), U(146), U(30), [("PDF", "pdf"), ("CBZ", "cbz"), ("ZIP", "zip")],
                  self.vars["format"], size=11)
        c.create_text(U(738), U(330), anchor="w", text=t("compression"), fill="#C8CBDB", font=F(12))
        Segmented(c, U(738), U(341), U(220), U(36),
                  [(t("comp_off"), "off"), (t("comp_light"), "light"), (t("comp_balanced"), "balanced"),
                   (t("comp_strong"), "strong")], self.vars["compress"], size=11)
        more = f"more{id(self)}"
        c.create_text(U(738), U(396), anchor="w", text=t("more_opts"), fill=LIGHT,
                      font=(FONT[0], -U(13), "bold underline"), tags=more)
        c.tag_bind(more, "<Button-1>", lambda e: self.export_options())
        c.tag_bind(more, "<Enter>", lambda e: c.config(cursor="hand2"))
        c.tag_bind(more, "<Leave>", lambda e: c.config(cursor=""))
        Btn(c, U(738), U(416), U(220), U(40), t("gen_file_project"), self.export_project_click, kind="primary", size=13)

    def page_step(self, d):
        self.page_offset = max(0, self.page_offset + d)
        self.draw_region("detail", self.draw_detail)

    def toggle_mark(self, n):
        info = self.current_project()
        if not info:
            return
        meta = load_meta(info["temp"])
        marked = set(meta.get("marked", []))
        marked ^= {n}
        meta["marked"] = sorted(marked)
        save_meta(info["temp"], meta)
        self.refresh_projects(draw=False)
        self.draw_region("detail", self.draw_detail)

    def new_capture(self):
        self.recap_active, self.recap_runs = False, []
        self.set_name("", False)
        self.vars["start"].set("1")
        self.switch_tab("capture")

    def open_current_folder(self):
        info = self.current_project()
        if info:
            open_path(info["out"] if os.path.isdir(info["out"]) else info["temp"])

    def continue_project(self, info):
        """Back to the Capture tab with the project's name and the next page filled in."""
        self.recap_active, self.recap_runs = False, []
        self.set_name(info["name"], False)
        nxt = info["last"] + 1
        self.vars["start"].set(str(nxt))
        if info["planned"]:
            self.vars["pages"].set(str(max(info["planned"] - info["last"], 1)))
        self.status_msg = t("continue_msg", name=info["name"], n=nxt)
        self.switch_tab("capture")
        self.c.itemconfig(self.status_item, text=self.status_msg)

    def recapture_marked(self):
        info = self.current_project()
        if not info:
            return
        runs = page_runs(info["marked"])
        if not runs:
            self.alert(t("d_nomark_t"), t("d_nomark"))
            return
        self.recap_active, self.recap_runs = True, runs[1:]
        self.set_name(info["name"], False)
        self.vars["start"].set(str(runs[0][0]))
        self.vars["pages"].set(str(runs[0][1]))
        self.status_msg = t("recap_go", n=runs[0][0])
        self.switch_tab("capture")
        self.c.itemconfig(self.status_item, text=self.status_msg)

    def delete_temp(self, info):
        ans = dialog(self.root, t("d_deltemp_t"), t("d_deltemp", n=info["captured"], name=info["name"]),
                     [(t("menu_delete_temp"), "primary"), (t("b_cancel"), "secondary")])
        if ans != 0:
            return
        for _, p in list_pages(info["temp"]):
            try:
                os.remove(p)
            except OSError:
                pass
        meta = load_meta(info["temp"])
        meta["marked"], meta["bookmarks"] = [], {}
        save_meta(info["temp"], meta)
        self.log(t("log_deleted", n=info["captured"]))
        self.refresh_projects()

    def image_options(self):
        """Format, trim borders, adjust, repeated pages and bookmarks, as chosen on screen."""
        v = self.vars
        crop, box = v["crop"].get(), parse_box(v["crop_box"].get())
        if crop == "manual" and not box:
            crop = "none"
        return dict(fmt=v["format"].get(), crop=crop, box=box, adjust=v["adjust"].get(), dups=v["dups"].get(),
                    bookmarks=v["bookmarks"].get())

    def export_project_click(self):
        info = self.current_project()
        if not info or not info["captured"]:
            self.alert("PDF", t("exp_none"))
            return
        try:
            first = int(self.vars["pfrom"].get() or 1)
            last = int(self.vars["pto"].get() or info["last"])
            assert 1 <= first <= last
        except (ValueError, AssertionError):
            self.alert(t("d_range_t"), t("d_range"))
            return
        self.export_project(info, first, last)

    def export_project(self, info, first=None, last=None):
        """Build a PDF from a project's pages (optionally a range) without touching the capture settings."""
        cfg = dict(temp=info["temp"], out=info["out"], name=info["name"], clean=False,
                   compress=self.vars["compress"].get(), ocr=self.vars["ocr"].get(), first=first, last=last,
                   **self.image_options(),
                   title=self.vars["title"].get().strip() if self.sel_name == info["name"] else "",
                   author=self.vars["author"].get().strip())
        full = (first is None or first <= (min(info["pages"]) if info["pages"] else 1)) \
            and (last is None or last >= info["last"])
        cfg["file"] = info["name"] if full else f"{info['name']} ({t('pg_abbr')}{first}-{last})"

        def work():
            self.set_status(t("pdf_building"))
            self.log(t("log_pdf_temp"))
            pdf = None
            try:
                pdf, line = self.export_pdf(cfg)
                msg = (self.saved_msg(cfg, pdf) + "\n" + line) if pdf else t("exp_none")
                self.log(msg.replace("\n", " "))
            except Exception as e:
                msg = t("pdf_fail", err=e)
                self.log(msg.replace("\n", " "), "err")
            self.set_status(msg.split("\n")[0])
            self.ui(lambda: (self.refresh_projects(), self.pdf_done_dialog(cfg.get("fmt", "pdf").upper(), msg, pdf)))

        threading.Thread(target=work, daemon=True).start()

    @staticmethod
    def saved_msg(cfg, path):
        return t("pdf_saved" if cfg.get("fmt", "pdf") == "pdf" else "file_saved", pdf=path)

    def pdf_done_dialog(self, title, msg, pdf):
        """Result dialog; with a PDF it offers to open the file or its folder."""
        if not pdf:
            self.alert(title, msg)
            return
        ans = dialog(self.root, title, msg, [(t("open_pdf"), "secondary"), (t("open_folder"), "secondary"),
                                             ("OK", "primary")])
        if ans == 0:
            open_path(pdf)
        elif ans == 1:
            open_path(os.path.dirname(pdf))

    # --- helpers ---
    def ui(self, fn, *a):
        try:
            self.root.after(0, fn, *a)
        except (RuntimeError, tk.TclError):  # the window is already closed
            pass

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
        if self.region_btn:
            self.region_btn.set_text(self.target_btn_text())
        if self.start_btn:
            self.start_btn.set_enabled(self.target_ready(), "primary")
        for b in self.name_btns:  # "from window" / "OCR title" wait for a source
            b.set_enabled(self.target_ready(), "secondary")
        self.refresh_chip()

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
        if self.log_btn:
            self.log_btn.set_text(t("hide_log") if self.log_visible else t("show_log"))
        if self.panel:
            self.panel.log_btn.set_text(t("hide_log") if self.log_capture else t("show_log"))

    def apply_log(self):
        """One log, shown where it gets in nobody's way: inside the capture window while capturing,
        beside the main window otherwise."""
        if self.running and self.panel:
            if self.log_win:
                self.log_win.destroy()
                self.log_win = None
            self.panel.set_log(self.log_capture)
        elif self.log_visible and not self.log_win:
            try:
                self.log_win = LogWindow(self)
            except Exception as e:
                self.log_visible = False
                self.set_status(t("log_open_fail", e=e))
            else:
                self.place_log_beside_main()
        elif not self.log_visible and self.log_win:
            self.log_win.destroy()
            self.log_win = None
        self.refresh_log_buttons()

    def place_log_beside_main(self):
        """Put the log next to the main window. With no room on either side, slide the main window over so
        both fit side by side: the log never sits on top of the app."""
        win, main = self.log_win, self.main_rect()
        if not win or not main:
            return
        mx, my, mw, mh = main
        L, T, R, B = monitor_bounds(win, mx + mw // 2, my + mh // 2)
        gap = U(10)
        if not (mx + mw + gap + win.W <= R or mx - gap - win.W >= L) and mw + gap + win.W <= R - L:
            nx = L + (R - L - (mw + gap + win.W)) // 2
            self.root.geometry(f"+{nx}+{self.root.winfo_y()}")
            self.root.update_idletasks()
            main = self.main_rect() or main
        win.place(None, [main], near=main)

    def toggle_log(self):
        if self.running:  # the capture window has its own switch
            self.log_capture = not self.log_capture
        else:
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

    def pick_dir(self, key, parent=None):
        d = filedialog.askdirectory(parent=parent or self.root)
        if d:
            self.vars[key].set(os.path.normpath(d))
            self.refresh_projects(draw=False)

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
                pdf=v["pdf"], end=v["end"], gap=v["gap"], clean=v["clean"], compress=v["compress"],
                ocr=v["ocr"], author=v["author"].strip(), **self.image_options())
            assert cfg["start"] >= 1 and cfg["pages"] >= 0
            if self.recap_active:  # recapturing marked pages: the PDF is generated afterwards, from Projects
                cfg["pdf"] = False
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
        """Build a project's PDF (range, compression, OCR, metadata). Returns (pdf_path or None, size line)."""
        level = cfg.get("compress", "off")
        q = COMPRESSION.get(level)
        if q:
            w = f"{q[1]}px" if q[1] else t("orig_width")
            self.log(t("log_comp", level=t("comp_" + level).lower(), q=q[0], w=w))
        else:
            self.log(t("log_comp_off"))
        fmt = cfg.get("fmt", "pdf")
        use_ocr = bool(cfg.get("ocr")) and fmt == "pdf"
        if use_ocr:
            try:
                _tesseract().get_tesseract_version()
            except Exception:  # Tesseract (or pytesseract) missing: still deliver the PDF, just not searchable
                use_ocr = False
                self.log(t("ocr_skip"), "warn")
        if use_ocr:
            self.log(t("log_ocr"))
        skip = set(find_duplicates(list_pages(cfg["temp"]))) if cfg.get("dups") else set()
        if skip:
            self.log(t("review_n", n=len(skip)) + ": " + ", ".join(str(n) for n in sorted(skip)))
        bookmarks = (load_meta(cfg["temp"]).get("bookmarks") or None) if cfg.get("bookmarks") else None
        pdf, orig = build_pdf(
            cfg["temp"], cfg["out"], cfg.get("file", cfg["name"]), cfg.get("clean", False), level,
            progress=lambda ph, i, n: self.set_status(t("pdf_" + ph, i=i, n=n)),
            first=cfg.get("first"), last=cfg.get("last"), title=cfg.get("title") or cfg["name"],
            author=cfg.get("author") or None, ocr=use_ocr,
            lang="por+eng" if LANG[0] == "pt" else "eng", fmt=fmt, crop=cfg.get("crop", "none"),
            box=cfg.get("box"), adjust=cfg.get("adjust", "original"), bookmarks=bookmarks, skip=skip)
        info = ""
        if pdf:
            info = t("pdf_size", size=mb(os.path.getsize(pdf)), orig=mb(orig))
            self.log(info)
            meta = load_meta(cfg["temp"])
            meta["pdf"] = dict(compress=level, ocr=bool(cfg.get("ocr")), at=time.strftime("%Y-%m-%d %H:%M:%S"),
                               size=os.path.getsize(pdf), fmt=fmt)
            save_meta(cfg["temp"], meta)
        return pdf, info

    # --- actions ---
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
        if cfg["start"] == 1 and existing and not self.recap_active:
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

    def update_project_meta(self, cfg):
        """Remember what a project is about: how many pages it should have, and when it last changed."""
        meta = load_meta(cfg["temp"])
        if cfg["pages"]:
            meta["planned"] = max(int(meta.get("planned", 0) or 0), cfg["start"] + cfg["pages"] - 1)
        meta["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
        save_meta(cfg["temp"], meta)

    def recap_step(self, reason, cfg, saved):
        """Recapture queue: unmark the pages just redone and prepare the next section. (title, message) or (None, None)."""
        if reason in ("count", "end") and saved:
            meta = load_meta(cfg["temp"])
            done = set(range(cfg["start"], cfg["start"] + saved))
            meta["marked"] = sorted(set(meta.get("marked", [])) - done)
            save_meta(cfg["temp"], meta)
            if self.recap_runs:
                s, n = self.recap_runs.pop(0)
                self.vars["start"].set(str(s))
                self.vars["pages"].set(str(n))
                return t("t_recap"), t("recap_next", n=s, left=len(self.recap_runs) + 1)
            self.recap_active = False
            return t("t_recap"), t("recap_done")
        self.recap_active, self.recap_runs = False, []
        return None, None

    # --- updates ---
    def start_update_check(self):
        """Look for a newer release every time the app opens (quietly): the version number turns yellow."""
        threading.Thread(target=self._update_worker, args=(False,), daemon=True).start()

    def check_update_now(self):
        """Manual check, from the version label in the header."""
        if self.running:
            return
        self.c.itemconfig(self.status_item, text=t("upd_checking"))
        threading.Thread(target=self._update_worker, args=(True,), daemon=True).start()

    def version_click(self):
        if self.running:
            return
        if self.update_info:
            self.offer_update(self.update_info)
        else:
            self.check_update_now()

    def _update_worker(self, manual):
        self.ui(self.show_update, check_update(), manual)

    def paint_version(self):
        try:
            self.c.itemconfig(self.ver_item, fill=YELLOW if self.update_info else MUTED)
        except (tk.TclError, AttributeError):
            pass

    def show_update(self, info, manual):
        if manual:
            self.c.itemconfig(self.status_item, text=self.status_msg)
        newer = info is not None and version_tuple(info["tag"]) > version_tuple(VERSION)
        self.update_info = info if newer else None
        self.paint_version()
        if self.running:
            return
        if info is None:
            if manual:
                self.alert(t("upd_check_t"), t("upd_fail"))
        elif not newer:
            if manual:
                self.alert(t("upd_none_t"), t("upd_none", cur=f"v{VERSION}"))
        elif manual:
            self.offer_update(info)

    def offer_update(self, info):
        ans = dialog(self.root, t("upd_title"),
                     t("upd_msg", new=info["tag"], cur=f"v{VERSION}") + "\n\n" + t("upd_auto"),
                     [(t("upd_now"), "primary"), (t("upd_notes"), "secondary"), (t("upd_later"), "secondary")])
        if ans == 0:
            self.auto_update(info)
        elif ans == 1:
            webbrowser.open(info["url"])

    def auto_update(self, info):
        """Download the release zip, replace the program files and restart (the packaged exe is rebuilt first)."""
        if self.running:
            self.alert(t("upd_check_t"), t("upd_busy"))
            return
        if not info.get("asset"):
            self.alert(t("upd_check_t"), t("upd_noasset"))
            webbrowser.open(info["url"])
            return
        frozen = bool(getattr(sys, "frozen", False))
        if frozen and not shutil.which("python"):  # the exe is rebuilt with Python by Installer.bat
            self.alert(t("upd_check_t"), t("upd_nopy"))
            webbrowser.open(info["asset"])
            return
        win = UpdateWindow(self.root, info["tag"])
        cancel = threading.Event()
        win.cancel_cmd = cancel.set
        threading.Thread(target=self._update_run, args=(info, win, cancel, frozen), daemon=True).start()

    def _update_run(self, info, win, cancel, frozen):
        tmp = tempfile.mkdtemp(prefix="page_capture_upd_")
        try:
            self.ui(win.step, 0)
            zp = os.path.join(tmp, "update.zip")
            download_file(info["asset"], zp, progress=lambda d, n: self.ui(win.progress, d / n if n else 0.5),
                          cancel=cancel)
            self.ui(win.step, 1)
            ex = os.path.join(tmp, "unzipped")
            with zipfile.ZipFile(zp) as z:
                z.extractall(ex)
            src = find_release_root(ex)
            if not src:
                raise RuntimeError("page_capture.py is not in the zip")
            newv = release_version(src)
            if newv and version_tuple(newv) <= version_tuple(VERSION):
                raise RuntimeError(f"the zip holds v{newv}")
            dest = root_dir() if frozen else app_dir()
            apply_update_files(src, dest, os.path.join(tmp, "backup"))
            self.ui(win.step, 2)
            if frozen:
                exe = sys.executable
                bat = os.path.join(tmp, "update.bat")
                with open(bat, "w", encoding="utf-8", newline="") as f:
                    f.write(updater_script(dest, exe, info["tag"], os.path.join(tmp, "PageCapture.old")))
                subprocess.Popen(["cmd.exe", "/c", bat], creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
                                 close_fds=True)
            else:
                subprocess.Popen([sys.executable, os.path.join(dest, "page_capture.py")], cwd=dest)
            time.sleep(1.0)
            self.ui(self.quit_for_update)
        except Exception as e:
            shutil.rmtree(tmp, ignore_errors=True)
            self.ui(win.destroy)
            if str(e) != "cancelled":
                self.ui(self.alert, t("upd_check_t"), t("upd_err", err=e))

    def quit_for_update(self):
        self.on_close()

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
        page_times = []
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
                t_page = time.time()
                self.log(t("log_capturing", n=n))
                cap = t("page_n", n=n)
                if cfg["mode"] == "scroll":
                    img = capture_page(tgt, cfg["scroll"], cfg["steps"], cfg["thresh"], cfg["gap"], self.log,
                                       delay=max(0.3, min(cfg["delay"], 1.0)),
                                       preview=lambda a: self.preview(a, cap))
                else:
                    img = tgt.grab()
                    if img is None:
                        raise RuntimeError(t("win_gone"))
                    self.preview(img, cap)
                exact = last is not None and last.shape == img.shape and np.mean(cv2.absdiff(last, img)) < 0.5
                repeat = cfg["dups"] and last is not None and (exact or same_page(last, img))
                if (cfg["end"] and exact) or repeat:
                    same += 1
                    if repeat and not (cfg["end"] and exact):
                        self.log(t("log_dup", n=n, k=same), "warn")
                        self.ui(lambda n=n: self.panel.set_notice(t("notice_dup", n=n)) if self.panel else None)
                    else:
                        self.log(t("log_same", n=n, k=same), "warn")
                    if same >= (2 if cfg["end"] else 3):  # the page did not change after 2-3 tries: the end
                        reason = "end"
                        break
                    pyautogui.press(cfg["key"])
                    time.sleep(cfg["delay"])
                    continue
                same, last = 0, img
                Image.fromarray(img).save(os.path.join(cfg["temp"], f"page_{n:03d}.png"))
                saved += 1
                n += 1
                page_times.append(time.time() - t_page)
                recent = page_times[-6:]
                eta = (sum(recent) / len(recent)) * (cfg["pages"] - saved) if cfg["pages"] and saved >= 2 else None
                total = t("total_of", p=cfg["pages"]) if cfg["pages"] else ""
                self.set_status(t("captured", n=n - 1, saved=saved, total=total))
                self.log(t("log_saved", n=n - 1, w=img.shape[1], h=img.shape[0]))
                self.ui(lambda s=saved, e=eta: self.panel.set_progress(s, cfg["pages"], e) if self.panel else None)
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
                self.log(self.saved_msg(cfg, pdf).replace("\n", " "))
        except Exception as e:
            reason, err = "error", str(e)
            self.log(t("log_error", e=e), "err")
        if cfg.get("pending_name") and not list_pages(cfg["temp"]):
            try:
                os.rmdir(cfg["temp"])  # nothing was captured: do not leave an empty working folder
            except OSError:
                pass
        if saved and os.path.isdir(cfg["temp"]):
            self.update_project_meta(cfg)
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
        if self.recap_active:
            rt, rm = self.recap_step(reason, cfg, saved)
            if rt:
                title, msg, pdf = rt, rm, None
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
        self.refresh_projects()
        self.root.attributes("-topmost", True)
        self.pdf_done_dialog(title, msg, pdf)
        self.root.attributes("-topmost", False)


# ---------- embedded background (brand gradient) ----------
BG_B64 = (
    "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"
    "pIhFP//Z"
)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
