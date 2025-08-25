import os
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

loan_id = "LN0011"  # Change as needed

resp = supabase.table("loans").select("*").eq("loan_id", loan_id).execute()
if resp.data:
    print(f"Loan found: {resp.data[0]}")
else:
    print(f"No loan found with loan_id={loan_id}")
