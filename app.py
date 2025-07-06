from flask import Flask, render_template, request, redirect, url_for, session
from functools import wraps
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from flask_migrate import Migrate
from authlib.integrations.flask_client import OAuth
# Initialize app
app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Register blueprints
from dynamic_pricing import dynamic_pricing_bp
from customer_behavior import customer_behavior_bp
from customer_behavior import simulate_beacon_data, save_heatmap, analyze_heatmap, recommend_products


app.register_blueprint(dynamic_pricing_bp)
app.register_blueprint(customer_behavior_bp)
app.secret_key = os.getenv("SECRET_KEY", 'your_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SERVER_NAME'] = 'localhost:5000'  # Important for OAuth redirects

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
# In-memory user "database"
users = [
    {'username': 'admin', 'password': 'admin'}
]
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20))
    is_verified = db.Column(db.Boolean, default=False)
    last_login = db.Column(db.DateTime)
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

# Inventory "database" with 10 sample products
inventory = [
    {'id': 1, 'name': 'Apple', 'sku': '10001', 'stock': 50, 'location': 'Aisle 1', 'min_threshold': 10, 'max_threshold': 100, 'base_price': 10.0},
    {'id': 2, 'name': 'Banana', 'sku': '10002', 'stock': 5, 'location': 'Aisle 2', 'min_threshold': 10, 'max_threshold': 100, 'base_price': 5.0},
    {'id': 3, 'name': 'Orange', 'sku': '10003', 'stock': 25, 'location': 'Aisle 3', 'min_threshold': 10, 'max_threshold': 80, 'base_price': 8.0},
    {'id': 4, 'name': 'Milk', 'sku': '10004', 'stock': 0, 'location': 'Aisle 4', 'min_threshold': 5, 'max_threshold': 50, 'base_price': 12.0},
    {'id': 5, 'name': 'Bread', 'sku': '10005', 'stock': 15, 'location': 'Aisle 5', 'min_threshold': 8, 'max_threshold': 40, 'base_price': 6.0},
    {'id': 6, 'name': 'Eggs', 'sku': '10006', 'stock': 100, 'location': 'Aisle 6', 'min_threshold': 20, 'max_threshold': 120, 'base_price': 7.5},
    {'id': 7, 'name': 'Cheese', 'sku': '10007', 'stock': 60, 'location': 'Aisle 7', 'min_threshold': 10, 'max_threshold': 80, 'base_price': 15.0},
    {'id': 8, 'name': 'Tomato', 'sku': '10008', 'stock': 8, 'location': 'Aisle 8', 'min_threshold': 10, 'max_threshold': 60, 'base_price': 4.5},
    {'id': 9, 'name': 'Potato', 'sku': '10009', 'stock': 200, 'location': 'Aisle 9', 'min_threshold': 30, 'max_threshold': 150, 'base_price': 3.0},
    {'id': 10, 'name': 'Onion', 'sku': '10010', 'stock': 40, 'location': 'Aisle 10', 'min_threshold': 20, 'max_threshold': 100, 'base_price': 4.0}
]

#Calculating dynamic_price for any product
def calculate_dynamic_price(product):
    base_price = product.get('base_price', 0)
    if product['stock'] == 0:
        return round(base_price * 1.5, 2)
    elif product['stock'] < product['min_threshold']:
        return round(base_price * 1.2, 2)
    elif product['stock'] > product['max_threshold']:
        return round(base_price * 0.85, 2)
    else:
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
    else:
        return 'Normal'

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

last_prices = {}

@app.route('/', methods=['GET'])
@login_required
def dashboard():
    query = request.args.get('q', '').strip().lower()
    for product in inventory:
        product['status'] = get_status(product)
        prev_price = last_prices.get(product['id'], product.get('base_price', 0))
        current_price = product['dynamic_price']
        if current_price == 'N/A':
            product['price_change'] = 'none'
        elif current_price > prev_price:
            product['price_change'] = 'increase'
        elif current_price < prev_price:
            product['price_change'] = 'decrease'
        else:
            product['price_change'] = 'none'
        last_prices[product['id']] = current_price

    filtered_inventory = [
        p for p in inventory
        if query in p['name'].lower() or query in p['sku'].lower() or query in p['location'].lower()
    ] if query else inventory

    return render_template('dashboard.html', inventory=filtered_inventory, query=query)

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
        elif User.query.filter((User.username == username) | (User.email == email)).first():
            error = 'Username or email already exists.'
        else:
            hashed_password = generate_password_hash(password)
            new_user = User(username=username, email=email, password=hashed_password, phone=phone)
            db.session.add(new_user)
            db.session.commit()
            send_confirmation_email(email, username)
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
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        else:
            error = "Invalid credentials"
    return render_template("login.html", error=error)

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
@app.route('/login/google')
def login_google():
    # Use the exact redirect URI that matches your Google Cloud Console
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri=redirect_uri)

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
            user = User(
                username=name,
                email=email,
                password='google_auth',
                phone='0000000000',
                is_verified=True
            )
            db.session.add(user)
            db.session.commit()

        session['user_id'] = user.id
        return redirect(url_for('dashboard'))
    except Exception as e:
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
        new_id = max([p['id'] for p in inventory]) + 1 if inventory else 1
        inventory.append({
            'id': new_id,
            'name': request.form['name'],
            'sku': request.form['sku'],
            'stock': int(request.form['stock']),
            'location': request.form['location'],
            'min_threshold': int(request.form['min_threshold']),
            'max_threshold': int(request.form['max_threshold']),
            'base_price': float(request.form['base_price'])
        })
        return redirect(url_for('dashboard'))
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
    from customer_behavior import simulate_beacon_data, save_heatmap, analyze_heatmap, recommend_products
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
