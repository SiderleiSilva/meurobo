import json
import os
import glob
import io
import pandas as pd

FOLDER_PATH = r"C:\NOVOS SIMULADOS\ROBO"
OUTPUT_JSON_PATH = os.path.join(FOLDER_PATH, "trades_data.json")

def ler_csv_profit(caminho_arquivo):
    """Lê arquivos CSV do Profit identificando o cabeçalho correto."""
    encodings = ['utf-16', 'latin1', 'utf-8-sig', 'utf-8', 'cp1252']
    
    for enc in encodings:
        try:
            with open(caminho_arquivo, 'r', encoding=enc) as f:
                linhas = f.readlines()
            
            header_index = -1
            for idx, linha in enumerate(linhas):
                if any(k in linha for k in ["Operação", "Lado", "Resultado", "Preço", "Data/Hora", "Ativo"]):
                    header_index = idx
                    break
            
            if header_index != -1:
                conteudo = "".join(linhas[header_index:])
                primeira_linha = linhas[header_index]
                sep = ';' if ';' in primeira_linha else ('\t' if '\t' in primeira_linha else ',')
                df = pd.read_csv(io.StringIO(conteudo), sep=sep)
                return df
        except Exception:
            continue
            
    return pd.read_csv(caminho_arquivo, sep=None, engine='python', on_bad_lines='skip')

def processar_relatorio():
    arquivos = glob.glob(os.path.join(FOLDER_PATH, "*.csv")) + glob.glob(os.path.join(FOLDER_PATH, "*.xlsx"))
    arquivos = [f for f in arquivos if not os.path.basename(f).startswith("~$")]
    
    if not arquivos:
        print("⚠️ Nenhum arquivo de relatório encontrado na pasta.")
        return

    todos_os_trades = []

    # Loop para ler TODOS os arquivos CSV/XLSX salvos na pasta
    for arquivo in arquivos:
        nome_arquivo = os.path.basename(arquivo)
        print(f"📄 Processando arquivo: {nome_arquivo}")

        try:
            if arquivo.endswith('.xlsx'):
                df = pd.read_excel(arquivo)
            else:
                df = ler_csv_profit(arquivo)

            nome_estrategia = os.path.splitext(nome_arquivo)[0].upper()

            for idx, row in df.iterrows():
                res_val = str(row.get("Resultado", row.get("Res. Operação", row.get("Total", 0))))
                
                if pd.isna(res_val) or res_val == "nan" or not res_val.strip():
                    continue

                res_clean = res_val.replace("R$", "").replace("pts", "").replace(".", "").replace(",", ".").strip()
                
                try:
                    pnl = float(res_clean)
                except ValueError:
                    continue

                lado_str = str(row.get("Lado/Quantidade", row.get("Lado", row.get("Tipo", "COMPRA")))).upper()
                tipo_trade = "COMPRA" if ("C" in lado_str or "COMPRA" in lado_str) else "VENDA"
                horario = str(row.get("Data/Hora", row.get("Horário", f"Trade #{idx+1}")))

                todos_os_trades.append({
                    "time": horario,
                    "strategy": nome_estrategia,
                    "asset": str(row.get("Ativo", "WIN")),
                    "type": tipo_trade,
                    "qty": 1,
                    "pnl": pnl
                })

        except Exception as e:
            print(f"❌ Erro ao ler o arquivo {nome_arquivo}: {e}")

    # Salva todos os trades unificados no JSON
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(todos_os_trades, f, ensure_ascii=False, indent=2)

    print("✅ Sucesso! Todas as estratégias da pasta foram unificadas no Dashboard.")

if __name__ == "__main__":
    processar_relatorio()

   