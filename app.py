from flask import Flask, render_template, request, redirect, url_for, session, flash
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

import firebase_admin
from firebase_admin import credentials, auth as firebase_auth

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from authlib.integrations.flask_client import OAuth

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", 'your_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Firebase Setup
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_key.json")
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

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20))
    is_verified = db.Column(db.Boolean, default=False)
    last_login = db.Column(db.DateTime)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    sku = db.Column(db.String(80), unique=True, nullable=False)
    stock = db.Column(db.Integer, default=0)
    location = db.Column(db.String(100))
    status = db.Column(db.String(50))

@app.route('/')
def home():
    return redirect(url_for('login'))

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
        elif not username or not password or not email:
            error = 'Please fill out all fields.'
        elif User.query.filter((User.username == username) | (User.email == email)).first():
            error = 'Username or email already exists.'
        else:
            hashed_password = generate_password_hash(password)
            new_user = User(username=username, email=email, password=hashed_password, phone=phone)
            db.session.add(new_user)
            db.session.commit()
            flash('Registered successfully. Please login.', 'success')
            return redirect(url_for('login'))

    return render_template('register.html', error=error)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username_or_email = request.form['username']
        password = request.form['password']
        user = User.query.filter((User.username == username_or_email) | (User.email == username_or_email)).first()

        if user and check_password_hash(user.password, password):
            user.last_login = datetime.utcnow()
            db.session.commit()
            session['logged_in'] = True
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('dashboard'))
        else:
            error = 'Invalid credentials.'

    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/firebase-login', methods=['POST'])
def firebase_login():
    try:
        id_token = request.json.get('idToken')
        decoded_token = firebase_auth.verify_id_token(id_token)
        email = decoded_token['email']
        name = decoded_token.get('name', 'User')

        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(username=name, email=email, password='firebase_user', phone='0000000000')
            db.session.add(user)
            db.session.commit()

        session['user_id'] = user.id
        session['username'] = user.username
        return {'message': 'Login successful'}
    except Exception as e:
        return {'error': str(e)}, 401

@app.route('/login/google')
def login_google():
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/login/google/callback')
def google_callback():
    try:
        token = google.authorize_access_token()
        resp = google.get('userinfo')
        user_info = resp.json()

        email = user_info['email']
        name = user_info.get('name', 'User')

        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(username=name, email=email, password='google_auth', phone='0000000000', is_verified=True)
            db.session.add(user)
            db.session.commit()

        session['user_id'] = user.id
        session['username'] = user.username
        return redirect(url_for('dashboard'))
    except Exception:
        flash("Google login failed. Please try again.", "error")
        return redirect(url_for('login'))

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/dashboard')
@login_required
def dashboard():
    inventory = Product.query.all()
    return render_template('dashboard.html', inventory=inventory)

@app.route('/product/<int:pid>')
@login_required
def product_detail(pid):
    product = Product.query.get_or_404(pid)
    return render_template('product_detail.html', product=product)

@app.route('/add_to_cart/<int:pid>', methods=['POST'])
def add_to_cart(pid):
    cart = session.get('cart', [])
    if pid not in cart:
        cart.append(pid)
    session['cart'] = cart
    return redirect(url_for('cart'))

@app.route('/remove_from_cart/<int:pid>', methods=['POST'])
def remove_from_cart(pid):
    cart = session.get('cart', [])
    if pid in cart:
        cart.remove(pid)
    session['cart'] = cart
    return redirect(url_for('cart'))

@app.route('/cart')
def cart():
    cart_ids = session.get('cart', [])
    cart_items = Product.query.filter(Product.id.in_(cart_ids)).all() if cart_ids else []
    return render_template('cart.html', cart_items=cart_items)

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if request.method == 'POST':
        session['cart'] = []
        flash("Payment successful!", "success")
        return redirect(url_for('dashboard'))
    return render_template('checkout.html')

if __name__ == '__main__':
    app.run(debug=True)
