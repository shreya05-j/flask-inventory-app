from flask import Flask, render_template, request, redirect, url_for, session
from functools import wraps

# Initialize app
app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Register blueprints
from dynamic_pricing import dynamic_pricing_bp
from customer_behavior import customer_behavior_bp
from customer_behavior import simulate_beacon_data, save_heatmap, analyze_heatmap, recommend_products


app.register_blueprint(dynamic_pricing_bp)
app.register_blueprint(customer_behavior_bp)

# In-memory user "database"
users = [
    {'username': 'admin', 'password': 'admin'}
]

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
        password = request.form['password']
        if any(u['username'] == username for u in users):
            error = 'Username already exists.'
        elif not username or not password:
            error = 'Please fill out all fields.'
        else:
            users.append({'username': username, 'password': password})
            return redirect(url_for('login'))
    return render_template('register.html', error=error)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = next((u for u in users if u['username'] == username and u['password'] == password), None)
        if user:
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            error = 'Invalid credentials.'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
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
