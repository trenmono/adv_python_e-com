from flask import Flask, jsonify, request, render_template, Blueprint, session, redirect, url_for, json
from flask import make_response,abort
import math
import data_store
from flask_sqlalchemy import  SQLAlchemy
from flask_migrate import Migrate


app = Flask(__name__)
app.secret_key = 'your-secret-key'
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///mydb.sqlite3"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    password = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)

store_bp = Blueprint('store_api', __name__)
stuff_bp = Blueprint('stuff', __name__, url_prefix='/admin/user')
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# HOME
@admin_bp.route('/')
@admin_bp.route('/<tab>')
def admin(tab='dashboard'):
    # Define valid tabs based on your templates/admin/dashboard/ folder
    valid_tabs = [
        'dashboard', 'analytics', 'customers',
        'inventory', 'orders', 'products', 'user_management'
    ]
    if tab not in valid_tabs:
        abort(404)  # Triggers your 404 error handler if the page doesn't exist

    return render_template("admin/master.html", tab=tab)

@stuff_bp.route('/')
@stuff_bp.route('/<tab>')
def stuff(tab='dashboard'):
    # Define valid tabs based on your templates/user/dashboard/ folder
    valid_tabs = [
        'dashboard', 'inventory', 'orders', 'products', 'profile'
    ]
    if tab not in valid_tabs:
        abort(404)
    return render_template("admin/user/master_stuff.html", tab=tab)


@app.route('/')
@app.route('/home')
def home():
    return render_template("front/home.html", products=data_store.PRODUCTS_DB)


@app.errorhandler(404)
def page_not_found(e):

    return render_template('front/page404.html'), 404

# PRODUCTS (PAGINATION)

@app.route('/products')
def product():
    page = request.args.get('page', 1, type=int)

    per_page = 9

    total_products = len(data_store.PRODUCTS_DB)
    total_pages = math.ceil(total_products / per_page)

    start = (page - 1) * per_page
    end = start + per_page

    products = data_store.PRODUCTS_DB[start:end]

    return render_template(
        'front/products.html',
        products=products,
        page=page,
        total_pages=total_pages,
        total_products=total_products
    )


# ======================================
# PRODUCT DETAIL
# ======================================
@app.route('/product-detail')
@app.route('/product-detail/<int:product_id>')
def product_detail(product_id=None):
    if product_id is None:
        product_id = request.args.get('id', type=int)

    product = next(
        (p for p in data_store.PRODUCTS_DB if p["id"] == product_id),
        None
    )

    if product is None:
        return render_template('front/page404.html'), 404

    response = make_response(
        render_template("front/product-detail.html", product=product, products=data_store.PRODUCTS_DB)
    )
    response.set_cookie(
        'last_viewed_product',
        json.dumps({
            'id': product['id'],
            'title': product['title'],
            'price': product['price'],
            'image': product['image'],
            'category': product['category']
        }),
        max_age=60 * 60 * 24,
        path='/'
    )
    return response


# ======================================
# CART PAGE
# ======================================
@app.route('/cart')
def cart():
    cart_items = json.loads(
        request.cookies.get('cart', '[]')
    )

    subtotal = sum(
        item['price'] * item['qty']
        for item in cart_items
    )

    tax = subtotal * 0.1
    total = subtotal + tax

    return render_template(
        'front/cart.html',
        cart=cart_items,
        subtotal=subtotal,
        tax=tax,
        total=total
    )

def get_cart_from_cookie():
    cart_cookie = request.cookies.get('cart')

    if not cart_cookie:
        return []

    try:
        return json.loads(cart_cookie)
    except:
        return []


def calculate_cart(cart):
    subtotal = sum(item['price'] * item['qty'] for item in cart)
    tax = subtotal * 0.1
    total = subtotal + tax
    return subtotal, tax, total


# ======================================
# CHECKOUT
# ======================================
@app.route('/checkout')
def checkout():
    cart = get_cart_from_cookie()
    subtotal, tax, total = calculate_cart(cart)

    return render_template(
        "front/checkout.html",
        cart=cart,
        subtotal=subtotal,
        tax=tax,
        total=total
    )

@app.route('/checkout/complete')
def checkout_complete():

    response = make_response(
        render_template("front/receipt.html")
    )

    response.set_cookie(
        'cart',
        '',
        expires=0
    )

    return response

# ======================================
# RECEIPT
# ======================================
@app.route('/receipt')
def receipt():
    cart = get_cart_from_cookie()

    subtotal = sum(item['price'] * item['qty'] for item in cart)
    tax = subtotal * 0.1
    total = subtotal + tax

    return render_template(
        "front/receipt.html",
        cart=cart,
        subtotal=subtotal,
        tax=tax,
        total=total
    )

# ======================================
# PAYMENT
# ======================================
@app.route('/payment', methods=['GET', 'POST'])
def payment():
    cart = get_cart_from_cookie()
    subtotal, tax, total = calculate_cart(cart)

    # ⚠️ shipping MUST come from form OR session
    shipping = {
        "first_name": request.form.get("first_name", ""),
        "last_name": request.form.get("last_name", ""),
        "phone": request.form.get("phone", ""),
        "address": request.form.get("address", ""),
        "email": request.form.get("email", ""),

    }

    session['shipping'] = shipping
    session['cart'] = cart

    return render_template(
        "front/payment.html",
        shipping=shipping,
        cart=cart,
        subtotal=subtotal,
        tax=tax,
        total=total
    )

@app.context_processor
def cart_count():
    cart = json.loads(request.cookies.get('cart', '[]'))

    count = len(cart)

    return dict(cart_count=count)

@app.route('/process-payment', methods=['POST'])
def process_payment():
    response = make_response(
        render_template('front/receipt.html')
    )

    response.delete_cookie('cart')
    response.delete_cookie('shipping')

    return response

@app.route('/cart/payment-success', methods=['POST'])
def payment_success():
    # 1. READ CART FIRST (before clearing)
    cart_cookie = request.cookies.get('cart')

    if cart_cookie:
        try:
            cart = json.loads(cart_cookie)
        except:
            cart = []
    else:
        cart = []

    # 2. CALCULATE TOTAL
    subtotal = sum(item['price'] * item['qty'] for item in cart)
    tax = subtotal * 0.1
    total = subtotal + tax

    # 3. CLEAR COOKIE AFTER READ
    resp = make_response(render_template(
        "front/receipt.html",
        cart=cart,
        subtotal=subtotal,
        tax=tax,
        total=total
    ))

    resp.set_cookie('cart', '', max_age=0, path='/')

    return resp

@app.route('/clear-cart-and-go-home')
def clear_cart_and_home():
    # Force delete the cart cookie, routing back to the store front
    response = make_response(redirect(url_for('product')))
    response.delete_cookie('cart', path='/')
    response.delete_cookie('shipping', path='/')
    return response

# ======================================
# CONFIRM-PAYMENT
# ======================================
@app.route('/cart/confirm-payment', methods=['POST'])
def confirm_payment():

    shipping = session.get('shipping', {})
    cart = session.get('cart', [])

    if not cart:
        cart = get_cart_from_cookie()


    if not cart:
        return redirect(url_for('product'))

    # 1. Calculate the financial breakdown first to keep the message template clean
    subtotal = sum(item['price'] * item['qty'] for item in cart)
    tax_rate = 0.1
    tax_amount = subtotal * tax_rate
    final_total = subtotal + tax_amount

    # 2. Build the Telegram order message
    order_message = "🛍 <b>NEW ORDER RECEIVED</b>\n"
    order_message += "───────────────────\n\n"

    order_message += "👤 <b>Shipping Details:</b>\n"
    order_message += f"• <b>Name:</b> {shipping.get('first_name', '')} {shipping.get('last_name', '')}\n"
    order_message += f"• <b>Phone:</b> <code>{shipping.get('phone', '')}</code>\n"
    order_message += f"• <b>Address:</b> <code>{shipping.get('address', '')}</code>\n"
    order_message+=f"• <b>Email:</b> <code>{shipping.get('email', '')}</code>\n\n"

    order_message += "📦 <b>Order Items:</b>\n"
    for item in cart:
        item_total = item['price'] * item['qty']
        order_message += f"▪️ {item['title']} <b>x{item['qty']}</b> - ${item_total:.2f}\n"

    # 3. Add the clear tax breakdown at the bottom
    order_message += "\n───────────────────\n"
    order_message += f"<b>Subtotal:</b> ${subtotal:.2f}\n"
    order_message += f"<b>Tax (10%):</b> ${tax_amount:.2f}\n"
    order_message += f"💰 <b>Total Due:</b> <code>${final_total:.2f}</code>"

    import requests
    token_bot ="8953023563:AAEr-4cP-FVghqawrKQuFzcfNc6y8rzsyaE"
    url = f"https://api.telegram.org/bot{token_bot}/sendMessage"

    payload = {
        "text": order_message,
        "parse_mode": "HTML",
        "chat_id": "@bot_python888",
        "disable_web_page_preview": False,
        "disable_notification": False,
        "reply_to_message_id": None
    }
    headers = {
        "accept": "application/json",
        "User-Agent": "Telegram Bot SDK - (https://github.com/irazasyed/telegram-bot-sdk)",
        "content-type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)

    print(response.text)
    # Save order to database here

    session.pop('cart', None)

    return redirect(url_for('receipt'))


# ======================================
# NEW ARRIVALS
# ======================================
@app.route('/new-arrival')
def new_arrival():
    products = [
        p for p in data_store.PRODUCTS_DB
        if p.get("is_new_arrival")
    ]

    return render_template(
        "front/new_arrival.html",
        products=products
    )


# ======================================
# BEST SELLERS
# ======================================
@app.route('/best-seller')
def best_seller():
    products = [
        p for p in data_store.PRODUCTS_DB
        if p.get("is_best_seller")
    ]

    return render_template(
        "front/best_seller.html",
        products=products
    )


# ======================================
# CATEGORY FILTER + PAGINATION
# ======================================
@app.route('/category')
def products_by_category():
    category = request.args.get('category')
    page = request.args.get('page', 1, type=int)

    if not category:
        return redirect(url_for('product'))

    filtered = [
        p for p in data_store.PRODUCTS_DB
        if p["category"] == category
    ]

    per_page = 9
    total_pages = math.ceil(len(filtered) / per_page)

    start = (page - 1) * per_page
    end = start + per_page

    products = filtered[start:end]

    return render_template(
        'front/products.html',
        products=products,
        page=page,
        total_pages=total_pages,
        category=category
    )


# ======================================
# CART ADD
# ======================================
@app.route('/cart/add', methods=['POST'])
def cart_add():
    product_id = int(request.form.get('product_id'))

    product = next(
        (p for p in data_store.PRODUCTS_DB if p['id'] == product_id),
        None
    )

    if not product:
        return jsonify({
            'success': False,
            'message': 'Product not found'
        }), 404

    cart = json.loads(request.cookies.get('cart', '[]'))

    existing = next(
        (item for item in cart if item['id'] == product_id),
        None
    )

    if existing:
        existing['qty'] += 1
    else:
        cart.append({
            'id': product['id'],
            'title': product['title'],
            'price': product['price'],
            'image': product['image'],
            'qty': 1
        })

    total_qty = len(cart)

    response = make_response(jsonify({
        'success': True,
        'cart_count': total_qty
    }))
    response = make_response(
        redirect(request.referrer or url_for('home'))
    )
    response.set_cookie(
        'cart',
        json.dumps(cart),
        max_age=60 * 60 * 24 * 7
    )

    return response

# ======================================
# CART REMOVE
# ======================================
@app.route('/cart/remove', methods=['POST'])
def cart_remove():
    product_id = int(request.form.get('product_id'))

    cart = json.loads(request.cookies.get('cart', '[]'))

    cart = [
        item for item in cart
        if item['id'] != product_id
    ]

    response = make_response(
        redirect(url_for('cart'))
    )

    response.set_cookie(
        'cart',
        json.dumps(cart),
        max_age=60 * 60 * 24 * 7
    )

    return response


# ======================================
# CART UPDATE
# ======================================
@app.route('/cart/update', methods=['POST'])
def cart_update():
    product_id = int(request.form.get('product_id'))
    qty = int(request.form.get('qty'))

    cart = json.loads(
        request.cookies.get('cart', '[]')
    )

    for item in cart:
        if item['id'] == product_id:
            item['qty'] = max(1, qty)

    response = make_response(
        redirect(url_for('cart'))
    )

    response.set_cookie(
        'cart',
        json.dumps(cart),
        max_age=60 * 60 * 24 * 7
    )

    return response


# ======================================
# API BLUEPRINT
# ======================================
@store_bp.route('/products', methods=['GET'])
def get_products():
    return jsonify(data_store.PRODUCTS_DB)


@store_bp.route('/products/<int:product_id>', methods=['GET'])
def get_product_by_id(product_id):
    product = next(
        (p for p in data_store.PRODUCTS_DB if p['id'] == product_id),
        None
    )
    if product:
        return jsonify(product)

    return jsonify({"error": "Product not found"}), 404


@store_bp.route('/products/category/<string:category_name>', methods=['GET'])
def get_products_by_category(category_name):
    filtered = [
        p for p in data_store.PRODUCTS_DB
        if p.get('category', '').lower() == category_name.lower()
    ]
    return jsonify(filtered)


@store_bp.route('/products/new-arrivals', methods=['GET'])
def get_new_arrivals():
    return jsonify([
        p for p in data_store.PRODUCTS_DB
        if p.get('is_new_arrival')
    ])


@store_bp.route('/products/best-sellers', methods=['GET'])
def get_best_sellers():
    return jsonify([
        p for p in data_store.PRODUCTS_DB
        if p.get('is_best_seller')
    ])


# ======================================
# REGISTER BLUEPRINT
# ======================================
app.register_blueprint(store_bp, url_prefix='/api')
app.register_blueprint(admin_bp)
app.register_blueprint(stuff_bp)


# ======================================
# RUN
# ======================================
if __name__ == '__main__':
    app.run(debug=True)