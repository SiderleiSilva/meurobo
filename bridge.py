import os
import json
import csv
import subprocess
import time
import re
import io
from datetime import datetime

def clean_float(val_str):
    if not val_str:
        return 0.0
    # Remove aspas, espaços normais e inquebráveis, prefixo R$
    s = str(val_str).replace('"', '').replace("'", '').replace('\xa0', '').replace('R$', '').replace(' ', '').strip()
    if not s:
        return 0.0

    # Trata formatos contábeis de número negativo: (150,00) ou 150,00-
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1]
    elif s.endswith('-'):
        s = '-' + s[:-1]

    # Trata padrão brasileiro de milhar e decimal (1.500,50 -> 1500.50 ou -150,00 -> -150.00)
    if '.' in s and ',' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')

    # Garante apenas dígitos, ponto e sinal de menos
    s = re.sub(r'[^0-9.-]', '', s)

    try:
        return float(s)
    except ValueError:
        return 0.0

def parse_csv_file(filepath):
    filename = os.path.basename(filepath)
    strategy_name = os.path.splitext(filename)[0]
    
    encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252', 'utf-16']
    raw_text = None

    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                raw_text = f.read()
            if raw_text and len(raw_text.strip()) > 0:
                break
        except Exception:
            continue

    if not raw_text:
        return []

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines:
        return []

    # Detecta o delimitador correto
    sample = "\n".join(lines[:10])
    semis = sample.count(';')
    commas = sample.count(',')
    tabs = sample.count('\t')

    if semis >= commas and semis >= tabs:
        delimiter = ';'
    elif commas >= semis and commas >= tabs:
        delimiter = ','
    else:
        delimiter = '\t'

    # Usa leitor nativo de CSV para tratar aspas e caracteres especiais
    reader = list(csv.reader(io.StringIO("\n".join(lines)), delimiter=delimiter))
    if not reader:
        return []

    # Localiza o cabeçalho
    header_idx = -1
    header = []

    for idx, row in enumerate(reader[:15]):
        row_str = " ".join([c.lower().strip() for c in row])
        if any(k in row_str for k in ['resultado', 'lucro', 'pnl', 'ativo', 'tipo', 'lado', 'qtd', 'quantidade', 'operação', 'operacao', 'liquido', 'líquido']):
            header_idx = idx
            header = [c.lower().strip() for c in row]
            break

    if header_idx == -1:
        header_idx = 0
        header = [c.lower().strip() for c in reader[0]]

    # Mapeamento flexível das colunas básicas
    time_idx = next((i for i, c in enumerate(header) if any(k in c for k in ['horario', 'horário', 'data', 'time', 'fechamento', 'abertura', 'dt.'])), -1)
    asset_idx = next((i for i, c in enumerate(header) if any(k in c for k in ['ativo', 'instrumento', 'asset', 'papel', 'symbol'])), -1)
    type_idx = next((i for i, c in enumerate(header) if any(k in c for k in ['tipo', 'lado', 'operacao', 'operação', 'c/v'])), -1)
    qty_idx = next((i for i, c in enumerate(header) if any(k in c for k in ['qtd', 'quantidade', 'volume', 'contratos'])), -1)

    # Identificação da coluna de resultado financeiro (PnL)
    pnl_idx = -1
    for i, c in enumerate(header):
        if any(k in c for k in ['r$', 'líquido', 'liquido', 'financeiro', 'lucro (r$)']):
            if not any(skip in c for skip in ['pts', 'pontos', '%', 'qtd']):
                pnl_idx = i
                break

    if pnl_idx == -1:
        for i, c in enumerate(header):
            if any(k in c for k in ['resultado', 'pnl', 'lucro', 'retorno', 'total']):
                if not any(skip in c for skip in ['pts', 'pontos', '%', 'qtd', 'preço', 'preco']):
                    pnl_idx = i
                    break

    trades = []
    for row in reader[header_idx + 1:]:
        if len(row) < 2:
            continue

        try:
            time_val = row[time_idx].strip() if time_idx != -1 and time_idx < len(row) else ''
            
            if asset_idx != -1 and asset_idx < len(row) and row[asset_idx].strip():
                asset_val = row[asset_idx].strip()
            else:
                asset_val = 'WDO' if 'WDO' in strategy_name.upper() else 'WIN'

            type_raw = row[type_idx].upper().strip() if type_idx != -1 and type_idx < len(row) else 'COMPRA'
            qty_raw = row[qty_idx].strip() if qty_idx != -1 and qty_idx < len(row) else '1'
            
            pnl_val = 0.0
            if pnl_idx != -1 and pnl_idx < len(row):
                pnl_val = clean_float(row[pnl_idx])
            else:
                # Fallback: varre a linha procurando o primeiro valor numérico válido
                for cell in row:
                    val = clean_float(cell)
                    if val != 0.0:
                        pnl_val = val
                        break

            trade_type = "COMPRA" if any(w in type_raw for w in ["COMP", "BUY", "C"]) else "VENDA"
            qty_num = int(abs(clean_float(qty_raw))) if clean_float(qty_raw) != 0 else 1

            trades.append({
                "time": time_val,
                "strategy": strategy_name,
                "asset": asset_val,
                "type": trade_type,
                "qty": qty_num,
                "pnl": pnl_val
            })
        except Exception:
            continue

    return trades

def process_all_csvs():
    all_trades = []
    csv_files = [f for f in os.listdir('.') if f.lower().endswith('.csv')]
    
    print(f"📁 Lendo {len(csv_files)} arquivos CSV na pasta:")
    for f in csv_files:
        trades = parse_csv_file(f)
        sample_pnl = next((t['pnl'] for t in trades if t['pnl'] != 0.0), 0.0)
        print(f"  └─ {f}: {len(trades)} trades extraídos. (Exemplo de resultado capturado: R$ {sample_pnl:.2f})")
        all_trades.extend(trades)

    with open('trades_data.json', 'w', encoding='utf-8') as jf:
        json.dump(all_trades, jf, ensure_ascii=False, indent=2)

    print(f"✅ Total consolidado: {len(all_trades)} trades salvos em 'trades_data.json'!")

def push_to_git():
    try:
        status = subprocess.check_output(['git', 'status', '--porcelain']).decode('utf-8')
        if not status.strip():
            return
        subprocess.run(['git', 'add', '.'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Auto-update trades'], check=True)
        subprocess.run(['git', 'push', 'origin', 'main', '--force'], check=True)
        print("🌐 GitHub atualizado com sucesso!")
    except Exception as e:
        print(f"⚠️ Git: {e}")

if __name__ == "__main__":
    print("==================================================")
    print("🚀 MONITOR DE ESTRATÉGIAS ATIVADO E RODANDO!")
    print("👀 Aguardando alterações nos arquivos CSV da pasta...")
    print("==================================================\n")
    
    last_files_state = {}

    while True:
        try:
            current_files_state = {
                f: os.path.getmtime(f) for f in os.listdir('.') if f.lower().endswith('.csv')
            }

            if current_files_state != last_files_state:
                now = datetime.now().strftime("%H:%M:%S")
                print(f"[{now}] 🔔 Alteração detectada nos relatórios! Atualizando...")
                
                process_all_csvs()
                push_to_git()
                
                last_files_state = current_files_state
                print(f"[{now}] 🟢 Monitoramento ativo. Aguardando próximas mudanças...\n")

        except Exception as e:
            print(f"⚠️ Erro durante monitoramento: {e}")

        time.sleep(3)