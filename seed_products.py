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

products = [
    {
        "name": "Glass Skin Shot ✨",
        "description": "Unlock your natural radiance. A potent blend of Aloe Vera, Lemon, Coconut Water, and Amla designed to hydrate and brighten your skin from within. Perfect for that 'glass skin' glow.",
        "image_url": "https://images.unsplash.com/photo-1610970881699-44a5587cabec?auto=format&fit=crop&w=600&q=80",
        "sku": "JCU_SHOT_GS",
        "sizes": [{"size": "60ml Shot", "price": 49}],
        "is_active": True
    },
    {
        "name": "Gut Health Shot 🌿",
        "description": "Your daily digestive companion. Cold-pressed Cucumber, Celery, Green Apple, Spinach, Lemon, and Pineapple to soothe your gut and boost immunity.",
        "image_url": "https://images.unsplash.com/photo-1622597467836-f38240662c8b?auto=format&fit=crop&w=600&q=80",
        "sku": "JCU_SHOT_GH",
        "sizes": [{"size": "60ml Shot", "price": 49}],
        "is_active": True
    },
    {
        "name": "Retinol Shot 🥕",
        "description": "The ultimate anti-aging elixir. Packed with natural Vitamin A from Carrots, Ginger, Orange, and Lemon to support skin renewal and youthful vitality.",
        "image_url": "https://images.unsplash.com/photo-1590779033100-9f60705a2f3b?auto=format&fit=crop&w=600&q=80",
        "sku": "JCU_SHOT_RT",
        "sizes": [{"size": "60ml Shot", "price": 49}],
        "is_active": True
    },
    {
        "name": "Glow Shot 💖",
        "description": "Beauty in a bottle. A vibrant mix of Orange, Beetroot, Strawberries, Lemon, and Apple to detoxify your system and bring out your natural blush.",
        "image_url": "https://images.unsplash.com/photo-1547514701-42782101795e?auto=format&fit=crop&w=600&q=80",
        "sku": "JCU_SHOT_GLOW",
        "sizes": [{"size": "60ml Shot", "price": 49}],
        "is_active": True
    },
    {
        "name": "Energy Booster Juice ⚡",
        "description": "Pre-workout oxygen in a bottle. Watermelon, Beetroot, Fresh Mint, and Lime to boost blood flow and keep you energized all day long.",
        "image_url": "https://images.unsplash.com/photo-1567375639073-956622ec96b4?auto=format&fit=crop&w=600&q=80",
        "sku": "JCU_JUICE_EB",
        "sizes": [
            {"size": "250ml Bottle", "price": 99},
            {"size": "500ml Bottle", "price": 179}
        ],
        "is_active": True
    }
]

def seed():
    print("Seeding products...")
    for p in products:
        try:
            # Check if product exists by SKU
            res = supabase.table('products').select('id').eq('sku', p['sku']).execute()
            if res.data:
                print(f"Updating {p['name']}...")
                supabase.table('products').update(p).eq('sku', p['sku']).execute()
            else:
                print(f"Inserting {p['name']}...")
                supabase.table('products').insert(p).execute()
        except Exception as e:
            print(f"Error seeding {p['name']}: {e}")
    print("Done!")

if __name__ == "__main__":
    seed()
