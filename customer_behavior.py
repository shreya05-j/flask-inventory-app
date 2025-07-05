import numpy as np
import matplotlib.pyplot as plt
import random

from flask import Blueprint, render_template
import numpy as np
import matplotlib.pyplot as plt
import random

customer_behavior_bp = Blueprint('customer_behavior_bp', __name__)
@customer_behavior_bp.route("/customer_behavior", methods=["GET"])
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

# Simulate customer paths
def simulate_beacon_data(num_customers=10, grid_size=(10, 10)):
    heatmap = np.zeros(grid_size)
    paths = []

    for _ in range(num_customers):
        path = []
        x, y = random.randint(0, grid_size[0]-1), random.randint(0, grid_size[1]-1)
        for _ in range(random.randint(5, 15)):
            path.append((x, y))
            heatmap[y][x] += 1
            dx, dy = random.choice([(0,1), (1,0), (0,-1), (-1,0)])
            x, y = max(0, min(grid_size[0]-1, x + dx)), max(0, min(grid_size[1]-1, y + dy))
        paths.append(path)

    return heatmap, paths

# Save heatmap image
def save_heatmap(heatmap, filename="static/heatmap.png"):
    plt.imshow(heatmap, cmap='hot', interpolation='nearest')
    plt.colorbar()
    plt.title("Customer Heatmap")
    plt.savefig(filename)
    plt.close()

# Analyze heatmap
def analyze_heatmap(heatmap):
    max_visits = np.max(heatmap)
    most_visited = np.unravel_index(np.argmax(heatmap), heatmap.shape)
    return {
        "most_visited": most_visited,
        "max_visits": int(max_visits)
    }

# Recommend products based on path
def recommend_products(path):
    if not path:
        return []
    last_location = path[-1]
    return [f"Product near ({last_location[0]}, {last_location[1]})"]
