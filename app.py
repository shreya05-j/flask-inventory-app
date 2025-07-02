from flask import Flask, render_template, request, redirect, url_for, session
from functools import wraps

# Initialize app
app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Register blueprints
from dynamic_pricing import dynamic_pricing_bp
from customer_behavior import customer_behavior_bp

app.register_blueprint(dynamic_pricing_bp)
app.register_blueprint(customer_behavior_bp)


# In-memory user "database"
users = [
    {'username': 'admin', 'password': 'admin'}
]

# Inventory "database" with 10 sample products
inventory = [
    {'id': 1, 'name': 'Apple', 'sku': '10001', 'stock': 50, 'location': 'Aisle 1', 'min_threshold': 10, 'max_threshold': 100},
    {'id': 2, 'name': 'Banana', 'sku': '10002', 'stock': 5, 'location': 'Aisle 2', 'min_threshold': 10, 'max_threshold': 100},
    {'id': 3, 'name': 'Orange', 'sku': '10003', 'stock': 25, 'location': 'Aisle 3', 'min_threshold': 10, 'max_threshold': 80},
    {'id': 4, 'name': 'Milk', 'sku': '10004', 'stock': 0, 'location': 'Aisle 4', 'min_threshold': 5, 'max_threshold': 50},
    {'id': 5, 'name': 'Bread', 'sku': '10005', 'stock': 15, 'location': 'Aisle 5', 'min_threshold': 8, 'max_threshold': 40},
    {'id': 6, 'name': 'Eggs', 'sku': '10006', 'stock': 100, 'location': 'Aisle 6', 'min_threshold': 20, 'max_threshold': 120},
    {'id': 7, 'name': 'Cheese', 'sku': '10007', 'stock': 60, 'location': 'Aisle 7', 'min_threshold': 10, 'max_threshold': 80},
    {'id': 8, 'name': 'Tomato', 'sku': '10008', 'stock': 8, 'location': 'Aisle 8', 'min_threshold': 10, 'max_threshold': 60},
    {'id': 9, 'name': 'Potato', 'sku': '10009', 'stock': 200, 'location': 'Aisle 9', 'min_threshold': 30, 'max_threshold': 150},
    {'id': 10, 'name': 'Onion', 'sku': '10010', 'stock': 40, 'location': 'Aisle 10', 'min_threshold': 20, 'max_threshold': 100}
]
#Calculating dynamic_price for any product
def calculate_dynamic_price(product):
    base_price = 10.0  # You can set this dynamically per product later

    # Example pricing logic based on stock levels
    if product['stock'] == 0:
        return base_price * 1.5  # Out of stock = raise price
    elif product['stock'] < product['min_threshold']:
        return base_price * 1.2  # Low stock = slightly higher price
    elif product['stock'] > product['max_threshold']:
        return base_price * 0.8  # Overstock = lower price
    else:
        return base_price  # Normal stock = base price

#Getting current status of the product in stock
def get_status(product):
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

#Route functions
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

@app.route('/', methods=['GET'])
@login_required
def dashboard():
    query = request.args.get('q', '').strip().lower()
    for product in inventory:
        product['status'] = get_status(product)
    if query:
        filtered_inventory = [
            p for p in inventory
            if query in p['name'].lower() or query in p['sku'].lower() or query in p['location'].lower()
        ]
    else:
        filtered_inventory = inventory
    return render_template('dashboard.html', inventory=filtered_inventory, query=query)

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
            'max_threshold': int(request.form['max_threshold'])
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
        return redirect(url_for('dashboard'))
    return render_template('edit_product.html', product=product)

if __name__ == '__main__':
    app.run(debug=True)
#Routing dynamic pricing
@app.route('/dynamic-pricing', methods=['GET'])
@login_required
def dynamic_pricing():
    return render_template('dynamic_pricing.html')


#Customer behavior 
from flask import render_template


@app.route("/customer_behavior", methods=["GET", "POST"])
def customer_behavior():
    # If there's any logic from customer_behavior.py to be used, call it here.
    return render_template("customer_behavior.html")


app = Flask(__name__)

@app.route("/customer_behavior", methods=["GET"])
def customer_behavior_view():
    # Step 1: Simulate data
    heatmap_data, paths = customer_behavior.simulate_beacon_data()

    # Step 2: Save heatmap to PNG (auto-generated on each visit)
    customer_behavior.save_heatmap(heatmap_data)

    # Step 3: Analyze and recommend
    analysis = {
        'heatmap': customer_behavior.analyze_heatmap(heatmap_data),
        'recommendations': customer_behavior.recommend_products(paths[0])
    }

    # Step 4: Flatten for chart
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

