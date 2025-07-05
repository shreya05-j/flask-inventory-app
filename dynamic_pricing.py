# dynamic_pricing.py
from flask import Blueprint, request, jsonify
import numpy as np
from sklearn.linear_model import LinearRegression

# Blueprint for modular route registration
dynamic_pricing_bp = Blueprint('dynamic_pricing', __name__)

# Train the simple ML model
model = LinearRegression()
model.fit(X, y)

@dynamic_pricing_bp.route('/api/calculate-price', methods=['POST'])
def calculate_price():
    data = request.get_json()
    try:
        demand = float(data['demand_level'])
        inventory = float(data['inventory_level'])
        competitor_price = float(data['competitor_price'])
        features = np.array([[demand, inventory, competitor_price]])
        predicted_price = model.predict(features)[0]
        return jsonify({
            'predicted_price': round(predicted_price, 2)
        })
    except KeyError as e:
        return jsonify({'error': f'Missing key: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500
