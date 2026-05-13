import os
import uuid
from supabase import create_client, Client
from dotenv import load_dotenv

# Load .env file explicitly
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env")

supabase: Client = create_client(supabase_url, supabase_key)

products = []

def seed():
    print("Seeding products...")
    for p in products:
        try:
            # Check if product exists by SKU
            res = supabase.table('products').select('id').eq('sku', p['sku']).execute()
            if res.data:
                print(f"Updating {p['sku']}...")
                supabase.table('products').update(p).eq('sku', p['sku']).execute()
            else:
                print(f"Inserting {p['sku']}...")
                supabase.table('products').insert(p).execute()
        except Exception as e:
            print(f"Error seeding {p['sku']}: {e}")
    print("Done!")

if __name__ == "__main__":
    seed()
