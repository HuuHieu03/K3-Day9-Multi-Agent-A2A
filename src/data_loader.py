import os
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np

class OlistDataLoader:
    """
    DataLoader chịu trách nhiệm tải 9 file CSV từ Olist Dataset vào bộ nhớ RAM
    và tạo các cấu trúc chỉ mục (Index / Dictionary) theo khóa (order_id, customer_id, seller_id,...)
    nhằm đảm bảo thời gian tra cứu O(1) và tuyệt đối KHÔNG bỏ sót bất kỳ trường thông tin nào.
    """
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        
        # Chỉ mục 1-1 (1 Key -> 1 Dict giữ 100% các cột)
        self.orders_index: Dict[str, Dict[str, Any]] = {}
        self.customers_index: Dict[str, Dict[str, Any]] = {}
        self.sellers_index: Dict[str, Dict[str, Any]] = {}
        self.products_index: Dict[str, Dict[str, Any]] = {}
        self.category_translation_index: Dict[str, str] = {}
        self.geolocation_index: Dict[int, Dict[str, Any]] = {}

        # Chỉ mục 1-Nhiều (1 Key -> List[Dict] giữ 100% các dòng & cột)
        self.items_index: Dict[str, List[Dict[str, Any]]] = {}
        self.payments_index: Dict[str, List[Dict[str, Any]]] = {}
        self.reviews_index: Dict[str, List[Dict[str, Any]]] = {}

        # Tiến hành nạp và index dữ liệu khi khởi tạo
        self.load_and_index_all()

    def _clean_df_to_records(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Chuyển đổi DataFrame thành danh sách từ điển (List of Dictionaries),
        thay thế giá trị NaN/NaT bằng None để dễ sử dụng và chuẩn hóa JSON.
        Đảm bảo 100% các cột đều được giữ nguyên tên và giá trị.
        """
        df_clean = df.astype(object).where(pd.notnull(df), None)
        return df_clean.to_dict(orient="records")

    def load_and_index_all(self):
        print(f"[OlistDataLoader] Starting loading and indexing from directory '{self.data_dir}'...")

        # 1. Tải bảng Orders (olist_orders_dataset.csv)
        orders_path = os.path.join(self.data_dir, "olist_orders_dataset.csv")
        if os.path.exists(orders_path):
            df_orders = pd.read_csv(orders_path)
            for row in self._clean_df_to_records(df_orders):
                self.orders_index[row["order_id"]] = row

        # 2. Tải bảng Customers (olist_customers_dataset.csv)
        customers_path = os.path.join(self.data_dir, "olist_customers_dataset.csv")
        if os.path.exists(customers_path):
            df_customers = pd.read_csv(customers_path)
            for row in self._clean_df_to_records(df_customers):
                self.customers_index[row["customer_id"]] = row

        # 3. Tải bảng Sellers (olist_sellers_dataset.csv)
        sellers_path = os.path.join(self.data_dir, "olist_sellers_dataset.csv")
        if os.path.exists(sellers_path):
            df_sellers = pd.read_csv(sellers_path)
            for row in self._clean_df_to_records(df_sellers):
                self.sellers_index[row["seller_id"]] = row

        # 4. Tải bảng Products (olist_products_dataset.csv)
        products_path = os.path.join(self.data_dir, "olist_products_dataset.csv")
        if os.path.exists(products_path):
            df_products = pd.read_csv(products_path)
            for row in self._clean_df_to_records(df_products):
                self.products_index[row["product_id"]] = row

        # 5. Tải bảng Product Category Translation
        translation_path = os.path.join(self.data_dir, "product_category_name_translation.csv")
        if os.path.exists(translation_path):
            df_trans = pd.read_csv(translation_path)
            for _, row in df_trans.iterrows():
                self.category_translation_index[row["product_category_name"]] = row["product_category_name_english"]

        # 6. Tải bảng Geolocation (olist_geolocation_dataset.csv)
        # Hướng dẫn bài lab: "Các cột *_zip_code_prefix có thể nối với geolocation_zip_code_prefix sau khi gộp geolocation theo zip code."
        geo_path = os.path.join(self.data_dir, "olist_geolocation_dataset.csv")
        if os.path.exists(geo_path):
            df_geo = pd.read_csv(geo_path)
            # Gộp theo geolocation_zip_code_prefix, lấy bản ghi đầu tiên đại diện cho từng zip code để không mất trường nào
            df_geo_grouped = df_geo.groupby("geolocation_zip_code_prefix", as_index=False).first()
            for row in self._clean_df_to_records(df_geo_grouped):
                self.geolocation_index[int(row["geolocation_zip_code_prefix"])] = row

        # 7. Tải bảng Order Items (olist_order_items_dataset.csv)
        items_path = os.path.join(self.data_dir, "olist_order_items_dataset.csv")
        if os.path.exists(items_path):
            df_items = pd.read_csv(items_path)
            for row in self._clean_df_to_records(df_items):
                oid = row["order_id"]
                if oid not in self.items_index:
                    self.items_index[oid] = []
                self.items_index[oid].append(row)

        # 8. Tải bảng Order Payments (olist_order_payments_dataset.csv)
        payments_path = os.path.join(self.data_dir, "olist_order_payments_dataset.csv")
        if os.path.exists(payments_path):
            df_payments = pd.read_csv(payments_path)
            for row in self._clean_df_to_records(df_payments):
                oid = row["order_id"]
                if oid not in self.payments_index:
                    self.payments_index[oid] = []
                self.payments_index[oid].append(row)

        # 9. Tải bảng Order Reviews (olist_order_reviews_dataset.csv)
        reviews_path = os.path.join(self.data_dir, "olist_order_reviews_dataset.csv")
        if os.path.exists(reviews_path):
            df_reviews = pd.read_csv(reviews_path)
            for row in self._clean_df_to_records(df_reviews):
                oid = row["order_id"]
                if oid not in self.reviews_index:
                    self.reviews_index[oid] = []
                self.reviews_index[oid].append(row)

        print(f"[OlistDataLoader] Finished indexing: {len(self.orders_index):,} orders, {len(self.items_index):,} order_items, {len(self.payments_index):,} payments.")

    def get_order_context(self, order_id: str) -> Dict[str, Any]:
        """
        Tra cứu O(1) và tổng hợp toàn bộ thông tin ngữ cảnh liên quan tới một đơn hàng.
        Đảm bảo trả về ĐẦY ĐỦ 100% các trường dữ liệu của Order, Customer, Items (kèm Seller, Product, Geolocation),
        Payments và Reviews mà không lược bỏ bất kỳ trường nào.
        """
        order_data = self.orders_index.get(order_id)
        if not order_data:
            return {
                "order_id": order_id,
                "found": False,
                "order": None,
                "customer": None,
                "items": [],
                "payments": [],
                "reviews": [],
                "summary_math": {
                    "item_total_brl": 0.0,
                    "freight_total_brl": 0.0,
                    "payment_total_brl": 0.0
                }
            }

        # Tra cứu Customer đầy đủ trường theo customer_id từ bảng orders
        customer_data = None
        if order_data.get("customer_id"):
            customer_data = self.customers_index.get(order_data["customer_id"])

        # Tra cứu danh sách Items và bổ sung thông tin Seller, Product cho từng Item
        raw_items = self.items_index.get(order_id, [])
        enriched_items = []
        item_total = 0.0
        freight_total = 0.0

        for item in raw_items:
            item_copy = dict(item)  # Giữ nguyên 100% cột gốc của order_items
            item_total += float(item_copy.get("price", 0.0) or 0.0)
            freight_total += float(item_copy.get("freight_value", 0.0) or 0.0)

            # Bổ sung toàn bộ trường của Seller
            seller_id = item_copy.get("seller_id")
            item_copy["seller_details"] = self.sellers_index.get(seller_id) if seller_id else None

            # Bổ sung toàn bộ trường của Product
            product_id = item_copy.get("product_id")
            if product_id and product_id in self.products_index:
                prod_data = dict(self.products_index[product_id])
                cat_name = prod_data.get("product_category_name")
                if cat_name in self.category_translation_index:
                    prod_data["product_category_name_english"] = self.category_translation_index[cat_name]
                item_copy["product_details"] = prod_data
            else:
                item_copy["product_details"] = None

            enriched_items.append(item_copy)

        # Tra cứu danh sách Payments và tính tổng payment
        payments = self.payments_index.get(order_id, [])
        payment_total = sum(float(p.get("payment_value", 0.0) or 0.0) for p in payments)

        # Tra cứu danh sách Reviews
        reviews = self.reviews_index.get(order_id, [])

        return {
            "order_id": order_id,
            "found": True,
            "order": dict(order_data),
            "customer": dict(customer_data) if customer_data else None,
            "items": enriched_items,
            "payments": [dict(p) for p in payments],
            "reviews": [dict(r) for r in reviews],
            "summary_math": {
                "item_total_brl": round(item_total, 2),
                "freight_total_brl": round(freight_total, 2),
                "payment_total_brl": round(payment_total, 2)
            }
        }
