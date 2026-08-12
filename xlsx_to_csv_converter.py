#!/usr/bin/env python3
"""
Conversor XLS/XLSX para CSV
Converte automaticamente arquivos da pasta de documentos do Itaú
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import logging
from typing import List, Tuple

try:
    import openpyxl
    import pandas as pd
except ImportError:
    print("Instalando dependências necessárias...")
    os.system("pip install openpyxl pandas")
    import openpyxl
    import pandas as pd


# Configuração de logging
log_file = Path(__file__).parent / "converter_log.txt"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class XLSXtoCSVConverter:
    def __init__(self, source_folder: str):
        """
        Inicializa o conversor

        Args:
            source_folder: Caminho da pasta contendo arquivos XLS/XLSX
        """
        self.source_folder = Path(source_folder)
        self.converted_files = []
        self.failed_files = []

        if not self.source_folder.exists():
            logger.error(f"Pasta não encontrada: {self.source_folder}")
            sys.exit(1)

    def find_excel_files(self) -> List[Path]:
        """Encontra todos os arquivos XLS/XLSX na pasta"""
        excel_extensions = {'.xls', '.xlsx', '.xlsm'}
        files = [
            f for f in self.source_folder.rglob('*')
            if f.suffix.lower() in excel_extensions and not f.name.startswith('~')
        ]
        logger.info(f"Encontrados {len(files)} arquivo(s) Excel")
        return sorted(files)

    def get_sheet_info(self, excel_file: Path) -> List[str]:
        """Obtém nomes das abas do arquivo Excel"""
        try:
            wb = openpyxl.load_workbook(excel_file, data_only=False)
            return wb.sheetnames
        except Exception as e:
            logger.error(f"Erro ao ler abas de {excel_file}: {e}")
            return []

    def convert_sheet_to_csv(self, excel_file: Path, sheet_name: str = None) -> bool:
        """
        Converte uma aba do Excel para CSV

        Args:
            excel_file: Caminho do arquivo Excel
            sheet_name: Nome da aba (None = primeira aba)

        Returns:
            True se converteu com sucesso
        """
        try:
            # Lê o arquivo Excel
            df = pd.read_excel(excel_file, sheet_name=sheet_name or 0)

            # Cria nome do arquivo CSV
            file_stem = excel_file.stem

            if sheet_name and sheet_name != (self.get_sheet_info(excel_file)[0] or 'Sheet1'):
                # Se tem múltiplas abas, adiciona nome da aba ao CSV
                csv_filename = f"{file_stem}_{sheet_name}.csv"
            else:
                csv_filename = f"{file_stem}.csv"

            csv_path = excel_file.parent / csv_filename

            # Salva como CSV
            df.to_csv(csv_path, index=False, encoding='utf-8-sig')

            logger.info(f"✓ Convertido: {excel_file.name} → {csv_filename}")
            self.converted_files.append((excel_file.name, csv_filename))
            return True

        except Exception as e:
            logger.error(f"✗ Erro ao converter {excel_file.name}: {e}")
            self.failed_files.append((excel_file.name, str(e)))
            return False

    def convert_all(self, skip_multiple_sheets: bool = False) -> None:
        """
        Converte todos os arquivos Excel encontrados

        Args:
            skip_multiple_sheets: Se True, não converte abas adicionais
        """
        files = self.find_excel_files()

        if not files:
            logger.warning("Nenhum arquivo Excel encontrado!")
            return

        logger.info(f"Iniciando conversão de {len(files)} arquivo(s)...\n")

        for excel_file in files:
            sheets = self.get_sheet_info(excel_file)

            if not sheets:
                logger.warning(f"Nenhuma aba encontrada em {excel_file.name}")
                continue

            # Converte primeira aba
            self.convert_sheet_to_csv(excel_file, sheets[0])

            # Converte abas adicionais (opcional)
            if not skip_multiple_sheets and len(sheets) > 1:
                for sheet in sheets[1:]:
                    self.convert_sheet_to_csv(excel_file, sheet)

        self.print_summary()

    def convert_single_file(self, filename: str) -> None:
        """Converte um arquivo específico"""
        file_path = self.source_folder / filename

        if not file_path.exists():
            logger.error(f"Arquivo não encontrado: {filename}")
            return

        sheets = self.get_sheet_info(file_path)
        logger.info(f"Abas encontradas: {sheets}\n")

        for i, sheet in enumerate(sheets, 1):
            logger.info(f"Convertendo aba {i}/{len(sheets)}: {sheet}")
            self.convert_sheet_to_csv(file_path, sheet)

        self.print_summary()

    def print_summary(self) -> None:
        """Imprime resumo da conversão"""
        print("\n" + "="*50)
        print("RESUMO DA CONVERSÃO")
        print("="*50)
        print(f"Total convertidos: {len(self.converted_files)}")
        print(f"Total com erro: {len(self.failed_files)}")

        if self.converted_files:
            print(f"\n✓ Convertidos com sucesso:")
            for original, csv in self.converted_files:
                print(f"  • {original} → {csv}")

        if self.failed_files:
            print(f"\n✗ Erros:")
            for filename, error in self.failed_files:
                print(f"  • {filename}: {error}")

        print(f"\nLog salvo em: {log_file}")
        print("="*50)


def main():
    """Função principal"""
    # Caminho da pasta do Itaú
    itau_folder = r"C:\Users\Juliane\OneDrive\Documentos\Itaú"

    # Cria conversor
    converter = XLSXtoCSVConverter(itau_folder)

    # Menu de opções
    if len(sys.argv) > 1:
        if sys.argv[1].lower() == '--single' and len(sys.argv) > 2:
            # Converte um arquivo específico
            converter.convert_single_file(sys.argv[2])
        elif sys.argv[1].lower() == '--help':
            print_help()
        else:
            print(f"Argumento desconhecido: {sys.argv[1]}")
            print_help()
    else:
        # Converte todos (padrão)
        converter.convert_all()


def print_help():
    """Mostra ajuda"""
    print("""
Conversor XLS/XLSX para CSV

Uso:
  python xlsx_to_csv_converter.py          # Converte todos os arquivos
  python xlsx_to_csv_converter.py --single arquivo.xlsx  # Converte um arquivo
  python xlsx_to_csv_converter.py --help   # Mostra esta ajuda

Pasta padrão: C:\\Users\\Juliane\\OneDrive\\Documentos\\Itaú

Recursos:
  • Converte arquivos XLS, XLSX e XLSM
  • Preserva codificação UTF-8 com BOM
  • Suporta múltiplas abas (converte cada uma como um CSV)
  • Gera log de operações
  • Ignora arquivos temporários (começam com ~)
    """)


if __name__ == "__main__":
    main()
