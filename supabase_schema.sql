-- Execute this script in your Supabase SQL Editor

-- 1. Create profiles table
CREATE TABLE public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT,
    email TEXT,
    phone TEXT,
    address TEXT,
    location TEXT,
    role TEXT DEFAULT 'user',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Secure profiles table
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public profiles are viewable by everyone."
    ON public.profiles FOR SELECT
    USING ( true );

CREATE POLICY "Users can insert their own profile."
    ON public.profiles FOR INSERT
    WITH CHECK ( auth.uid() = id );

CREATE POLICY "Users can update own profile."
    ON public.profiles FOR UPDATE
    USING ( auth.uid() = id );

-- 2. Create orders table
CREATE TABLE public.orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    order_number TEXT UNIQUE NOT NULL,
    razorpay_order_id TEXT,
    total_amount NUMERIC(10, 2) NOT NULL,
    status TEXT DEFAULT 'created',
    items JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Secure orders table
ALTER TABLE public.orders ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own orders."
    ON public.orders FOR SELECT
    USING ( auth.uid() = user_id OR (SELECT role FROM public.profiles WHERE id = auth.uid()) = 'admin' );

CREATE POLICY "Users can insert their own orders."
    ON public.orders FOR INSERT
    WITH CHECK ( auth.uid() = user_id );

CREATE POLICY "Users can update their own orders."
    ON public.orders FOR UPDATE
    USING ( auth.uid() = user_id );

-- Optional: Create an admin user automatically (run this AFTER signing up via the app)
-- UPDATE public.profiles SET role = 'admin' WHERE email = 'your_admin_email@example.com';

-- 3. Create cart_items table (persistent DB cart)
CREATE TABLE IF NOT EXISTS public.cart_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    product_id TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE(user_id, product_id)
);

ALTER TABLE public.cart_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users manage their own cart."
    ON public.cart_items FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- 4. Create remember_tokens table (cookie-based "Remember Me")
CREATE TABLE IF NOT EXISTS public.remember_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    token TEXT UNIQUE NOT NULL,
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- remember_tokens is server-side only; disable RLS to allow backend inserts
ALTER TABLE public.remember_tokens DISABLE ROW LEVEL SECURITY;

-- Optional: Add payment_id and tax columns to orders (run if orders table already exists)
ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS payment_id TEXT;
ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS subtotal NUMERIC(10,2);
ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS tax NUMERIC(10,2);

-- 5. Create products table
CREATE TABLE IF NOT EXISTS public.products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    description TEXT,
    image_url TEXT,
    sku TEXT UNIQUE,
    sizes JSONB NOT NULL DEFAULT '[{"size": "Standard", "price": 100}]'::jsonb,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

ALTER TABLE public.products ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Products are viewable by everyone."
    ON public.products FOR SELECT
    USING ( true );

CREATE POLICY "Only admins can modify products"
    ON public.products FOR ALL
    USING ( (SELECT role FROM public.profiles WHERE id = auth.uid()) = 'admin' );

-- Update cart_items table to include size
ALTER TABLE public.cart_items ADD COLUMN IF NOT EXISTS size TEXT;
ALTER TABLE public.cart_items DROP CONSTRAINT IF EXISTS cart_items_user_id_product_id_key;
ALTER TABLE public.cart_items ADD CONSTRAINT cart_items_user_id_product_id_size_key UNIQUE(user_id, product_id, size);

-- 6. Create reviews table
CREATE TABLE IF NOT EXISTS public.reviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    comment TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE(user_id, product_id)
);

ALTER TABLE public.reviews DISABLE ROW LEVEL SECURITY;

-- =====================================================================
-- ⚠️  IMPORTANT — DISABLE ROW LEVEL SECURITY ON ALL TABLES
-- =====================================================================
-- Flask uses the Supabase anon key on the SERVER side.
-- On the server, auth.uid() is always NULL (no user JWT).
-- ALL RLS policies like "auth.uid() = user_id" will block inserts/updates.
-- Flask already enforces authentication via sessions — disabling RLS is safe.
-- =====================================================================
ALTER TABLE public.profiles   DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.orders     DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.cart_items DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.products   DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.reviews    DISABLE ROW LEVEL SECURITY;
-- remember_tokens already has RLS disabled (see above)

-- =====================================================================
-- CLEANUP — Remove stale cart rows with old hardcoded product IDs
-- (leftover from when products were "1", "2", "3" in memory)
-- =====================================================================
DELETE FROM public.cart_items
WHERE product_id NOT IN (SELECT id::text FROM public.products);

-- =====================================================================
-- ADMIN — Promote a user to admin after they sign up via the app
-- =====================================================================
-- UPDATE public.profiles SET role = 'admin' WHERE email = 'your_email@example.com';

