import requests
import frappe
import json

def site_details():
    docSettings = frappe.get_doc('Shopify Product Sync')
   
    shopify_token = docSettings.get_password('shopify_token')
    shopify_url = docSettings.shopify_url
    price_list = docSettings.price_list
    
    return shopify_token, shopify_url, price_list


a= site_details()

def get_shopify_headers():
    return {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": a[0]
    }

        
def find_product_by_sku(sku):
    url = f"{a[1]}/admin/api/2024-01/graphql.json"
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


get_all = frappe.db.get_all('Item', {'custom_sync_to_shopify':1}, ['*'])

for i in get_all:
    existing_price = frappe.get_all(
        "Item Price",
        filters={
            "item_code": i.item_code,
            "price_list":'EBI Lucknow',
        },
        fields=["name", "price_list_rate", "valid_from", "modified"],
        order_by="valid_from desc, modified desc",
        limit=1
    )
    if not existing_price:
        shopify_product = find_product_by_sku(i.item_code)
        variant = {}
        variant["price"] = float(i.mrp) * 0.8
        
        product = {
            "product": {
                "variant": variant
            }
        }
        if shopify_product:
            product_id = shopify_product["id"]
            update_url = f"{a[1]}/admin/api/2024-01/products/{product_id.split('/')[-1]}.json"
            
            response = requests.put(update_url, headers=get_shopify_headers(), data=json.dumps(product))
