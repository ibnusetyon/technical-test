import pandas as pd
import json

def load_data(file_path):
    print("Loading dataset...")
    data = []
    with open(file_path, 'r') as f:
        for line in f:
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    
    df = pd.DataFrame(data)
    
    time_col = None
    for col in ['timestamp', '@timestamp', 'time', 'ts', 'date', 'created_at']:
        if col in df.columns:
            time_col = col
            break
            
    if time_col:
        df['timestamp_parsed'] = pd.to_datetime(df[time_col], errors='coerce')
    else:
        df['timestamp_parsed'] = pd.NaT
        
    return df

def analyze_explore(df):
    print("\n--- 1. EXPLORE THE DATASET ---")
    if not df['timestamp_parsed'].isna().all():
        print(f"Time Range: {df['timestamp_parsed'].min()} to {df['timestamp_parsed'].max()}")
    else:
        print("Time Range: Unknown")
        
    if 'team' in df.columns:
        print(f"Teams: {df['team'].unique().tolist()}")
    if 'service' in df.columns:
        print(f"Services: {df['service'].unique().tolist()}")
        
    print(f"Total Requests (Traffic): {len(df)}")

def analyze_reliability(df):
    print("\n--- 2. RELIABILITY ANALYSIS ---")
    status_col = 'status_code' if 'status_code' in df.columns else 'status' if 'status' in df.columns else None
    
    if status_col:
        df[status_col] = pd.to_numeric(df[status_col], errors='coerce')
        error_df = df[df[status_col] >= 500]
        error_rate = (len(error_df) / len(df)) * 100
        print(f"Global 5xx Error Rate: {error_rate:.2f}%")
        
        if 'service' in df.columns and not error_df.empty:
            print("\nTop Failing Services (5xx counts):")
            print(error_df['service'].value_counts().head(5))

def analyze_performance(df):
    print("\n--- 3. PERFORMANCE ANALYSIS ---")
    # PERBAIKAN: Menambahkan 'latency_ms' agar bisa dideteksi
    lat_col = 'latency_ms' if 'latency_ms' in df.columns else 'latency' if 'latency' in df.columns else 'duration' if 'duration' in df.columns else None
    
    if lat_col and 'service' in df.columns:
        df[lat_col] = pd.to_numeric(df[lat_col], errors='coerce')
        perf_stats = df.groupby('service')[lat_col].quantile([0.5, 0.9, 0.99]).unstack()
        perf_stats.columns = ['p50 (ms)', 'p90 (ms)', 'p99 (ms)']
        print("\nLatency Percentiles per Service:")
        print(perf_stats.sort_values('p99 (ms)', ascending=False).round(2))
    else:
        print("Kolom latency atau service tidak ditemukan.")

def incident_investigation(df):
    print("\n--- 4. INCIDENT INVESTIGATION ---")
    status_col = 'status_code' if 'status_code' in df.columns else 'status' if 'status' in df.columns else None
    
    if status_col and not df['timestamp_parsed'].isna().all():
        df_temp = df.copy()
        df_temp.set_index('timestamp_parsed', inplace=True)
        df_temp[status_col] = pd.to_numeric(df_temp[status_col], errors='coerce')
        
        errors_per_min = df_temp[df_temp[status_col] >= 500].resample('1min').size()
        if not errors_per_min.empty and errors_per_min.max() > 0:
            peak_error_time = errors_per_min.idxmax()
            print(f"Insiden terdeteksi (lonjakan error): {peak_error_time} dengan {errors_per_min.max()} errors/menit.")
        else:
            print("Tidak ada insiden signifikan yang terdeteksi.")

def cost_analysis(df):
    print("\n--- 5. COST ANALYSIS ---")
    df['log_size_bytes'] = df.apply(lambda x: len(json.dumps(x.dropna().to_dict(), default=str)), axis=1)
    
    if 'team' in df.columns:
        print("\nTop Teams by Log Volume (Bytes):")
        print(df.groupby('team')['log_size_bytes'].sum().sort_values(ascending=False).head())

if __name__ == "__main__":
    file_path = "logs_10k.jsonl" 
    try:
        df = load_data(file_path)
        if not df.empty:
            analyze_explore(df)
            analyze_reliability(df)
            analyze_performance(df)
            incident_investigation(df)
            cost_analysis(df)
    except FileNotFoundError:
        print(f"Error: File '{file_path}' tidak ditemukan di lokasi script ini.")