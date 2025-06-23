import frappe
import requests
import json
from lifelong_shopify_integration.lifelong_shopify_integration.customizations.item import push_item_to_shopify

def site_details():
    docSettings = frappe.get_single("Shopify Product Sync")
    target_key = docSettings.get_password('secret_key')
    target_url = docSettings.target_url
    target_user = docSettings.target_user
    price_list = docSettings.price_list

    return target_url, target_user, target_key, price_list

@frappe.whitelist()
def sync_bsr():
    get_sync_item = frappe.db.get_all('Item', {"custom_sync_to_shopify": 1}, ['name'])

    if not get_sync_item:
        return

    target_url, target_user, target_token, price_list = site_details()

    session = requests.Session()

    login_url = f"{target_url}/api/method/login"

    login_payload = {
        "usr": target_user,
        "pwd": target_token
    }

    try:
        login_response = session.post(login_url, data=login_payload)

        if login_response.status_code != 200:
            return
        
        if not price_list:
            frappe.log_error(
                title="Price List not Set",
                message=f"Price List not Set"
            )
            return

        
        for item in get_sync_item:
            get_doc = frappe.get_doc('Item', item['name'])
            if get_doc.customer_items:
                ref_codes = []
                for code in get_doc.customer_items:
                    bsin_value = code.ref_code
                    if bsin_value not in ref_codes:
                        ref_codes.append(bsin_value)

                        bsr_url = f"{target_url}/api/resource/BSR?limit_page_length=1000&fields=[\"*\"]&order_by=date desc"

                        bsr_response = session.get(bsr_url)

                        if bsr_response.status_code == 200:
                            bsr_parents = bsr_response.json().get("data", [])

                            for bsr in bsr_parents:
                                bsr_name = bsr["name"]

                                bsr_detail_url = f"{target_url}/api/resource/BSR/{bsr_name}"
                                detail_response = session.get(bsr_detail_url)

                                if detail_response.status_code == 200:
                                    bsr_doc = detail_response.json().get("data", {})
                                    child_rows = bsr_doc.get("bsr_items", [])

                                    for row in child_rows:
                                        if row.get("request_asin") == bsin_value:
                                            existing_price = frappe.db.exists("Item Price", {
                                                "item_code": get_doc.item_code,
                                                "price_list": price_list,
                                                "valid_from": bsr["date"]
                                            })

                                            if not existing_price:
                                                price_doc = frappe.new_doc("Item Price")
                                                price_doc.item_code = get_doc.item_code
                                                price_doc.price_list = price_list
                                                price_doc.price_list_rate = row.get("rrp_value")
                                                price_doc.currency = "INR"
                                                price_doc.valid_from = bsr["date"]
                                                price_doc.save()
                                                frappe.db.commit()
                                                push_item_to_shopify(get_doc.item_code, "on_update")

                                            break 

                                else:
                                    frappe.log_error(
                                        title="BSR Fetch Failed",
                                        message=f"Failed to fetch BSR {bsr_name}: {detail_response.status_code} - {detail_response.text}"
                                    )                       

                        else:
                            frappe.log_error(
                                title="BSR Parent List Fetch Failed",
                                message=f"Failed to fetch BSR parent list: {bsr_response.status_code} - {bsr_response.text}"
                            )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "sync_bsr: Error during API call")
