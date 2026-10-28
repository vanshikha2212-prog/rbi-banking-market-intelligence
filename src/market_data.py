banks = {"HDFCBANK":"HDFC Bank","ICICIBANK":"ICICI Bank","AXISBANK":"Axis Bank","SBIN":"State Bank of India","BANKBARODA":"Bank of Baroda","CANBK":"Canara Bank"}
benchmarks = ["NIFTY 50", "NIFTY BANK"]
print("--- BANKS ---")
for symbol, name in banks.items(): print(symbol, "→", name)
print("\n--- BENCHMARKS ---")
for benchmark in benchmarks: print(benchmark)
