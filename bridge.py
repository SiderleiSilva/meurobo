import os
import json
import csv
import subprocess
import time
from datetime import datetime

def clean_float(val_str):
    if not val_str:
        return 0.0
    s = str(val_str).replace('R$', '').replace(' ', '').replace('+', '').strip()
    if not s:
        return 0.0
    if '.' in s and ',' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return 0.0

def parse_csv_file(filepath):
    filename = os.path.basename(filepath)
    strategy_name = os.path.splitext(filename)[0]
    
    encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252', 'utf-16']
    content = None

    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                content = f.readlines()
            if content and len(content) > 0:
                break
        except Exception:
            continue

    if not content:
        return []

    lines = [line.strip() for line in content if line.strip()]
    if not lines:
        return []

    sample = "".join(lines[:20])
    semis = sample.count(';')
    commas = sample.count(',')
    tabs = sample.count('\t')

    if semis >= commas and semis >= tabs:
        delimiter = ';'
    elif commas >= semis and commas >= tabs:
        delimiter = ','
    else:
        delimiter = '\t'

    header_idx = -1
    header = []

    for idx, line in enumerate(lines[:15]):
        cols = [c.strip().lower() for c in line.split(delimiter)]
        line_str = " ".join(cols)
        if any(k in line_str for k in ['resultado', 'lucro', 'pnl', 'ativo', 'tipo', 'lado', 'qtd', 'quantidade', 'operação', 'operacao', 'liquido', 'líquido']):
            header_idx = idx
            header = cols
            break

    if header_idx == -1:
        header_idx = 0
        header = [c.strip().lower() for c in lines[0].split(delimiter)]

    time_idx = next((i for i, c in enumerate(header) if any(k in c for k in ['horario', 'horário', 'data', 'time', 'fechamento', 'abertura', 'dt.'])), -1)
    asset_idx = next((i for i, c in enumerate(header) if any(k in c for k in ['ativo', 'instrumento', 'asset', 'papel', 'symbol'])), -1)
    type_idx = next((i for i, c in enumerate(header) if any(k in c for k in ['tipo', 'lado', 'operacao', 'operação', 'c/v'])), -1)
    qty_idx = next((i for i, c in enumerate(header) if any(k in c for k in ['qtd', 'quantidade', 'volume', 'contratos'])), -1)
    pnl_idx = next((i for i, c in enumerate(header) if any(k in c for k in ['resultado', 'lucro', 'pnl', 'liquido', 'líquido', 'retorno'])), -1)

    trades = []
    for line in lines[header_idx + 1:]:
        row = [c.strip() for c in line.split(delimiter)]
        if len(row) < 2:
            continue

        try:
            time_val = row[time_idx] if time_idx != -1 and time_idx < len(row) else ''
            
            if asset_idx != -1 and asset_idx < len(row) and row[asset_idx]:
                asset_val = row[asset_idx]
            else:
                asset_val = 'WDO' if 'WDO' in strategy_name.upper() else 'WIN'

            type_raw = row[type_idx].upper() if type_idx != -1 and type_idx < len(row) else 'COMPRA'
            qty_raw = row[qty_idx] if qty_idx != -1 and qty_idx < len(row) else '1'
            pnl_raw = row[pnl_idx] if pnl_idx != -1 and pnl_idx < len(row) else '0'

            trade_type = "COMPRA" if any(w in type_raw for w in ["COMP", "BUY", "C"]) else "VENDA"
            qty_num = int(abs(clean_float(qty_raw))) if clean_float(qty_raw) != 0 else 1
            pnl_val = clean_float(pnl_raw)

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
    
    print(f"📁 Lendo {len(csv_files)} arquivos CSV na pasta...")
    for f in csv_files:
        trades = parse_csv_file(f)
        print(f"  └─ {f}: {len(trades)} trades extraídos.")
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
            # Mapeia os arquivos CSV e suas datas de modificação
            current_files_state = {
                f: os.path.getmtime(f) for f in os.listdir('.') if f.lower().endswith('.csv')
            }

            # Se houver qualquer modificação, adição ou remoção de CSV
            if current_files_state != last_files_state:
                now = datetime.now().strftime("%H:%M:%S")
                print(f"[{now}] 🔔 Alteração detectada nos relatórios! Atualizando...")
                
                process_all_csvs()
                push_to_git()
                
                last_files_state = current_files_state
                print(f"[{now}] 🟢 Monitoramento ativo. Aguardando próximas mudanças...\n")

        except Exception as e:
            print(f"⚠️ Erro durante monitoramento: {e}")

        time.sleep(3)  # Checa a pasta a cada 3 segundos