import os
import sys
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    print("Error: SUPABASE_URL and SUPABASE_KEY must be set.")
    exit(1)

supabase: Client = create_client(supabase_url, supabase_key)

def make_admin(email):
    print(f"Attempting to make {email} an admin...")
    try:
        # First find the user ID from the profiles table
        res = supabase.table('profiles').select('id').eq('email', email).execute()
        if not res.data:
            print(f"Error: No user found with email {email}")
            return

        user_id = res.data[0]['id']
        
        # Update their role to 'admin'
        update_res = supabase.table('profiles').update({'role': 'admin'}).eq('id', user_id).execute()
        
        if update_res.data:
            print(f"Success! {email} is now an ADMIN.")
        else:
            print("Update failed. Please check your permissions.")

    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python make_admin.py user@example.com")
    else:
        make_admin(sys.argv[1])
