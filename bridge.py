import os
import json
import csv
import subprocess

def parse_csv_file(filepath):
    filename = os.path.basename(filepath)
    # Define o nome da estratégia com base no nome do arquivo (sem extensão)
    strategy_name = os.path.splitext(filename)[0]
    
    trades = []
    encodings = ['utf-8', 'latin-1', 'utf-16', 'cp1252']
    content = None

    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                content = f.readlines()
            break
        except UnicodeDecodeError:
            continue

    if not content:
        return []

    # Identifica o separador (; ou ,)
    delimiter = ';' if ';' in content[0] else ','
    reader = csv.reader(content, delimiter=delimiter)
    rows = [r for r in reader if r]

    if not rows:
        return []

    header = [c.strip().lower() for c in rows[0]]

    # Localização das colunas
    time_idx = next((i for i, c in enumerate(header) if any(k in c for k in ['horario', 'horário', 'data', 'time'])), -1)
    asset_idx = next((i for i, c in enumerate(header) if any(k in c for k in ['ativo', 'instrumento', 'asset'])), -1)
    type_idx = next((i for i, c in enumerate(header) if any(k in c for k in ['tipo', 'lado', 'operacao', 'operação'])), -1)
    qty_idx = next((i for i, c in enumerate(header) if any(k in c for k in ['qtd', 'quantidade', 'volume'])), -1)
    pnl_idx = next((i for i, c in enumerate(header) if any(k in c for k in ['resultado', 'lucro', 'pnl', 'liquido', 'líquido'])), -1)

    for row in rows[1:]:
        try:
            time_val = row[time_idx].strip() if time_idx != -1 and time_idx < len(row) else ''
            asset_val = row[asset_idx].strip() if asset_idx != -1 and asset_idx < len(row) else ('WDO' if 'WDO' in strategy_name else 'WIN')
            type_val = row[type_idx].strip().upper() if type_idx != -1 and type_idx < len(row) else 'COMPRA'
            qty_val = row[qty_idx].strip() if qty_idx != -1 and qty_idx < len(row) else '1'
            pnl_str = row[pnl_idx].strip() if pnl_idx != -1 and pnl_idx < len(row) else '0'

            # Formatação do PnL para número
            pnl_clean = pnl_str.replace('R$', '').replace('.', '').replace(',', '.').strip()
            pnl_val = float(pnl_clean) if pnl_clean else 0.0

            qty_num = int(qty_val) if qty_val.isdigit() else 1
            trade_type = "COMPRA" if any(w in type_val for w in ["COMP", "BUY", "C"]) else "VENDA"

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
    
    print(f"📁 Encontrados {len(csv_files)} arquivos CSV na pasta:")
    for f in csv_files:
        trades = parse_csv_file(f)
        print(f"  └─ {f}: {len(trades)} operações carregadas.")
        all_trades.extend(trades)

    with open('trades_data.json', 'w', encoding='utf-8') as jf:
        json.dump(all_trades, jf, ensure_ascii=False, indent=2)

    print(f"\n✅ 'trades_data.json' ATUALIZADO com {len(all_trades)} trades no total!")

def push_to_git():
    try:
        status = subprocess.check_output(['git', 'status', '--porcelain']).decode('utf-8')
        if not status.strip():
            return
        subprocess.run(['git', 'add', '.'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Auto-update trades'], check=True)
        subprocess.run(['git', 'push', 'origin', 'main', '--force'], check=True)
        print("🌐 GitHub sincronizado com sucesso!")
    except Exception as e:
        print(f"⚠️ Git: {e}")

if __name__ == "__main__":
    print("🚀 Iniciando leitura da pasta...")
    process_all_csvs()
    push_to_git()
    print("\n⌛ Processo concluído com sucesso!")