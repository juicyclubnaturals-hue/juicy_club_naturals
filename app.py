import os
import uuid
import hashlib
import requests
import re
import random
import string
import razorpay
from datetime import timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, make_response
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "fallback_secret_key")
app.permanent_session_lifetime = timedelta(days=30)  # Max session duration

# Initialize Supabase
supabase_url = os.environ.get("SUPABASE_URL", "")
supabase_key = os.environ.get("SUPABASE_KEY", "")
supabase: Client = None
if supabase_url and supabase_key:
    try:
        supabase = create_client(supabase_url, supabase_key)
    except Exception as e:
        print(f"Failed to initialize Supabase client: {e}")
        supabase = None

# Initialize Razorpay
razorpay_key_id = os.environ.get("RAZORPAY_KEY_ID", "")
razorpay_key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
razorpay_client = None
if razorpay_key_id and razorpay_key_secret:
    razorpay_client = razorpay.Client(auth=(razorpay_key_id, razorpay_key_secret))

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def get_product(product_id):
    """Fetch product from DB."""
    if not supabase: return None
    try:
        resp = supabase.table('products').select('*').eq('id', product_id).execute()
        return resp.data[0] if resp.data else None
    except Exception as e:
        print(f"Fetch product error: {e}")
        return None

def is_password_strong(password):
    """Validate password complexity."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one number."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character."
    return True, ""

def is_password_leaked(password):
    """Check HIBP API for compromised password."""
    sha1_password = hashlib.sha1(password.encode('utf-8')).hexdigest().upper()
    prefix, suffix = sha1_password[:5], sha1_password[5:]
    try:
        response = requests.get(f"https://api.pwnedpasswords.com/range/{prefix}", timeout=3)
        if response.status_code == 200:
            for h, count in (line.split(':') for line in response.text.splitlines()):
                if h == suffix:
                    return True
    except Exception as e:
        print(f"HIBP check error: {e}")
    return False

def load_user_from_cookie():
    """Auto-login user if a valid remember_me cookie exists."""
    if 'user' in session:
        return  # Already logged in
    remember_token = request.cookies.get('remember_me')
    if remember_token and supabase:
        try:
            result = supabase.table('remember_tokens').select('user_id, email, is_admin').eq('token', remember_token).execute()
            if result.data:
                row = result.data[0]
                session.permanent = True
                session['user'] = row['user_id']
                session['email'] = row['email']
                if row.get('is_admin'):
                    session['is_admin'] = True
        except Exception as e:
            print(f"Cookie restore error: {e}")

def get_db_cart(user_id):
    """Fetch the user's cart from Supabase (single batch query)."""
    try:
        result = supabase.table('cart_items').select('*').eq('user_id', user_id).execute()
        if not result.data:
            return {}

        # Collect unique product IDs and fetch them all at once
        product_ids = list({str(row['product_id']) for row in result.data})
        prod_resp   = supabase.table('products').select('*').in_('id', product_ids).execute()
        prod_map    = {str(p['id']): p for p in (prod_resp.data or [])}

        cart = {}
        for row in result.data:
            pid  = str(row['product_id'])
            size = row.get('size') or 'Standard'
            prod = prod_map.get(pid)
            if not prod:
                continue  # Product deleted from DB — skip it

            # Determine price for the matching size
            sizes = prod.get('sizes') or []
            price = 0.0
            for s in sizes:
                if s.get('size') == size:
                    price = float(s.get('price', 0))
                    break
            else:
                if sizes:
                    price = float(sizes[0].get('price', 0))

            cart_key = f"{pid}_{size}"
            cart[cart_key] = {
                "product_id":  pid,
                "name":        prod['name'],
                "sku":         prod.get('sku', ''),
                "size":        size,
                "price":       price,
                "image":       prod.get('image_url') or '',
                "quantity":    row['quantity'],
                "cart_row_id": row['id'],
            }
        return cart
    except Exception as e:
        print(f"DB cart fetch error: {e}")
        return {}

def upsert_db_cart(user_id, product_id, size, quantity):
    """Insert or update a cart item in Supabase."""
    try:
        existing = supabase.table('cart_items').select('id, quantity').eq('user_id', user_id).eq('product_id', product_id).eq('size', size).execute()
        if existing.data:
            new_qty = existing.data[0]['quantity'] + quantity
            res = supabase.table('cart_items').update({'quantity': new_qty}).eq('id', existing.data[0]['id']).execute()
            print(f"[CART] Updated qty={new_qty} for product={product_id} size={size} user={user_id}")
        else:
            res = supabase.table('cart_items').insert({'user_id': user_id, 'product_id': product_id, 'size': size, 'quantity': quantity}).execute()
            print(f"[CART] Inserted product={product_id} size={size} user={user_id} result={res.data}")
    except Exception as e:
        print(f"[CART ERROR] upsert_db_cart failed: {e}")
        raise  # re-raise so caller can flash an error

def clear_db_cart(user_id):
    """Remove all cart items for a user from Supabase."""
    try:
        supabase.table('cart_items').delete().eq('user_id', user_id).execute()
    except Exception as e:
        print(f"DB cart clear error: {e}")

def calc_totals(cart):
    """Calculate subtotal, 12% GST, and total."""
    subtotal = sum(item['price'] * item['quantity'] for item in cart.values())
    tax = round(subtotal * 0.12, 2)
    total = round(subtotal + tax, 2)
    return round(subtotal, 2), tax, total

# ─── ROUTES ──────────────────────────────────────────────────────────────────

@app.before_request
def auto_login():
    """Try cookie-based restore on every request."""
    load_user_from_cookie()

@app.route('/manifest.json')
def manifest():
    return app.send_static_file('manifest.json')

@app.route('/sw.js')
def service_worker():
    return app.send_static_file('sw.js')

@app.route('/sitemap.xml')
def sitemap():
    return app.send_static_file('sitemap.xml')

@app.route('/robots.txt')
def robots():
    return app.send_static_file('robots.txt')

def generate_sku():
    """Generates a unique SKU with JCU_ prefix and 6 random digits."""
    return f"JCU_{''.join(random.choices(string.digits, k=6))}"

@app.route('/')
def home():
    purchased_product_ids = []
    cart_count = 0
    if 'user' in session:
        cart_items = get_db_cart(session['user'])
        cart_count = sum(item['quantity'] for item in cart_items.values())
        
        # Fetch purchased product IDs for review validation
        try:
            orders_resp = supabase.table('orders').select('items').eq('user_id', session['user']).eq('status', 'paid').execute()
            p_ids = set()
            for o in (orders_resp.data or []):
                items = o.get('items', {})
                for k, itm in items.items():
                    if itm.get('product_id'):
                        p_ids.add(str(itm['product_id']))
            purchased_product_ids = list(p_ids)
        except: pass
    
    # Fetch active products
    products = []
    if supabase:
        try:
            resp = supabase.table('products').select('*').eq('is_active', True).execute()
            products = resp.data or []
            
            # Step 1: Initialize defaults for all products (Prevents Jinja2 UndefinedError)
            for p in products:
                p['avg_rating'] = 0
                p['review_count'] = 0
                p['can_review'] = str(p['id']) in purchased_product_ids
                if not p.get('sku'): p['sku'] = ''

            # Step 2: Fetch and map review data
            try:
                reviews_resp = supabase.table('reviews').select('product_id, rating').execute()
                reviews_data = reviews_resp.data or []
                
                rating_map = {}
                for r in reviews_data:
                    pid = str(r['product_id'])
                    if pid not in rating_map:
                        rating_map[pid] = []
                    rating_map[pid].append(r['rating'])
                
                for p in products:
                    pid = str(p['id'])
                    # Auto-generate SKU if missing (migration)
                    if not p.get('sku'):
                        new_sku = generate_sku()
                        try:
                            supabase.table('products').update({'sku': new_sku}).eq('id', pid).execute()
                            p['sku'] = new_sku
                        except: pass

                    ratings = rating_map.get(pid, [])
                    if ratings:
                        p['avg_rating'] = round(sum(ratings) / len(ratings), 1)
                        p['review_count'] = len(ratings)
            except Exception as re:
                print(f"Error calculating ratings: {re}")
                    
        except Exception as e:
            print("Error fetching products:", e)

    return render_template('index.html', products=products, cart_count=cart_count)

@app.route('/submit_review/<product_id>', methods=['POST'])
def submit_review(product_id):
    if 'user' not in session:
        flash('Please login to submit a review', 'error')
        return redirect(url_for('login'))
    
    rating = request.form.get('rating', type=int)
    comment = request.form.get('comment', '').strip()
    
    if not rating or not (1 <= rating <= 5):
        flash('Please provide a valid rating (1-5 stars)', 'error')
        return redirect(url_for('home'))
        
    # Enforce purchase requirement
    try:
        orders_resp = supabase.table('orders').select('items').eq('user_id', session['user']).eq('status', 'paid').execute()
        has_purchased = False
        for o in (orders_resp.data or []):
            items = o.get('items', {})
            for k, itm in items.items():
                if str(itm.get('product_id')) == str(product_id):
                    has_purchased = True
                    break
            if has_purchased: break
        
        if not has_purchased:
            flash('You can only review products you have purchased.', 'error')
            return redirect(url_for('home'))
    except Exception as ve:
        flash(f'Error verifying purchase: {str(ve)}', 'error')
        return redirect(url_for('home'))

    try:
        supabase.table('reviews').upsert({
            'user_id': session['user'],
            'product_id': product_id,
            'rating': rating,
            'comment': comment
        }).execute()
        flash('Thank you! Your review has been submitted.', 'success')
    except Exception as e:
        flash(f'Error submitting review: {str(e)}', 'error')
        
    return redirect(url_for('home'))

# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name     = request.form.get('name')
        email    = request.form.get('email')
        password = request.form.get('password')
        phone    = request.form.get('phone')
        address  = request.form.get('address')
        location = request.form.get('location')

        is_strong, msg = is_password_strong(password)
        if not is_strong:
            flash(msg, 'error')
            return render_template('signup.html')

        if is_password_leaked(password):
            flash('This password appeared in a data breach. Please choose a unique password.', 'error')
            return render_template('signup.html')

        try:
            auth_response = supabase.auth.sign_up({"email": email, "password": password})
            user_id = auth_response.user.id

            # RLS workaround: sign in to get a valid session token
            supabase.auth.sign_in_with_password({"email": email, "password": password})

            supabase.table('profiles').insert({
                "id": user_id, "name": name, "email": email,
                "phone": phone, "address": address, "location": location, "role": "user"
            }).execute()

            flash('Signup successful! Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Signup failed: {str(e)}', 'error')

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email       = request.form.get('email')
        password    = request.form.get('password')
        remember_me = request.form.get('remember_me')  # checkbox value

        try:
            response = supabase.auth.sign_in_with_password({"email": email, "password": password})
            user_id  = response.user.id

            # Set session as permanent if remember_me checked
            session.permanent = bool(remember_me)
            session['user']   = user_id
            session['email']  = email

            profile = supabase.table('profiles').select('role').eq('id', user_id).single().execute()
            is_admin = profile.data and profile.data.get('role') == 'admin'
            if is_admin:
                session['is_admin'] = True

            resp = make_response(redirect(url_for('home')))

            if remember_me:
                token = uuid.uuid4().hex
                # Store token in DB
                supabase.table('remember_tokens').insert({
                    'token': token, 'user_id': user_id,
                    'email': email, 'is_admin': is_admin or False
                }).execute()
                # Set cookie for 30 days
                resp.set_cookie('remember_me', token, max_age=30*24*3600, httponly=True, samesite='Lax')

            flash('Logged in successfully!', 'success')
            return resp
        except Exception as e:
            flash(f'Login failed: {str(e)}', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    # Remove remember_me token from DB if cookie exists
    token = request.cookies.get('remember_me')
    if token and supabase:
        try:
            supabase.table('remember_tokens').delete().eq('token', token).execute()
        except Exception:
            pass

    session.clear()
    resp = make_response(redirect(url_for('home')))
    resp.delete_cookie('remember_me')
    flash('Logged out successfully.', 'info')
    return resp

# ── Cart ──────────────────────────────────────────────────────────────────────

@app.route('/cart')
def cart():
    if 'user' not in session:
        flash('Please login to view your cart.', 'error')
        return redirect(url_for('login'))

    cart_items = get_db_cart(session['user'])
    subtotal, tax, total = calc_totals(cart_items)
    return render_template('cart.html', cart=cart_items, subtotal=subtotal, tax=tax, total=total)

@app.route('/add_to_cart/<product_id>', methods=['POST'])
def add_to_cart(product_id):
    if 'user' not in session:
        flash('Please login first to add items to your cart.', 'error')
        return redirect(url_for('login'))

    size = request.form.get('size', 'Standard')
    print(f"[ADD TO CART] product_id={product_id} size={size} user={session.get('user')}")

    product = get_product(product_id)
    if not product:
        print(f"[ADD TO CART] Product not found in DB: {product_id}")
        flash(f'Product not found (ID: {product_id}). Please refresh the menu.', 'error')
        return redirect(url_for('home'))

    try:
        upsert_db_cart(session['user'], product_id, size, 1)
        msg = f"{product['name']} ({size}) added to cart!"
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Calculate new cart count
            cart_items = get_db_cart(session['user'])
            cart_count = sum(item['quantity'] for item in cart_items.values())
            return jsonify({'success': True, 'message': msg, 'cart_count': cart_count})
        flash(msg, 'success')
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': str(e)}), 400
        flash(f'Could not add to cart: {str(e)}', 'error')

    return redirect(url_for('home') + "#menu")

@app.route('/remove_from_cart/<product_id>/<size>', methods=['POST'])
def remove_from_cart(product_id, size):
    if 'user' not in session:
        return redirect(url_for('login'))
    try:
        supabase.table('cart_items').delete().eq('user_id', session['user']).eq('product_id', product_id).eq('size', size).execute()
        flash('Item removed from cart.', 'info')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('cart'))

@app.route('/api/cart/update', methods=['POST'])
def api_update_cart():
    """AJAX endpoint: increment or decrement cart item quantity."""
    if 'user' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    data       = request.get_json()
    product_id = str(data.get('product_id'))
    size       = data.get('size')
    action     = data.get('action')  # 'increment' | 'decrement' | 'remove'

    product = get_product(product_id)
    if not product:
        return jsonify({'error': 'Invalid product'}), 400

    user_id = session['user']

    try:
        # Build query
        query = supabase.table('cart_items').select('id, quantity, size').eq('user_id', user_id).eq('product_id', product_id).eq('size', size)
        existing = query.execute()

        if not existing.data:
            return jsonify({'error': 'Item not in cart'}), 404

        row = existing.data[0]
        effective_size = row.get('size') or 'Standard'
        new_qty = row['quantity'] + (1 if action == 'increment' else -1)

        if action == 'remove' or new_qty <= 0:
            supabase.table('cart_items').delete().eq('id', row['id']).execute()
            new_qty = 0
        else:
            supabase.table('cart_items').update({'quantity': new_qty}).eq('id', row['id']).execute()

        # Recalculate totals
        cart = get_db_cart(user_id)
        subtotal, tax, total = calc_totals(cart)
        
        cart_key = f"{product_id}_{effective_size}"
        item_price = cart.get(cart_key, {}).get('price', 0)

        return jsonify({
            'product_id': product_id,
            'size': effective_size,
            'new_qty': new_qty,
            'item_total': round(item_price * new_qty, 2),
            'subtotal': subtotal,
            'tax': tax,
            'total': total
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── Checkout ──────────────────────────────────────────────────────────────────

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'user' not in session:
        flash('Please login to checkout.', 'error')
        return redirect(url_for('login'))

    cart_items = get_db_cart(session['user'])
    if not cart_items:
        flash('Your cart is empty.', 'error')
        return redirect(url_for('home'))

    subtotal, tax, total_amount = calc_totals(cart_items)

    if request.method == 'POST':
        if not razorpay_client:
            flash('Payment gateway not configured.', 'error')
            return redirect(url_for('cart'))

        order_receipt   = f"order_{uuid.uuid4().hex[:10]}"
        amount_in_paise = int(total_amount * 100)

        try:
            razorpay_order = razorpay_client.order.create(dict(
                amount=amount_in_paise, currency='INR', receipt=order_receipt
            ))
        except Exception as e:
            flash(f'Payment gateway error: {str(e)}', 'error')
            return redirect(url_for('cart'))

        order_data = {
            "user_id": session['user'],
            "order_number": order_receipt,
            "razorpay_order_id": razorpay_order['id'],
            "total_amount": total_amount,
            "subtotal": subtotal,
            "tax": tax,
            "status": "created",
            "items": cart_items
        }
        supabase.table('orders').insert(order_data).execute()

        return render_template('checkout.html',
                               razorpay_order_id=razorpay_order['id'],
                               amount=amount_in_paise,
                               key_id=razorpay_key_id,
                               user_email=session['email'])

    return render_template('checkout_confirm.html', subtotal=subtotal, tax=tax, total=total_amount)

@app.route('/payment/success', methods=['POST'])
def payment_success():
    # Validate incoming data
    if not all([payment_id, razorpay_order_id, signature]):
        print(f"[PAYMENT] ERROR: Missing payment data. p_id={payment_id}, o_id={razorpay_order_id}, sig={signature}")
        flash('Payment details missing from gateway. Please contact support.', 'error')
        return redirect(url_for('home'))

    params_dict = {
        'razorpay_order_id': razorpay_order_id,
        'razorpay_payment_id': payment_id,
        'razorpay_signature': signature
    }

    try:
        print(f"[PAYMENT] Verifying signature for order_id: {razorpay_order_id}")
        # Verify with Razorpay SDK
        try:
            razorpay_client.utility.verify_payment_signature(params_dict)
        except Exception as sig_err:
            print(f"[PAYMENT] Signature Verification Failed: {str(sig_err)}")
            flash('Payment security verification failed. If money was deducted, please contact support.', 'error')
            return redirect(url_for('home'))

        receipt_token = f"REC-{uuid.uuid4().hex[:8].upper()}"
        
        # Log update attempt
        print(f"[PAYMENT] Signature verified. Updating order {razorpay_order_id} to status 'paid'...")
        
        update_resp = supabase.table('orders').update({
            "status": "paid", 
            "payment_id": payment_id
        }).eq("razorpay_order_id", razorpay_order_id).execute()
        
        print(f"[PAYMENT] DB Update Result: {update_resp.data}")
        
        if not update_resp.data:
            print(f"[PAYMENT] WARNING: No order found in DB with razorpay_order_id: {razorpay_order_id}")

        clear_db_cart(session['user'])
        flash(f'Payment successful! Your order has been placed.', 'success')
        return redirect(url_for('receipt', order_id=razorpay_order_id, token=receipt_token))
    except Exception as e:
        print(f"[PAYMENT] ERROR: {str(e)}")
        flash('Payment verification failed.', 'error')
        return redirect(url_for('home'))

@app.route('/receipt/<order_id>')
def receipt(order_id):
    if 'user' not in session:
        flash('Please login to view receipt.', 'error')
        return redirect(url_for('login'))
        
    token = request.args.get('token', '')
    
    try:
        resp = supabase.table('orders').select('*, profiles(name, email, phone, address)').eq('razorpay_order_id', order_id).execute()
        if not resp.data:
            flash('Order not found.', 'error')
            return redirect(url_for('home'))
            
        order = resp.data[0]
        if order['user_id'] != session['user'] and not session.get('is_admin'):
            flash('Unauthorized access.', 'error')
            return redirect(url_for('home'))
            
        return render_template('receipt.html', order=order, token=token)
    except Exception as e:
        flash(f'Error fetching receipt: {str(e)}', 'error')
        return redirect(url_for('home'))

@app.route('/my-orders')
def my_orders():
    if 'user' not in session:
        flash('Please login to view your orders.', 'error')
        return redirect(url_for('login'))
    
    try:
        # Fetch all orders for the user, ordered by most recent
        resp = supabase.table('orders').select('*').eq('user_id', session['user']).order('created_at', desc=True).execute()
        orders = resp.data or []
        
        # Calculate totals and counts for a nice summary
        paid_count = sum(1 for o in orders if o.get('status') == 'paid')
        
        return render_template('orders.html', orders=orders, paid_count=paid_count)
    except Exception as e:
        flash(f'Error fetching orders: {str(e)}', 'error')
        return redirect(url_for('home'))

# ── Admin ─────────────────────────────────────────────────────────────────────

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

@app.route('/admin')
def admin():
    if not session.get('is_admin'):
        flash('Unauthorized access.', 'error')
        return redirect(url_for('home'))

    orders_resp   = supabase.table('orders').select('*, profiles(name, email, phone, address)').order('created_at', desc=True).execute()
    products_resp = supabase.table('products').select('*').order('created_at', desc=True).execute()
    reviews_resp  = supabase.table('reviews').select('*, profiles(name, email), products(name)').order('created_at', desc=True).execute()
    
    orders   = orders_resp.data or []
    products = products_resp.data or []
    reviews  = reviews_resp.data or []

    revenue = sum(o['total_amount'] for o in orders if o.get('status') == 'paid')
    pending = sum(1 for o in orders if o.get('status') != 'paid')

    stats = {
        'total_orders': len(orders),
        'revenue':      revenue,
        'pending':      pending,
        'products':     len(products),
        'reviews':      len(reviews),
    }
    return render_template('admin.html', orders=orders, products=products, reviews=reviews, stats=stats)


@app.route('/admin/products/save', methods=['POST'])
def admin_product_save():
    if not session.get('is_admin'):
        flash('Unauthorized.', 'error')
        return redirect(url_for('home'))

    product_id  = request.form.get('product_id') or None
    name        = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    image_url   = request.form.get('image_url', '').strip()
    is_active   = request.form.get('is_active', 'true') == 'true'

    # Handle file upload (takes priority over URL)
    f = request.files.get('image_file')
    if f and f.filename and allowed_file(f.filename):
        ext      = f.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        f.save(os.path.join(UPLOAD_FOLDER, filename))
        image_url = url_for('static', filename=f'uploads/{filename}', _external=False)

    # Build sizes list
    size_names  = request.form.getlist('size_name[]')
    size_prices = request.form.getlist('size_price[]')
    sizes = [
        {'size': sn.strip(), 'price': float(sp or 0)}
        for sn, sp in zip(size_names, size_prices) if sn.strip()
    ]
    if not sizes:
        sizes = [{'size': 'Standard', 'price': 0}]

    payload = {
        'name':        name,
        'description': description,
        'image_url':   image_url,
        'is_active':   is_active,
        'sizes':       sizes,
    }

    # Generate SKU if it's a new product or missing
    sku = request.form.get('sku', '').strip()
    if not sku:
        sku = generate_sku()
    payload['sku'] = sku

    try:
        if product_id:
            supabase.table('products').update(payload).eq('id', product_id).execute()
            flash(f'Product "{name}" updated!', 'success')
        else:
            supabase.table('products').insert(payload).execute()
            flash(f'Product "{name}" added!', 'success')
    except Exception as e:
        flash(f'Error saving product: {e}', 'error')

    return redirect(url_for('admin') + '#tab-products')


@app.route('/admin/products/delete/<product_id>', methods=['POST'])
def admin_product_delete(product_id):
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 403
    try:
        supabase.table('products').delete().eq('id', product_id).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Set debug=False for production deployment
    app.run(debug=False, port=5000)
