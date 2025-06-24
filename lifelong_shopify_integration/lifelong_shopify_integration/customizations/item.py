from lifelong_shopify_integration.lifelong_shopify_integration.customizations.doc_events.utility_functions import transfer_entry
import requests
import frappe
import json

def insert_after(self, method=None):
    if self.custom_sync_to_shopify == 1:
        # transfer_entry(self, method)
        push_item_to_shopify(self.item_code, method)

def update(doc, method=None):
    if doc.custom_sync_to_shopify == 1:
        # transfer_entry(doc, method)
        push_item_to_shopify(doc.item_code, method)

def delete(doc, method=None):
    if doc.custom_sync_to_shopify == 1:
        # transfer_entry(doc, method)
        push_item_to_shopify(doc.item_code, method)


def site_details():
    shopify_records = frappe.get_doc('Shopify Product Sync')
    docSettings = frappe.get_single("Shopify Product Sync")
    shopify_token = docSettings.get_password('shopify_token')
    shopify_url = shopify_records.shopify_url
    price_list = docSettings.price_list
    
    return shopify_token, shopify_url, price_list


SHOPIFY_ACCESS_TOKEN, SHOPIFY_STORE_URL, price_list= site_details()


def get_shopify_headers():
    return {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN
    }

def prepare_shopify_product(item_doc, method):
    variant = {
        "title": item_doc.item_name,
        "compare_at_price":str(item_doc.mrp or 0),
        "taxable": False,
        "barcode": get_barcode(item_doc.item_code),
        "fulfillment_service": "manual",
        "grams": 0,
        "inventory_management": "shopify",
        "requires_shipping": True,
        "sku": item_doc.item_code,
        "weight": item_doc.weight_per_unit,
        "weight_unit": item_doc.weight_uom,
    }

    product = {
        "product": {
            "title": item_doc.item_name,
            "body_html": item_doc.description or "",
            "vendor": item_doc.brand or "",
            "product_type": frappe.db.get_value('Item Group', item_doc.item_group, 'custom_shopify_item_group_abbreviation') or item_doc.item_group
        }
    }
    tags_list = ["ERPNext", item_doc.item_group, item_doc.brand]
    if item_doc.sku_classification == 'Head':
        product["product"]['tags'] = 'Bestseller'
        
    if method == "on_update":
        existing_price = frappe.get_all(
            "Item Price",
            filters={
                "item_code": item_doc.item_code,
                "price_list": price_list,
            },
            fields=["name", "price_list_rate", "valid_from", "modified"],
            order_by="valid_from desc, modified desc",
            limit=1
        )
        if existing_price:
            variant["price"] = existing_price[0]['price_list_rate']
        if variant["price"] <= (0.5 * item_doc.mrp):
            tags_list.append("Discount")
        if variant["price"] > (0.7 * item_doc.mrp):
            tags_list.append("Sales/Offer")

        product["product"]["variants"] = [variant]

    if item_doc.disabled == 1:
        product["product"]['status'] = 'draft'
    else:
        existing_price = frappe.get_all(
            "Item Price",
            filters={
                "item_code": item_doc.item_code,
                "price_list": price_list,
            },
            fields=["name", "price_list_rate", "valid_from", "modified"],
            order_by="valid_from desc, modified desc",
            limit=1
        )
        if existing_price:
            variant["price"] = existing_price[0]['price_list_rate']
        else:
            variant["price"] = 100
        if variant["price"] <= (0.5 * item_doc.mrp):
            tags_list.append("Discount")
        if variant["price"] > (0.7 * item_doc.mrp):
            tags_list.append("Sales/Offer")

        product["product"]['status'] = 'draft'
        product["product"]["variants"] = [variant]

    tags_string = ", ".join(tags_list)
    product["product"]['tags'] = tags_string

    return product

def get_stock_qty(item_code):
    stock = frappe.db.get_value("Bin", {"item_code": item_code}, "actual_qty")
    return stock or 0

def get_barcode(item_code):
    result = frappe.get_all(
        "Item Barcode",
        filters={"parent": item_code},
        fields=["barcode"],
        limit=1
    )
    if result:
        return result[0]["barcode"]
    return ""

def push_item_to_shopify(item_code, method):
    item_doc = frappe.get_doc("Item", item_code)
    product_payload = prepare_shopify_product(item_doc, method)

    shopify_product = find_product_by_sku(item_doc.item_code)

    
    if shopify_product:
        product_id = shopify_product["id"]
        update_url = f"{SHOPIFY_STORE_URL}/admin/api/2024-01/products/{product_id.split('/')[-1]}.json"
        
        response = requests.put(update_url, headers=get_shopify_headers(), data=json.dumps(product_payload))
        
        if response.status_code == 200:
            frappe.msgprint(f"Shopify product UPDATED for {item_code}")
        else:
            frappe.throw(f"Error updating Shopify product: {response.status_code} {response.text}")
    else:
        url = f"{SHOPIFY_STORE_URL}/admin/api/2024-01/products.json"
        response = requests.post(url, headers=get_shopify_headers(), data=json.dumps(product_payload))
        
        if response.status_code == 201:
            frappe.msgprint(f"Shopify product created for {item_code}")
        else:
            frappe.throw(f"Error pushing to Shopify: {response.status_code} {response.text}")


def find_product_by_sku(sku):
    url = f"{SHOPIFY_STORE_URL}/admin/api/2024-01/graphql.json"
    query = """
    query {
      products(first: 1, query: "sku:%s") {
        edges {
          node {
            id
            title
            variants(first: 5) {
              edges {
                node {
                  id
                  sku
                  inventoryQuantity
                }
              }
            }
          }
        }
      }
    }
    """ % sku
    
    response = requests.post(url, headers=get_shopify_headers(), json={"query": query})
    data = response.json()
    
    products = data.get("data", {}).get("products", {}).get("edges", [])
    if products:
        return products[0]["node"]
    return None
