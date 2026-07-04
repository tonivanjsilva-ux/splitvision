# Plano de Implementação: Otimização e Segurança do SplitVision

Este plano descreve a substituição das dependências externas pesadas (`Tesseract OCR` e `Poppler`) por soluções nativas e em processo (`Windows Native OCR` e `PyPDFium2`). Essa mudança reduzirá o tamanho do aplicativo no disco em cerca de 100 MB, tornará a execução muito mais rápida e evitará falsos positivos de antivírus causados pelo disparo de subprocessos executáveis (`tesseract.exe`, `pdftoppm.exe`).

## User Review Required

> [!IMPORTANT]
> **Requisitos do Sistema:** O aplicativo agora dependerá do recurso de OCR nativo do Windows (disponível por padrão no Windows 10 e 11). O idioma correspondente ao PDF (ex: `pt-BR`) deve estar instalado nas configurações de idioma do Windows (geralmente já está se o Windows do usuário estiver em português).

> [!WARNING]
> **Subprocessos Removidos:** Removemos completamente a necessidade de rodar arquivos executáveis externos. Toda a renderização de PDF e o OCR ocorrerão dentro do próprio processo do Python usando extensões C compiladas. Isso reduz drasticamente as chances de detecção heurística de antivírus (falsos positivos de malware).

## Open Questions

Não há dúvidas em aberto. A viabilidade do `winrt` OCR no ambiente do usuário foi testada com sucesso e detectou strings de teste perfeitamente.

## Proposed Changes

### Core Engine & Dependencies

Substituição das bibliotecas de renderização de imagem e OCR.

#### [MODIFY] [splitvision.py](file:///c:/Users/Tonivan/Downloads/SplitVision-1-0/splitvision.py)

1. **Remover Imports de Subprocessos e Ferramentas Antigas:**
   - Remover `import subprocess` e a função de desvio de janela preta `popen_sem_janela`.
   - Remover `import pytesseract` e `from pdf2image import convert_from_path`.

2. **Adicionar Novos Imports:**
   - Adicionar `import pypdfium2 as pdfium`.
   - Adicionar `import winocr`.
   - Adicionar `import winrt.windows.media.ocr as ocr`.

3. **Adicionar Detecção Dinâmica do Idioma do OCR:**
   - Implementar `obter_idioma_ocr()` para buscar dinamicamente as tags de idioma OCR suportadas pelo Windows (preferindo `pt-BR`, `pt-PT` ou qualquer variação de português/inglês instalada).

4. **Refatorar Fallback de OCR:**
   - Substituir `convert_from_path` (que chamava o `pdftoppm.exe` do Poppler) por renderização direta em processo com `pypdfium2`.
   - Substituir o OCR do Tesseract por `winocr.recognize_pil_sync` usando o idioma detectado do sistema Windows.

5. **Limpar Constantes Antigas:**
   - Remover caminhos absolutos e referências a `poppler` e `tesseract`.

---

### Cleanup

#### [DELETE] `tesseract/` (diretório)
- Remover o diretório `tesseract` do workspace (~83 MB).

#### [DELETE] `poppler/` (diretório)
- Remover o diretório `poppler` do workspace (~24 MB).

## Verification Plan

### Automated Tests
1. Rodar um script de teste para garantir a importação das novas bibliotecas (`pypdfium2`, `winrt`, `winocr`).
2. Executar o script `splitvision.py` localmente no interpretador Python e verificar a interface.

### Manual Verification
1. Abrir o aplicativo otimizado e arrastar um arquivo PDF.
2. Processar o PDF escolhendo um diretório de destino.
3. Verificar no arquivo `log_processamento.txt` se a leitura foi feita via `Texto Digital` ou pelo novo `OCR Windows (pt-BR)`.
4. Compilar o executável com Nuitka e rodar o executável gerado para validar que ele funciona perfeitamente sem as pastas `poppler` e `tesseract`.
