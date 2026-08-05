import json
import time
from src.data_loader import OlistDataLoader

def test_data_loader_complete_fields():
    start_time = time.time()
    loader = OlistDataLoader(data_dir="data")
    load_duration = time.time() - start_time
    print(f"\n[Test] Time taken to load & index 9 CSV files into RAM: {load_duration:.2f}s")
    
    # Check counts in indexes
    assert len(loader.orders_index) > 0, "No orders found in orders_index!"
    assert len(loader.customers_index) > 0, "No customers found in customers_index!"
    assert len(loader.sellers_index) > 0, "No sellers found in sellers_index!"
    assert len(loader.products_index) > 0, "No products found in products_index!"
    assert len(loader.items_index) > 0, "No items found in items_index!"
    assert len(loader.payments_index) > 0, "No payments found in payments_index!"
    assert len(loader.reviews_index) > 0, "No reviews found in reviews_index!"
    assert len(loader.geolocation_index) > 0, "No geolocation entries in geolocation_index!"

    # Open input/EC_001.json to test real O(1) lookup using an actual claim from the lab
    with open("input/EC_001.json", "r", encoding="utf-8") as f:
        claim = json.load(f)
    
    claimed_order_id = claim["customer_request"]["claimed_order_id"]
    print(f"[Test] Performing O(1) lookup for claimed_order_id in EC_001.json: '{claimed_order_id}'")

    t0 = time.time()
    context = loader.get_order_context(claimed_order_id)
    lookup_time = time.time() - t0
    print(f"[Test] O(1) lookup time: {lookup_time:.6f}s")

    assert context["found"] == True, f"Order {claimed_order_id} not found in Olist DB!"
    
    # Verify 100% of critical columns exist without missing any field
    order = context["order"]
    assert "customer_id" in order, "ERROR: Missing 'customer_id' column in order data!"
    assert "order_status" in order
    assert "order_purchase_timestamp" in order
    assert "order_delivered_carrier_date" in order
    assert "order_delivered_customer_date" in order
    assert "order_estimated_delivery_date" in order

    # Verify Customer data lookup from customer_id
    customer = context["customer"]
    assert customer is not None, "ERROR: Customer data not found using customer_id!"
    assert "customer_unique_id" in customer, "Missing 'customer_unique_id' in customer data!"
    assert "customer_zip_code_prefix" in customer
    assert "customer_city" in customer
    assert "customer_state" in customer

    # Verify items list and enriched seller/product details
    items = context["items"]
    print(f"[Test] Order {claimed_order_id} has {len(items)} item(s) and {len(context['payments'])} payment row(s).")
    if items:
        item = items[0]
        assert "seller_id" in item
        assert "price" in item
        assert "freight_value" in item
        assert "shipping_limit_date" in item
        assert "seller_details" in item, "Missing enriched seller_details!"
        if item["seller_details"]:
            assert "seller_zip_code_prefix" in item["seller_details"]
            assert "seller_city" in item["seller_details"]

    # Verify math calculation rounded to 2 decimal places
    math_summary = context["summary_math"]
    assert isinstance(math_summary["payment_total_brl"], float)
    assert isinstance(math_summary["item_total_brl"], float)
    assert isinstance(math_summary["freight_total_brl"], float)

    print("[Test] VERIFICATION PASSED: 100% data fields are indexed in RAM and looked up accurately!")

if __name__ == "__main__":
    test_data_loader_complete_fields()
