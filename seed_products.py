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
        "name": "Glass Skin Elixir",
        "description": "Functional radiance in a bottle. A targeted blend of Aloe Vera, Amla, and Coconut Water designed to stimulate collagen and deliver a luminous, 'glass skin' finish.",
        "image_url": "https://images.unsplash.com/photo-1610970881699-44a5587cabec?auto=format&fit=crop&w=600&q=80",
        "sku": "JCU_SHOT_GS",
        "sizes": [{"size": "60ml Shot", "price": 49}],
        "is_active": True
    },
    {
        "name": "Gut Vitality Shot",
        "description": "Functional digestive support. Cold-pressed Celery, Green Apple, and Ginger formulated to soothe the gut lining and optimize nutrient absorption.",
        "image_url": "https://images.unsplash.com/photo-1622597467836-f38240662c8b?auto=format&fit=crop&w=600&q=80",
        "sku": "JCU_SHOT_GH",
        "sizes": [{"size": "60ml Shot", "price": 49}],
        "is_active": True
    },
    {
        "name": "Retinol Renewal Shot",
        "description": "Targeted anti-aging nutrition. High-bioavailable Vitamin A from Carrots and Ginger to support cellular turnover and youthful skin elasticity.",
        "image_url": "https://images.unsplash.com/photo-1590779033100-9f60705a2f3b?auto=format&fit=crop&w=600&q=80",
        "sku": "JCU_SHOT_RT",
        "sizes": [{"size": "60ml Shot", "price": 49}],
        "is_active": True
    },
    {
        "name": "Lumina Glow Shot",
        "description": "Functional beauty boost. A vibrant synergy of Beetroot and Citrus to detoxify the bloodstream and enhance natural skin luminosity.",
        "image_url": "https://images.unsplash.com/photo-1547514701-42782101795e?auto=format&fit=crop&w=600&q=80",
        "sku": "JCU_SHOT_GLOW",
        "sizes": [{"size": "60ml Shot", "price": 49}],
        "is_active": True
    },
    {
        "name": "Peak Energy Elixir",
        "description": "Functional endurance fuel. Watermelon and Beetroot nitric oxide boosters to enhance circulation and provide sustained natural energy.",
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
