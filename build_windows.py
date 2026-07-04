import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "dist"
BUILD = ROOT / "build"


def run(cmd):
    print("\n>>", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(ROOT))


def clean():
    for folder in [OUTPUT, BUILD]:
        if folder.exists():
            try:
                shutil.rmtree(folder)
            except Exception as e:
                # O OneDrive ou o Windows Explorer costumam bloquear a remoção da pasta raiz.
                # Nesses casos, tentamos remover o conteúdo interno e ignorar a falha na pasta raiz.
                print(f"Aviso: Não foi possível remover a pasta raiz {folder.name} ({e}).")
                print("Limpando arquivos internos...")
                for item in folder.iterdir():
                    try:
                        if item.is_dir():
                            shutil.rmtree(item, ignore_errors=True)
                        else:
                            item.unlink()
                    except Exception as err:
                        print(f"Não foi possível remover {item.name}: {err}")


def main():
    clean()
    run([sys.executable, "-m", "pip", "install", "--upgrade", "pip", "pyinstaller"])
    
    # Importar pacotes para descobrir caminhos absolutos de dados
    import pypdfium2
    import pypdfium2_raw
    pypdfium2_path = Path(pypdfium2.__file__).parent
    pypdfium2_raw_path = Path(pypdfium2_raw.__file__).parent

    run([
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconsole",
        "--onefile",
        "--windowed",
        "--name",
        "splitvision",
        "--icon",
        "splitvision.ico",
        "--distpath",
        str(OUTPUT),
        "--workpath",
        str(BUILD),
        "--optimize",
        "2",
        "--exclude-module",
        "matplotlib",
        "--exclude-module",
        "tkinter.test",
        # Adicionar arquivos de dados do pypdfium2
        "--add-data", f"{pypdfium2_path / 'version.json'};pypdfium2",
        "--add-data", f"{pypdfium2_raw_path / 'version.json'};pypdfium2_raw",
        "--add-data", f"{pypdfium2_raw_path / 'pdfium.dll'};pypdfium2_raw",
        # Imports implícitos (hidden imports) para winrt e dependências
        "--hidden-import", "winrt",
        "--hidden-import", "winrt.windows.media.ocr",
        "--hidden-import", "winrt.windows.globalization",
        "--hidden-import", "winrt.windows.storage.streams",
        "--hidden-import", "winrt.windows.graphics.imaging",
        "--hidden-import", "winrt.windows.foundation",
        "--hidden-import", "winrt.windows.foundation.collections",
        "--hidden-import", "winocr",
        "--hidden-import", "windnd",
        "splitvision.py",
    ])
    print("\nBuild concluído em:", OUTPUT)


if __name__ == "__main__":
    main()
