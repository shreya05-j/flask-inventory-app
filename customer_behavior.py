# customer_behavior.py
from flask import Blueprint, render_template, request
import random

customer_behavior_bp = Blueprint('customer_behavior', __name__)

# Mock customer path and dwell time data generator
def generate_mock_customer_data():
    zones = ['Entrance', 'Aisle 1', 'Aisle 2', 'Aisle 3', 'Checkout']
    path = random.sample(zones, k=len(zones))
    dwell_times = {zone: random.randint(1, 10) for zone in path}  # minutes
    return path, dwell_times

@customer_behavior_bp.route('/customer_behavior', methods=['GET', 'POST'])
def customer_behavior_view():
    # Generate simulated data
    customer_path, dwell_data = generate_mock_customer_data()

    return render_template(
        'customer_behavior.html',
        path=customer_path,
        dwell_times=dwell_data,
        heatmap_img='heatmap.png'  # static image
    )
