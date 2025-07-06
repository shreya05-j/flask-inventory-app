// Firebase Google Sign-in logic
import { initializeApp } from "https://www.gstatic.com/firebasejs/11.10.0/firebase-app.js";
import { getAuth, signInWithPopup, GoogleAuthProvider } from "https://www.gstatic.com/firebasejs/11.10.0/firebase-auth.js";

const firebaseConfig = {
  apiKey: "AIzaSyAHRv6CTf2vp7oNce5sLsjWymhPNaKnWIQ",
  authDomain: "inventoryapp-a4e1c.firebaseapp.com",
  projectId: "inventoryapp-a4e1c",
  storageBucket: "inventoryapp-a4e1c.appspot.com",
  messagingSenderId: "878430312214",
  appId: "1:878430312214:web:1d02aeae3474f156936237",
  measurementId: "G-VEZMJM5XXG"
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const provider = new GoogleAuthProvider();

document.addEventListener("DOMContentLoaded", () => {
  const googleBtn = document.getElementById("google-signin");
  if (googleBtn) {
    googleBtn.addEventListener("click", () => {
      signInWithPopup(auth, provider)
        .then((result) => result.user.getIdToken())
        .then((idToken) => {
          return fetch("/firebase-login", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ idToken }),
          });
        })
        .then((res) => res.json())
        .then((data) => {
          if (data.redirect) {
            window.location.href = data.redirect;
          }
        })
        .catch((error) => {
          console.error("Firebase login failed", error);
          alert("Google login failed!");
        });
    });
  }
});

document.addEventListener('DOMContentLoaded', function() {
    // Mobile menu toggle
    const mobileMenuBtn = document.createElement('button');
    mobileMenuBtn.innerHTML = '<i class="fas fa-bars"></i>';
    mobileMenuBtn.classList.add('mobile-menu-btn');
    document.querySelector('.top-nav').prepend(mobileMenuBtn);
    
    mobileMenuBtn.addEventListener('click', function() {
        document.querySelector('.sidebar').classList.toggle('active');
    });

    // Real-time stock status updates
    const stockCells = document.querySelectorAll('.inventory-table td:nth-child(3)');
    stockCells.forEach(cell => {
        const stock = parseInt(cell.textContent);
        const row = cell.parentElement;
        
        if (stock === 0) {
            row.classList.add('critical-row');
        } else if (stock < 5) {
            row.classList.add('warning-row');
        }
    });

    // Search functionality enhancement
    const searchInput = document.querySelector('.search-container input');
    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase();
        const rows = document.querySelectorAll('.inventory-table tbody tr');
        
        rows.forEach(row => {
            const name = row.cells[0].textContent.toLowerCase();
            const sku = row.cells[1].textContent.toLowerCase();
            const location = row.cells[3].textContent.toLowerCase();
            
            if (name.includes(searchTerm) || sku.includes(searchTerm) || location.includes(searchTerm)) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    });

    // Notification dropdown
    const notificationBtn = document.querySelector('.notifications');
    const notificationDropdown = document.createElement('div');
    notificationDropdown.classList.add('notification-dropdown');
    notificationDropdown.innerHTML = `
        <div class="dropdown-header">
            <h4>Notifications</h4>
            <span class="mark-read">Mark all as read</span>
        </div>
        <div class="notification-list">
            <div class="notification-item">
                <i class="fas fa-exclamation-circle text-danger"></i>
                <div class="notification-content">
                    <p>Product "Milk" is out of stock</p>
                    <small>2 hours ago</small>
                </div>
            </div>
            <div class="notification-item">
                <i class="fas fa-exclamation-triangle text-warning"></i>
                <div class="notification-content">
                    <p>Product "Banana" is low on stock</p>
                    <small>5 hours ago</small>
                </div>
            </div>
            <div class="notification-item">
                <i class="fas fa-info-circle text-primary"></i>
                <div class="notification-content">
                    <p>New inventory report available</p>
                    <small>1 day ago</small>
                </div>
            </div>
        </div>
    `;
    
    notificationBtn.appendChild(notificationDropdown);
    
    notificationBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        notificationDropdown.classList.toggle('show');
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', function() {
        notificationDropdown.classList.remove('show');
    });

    // Dynamic status updates
    function updateStockStatus() {
        fetch('/api/inventory')
            .then(response => response.json())
            .then(data => {
                // Update the table with new data
                console.log('Inventory data updated', data);
            })
            .catch(error => console.error('Error fetching inventory:', error));
    }

    // Update every 5 minutes
    setInterval(updateStockStatus, 300000);
    
    // Initial update
    updateStockStatus();
});

const socket = io.connect(`wss://${window.location.host}`);

socket.on('stock_alert', (data) => {
    const alertHTML = `
        <div class="toast alert-${data.count > 3 ? 'danger' : 'warning'}">
            ${data.count} items need restocking!
            <button class="btn-sm">View</button>
        </div>
    `;
    document.querySelector('.toast-container').insertAdjacentHTML('beforeend', alertHTML);
    
    // Update dashboard counters without refresh
    document.querySelector('.out-of-stock p').textContent = 
        parseInt(document.querySelector('.out-of-stock p').textContent) + data.count;
});

document.querySelectorAll('[data-sort]').forEach(header => {
    header.addEventListener('click', async () => {
        const sortBy = header.dataset.sort;
        const isAsc = !header.classList.contains('asc');
        
        // Clear other sort headers
        document.querySelectorAll('[data-sort]').forEach(h => 
            h.classList.remove('asc', 'desc'));
        
        // Set current sort direction
        header.classList.add(isAsc ? 'asc' : 'desc');
        
        // Fetch sorted data
        const response = await fetch(header.closest('table').dataset.sortUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sort: sortBy, order: isAsc ? 'asc' : 'desc' })
        });
        
        // Update table body
        document.querySelector('tbody').innerHTML = await response.text();
    });
});