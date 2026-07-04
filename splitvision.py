import os
import re
import sys
import threading
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageFont, ImageTk
from PyPDF2 import PdfReader, PdfWriter
import pypdfium2 as pdfium
import windnd
import winocr
import winrt.windows.media.ocr as ocr

# Determina caminho absoluto para o executável ou script
if getattr(sys, "frozen", False):
    diretorio_base = os.path.dirname(sys.executable)
else:
    diretorio_base = os.path.dirname(os.path.abspath(__file__))

arquivo_pdf = None  # caminho do PDF selecionado


def obter_idioma_ocr():
    try:
        idiomas = [lang.language_tag for lang in ocr.OcrEngine.available_recognizer_languages]
        if not idiomas:
            return None

        # Preferir português
        for tag in ("pt-BR", "pt-PT", "pt"):
            for disp in idiomas:
                if disp.lower() == tag.lower() or disp.lower().startswith(tag.lower() + "-"):
                    return disp

        # Preferir inglês
        for tag in ("en-US", "en"):
            for disp in idiomas:
                if disp.lower() == tag.lower() or disp.lower().startswith(tag.lower() + "-"):
                    return disp

        return idiomas[0]
    except Exception:
        return None


def carregar_idiomas_ocr():
    try:
        return [lang.language_tag for lang in ocr.OcrEngine.available_recognizer_languages]
    except Exception:
        return []


def sanitizar_nome_arquivo(nome):
    if not nome:
        return "pagina"
    # Substitui caracteres inválidos do Windows por hífens
    nome_limpo = re.sub(r'[\\/*?:"<>|]', "-", nome)
    # Remove múltiplos hífens ou espaços
    nome_limpo = re.sub(r'-+', "-", nome_limpo)
    nome_limpo = re.sub(r'\s+', " ", nome_limpo)
    return nome_limpo.strip("- ")


def validar_caminho_pdf(caminho):
    if not caminho:
        raise ValueError("Nenhum arquivo foi selecionado.")
    caminho_abs = os.path.abspath(caminho)
    if not os.path.isfile(caminho_abs):
        raise FileNotFoundError(f"Arquivo PDF não encontrado: {caminho_abs}")
    if not caminho_abs.lower().endswith(".pdf"):
        raise ValueError("O arquivo selecionado não é um PDF válido.")
    return caminho_abs


def validar_pasta_saida(pasta):
    if not pasta:
        raise ValueError("Nenhuma pasta de saída foi selecionada.")
    pasta_abs = os.path.abspath(pasta)
    if os.path.exists(pasta_abs) and not os.path.isdir(pasta_abs):
        raise NotADirectoryError(f"O caminho de saída não é uma pasta válida: {pasta_abs}")
    return pasta_abs


def escolher_arquivo():
    global arquivo_pdf
    caminho = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
    if caminho:
        try:
            arquivo_pdf = validar_caminho_pdf(caminho)
            atualizar_interface_arquivo()
        except Exception as exc:
            messagebox.showerror("Arquivo inválido", str(exc))


def dropped_files(files):
    global arquivo_pdf
    if files:
        caminho = files[0]
        try:
            arquivo_pdf = validar_caminho_pdf(caminho)
            atualizar_interface_arquivo()
        except Exception as exc:
            messagebox.showwarning("Formato incorreto", str(exc))


def escolher_pasta_saida():
    pasta = filedialog.askdirectory(title="Selecione a pasta onde salvar os arquivos split")
    if pasta:
        try:
            pasta_valida = validar_pasta_saida(pasta)
            pasta_saida_var.set(pasta_valida)
        except Exception as exc:
            messagebox.showerror("Pasta inválida", str(exc))


def atualizar_interface_arquivo():
    global arquivo_pdf
    if arquivo_pdf:
        nome_curto = os.path.basename(arquivo_pdf)
        if len(nome_curto) > 35:
            nome_curto = nome_curto[:32] + "..."
        texto_label = f"PDF Carregado: {nome_curto}"
        lbl_arquivo.config(
            text=texto_label,
            bg="#0067C0",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=10,
            pady=8,
            relief="flat",
        )
        lbl_arquivo.pack(pady=10)
        
        # Define diretório padrão se ainda não estiver configurado
        if not pasta_saida_var.get():
            pasta_saida_var.set(os.path.dirname(arquivo_pdf))
            
        set_progresso(0)
        btn_processar.config(state="normal", bg=COR_ATIVO, fg=COR_TEXTO)
    else:
        lbl_arquivo.pack_forget()
        btn_processar.config(state="disabled", bg=COR_DESATIVADO, fg=COR_TEXTO_DESATIVADO, disabledforeground=COR_TEXTO_DESATIVADO)


def set_progresso(porcentagem, total_paginas=None, pagina_atual=None):
    canvas_progresso.delete("all")
    # Fundo da barra
    canvas_progresso.create_rectangle(0, 0, 380, 25, fill="#E5E5E5", outline="", width=0)
    # Progresso preenchido
    largura = int(380 * (porcentagem / 100))
    if largura > 0:
        canvas_progresso.create_rectangle(0, 0, largura, 25, fill="#0067C0", outline="", width=0)
    
    # Texto
    if total_paginas and pagina_atual:
        texto = f"{porcentagem}% ({pagina_atual}/{total_paginas})"
    else:
        texto = f"{porcentagem}%"
    
    cor_texto = "#1A1A1A" if porcentagem < 50 else "#FFFFFF"
    canvas_progresso.create_text(190, 12, text=texto, font=("Segoe UI", 10, "bold"), fill=cor_texto)


def limpar_texto(texto):
    if not texto:
        return ""
    return re.sub(r"\s+", " ", texto).strip()


def extrair_dados_nome_codigo_data(texto):
    if not texto:
        return None

    linhas = texto.splitlines()
    for idx, linha in enumerate(linhas):
        match_codigo = re.search(r'C[óoí]{1,2}d[oií]?go\s*[:\-]?\s*(\d+)', linha, re.IGNORECASE)
        match_nome = re.search(r'\bNome\s*[:\-]?\s*', linha, re.IGNORECASE)
        
        if match_nome and match_codigo:
            start_nome_val = match_nome.end()
            end_nome_val = match_codigo.start()
            
            if start_nome_val < end_nome_val:
                nome = limpar_texto(linha[start_nome_val:end_nome_val])
                codigo = match_codigo.group(1)
                
                # Procura a data nas linhas seguintes
                data = None
                for j in range(idx + 1, len(linhas)):
                    linha_data = linhas[j]
                    match_data = re.search(r'Data\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', linha_data, re.IGNORECASE)
                    if not match_data:
                        match_data = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', linha_data)
                    
                    if match_data:
                        data = match_data.group(1).replace("/", "-")
                        break # Encontrou a data, não precisa ler mais
                
                if nome and codigo:
                    return nome, codigo, data

    # Se não encontrou no formato específico da mesma linha, faz o fallback para a busca genérica
    nome = None
    codigo = None
    data = None

    padrao_nome = re.search(r"Nome\s*[:\-]\s*(.+?)(?=\n|$|C[óoí]{1,2}d[oií]?go)", texto, re.IGNORECASE | re.DOTALL)
    if padrao_nome:
        nome = limpar_texto(padrao_nome.group(1))
        if nome and (nome.lower().startswith("código") or nome.lower().startswith("codigo")):
            nome = None

    padrao_codigo = re.search(r"C[óoí]{1,2}d[oií]?go\s*[:\-]\s*(\d+)", texto, re.IGNORECASE)
    if padrao_codigo:
        codigo = padrao_codigo.group(1)

    padrao_data = re.search(r"Data\s*[:\-]\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", texto, re.IGNORECASE)
    if not padrao_data:
        padrao_data = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", texto)
    if padrao_data:
        data = padrao_data.group(1).replace("/", "-")

    if nome and codigo:
        return nome, codigo, data
    return None


def montar_nome_personalizado(texto):
    dados = extrair_dados_nome_codigo_data(texto)
    if not dados:
        return None
    nome, codigo, data = dados
    if data:
        return f"{codigo} - {nome} - {data}"
    return f"{codigo} - {nome}"


def reconstruir_layout_ocr(res):
    if not res or not res.get("lines"):
        return ""
    words = []
    for line in res.get("lines", []):
        for w in line.get("words", []):
            rect = w.get("bounding_rect", {})
            words.append({
                "text": w.get("text", ""),
                "x": rect.get("x", 0),
                "y": rect.get("y", 0)
            })
    if not words:
        return ""
    reconstructed_lines = []
    tolerance = 15
    words_sorted = sorted(words, key=lambda wd: wd["y"])
    current_line_words = []
    for w in words_sorted:
        if not current_line_words:
            current_line_words.append(w)
        else:
            avg_y = sum(x["y"] for x in current_line_words) / len(current_line_words)
            if abs(w["y"] - avg_y) <= tolerance:
                current_line_words.append(w)
            else:
                current_line_words.sort(key=lambda wd: wd["x"])
                reconstructed_lines.append(" ".join(x["text"] for x in current_line_words))
                current_line_words = [w]
    if current_line_words:
        current_line_words.sort(key=lambda wd: wd["x"])
        reconstructed_lines.append(" ".join(x["text"] for x in current_line_words))
    return "\n".join(reconstructed_lines)


def corrigir_rotacao_pagina(pdf_path, page_num):
    """Renderiza página para OCR com qualidade."""
    try:
        doc = pdfium.PdfDocument(pdf_path)
        page = doc[page_num]
        bitmap = page.render(scale=3)
        img = bitmap.to_pil()
        page.close()
        doc.close()
        return img
    except Exception:
        try:
            with Image.open(pdf_path) as img:
                if hasattr(img, "n_frames") and img.n_frames > page_num:
                    img.seek(page_num)
                elif page_num != 0:
                    return None
                if img.mode != "RGB":
                    img = img.convert("RGB")
                return img.copy()
        except Exception:
            return None


def limpar_logs():
    txt_log.config(state="normal")
    txt_log.delete("1.0", tk.END)
    txt_log.config(state="disabled")


def adicionar_log(mensagem):
    txt_log.config(state="normal")
    
    # Determina a tag de cor com base nas palavras-chave do log
    if "[ERRO]" in mensagem or "[ERRO CRÍTICO]" in mensagem or "falhou" in mensagem or "FALHA" in mensagem:
        tag = "erro"
    elif "[AVISO]" in mensagem or "Alerta" in mensagem:
        tag = "aviso"
    elif "[SUCESSO]" in mensagem or "PROCESSAMENTO CONCLUÍDO" in mensagem:
        tag = "sucesso"
    elif "=== " in mensagem:
        tag = "titulo"
    elif "[INFO]" in mensagem:
        tag = "info"
    else:
        tag = "normal"
        
    txt_log.insert(tk.END, mensagem + "\n", tag)
    txt_log.see(tk.END)
    txt_log.config(state="disabled")


# Cores customizáveis para os botões (Opção 2)
COR_ATIVO = "#0067C0"       # Altere esta cor para mudar o fundo ativo do botão
COR_HOVER = "#164FAF"       # Cor ao passar o mouse por cima
COR_DESATIVADO = "#0380ee"  # Cor do botão desativado
COR_TEXTO = "#FFFFFF"       # Cor do texto do botão ativo
COR_TEXTO_DESATIVADO = "#FFFFFF" # Cor do texto desativado

def desativar_botoes():
    btn_escolher.config(state="normal", bg=COR_DESATIVADO, fg=COR_TEXTO_DESATIVADO)
    btn_processar.config(state="disabled", bg=COR_DESATIVADO, fg=COR_TEXTO_DESATIVADO, disabledforeground=COR_TEXTO_DESATIVADO)
    btn_alterar_destino.config(state="disabled")
    combo_idioma.config(state="disabled")


def restaurar_botoes():
    btn_escolher.config(state="normal", bg=COR_ATIVO, fg=COR_TEXTO)
    if arquivo_pdf:
        btn_processar.config(state="normal", bg=COR_ATIVO, fg=COR_TEXTO)
    else:
        btn_processar.config(state="disabled", bg=COR_DESATIVADO, fg=COR_TEXTO_DESATIVADO, disabledforeground=COR_TEXTO_DESATIVADO)
    btn_alterar_destino.config(state="normal")
    
    if idiomas_disponiveis:
        combo_idioma.config(state="readonly")
    else:
        combo_idioma.config(state="disabled")


def processar_pdf_thread(caminho_pdf, pasta_saida, idioma_ocr_selecionado):
    log_caminho = os.path.join(pasta_saida, "log_processamento.txt")
    try:
        caminho_pdf = validar_caminho_pdf(caminho_pdf)
        pasta_saida = validar_pasta_saida(pasta_saida)
        os.makedirs(pasta_saida, exist_ok=True)

        # Limpa console de logs da interface
        root.after(0, limpar_logs)
        root.after(0, lambda: set_progresso(0))

        with open(log_caminho, "w", encoding="utf-8") as log_f:
            def registrar_log(msg):
                timestamp = datetime.now().strftime("%H:%M:%S")
                msg_formatada = f"[{timestamp}] {msg}"
                log_f.write(msg_formatada + "\n")
                log_f.flush()
                root.after(0, lambda m=msg_formatada: adicionar_log(m))

            registrar_log("=== INICIANDO EXTRAÇÃO E ORGANIZAÇÃO - SPLITVISION ===")
            if idioma_ocr_selecionado and idioma_ocr_selecionado != "Nenhum disponível":
                registrar_log(f"[INFO] OCR ativo com idioma: {idioma_ocr_selecionado}")
            else:
                registrar_log("[AVISO] OCR do Windows inativo ou nenhum idioma disponível.")

            reader = PdfReader(caminho_pdf)
            total_paginas = len(reader.pages)
            registrar_log(f"[INFO] Arquivo: {os.path.basename(caminho_pdf)} ({total_paginas} páginas)")

            root.after(0, lambda: set_progresso(0, total_paginas, 0))

            regex_padrao = re.compile(
                r"(\bDoc(?:umento|urnento|umeuto)?\b\s*[:\-]?\s*(\d+)|\b[O0]\s*\.?\s*S\b\s*\.?\s*[:\-]?\s*(\d+))",
                re.IGNORECASE,
            )

            def pagina_eh_continuacao(texto):
                return bool(re.search(r"\b(?:p\S?g[ií]?na|page|pg)\s*[:#\-]?\s*\d+\b", texto, re.IGNORECASE))

            def salvar_grupo(grupo):
                if not grupo or not grupo["paginas"]:
                    return
                writer = PdfWriter()
                for pagina in grupo["paginas"]:
                    writer.add_page(pagina)
                
                nome_seguro = sanitizar_nome_arquivo(grupo['nome_arquivo'])
                caminho_saida = os.path.join(pasta_saida, f"{nome_seguro}.pdf")
                with open(caminho_saida, "wb") as f:
                    writer.write(f)
                
                registrar_log(
                    f"[SUCESSO] Documento agrupado salvo: {nome_seguro}.pdf ({grupo['origem']}) -> {len(grupo['paginas'])} página(s)"
                )

            grupo_atual = None

            for i in range(total_paginas):
                page = reader.pages[i]
                texto_digital = ""

                try:
                    texto_digital = page.extract_text() or ""
                except Exception as e:
                    registrar_log(f"[AVISO] Não foi possível extrair texto digital da Página {i+1}: {str(e)}")

                texto_limpo = texto_digital.strip()
                padrao = None
                texto_analisado = ""
                origem = "Texto Digital"

                if texto_limpo:
                    padrao = regex_padrao.search(texto_limpo)
                    if padrao:
                        texto_analisado = texto_limpo
                    else:
                        nome_personalizado = montar_nome_personalizado(texto_limpo)
                        if nome_personalizado:
                            padrao = True
                            texto_analisado = texto_limpo

                if not padrao:
                    if idioma_ocr_selecionado and idioma_ocr_selecionado != "Nenhum disponível":
                        origem = f"OCR Windows ({idioma_ocr_selecionado})"
                        try:
                            img_pil = corrigir_rotacao_pagina(caminho_pdf, i)
                            if img_pil is not None:
                                # 1. Tenta OCR na orientação padrão (0 graus)
                                res = winocr.recognize_pil_sync(img_pil, lang=idioma_ocr_selecionado)
                                texto_ocr = reconstruir_layout_ocr(res)
                                texto_analisado = texto_ocr
                                padrao = regex_padrao.search(texto_ocr)
                                if not padrao:
                                    nome_personalizado = montar_nome_personalizado(texto_ocr)
                                    if nome_personalizado:
                                        padrao = True
                                        texto_analisado = texto_ocr
                                
                                # 2. Se não detectou o padrão, tenta rotacionar a imagem para ler
                                if not padrao:
                                    # Mapeamento: (Pillow Transpose, PDF Rotate Clockwise, Descrição de Log)
                                    tentativas_rotacao = [
                                        (Image.ROTATE_180, 180, "180° (de ponta cabeça)"),
                                        (Image.ROTATE_90, 270, "90° anti-horário"),
                                        (Image.ROTATE_270, 90, "90° horário")
                                    ]
                                    for pil_rot, pdf_rot, desc in tentativas_rotacao:
                                        try:
                                            img_rot = img_pil.transpose(pil_rot)
                                            res_rot = winocr.recognize_pil_sync(img_rot, lang=idioma_ocr_selecionado)
                                            texto_rot = reconstruir_layout_ocr(res_rot)
                                            
                                            padrao_rot = regex_padrao.search(texto_rot)
                                            if not padrao_rot:
                                                nome_pers_rot = montar_nome_personalizado(texto_rot)
                                                if nome_pers_rot:
                                                    padrao_rot = True
                                            
                                            if padrao_rot:
                                                # Rotaciona a página do PDF permanentemente
                                                page.rotate(pdf_rot)
                                                padrao = padrao_rot
                                                texto_analisado = texto_rot
                                                registrar_log(f"[SUCESSO] Página {i+1} corrigida de orientação: rotacionada em {desc} para leitura.")
                                                break
                                        except Exception as e_rot:
                                            registrar_log(f"[AVISO] Falha ao tentar rotação {desc} na página {i+1}: {str(e_rot)}")
                            else:
                                texto_analisado = "Falha ao renderizar imagem"
                                registrar_log(f"[AVISO] Página {i+1}: OCR falhou na renderização de imagem.")
                        except Exception as exc:
                            texto_analisado = f"[ERRO OCR]: {str(exc)}"
                            registrar_log(f"[ERRO] Página {i+1}: Erro durante OCR - {str(exc)}")
                    else:
                        origem = "Sem OCR"
                        texto_analisado = "OCR Inativo"
                        registrar_log(f"[AVISO] Página {i+1}: OCR não executado.")

                nome_identificador = None
                nome_arquivo = f"pagina_{i+1}"
                
                if padrao:
                    if isinstance(padrao, bool):
                        nome_personalizado = montar_nome_personalizado(texto_analisado)
                        if nome_personalizado:
                            nome_identificador = nome_personalizado
                            nome_arquivo = nome_personalizado
                        else:
                            nome_arquivo = f"pagina_{i+1}"
                    else:
                        numero = padrao.group(2) if padrao.group(2) else padrao.group(3)
                        prefixo = "Documento" if padrao.group(2) is not None else "OS"
                        nome_identificador = f"{prefixo}_{numero}"
                        nome_arquivo = nome_identificador

                    # Sanitiza para exibição de log limpa
                    nome_exibicao = sanitizar_nome_arquivo(nome_arquivo)
                    registrar_log(
                        f"[INFO] Página {i+1}: Padrão detectado! Renomeando para '{nome_exibicao}.pdf' ({origem})."
                    )
                else:
                    if grupo_atual is not None:
                        registrar_log(
                            f"[INFO] Página {i+1}: Sem padrão novo. Agrupada ao documento '{sanitizar_nome_arquivo(grupo_atual['nome_arquivo'])}.pdf' ({origem})."
                        )
                    else:
                        nome_exibicao = sanitizar_nome_arquivo(nome_arquivo)
                        registrar_log(
                            f"[INFO] Página {i+1}: Padrão não detectado. Salva como '{nome_exibicao}.pdf' ({origem})."
                        )

                if nome_identificador:
                    if grupo_atual is None:
                        grupo_atual = {"nome_arquivo": nome_arquivo, "paginas": [page], "origem": origem}
                    elif nome_identificador != grupo_atual.get("nome_arquivo"):
                        salvar_grupo(grupo_atual)
                        grupo_atual = {"nome_arquivo": nome_arquivo, "paginas": [page], "origem": origem}
                    else:
                        grupo_atual["paginas"].append(page)
                elif grupo_atual is not None:
                    grupo_atual["paginas"].append(page)
                else:
                    if grupo_atual is not None:
                        salvar_grupo(grupo_atual)
                        grupo_atual = None
                    
                    writer = PdfWriter()
                    writer.add_page(page)
                    nome_seguro = sanitizar_nome_arquivo(nome_arquivo)
                    caminho_saida = os.path.join(pasta_saida, f"{nome_seguro}.pdf")
                    with open(caminho_saida, "wb") as f:
                        writer.write(f)
                    registrar_log(f"[SUCESSO] Página individual salva: {nome_seguro}.pdf ({origem})")

                porcentagem = int((i + 1) / total_paginas * 100)
                root.after(0, lambda p=porcentagem, t=total_paginas, curr=i + 1: set_progresso(p, t, curr))

            if grupo_atual is not None:
                salvar_grupo(grupo_atual)

            registrar_log("=== PROCESSAMENTO CONCLUÍDO COM SUCESSO ===")

        def finalizar_sucesso():
            messagebox.showinfo(
                "Sucesso",
                f"✅ Arquivo processado!\nSalvo em:\n{pasta_saida}\nConsulte o console de logs ou o arquivo 'log_processamento.txt' para mais detalhes.",
            )
            root.after(0, restaurar_botoes)

        root.after(0, finalizar_sucesso)

    except Exception as exc:
        def finalizar_erro(err_msg):
            adicionar_log(f"[ERRO CRÍTICO] Falha no processamento: {err_msg}")
            messagebox.showerror("Erro", f"Ocorreu um erro crítico durante o processamento:\n{err_msg}")
            root.after(0, restaurar_botoes)

        root.after(0, finalizar_erro, str(exc))


def processar_pdf():
    global arquivo_pdf
    if not arquivo_pdf:
        messagebox.showwarning("Aviso", "Selecione ou arraste primeiro um arquivo PDF!")
        return

    pasta_saida = pasta_saida_var.get()
    try:
        pasta_saida = validar_pasta_saida(pasta_saida)
    except Exception as exc:
        messagebox.showerror("Pasta inválida", f"A pasta de saída configurada é inválida:\n{str(exc)}")
        return

    desativar_botoes()
    set_progresso(0)

    idioma_ocr_selecionado = idioma_ocr_var.get()
    
    threading.Thread(
        target=processar_pdf_thread, 
        args=(arquivo_pdf, pasta_saida, idioma_ocr_selecionado), 
        daemon=True
    ).start()


# --- Interface Gráfica ---
root = tk.Tk()
root.title("SplitVision PDF v1.1.0 - Organizador Inteligente")
root.geometry("1000x650")
root.minsize(850, 550)
root.configure(bg="#F1F3F5")

try:
    root.iconbitmap("splitvision.ico")
except Exception:
    pass

# Variáveis de Controle
pasta_saida_var = tk.StringVar()
idioma_ocr_var = tk.StringVar()

# Estilização TTK
style = ttk.Style()
style.theme_use("clam")
style.configure("TFrame", background="#F1F3F5")
style.configure("TLabelframe", background="#FFFFFF", bordercolor="#E9ECEF", borderwidth=1)
style.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"), foreground="#495057", background="#FFFFFF")
style.configure("TEntry", fieldbackground="#F8F9FA", bordercolor="#CED4DA", padding=5)
style.configure("TCombobox", fieldbackground="#F8F9FA", bordercolor="#CED4DA")

# --- Cabeçalho (Header Banner) ---
header_frame = tk.Frame(root, bg="#0067C0", height=80)
header_frame.pack(fill="x", side="top")
header_frame.pack_propagate(False)

lbl_titulo = tk.Label(
    header_frame, 
    text="SplitVision PDF", 
    font=("Segoe UI", 20, "bold"), 
    fg="white", 
    bg="#0067C0"
)
lbl_titulo.pack(anchor="w", padx=25, pady=(15, 0))

lbl_subtitulo = tk.Label(
    header_frame, 
    text="Organização inteligente de páginas de PDF com OCR integrado e in-process", 
    font=("Segoe UI", 10), 
    fg="#D0E1FD", 
    bg="#0067C0"
)
lbl_subtitulo.pack(anchor="w", padx=25, pady=(0, 10))


# --- Corpo Principal (Two Panes) ---
body_frame = tk.Frame(root, bg="#F1F3F5", padx=15, pady=15)
body_frame.pack(fill="both", expand=True)

# Grid Layout: 2 colunas
body_frame.columnconfigure(0, weight=4, minsize=400) # Coluna de Controles (Esquerda)
body_frame.columnconfigure(1, weight=5, minsize=400) # Coluna de Logs (Direita)
body_frame.rowconfigure(0, weight=1)

# PANE ESQUERDA (Controles)
pane_esquerda = ttk.Frame(body_frame, style="TFrame")
pane_esquerda.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

# Card de Arquivo e Arraste
card_arquivo = ttk.LabelFrame(pane_esquerda, text=" 1. Selecionar Arquivo PDF ")
card_arquivo.pack(fill="x", pady=(0, 10))

canvas_arraste = tk.Canvas(card_arquivo, height=130, bg="#F8F9FA", highlightthickness=0)
canvas_arraste.pack(fill="x", padx=15, pady=15)
canvas_arraste.create_rectangle(4, 4, 380, 126, outline="#0067C0", dash=(4, 4), width=1)
canvas_arraste.create_text(190, 30, text="Arraste e solte o PDF aqui", font=("Segoe UI", 11, "bold"), fill="#212529")
canvas_arraste.create_text(190, 55, text="ou se preferir clique no botão abaixo", font=("Segoe UI", 9), fill="#6C757D")

# Imagens de botões Pillow com Fallback
def _create_rounded_button_image(width, height, radius, color, text, text_color):
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    start_color = color
    end_color = color
    if isinstance(color, str) and "," in color:
        parts = [part.strip() for part in color.split(",", 1)]
        if len(parts) == 2:
            start_color, end_color = parts

    def hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 6:
            return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
        return (0, 0, 0)

    sc = hex_to_rgb(start_color)
    ec = hex_to_rgb(end_color)

    if start_color != end_color:
        gradient = Image.new("RGBA", (width, height))
        gradient_draw = ImageDraw.Draw(gradient)
        for y in range(height):
            t = y / max(height - 1, 1)
            r = int(sc[0] + (ec[0] - sc[0]) * t)
            g = int(sc[1] + (ec[1] - sc[1]) * t)
            b = int(sc[2] + (ec[2] - sc[2]) * t)
            gradient_draw.line((0, y, width, y), fill=(r, g, b, 255))

        mask = Image.new("L", (width, height), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle((0, 0, width, height), radius=radius, fill=255)
        img.paste(gradient, (0, 0), mask)
    else:
        draw.rounded_rectangle((0, 0, width, height), radius=radius, fill=start_color)

    font = None
    for font_name in ["segoeui.ttf", "arial.ttf", "tahoma.ttf", "seguiemj.ttf"]:
        try:
            font = ImageFont.truetype(font_name, 12)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
    except Exception:
        try:
            w, h = font.getsize(text)
        except Exception:
            w, h = 80, 15

    draw.text(((width - w) / 2, (height - h) / 2), text, font=font, fill=text_color)
    return ImageTk.PhotoImage(img)

# --- Botões Estilizados Sem Imagens (Opção 2) ---
btn_escolher = tk.Button(
    canvas_arraste, 
    text="Escolher Arquivo",
    command=escolher_arquivo,
    font=("Segoe UI", 10, "bold"),
    fg=COR_TEXTO,
    bg=COR_ATIVO,
    activebackground=COR_HOVER,
    activeforeground=COR_TEXTO,
    disabledforeground=COR_TEXTO_DESATIVADO,
    bd=0,
    relief="flat",
    cursor="hand2",
    padx=15,
    pady=6
)
canvas_arraste.create_window(190, 92, window=btn_escolher)

def on_enter_escolher(e):
    if btn_escolher["state"] == "normal":
        btn_escolher.config(bg=COR_HOVER)

def on_leave_escolher(e):
    if btn_escolher["state"] == "normal":
        btn_escolher.config(bg=COR_ATIVO)

btn_escolher.bind("<Enter>", on_enter_escolher)
btn_escolher.bind("<Leave>", on_leave_escolher)

lbl_arquivo = tk.Label(card_arquivo, font=("Segoe UI", 10, "bold"), bg="white", borderwidth=0)


# Card de Configuração de Destino
card_destino = ttk.LabelFrame(pane_esquerda, text=" 2. Pasta de Saída ")
card_destino.pack(fill="x", pady=(0, 10))

frame_destino_sub = tk.Frame(card_destino, bg="white")
frame_destino_sub.pack(fill="x", padx=15, pady=15)

entry_destino = ttk.Entry(frame_destino_sub, textvariable=pasta_saida_var, font=("Segoe UI", 9))
entry_destino.pack(side="left", fill="x", expand=True, padx=(0, 10))

btn_alterar_destino = ttk.Button(frame_destino_sub, text="Alterar", command=escolher_pasta_saida)
btn_alterar_destino.pack(side="right")


# Card de Opções do OCR
card_ocr = ttk.LabelFrame(pane_esquerda, text=" 3. Configurações de OCR ")
card_ocr.pack(fill="x", pady=(0, 10))

frame_ocr_sub = tk.Frame(card_ocr, bg="white")
frame_ocr_sub.pack(fill="x", padx=15, pady=15)

lbl_ocr_info = tk.Label(
    frame_ocr_sub, 
    text="Idioma do OCR do Windows (Native OcrEngine):", 
    font=("Segoe UI", 9), 
    bg="white", 
    fg="#495057"
)
lbl_ocr_info.pack(anchor="w", pady=(0, 5))

idiomas_disponiveis = carregar_idiomas_ocr()
combo_idioma = ttk.Combobox(frame_ocr_sub, textvariable=idioma_ocr_var, state="readonly", font=("Segoe UI", 9))

if idiomas_disponiveis:
    combo_idioma['values'] = idiomas_disponiveis
    default_lang = obter_idioma_ocr()
    if default_lang in idiomas_disponiveis:
        combo_idioma.set(default_lang)
    else:
        combo_idioma.set(idiomas_disponiveis[0])
else:
    combo_idioma['values'] = ["Nenhum disponível"]
    combo_idioma.set("Nenhum disponível")
    combo_idioma.config(state="disabled")

combo_idioma.pack(fill="x")


# Progresso e Botão de Ação
card_acao = tk.Frame(pane_esquerda, bg="#F1F3F5")
card_acao.pack(fill="x", pady=(10, 0))

canvas_progresso = tk.Canvas(card_acao, width=380, height=25, bg="#F1F3F5", highlightthickness=0)
canvas_progresso.pack(pady=(0, 10))
set_progresso(0)

btn_processar = tk.Button(
    card_acao,
    text="Separar e Renomear",
    command=processar_pdf,
    font=("Segoe UI", 11, "bold"),
    fg=COR_TEXTO_DESATIVADO,
    bg=COR_DESATIVADO,
    activebackground=COR_HOVER,
    activeforeground=COR_TEXTO,
    disabledforeground=COR_TEXTO_DESATIVADO,
    bd=0,
    relief="flat",
    state="disabled",
    cursor="hand2",
    padx=30,
    pady=10
)
btn_processar.pack(pady=5)

def on_enter_processar(e):
    if btn_processar["state"] == "normal":
        btn_processar.config(bg=COR_HOVER)

def on_leave_processar(e):
    if btn_processar["state"] == "normal":
        btn_processar.config(bg=COR_ATIVO)

btn_processar.bind("<Enter>", on_enter_processar)
btn_processar.bind("<Leave>", on_leave_processar)


# PANE DIREITA (Logs)
pane_direita = ttk.LabelFrame(body_frame, text=" Log de Processamento (Tempo Real) ")
pane_direita.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

# Container para text box e scrollbar
log_container = tk.Frame(pane_direita, bg="#1A1D20")
log_container.pack(fill="both", expand=True, padx=10, pady=10)

txt_log = tk.Text(
    log_container, 
    bg="#1A1D20", 
    fg="#E9ECEF", 
    insertbackground="white",
    font=("Consolas", 9), 
    relief="flat",
    state="disabled",
    wrap="word"
)
txt_log.pack(side="left", fill="both", expand=True)

# Custom tags coloridas para o console de log
txt_log.tag_config("erro", foreground="#FF6B6B")       # vermelho suave
txt_log.tag_config("aviso", foreground="#FFD25A")      # amarelo suave
txt_log.tag_config("sucesso", foreground="#51CF66")    # verde suave
txt_log.tag_config("titulo", foreground="#339AF0", font=("Consolas", 9, "bold")) # azul negrito
txt_log.tag_config("info", foreground="#9ECBFF")       # azul claro suave
txt_log.tag_config("normal", foreground="#E9ECEF")     # cinza claro

scrollbar_log = ttk.Scrollbar(log_container, orient="vertical", command=txt_log.yview)
scrollbar_log.pack(side="right", fill="y")
txt_log.config(yscrollcommand=scrollbar_log.set)


# --- Rodapé (Footer) ---
footer_frame = tk.Frame(root, bg="#F1F3F5")
footer_frame.pack(side="bottom", pady=10)

lbl_rodape_p1 = tk.Label(
    footer_frame,
    text="SplitVision PDF v1.1.0 | Desenvolvido por ",
    font=("Segoe UI", 8),
    fg="#6C757D",
    bg="#F1F3F5"
)
lbl_rodape_p1.pack(side="left")

lbl_rodape_p2 = tk.Label(
    footer_frame,
    text="Tonivan Joseph",
    font=("Segoe UI", 8, "bold"),
    fg="#6C757D",
    bg="#F1F3F5"
)
lbl_rodape_p2.pack(side="left")

lbl_rodape_p3 = tk.Label(
    footer_frame,
    text=" | Todos os direitos reservados",
    font=("Segoe UI", 8),
    fg="#6C757D",
    bg="#F1F3F5"
)
lbl_rodape_p3.pack(side="left")


# Registra Drop global de arquivos (com fallback para compatibilidade)
if hasattr(windnd, "hook_dropfiles"):
    windnd.hook_dropfiles(root, func=dropped_files, force_unicode=True)
elif hasattr(windnd, "drop_files"):
    windnd.drop_files(root, func=dropped_files, force_unicode=True)

# Mantém referências das imagens Pillow para evitar coleta de lixo (garbage collection)
_IMG_REFS = []

# Inicializa exibindo uma mensagem de boas-vindas no painel de log
adicionar_log("=== BEM-VINDO AO SPLITVISION PDF ===")
adicionar_log("[INFO] Aguardando seleção de arquivo PDF para iniciar...")

root.mainloop()