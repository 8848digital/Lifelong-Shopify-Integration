from lifelong_shopify_integration.lifelong_shopify_integration.customizations.item.doc_events.utility_functions import push_item_to_shopify

def insert_after(self, method=None):
    if self.custom_sync_to_shopify == 1:
        push_item_to_shopify(self.item_code, method)

def update(doc, method=None):
    if doc.custom_sync_to_shopify == 1:
        push_item_to_shopify(doc.item_code, method)

def delete(doc, method=None):
    if doc.custom_sync_to_shopify == 1:
        push_item_to_shopify(doc.item_code, method)


