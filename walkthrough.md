# Walkthrough: Otimização do SplitVision

Concluímos a otimização do aplicativo **SplitVision** com sucesso. Substituímos as dependências externas pesadas por bibliotecas integradas e nativas em processo, melhorando a portabilidade, diminuindo o tamanho em disco e evitando qualquer comportamento que pudesse ser interpretado por antivírus como malware (heurística de subprocessos).

## Mudanças Realizadas

1. **Substituição do Poppler por PyPDFium2**:
   - Removemos a biblioteca `pdf2image` e o utilitário externo `pdftoppm.exe` do Poppler.
   - Implementamos a renderização de páginas de PDF diretamente em processo utilizando o `pypdfium2` (Google PDFium wrapper).

2. **Substituição do Tesseract OCR por Windows Native OCR**:
   - Removemos a dependência do `pytesseract` e do motor do `tesseract` executável externo.
   - Implementamos o acesso às APIs nativas de OCR do Windows (`Windows.Media.Ocr`) através da biblioteca `winocr` e do `winrt`.
   - Adicionamos a detecção dinâmica de idioma (`obter_idioma_ocr()`), priorizando o português (`pt-BR`) instalado no sistema do usuário.

3. **Remoção de Execução de Subprocessos**:
   - Removemos o desvio de criação de processos (`subprocess.Popen` e o patch associado).
   - O aplicativo agora executa de forma 100% interna ("in-process"), eliminando disparos de janelas ocultas e o risco de ser classificado como malware ou comportamento suspeito por antivírus (heurísticas comuns).

4. **Limpeza do Workspace**:
   - Deletamos as pastas obsoletas `poppler/` (24 MB) e `tesseract/` (83 MB).

---

## Comparação de Tamanho e Distribuição

| Componente | Antes | Depois | Redução |
| :--- | :--- | :--- | :--- |
| **Pasta Poppler** | 24,02 MB | *Removida* | -24,02 MB |
| **Pasta Tesseract** | 83,14 MB | *Removida* | -83,14 MB |
| **Pasta Standalone (`.dist`)** | 49,04 MB | 64,16 MB | +15,12 MB *(pelo PyPDFium2 + WinRT)* |
| **Tamanho Total de Distribuição** | **156,20 MB** | **64,16 MB** | **-92,04 MB (Redução de ~59%)** |

---

## Verificação e Testes

- **Compilação**: Compilamos com Nuitka com sucesso (`nuitka --standalone --enable-plugin=tk-inter --windows-console-mode=disable splitvision.py`).
- **Execução**: O executável compilado em `splitvision.dist\splitvision.exe` inicializa a interface gráfica normalmente e se integra perfeitamente ao sistema de drag-and-drop (`pywindnd`).
- **Logs**: O arquivo `log_processamento.txt` agora informa corretamente se a página foi lida por texto digital ou utilizando o `OCR Windows (pt-BR)`.
