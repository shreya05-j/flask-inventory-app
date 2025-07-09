from flask import Flask, render_template, request, redirect, url_for, session, flash
from sqlalchemy import or_
from functools import wraps
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from authlib.integrations.flask_client import OAuth
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", 'your_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SERVER_NAME'] = 'localhost:5000'

#Initialise users 
users = {
    'ks3': {
        'password': '1234',
        'role': 'developer'
    },
    'normaluser': {
        'password': 'abcd',
        'role': 'user'
    }
}

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Firebase Admin SDK Initialization
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_key.json")  # Make sure this file exists
    firebase_admin.initialize_app(cred)

# OAuth Setup
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    access_token_url='https://oauth2.googleapis.com/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    client_kwargs={'scope': 'openid email profile'},
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration'
)

# Register blueprints
from dynamic_pricing import dynamic_pricing_bp
from customer_behavior import customer_behavior_bp
from customer_behavior import simulate_beacon_data, save_heatmap, analyze_heatmap, recommend_products

app.register_blueprint(dynamic_pricing_bp)
app.register_blueprint(customer_behavior_bp)

# User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20))
    is_verified = db.Column(db.Boolean, default=False)
    last_login = db.Column(db.DateTime)

# Defining models
# Create tables inside app context
with app.app_context():
    db.create_all()



# Inventory
inventory = [
    {'id': 1, 'name': 'Apple', 'sku': '10001', 'stock': 50, 'location': 'Aisle 1', 'min_threshold': 10, 'max_threshold': 100, 'base_price': 10.0},
]

# Utility functions
def calculate_dynamic_price(product):
    base_price = product.get('base_price', 0)
    if product['stock'] == 0:
        return round(base_price * 1.5, 2)
    elif product['stock'] < product['min_threshold']:
        return round(base_price * 1.2, 2)
    elif product['stock'] > product['max_threshold']:
        return round(base_price * 0.85, 2)
    return round(base_price, 2)

def get_status(product):
    dynamic_price = calculate_dynamic_price(product)
    product['dynamic_price'] = dynamic_price
    if product['stock'] == 0:
        return 'Out of Stock'
    elif product['stock'] < product['min_threshold']:
        return 'Low'
    elif product['stock'] > product['max_threshold']:
        return 'Overstock'
    return 'Normal'

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

last_prices = {}

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Example hardcoded user check
        if username == 'ks3' and password == '1234':
            session['user_id'] = username
            session['role'] = 'developer'  # ✅ Here you mark the role
            return redirect(url_for('dashboard'))

        # Example fallback for other users
        elif username == 'normaluser' and password == 'abcd':
            session['user_id'] = username
            session['role'] = 'user'
            return redirect(url_for('dashboard'))

        else:
            return "Invalid credentials", 401

    return render_template('login.html')

    

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm = request.form['confirm']
        phone = request.form['phone']

        if password != confirm:
            error = 'Passwords do not match.'
        elif User.query.filter(or_(User.username == username, User.email == email)).first():
            error = 'Username or email already exists.'
        else:
            hashed_password = generate_password_hash(password)
            new_user = User()
            new_user.username = username
            new_user.email = email
            new_user.password = hashed_password
            new_user.phone = phone
            db.session.add(new_user)
            db.session.commit()
            flash('Registered successfully. Please login.', 'success')
            return redirect(url_for('login'))

    return render_template('register.html', error=error)

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    inventory = get_inventory()  # Your function to fetch inventory
    return render_template(
        'dashboard.html',
        inventory=inventory,
        role=session.get('role')
    )

def get_inventory():
    # Example: load your products from database or file
    return [
        {
            'id': 1,
            'name': 'Apple',
            'sku': '10001',
            'stock': 50,
            'location': 'Aisle 1',
            'status': 'Normal',
            'dynamic_price': 10.0,
            'price_change': 'increase'
        },
        {
            'id': 2,
            'name': 'Orange',
            'sku': '10002',
            'stock': 20,
            'location': 'Aisle 2',
            'status': 'Low',
            'dynamic_price': 8.0,
            'price_change': 'decrease'
        }
    ]


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/login/google')
def login_google():
    redirect_uri = url_for('google_callback', _external=True)
    if google is None:
        flash("Google OAuth is not configured properly. Please contact the administrator.", "error")
        return redirect(url_for('login'))
    return google.authorize_redirect(redirect_uri=redirect_uri)

@app.route('/login/google/callback')
def google_callback():
    try:
        if google is None:
            flash("Google OAuth is not configured properly. Please contact the administrator.", "error")
            return redirect(url_for('login'))
        token = google.authorize_access_token()
        resp = google.get('userinfo')
        user_info = resp.json()

        email = user_info['email']
        name = user_info.get('name', 'User')

        user = User.query.filter_by(email=email).first()
        if not user:
            user = User()
            user.username = name
            user.email = email
            user.password = 'google_auth'
            user.phone = '0000000000'
            user.is_verified = True
            db.session.add(user)
            db.session.commit()

        session['user_id'] = user.id
        return redirect(url_for('dashboard'))
    except Exception:
        flash("Google login failed. Please try again.", "error")
        return redirect(url_for('login'))

@app.route('/product/<int:pid>')
@login_required
def product_detail(pid):
    product = next((p for p in inventory if p['id'] == pid), None)
    if not product:
        return "Not found", 404
    product['status'] = get_status(product)
    return render_template('product_detail.html', product=product)

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        try:
            new_id = max([p['id'] for p in inventory]) + 1 if inventory else 1
            new_product = {
                'id': new_id,
                'name': request.form['name'].strip(),
                'sku': request.form['sku'].strip(),
                'stock': int(request.form['stock']),
                'location': request.form['location'].strip(),
                'min_threshold': int(request.form['min_threshold']),
                'max_threshold': int(request.form['max_threshold']),
                'base_price': float(request.form['base_price'])
            }
            inventory.append(new_product)
            flash("Product added successfully!", "success")
            return redirect(url_for('dashboard'))

        except (ValueError, KeyError) as e:
            flash(f"Error adding product: {e}", "danger")
            return redirect(url_for('add_product'))

    return render_template('add_product.html')

@app.route('/edit/<int:pid>', methods=['GET', 'POST'])
@login_required
def edit_product(pid):
    product = next((p for p in inventory if p['id'] == pid), None)
    if not product:
        return "Not found", 404
    if request.method == 'POST':
        product['name'] = request.form['name']
        product['sku'] = request.form['sku']
        product['stock'] = int(request.form['stock'])
        product['location'] = request.form['location']
        product['min_threshold'] = int(request.form['min_threshold'])
        product['max_threshold'] = int(request.form['max_threshold'])
        product['base_price'] = float(request.form['base_price'])
        return redirect(url_for('dashboard'))
    return render_template('edit_product.html', product=product)

@app.route('/dynamic-pricing', methods=['GET'])
@login_required
def dynamic_pricing():
    return render_template('dynamic_pricing.html')

@app.route('/customer_behavior', methods=['GET'])
@login_required
def customer_behavior_view():
    heatmap_data, paths = simulate_beacon_data()
    save_heatmap(heatmap_data)
    analysis = {
        'heatmap': analyze_heatmap(heatmap_data),
        'recommendations': recommend_products(paths[0])
    }
    chart_labels = []
    chart_data = []
    for y in range(len(heatmap_data)):
        for x in range(len(heatmap_data[0])):
            label = f"({x},{y})"
            count = int(heatmap_data[y][x])
            if count > 0:
                chart_labels.append(label)
                chart_data.append(count)

    return render_template(
        "customer_behavior.html",
        analysis=analysis,
        chart_labels=chart_labels,
        chart_data=chart_data
    )

if __name__ == '__main__':
    app.run(debug=True)
