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


# ======================================
# FRONT-END ROUTES (templates/front-end/)
# ======================================

# 1. HOME
@app.route('/')
@app.route('/home')
def home():
    return render_template("front-end/guest/home.html", products=data_store.PRODUCTS_DB)


# 2. ERROR HANDLER (404)
@app.errorhandler(404)
def page_not_found(e):
    return render_template('front-end/errors/404.html'), 404


# 3. PRODUCTS CATALOG (PAGINATION)
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
        'front-end/guest/products.html',
        products=products,
        page=page,
        total_pages=total_pages,
        total_products=total_products
    )


@app.route('/products-alias', endpoint='products')
def products_alias():
    return redirect(url_for('product'))


# 4. PRODUCT DETAIL
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
        return render_template('front-end/errors/404.html'), 404

    response = make_response(
        render_template("front-end/guest/product_detail.html", product=product, products=data_store.PRODUCTS_DB)
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


# 5. CART HELPERS & CART PAGE
def get_cart_from_cookie():
    cart_cookie = request.cookies.get('cart')
    if not cart_cookie:
        return []
    try:
        return json.loads(cart_cookie)
    except Exception:
        return []


def calculate_cart(cart):
    subtotal = sum(item.get('price', 0) * item.get('qty', 1) for item in cart)
    tax = subtotal * 0.1
    total = subtotal + tax
    return subtotal, tax, total


@app.context_processor
def cart_count():
    cart = get_cart_from_cookie()
    return dict(cart_count=len(cart))


@app.route('/cart')
def cart():
    cart_items = get_cart_from_cookie()
    subtotal, tax, total = calculate_cart(cart_items)

    return render_template(
        'front-end/guest/cart.html',
        cart=cart_items,
        subtotal=subtotal,
        tax=tax,
        total=total
    )


# 6. CHECKOUT
@app.route('/checkout')
def checkout():
    cart = get_cart_from_cookie()
    subtotal, tax, total = calculate_cart(cart)

    return render_template(
        "front-end/popup/checkout_model.html",
        cart=cart,
        subtotal=subtotal,
        tax=tax,
        total=total
    )


@app.route('/checkout/complete')
def checkout_complete():
    response = make_response(
        render_template("front-end/popup/receipt_model.html")
    )
    response.set_cookie('cart', '', expires=0, path='/')
    return response


# 7. RECEIPT
@app.route('/receipt')
def receipt():
    cart = get_cart_from_cookie()
    subtotal, tax, total = calculate_cart(cart)

    return render_template(
        "front-end/popup/receipt_model.html",
        cart=cart,
        subtotal=subtotal,
        tax=tax,
        total=total
    )


# 8. PAYMENT & PROCESS PAYMENT
@app.route('/payment', methods=['GET', 'POST'])
def payment():
    cart = get_cart_from_cookie()
    subtotal, tax, total = calculate_cart(cart)

    if request.method == 'POST':
        shipping = {
            "first_name": request.form.get("first_name", ""),
            "last_name": request.form.get("last_name", ""),
            "phone": request.form.get("phone", ""),
            "address": request.form.get("address", ""),
            "email": request.form.get("email", ""),
        }
        session['shipping'] = shipping
        session['cart'] = cart
    else:
        shipping = session.get('shipping', {
            "first_name": "", "last_name": "", "phone": "", "address": "", "email": ""
        })

    return render_template(
        "front-end/popup/payment_model.html",
        shipping=shipping,
        cart=cart,
        subtotal=subtotal,
        tax=tax,
        total=total
    )


@app.route('/process-payment', methods=['POST'])
def process_payment():
    response = make_response(
        render_template('front-end/popup/receipt_model.html')
    )
    response.delete_cookie('cart', path='/')
    response.delete_cookie('shipping', path='/')
    return response


@app.route('/cart/payment-success', methods=['POST'])
def payment_success():
    cart = get_cart_from_cookie()
    subtotal, tax, total = calculate_cart(cart)

    resp = make_response(render_template(
        "front-end/popup/receipt_model.html",
        cart=cart,
        subtotal=subtotal,
        tax=tax,
        total=total
    ))
    resp.set_cookie('cart', '', max_age=0, path='/')
    return resp


@app.route('/clear-cart-and-go-home')
def clear_cart_and_home():
    response = make_response(redirect(url_for('product')))
    response.delete_cookie('cart', path='/')
    response.delete_cookie('shipping', path='/')
    return response


@app.route('/cart/confirm-payment', methods=['POST'])
def confirm_payment():
    shipping = session.get('shipping', {})
    cart = session.get('cart', [])

    if not cart:
        cart = get_cart_from_cookie()

    if not cart:
        return redirect(url_for('product'))

    subtotal, tax_amount, final_total = calculate_cart(cart)

    order_message = "🛍 <b>NEW ORDER RECEIVED</b>\n"
    order_message += "───────────────────\n\n"

    order_message += "👤 <b>Shipping Details:</b>\n"
    order_message += f"• <b>Name:</b> {shipping.get('first_name', '')} {shipping.get('last_name', '')}\n"
    order_message += f"• <b>Phone:</b> <code>{shipping.get('phone', '')}</code>\n"
    order_message += f"• <b>Address:</b> <code>{shipping.get('address', '')}</code>\n"
    order_message += f"• <b>Email:</b> <code>{shipping.get('email', '')}</code>\n\n"

    order_message += "📦 <b>Order Items:</b>\n"
    for item in cart:
        item_total = item.get('price', 0) * item.get('qty', 1)
        order_message += f"▪️ {item.get('title', 'Product')} <b>x{item.get('qty', 1)}</b> - ${item_total:.2f}\n"

    order_message += "\n───────────────────\n"
    order_message += f"<b>Subtotal:</b> ${subtotal:.2f}\n"
    order_message += f"<b>Tax (10%):</b> ${tax_amount:.2f}\n"
    order_message += f"💰 <b>Total Due:</b> <code>${final_total:.2f}</code>"

    import requests
    token_bot = "8953023563:AAEr-4cP-FVghqawrKQuFzcfNc6y8rzsyaE"
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

    try:
        requests.post(url, json=payload, headers=headers, timeout=5)
    except Exception as e:
        print(f"Telegram notification error: {e}")

    session.pop('cart', None)
    return redirect(url_for('receipt'))


# 9. NEW ARRIVALS
@app.route('/new-arrival')
def new_arrival():
    products = [
        p for p in data_store.PRODUCTS_DB
        if p.get("is_new_arrival")
    ]
    return render_template(
        "front-end/guest/new_arrival.html",
        products=products
    )


# 10. BEST SELLERS
@app.route('/best-seller')
def best_seller():
    products = [
        p for p in data_store.PRODUCTS_DB
        if p.get("is_best_seller")
    ]
    return render_template(
        "front-end/guest/best_seller.html",
        products=products
    )


# 11. CATEGORY FILTER + PAGINATION
@app.route('/category')
def products_by_category():
    category = request.args.get('category')
    page = request.args.get('page', 1, type=int)

    if not category:
        return redirect(url_for('product'))

    filtered = [
        p for p in data_store.PRODUCTS_DB
        if p.get("category", "").lower() == category.lower()
    ]

    per_page = 9
    total_pages = math.ceil(len(filtered) / per_page) if filtered else 1

    start = (page - 1) * per_page
    end = start + per_page

    products = filtered[start:end]

    return render_template(
        'front-end/guest/products.html',
        products=products,
        page=page,
        total_pages=total_pages,
        category=category
    )


# 12. GUEST PAGES (CONTACT, SHIPPING, PRIVACY, RETURNS)
@app.route('/contact')
def contact():
    return render_template('front-end/guest/contact.html')


@app.route('/shipping-info')
def shipping_info():
    return render_template('front-end/guest/shipping_info.html')


@app.route('/privacy-policy')
def privacy_policy():
    return render_template('front-end/guest/privacy_policy.html')


@app.route('/returns')
def returns():
    return render_template('front-end/guest/shipping_info.html')


# 13. AUTH ROUTES
@app.route('/signin')
@app.route('/login')
def signin():
    return render_template('front-end/auth/signin.html')


@app.route('/signup')
@app.route('/register')
def signup():
    return render_template('front-end/auth/signup.html')


@app.route('/forgot-password')
def forgot_password():
    return render_template('front-end/auth/forgot_password.html')


# 14. USER PROFILE ROUTES
@app.route('/profile')
def profile():
    return render_template('front-end/user/profile.html')


@app.route('/profile/edit')
def edit_profile():
    return render_template('front-end/user/edit_profile.html')


@app.route('/profile/orders')
def order_history():
    return render_template('front-end/user/order_history.html')


@app.route('/wishlist')
def wishlist():
    return render_template('front-end/user/wishlist.html')


@app.route('/address-book')
def address_book():
    return render_template('front-end/user/address_book.html')


@app.route('/change-password')
def change_password():
    return render_template('front-end/user/change_password.html')


# 15. CART ACTIONS (ADD, REMOVE, UPDATE)
@app.route('/cart/add', methods=['POST'])
def cart_add():
    product_id = request.form.get('product_id', type=int)
    if not product_id:
        return redirect(url_for('product'))

    product = next(
        (p for p in data_store.PRODUCTS_DB if p['id'] == product_id),
        None
    )

    if not product:
        return redirect(url_for('product'))

    cart = get_cart_from_cookie()

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
            'category': product['category'],
            'qty': 1
        })

    response = make_response(
        redirect(request.referrer or url_for('home'))
    )
    response.set_cookie(
        'cart',
        json.dumps(cart),
        max_age=60 * 60 * 24 * 7,
        path='/'
    )
    return response


@app.route('/cart/remove', methods=['POST'])
def cart_remove():
    product_id = request.form.get('product_id', type=int)
    cart = get_cart_from_cookie()

    if product_id is not None:
        cart = [item for item in cart if item.get('id') != product_id]

    response = make_response(redirect(url_for('cart')))
    response.set_cookie('cart', json.dumps(cart), max_age=60 * 60 * 24 * 7, path='/')
    return response


@app.route('/cart/update', methods=['POST'])
def cart_update():
    product_id = request.form.get('product_id', type=int)
    qty = request.form.get('qty', type=int)
    cart = get_cart_from_cookie()

    if product_id is not None and qty is not None:
        if qty <= 0:
            cart = [item for item in cart if item.get('id') != product_id]
        else:
            for item in cart:
                if item.get('id') == product_id:
                    item['qty'] = qty

    response = make_response(redirect(url_for('cart')))
    response.set_cookie('cart', json.dumps(cart), max_age=60 * 60 * 24 * 7, path='/')
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