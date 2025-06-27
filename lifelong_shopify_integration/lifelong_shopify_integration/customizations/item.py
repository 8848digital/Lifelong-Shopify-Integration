from lifelong_shopify_integration.lifelong_shopify_integration.customizations.doc_events.utility_functions import transfer_entry
import requests
import frappe
import json

def insert_after(self, method=None):
    if self.custom_sync_to_shopify == 1:
        if self.weight_uom == 'KGS':
            self.weight_uom = 'kg'
        # transfer_entry(self, method)
        push_item_to_shopify(self.item_code, method)

def update(doc, method=None):
    if doc.custom_sync_to_shopify == 1:
        if doc.weight_uom == 'KGS':
            doc.weight_uom = 'kg'
        # transfer_entry(doc, method)
        push_item_to_shopify(doc.item_code, method)

def delete(doc, method=None):
    if doc.custom_sync_to_shopify == 1:
        if doc.weight_uom == 'KGS':
            doc.weight_uom = 'kg'
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
    tags_list = ["ERPNext", item_doc.item_group, item_doc.brand, item_doc.sub_catergory]
    if item_doc.sku_classification == 'Head':
        tags_list.append('Bestseller')
        
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
        shopify_product = find_product_by_sku(item_doc.item_code)

        if not shopify_product:
            product, tags_list, variant = set_new_entry(item_doc, variant, product, tags_list)
        else:
            if existing_price:
                variant["price"] = existing_price[0]['price_list_rate']
            elif shopify_product:
                variant["price"] = float(shopify_product['variants']['edges'][0]['node']['price'])

            if variant["price"] <= (0.5 * float(item_doc.mrp)) and item_doc.sku_classification != 'Head':
                tags_list.append("Discount")
            if variant["price"] > (0.7 * float(item_doc.mrp)) and item_doc.sku_classification != 'Head':
                tags_list.append("Sales/Offer")

            product["product"]["variants"] = [variant]

    if item_doc.disabled == 1:
        product["product"]['status'] = 'draft'
    if method == "after_insert":
        product, tags_list = set_new_entry(item_doc, variant, product, tags_list)

    tags_string = ", ".join(tags_list)
    product["product"]['tags'] = tags_string

    return product

def set_new_entry(item_doc, variant, product, tags_list):
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
    if variant["price"] <= (0.5 * float(item_doc.mrp)) and item_doc.sku_classification != 'Head':
        tags_list.append("Discount")
    if variant["price"] > (0.7 * float(item_doc.mrp)) and item_doc.sku_classification != 'Head':
        tags_list.append("Sales/Offer")

    product["product"]['status'] = 'draft'
    product["product"]["variants"] = [variant]

    return product, tags_list, variant

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

def generate_shopify_info_html(item_doc):
    if not item_doc.custom_shopify_information:
        return ""

    html = """
    <table style="border-collapse: collapse; width: 100%; font-family: Arial, sans-serif; font-size: 14px;">
        <thead>
            <tr style="background-color: #f2f2f2;">
                <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Attribute</th>
                <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Value</th>
            </tr>
        </thead>
        <tbody>
    """

    for row in item_doc.custom_shopify_information:
        fields_to_include = [
            ("Brand", row.brand),
            ("Colour", row.colour),
            ("Product Dimensions", row.product_dimensions),
            ("Blade Material", row.blade_material),
            ("Special Feature", row.special_feature),
            ("Capacity", row.capacity),
            ("Control Type", row.control_type),
            ("Item Weight", row.item_weight),
            ("Model Name", row.model_name),
            ("Dishwasher Safe", row.is_dishwasher_safe),
            ("About This Item", row.about_this_item)
        ]
        for i, (label, value) in enumerate(fields_to_include):
            if value:
                row_style = "background-color: #f9f9f9;" if i % 2 else ""
                html += f"""
                <tr style="{row_style}">
                    <td style="border: 1px solid #ddd; padding: 8px;">{label}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{value}</td>
                </tr>
                """

    html += "</tbody></table>"
    return html

def push_item_to_shopify(item_code, method):
    item_doc = frappe.get_doc("Item", item_code)
    product_payload = prepare_shopify_product(item_doc, method)

    shopify_product = find_product_by_sku(item_doc.item_code)

    informations = generate_shopify_info_html(item_doc)


    
    if shopify_product:
        product_id = shopify_product["id"]
        update_url = f"{SHOPIFY_STORE_URL}/admin/api/2024-01/products/{product_id.split('/')[-1]}.json"
        
        response = requests.put(update_url, headers=get_shopify_headers(), data=json.dumps(product_payload))
        
        if response.status_code == 200:
            frappe.msgprint(f"Shopify product UPDATED for {item_code}")
            metafield_url = f"{SHOPIFY_STORE_URL}/admin/api/2024-01/products/{product_id.split('/')[-1]}/metafields.json"
            metafield_update = requests.get(metafield_url, headers=get_shopify_headers())
            if metafield_update.status_code == 200:
                metafield_id = metafield_update.json()["metafields"][0]["id"]
                metafield_update_url = f"{SHOPIFY_STORE_URL}/admin/api/2024-01/metafields/{metafield_id}.json"
                payload = {
                    "metafield": {
                        "id": metafield_id,
                        "value": informations,
                        "type": "multi_line_text_field"
                    }
                }
                response = requests.put(metafield_update_url, headers=get_shopify_headers(), data=json.dumps(payload))

        else:
            frappe.throw(f"Error updating Shopify product: {response.status_code} {response.text}")
    else:
        url = f"{SHOPIFY_STORE_URL}/admin/api/2024-01/products.json"
        response = requests.post(url, headers=get_shopify_headers(), data=json.dumps(product_payload))
        
        if response.status_code == 201:
            frappe.msgprint(f"Shopify product created for {item_code}")
            product_data = response.json()["product"]
            product_id = product_data["id"]
            metafield = f"{SHOPIFY_STORE_URL}/admin/api/2024-01/products/{product_id}/metafields.json"
            meta_payload = {
                "metafield": {
                    "namespace": "custom",
                    "key": "specifications",
                    "value": informations,
                    "type": "multi_line_text_field"
                }
            }
            metafield_creation = requests.post(metafield, headers=get_shopify_headers(), data=json.dumps(meta_payload))

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
                  price
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
