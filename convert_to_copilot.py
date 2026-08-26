import json
import csv
import os

def convert_json_to_csv(json_path, output_dir):
    """Convert portfolio JSON to Copilot-friendly CSV files"""
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Overall data
    overall_fields = ['date', 'eval', 'invested', 'pct', 'pnl', 'trueEval', 'trueInvested', 'truePnl', 'truePct']
    with open(os.path.join(output_dir, 'overall.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(overall_fields)
        for row in data['overall']:
            writer.writerow([row.get(field, '') for field in overall_fields])
    
    # 2. Per-stock data
    for stock_name, stock_data in data['stocks'].items():
        safe_name = stock_name.replace('/', '_').replace('\\', '_').replace(' ', '_')
        with open(os.path.join(output_dir, f'stock_{safe_name}.csv'), 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['date', 'pct', 'invested', 'pnl'])
            for row in stock_data:
                writer.writerow([row.get('date', ''), row.get('pct', ''), row.get('invested', ''), row.get('pnl', '')])
    
    # 3. Realized stocks data
    with open(os.path.join(output_dir, 'realized_stocks.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['stock', 'pnl', 'principal', 'held', 'pct'])
        for stock_name, stock_info in data['realizedStocks'].items():
            writer.writerow([stock_name, stock_info.get('pnl', ''), stock_info.get('principal', ''), stock_info.get('held', ''), stock_info.get('pct', '')])
    
    # 4. Metadata
    with open(os.path.join(output_dir, 'metadata.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['key', 'value'])
        writer.writerow(['lastUpdated', data.get('lastUpdated', '')])
        writer.writerow(['realizedFrom', data.get('realizedFrom', '')])
        writer.writerow(['realizedSchemaVersion', data.get('realizedSchemaVersion', '')])
        writer.writerow(['realizedAsOf', data.get('realizedAsOf', '')])
    
    print(f"Conversion complete! Files saved to: {output_dir}")
    print(f"  - overall.csv")
    print(f"  - stock_*.csv ({len(data['stocks'])} stock files)")
    print(f"  - realized_stocks.csv")
    print(f"  - metadata.csv")

if __name__ == '__main__':
    json_path = r'../../../Downloads/portfolio_data (1).json'
    output_dir = r'../../../Downloads/portfolio_copilot'
    convert_json_to_csv(json_path, output_dir)