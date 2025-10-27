async function loadProducts(query = '', minPrice = '', maxPrice = '') {
  try {
    let url = `/truck-rewards/products?q=${encodeURIComponent(query)}`;
    if (minPrice) url += `&min_price=${encodeURIComponent(minPrice)}`;
    if (maxPrice) url += `&max_price=${encodeURIComponent(maxPrice)}`;

    const response = await fetch(url);
    const products = await response.json();

    const container = document.getElementById("products");
    container.innerHTML = "";

    if (products.length === 0) {
      container.innerHTML = "<p>No products found matching your criteria.</p>";
      return;
    }

    products.forEach(p => {
      const card = document.createElement("div");
      card.className = "product-card";
      const imageUrl = p.image || 'https://i.ebayimg.com/images/g/placeholder/s-l225.jpg';
      
      const productData = JSON.stringify(p);

      card.innerHTML = `
        <img src="${imageUrl}" alt="${p.title}">
        <div class="title">${p.title}</div>
        <div class="price">$${p.price.toFixed(2)}</div>
        <div class="points">${p.pointsEquivalent} points</div>
        <button class="add-to-cart-btn" data-product='${productData}'>Add to Cart</button>
        <button class="add-to-wishlist-btn" data-product='${productData}'>Add to Wishlist</button>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error("Error loading products:", err);
    container.innerHTML = "<p>Error loading products.</p>";
  }
}

async function addToCart(productData) {
  try {
    const csrfToken = document.querySelector('input[name="csrf_token"]').value;

    const response = await fetch('/truck-rewards/add_to_cart', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': csrfToken 
      },
      body: new URLSearchParams(productData)
    });

    if (response.ok) {
      alert(`'${productData.title}' was added to your cart!`);
      fetchCartCount();
    } else {
      throw new Error('Failed to add item to cart.');
    }
  } catch (err) {
    console.error("Error adding to cart:", err);
    alert("There was an error adding the item to your cart.");
  }
}

async function addToWishlist(productData) {
  try {
    const csrfToken = document.querySelector('input[name="csrf_token"]').value;

    const response = await fetch('/truck-rewards/wishlist/add', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': csrfToken 
      },
      body: new URLSearchParams(productData)
    });

    const result = await response.json();
    alert(result.message);
  } catch (err) {
    console.error("Error adding to wishlist:", err);
    alert("There was an error adding the item to your wishlist.");
  }
}

document.addEventListener('DOMContentLoaded', () => {
  loadProducts();

  const searchForm = document.getElementById('search-form');
  if (searchForm) {
    searchForm.addEventListener('submit', (event) => {
      event.preventDefault();
      const searchInput = document.getElementById('search-input');
      const minPriceInput = document.getElementById('min-price');
      const maxPriceInput = document.getElementById('max-price');
      loadProducts(searchInput.value, minPriceInput.value, maxPriceInput.value);
    });
  }

  document.getElementById('products').addEventListener('click', (event) => {
    if (event.target && event.target.classList.contains('add-to-cart-btn')) {
      const productData = JSON.parse(event.target.dataset.product);
      addToCart(productData);
    }
    if (event.target && event.target.classList.contains('add-to-wishlist-btn')) {
      const productData = JSON.parse(event.target.dataset.product);
      addToWishlist(productData);
    }
  });
});
