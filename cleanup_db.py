# import os
# from supabase import create_client, Client
# from dotenv import load_dotenv

# load_dotenv()

# supabase_url = os.environ.get("SUPABASE_URL")
# supabase_key = os.environ.get("SUPABASE_KEY")

# if not supabase_url or not supabase_key:
#     print("Error: SUPABASE_URL and SUPABASE_KEY must be set.")
#     exit(1)

# supabase: Client = create_client(supabase_url, supabase_key)

# def cleanup():
#     print("Deleting all products from database...")
#     try:
#         # Delete all rows from products table
#         # We use a filter that matches all (e.g., id is not null)
#         res = supabase.table('products').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
#         print(f"Cleanup complete. Deleted {len(res.data)} products.")
#     except Exception as e:
#         print(f"Error during cleanup: {str(e)}")

# if __name__ == "__main__":
#     cleanup()
