from lifelong_shopify_integration.lifelong_shopify_integration.customizations.doc_events.utility_functions import transfer_entry

def insert_after(self, method=None):
    if self.dt == 'Item':
        transfer_entry(self, method)

def update(doc, method=None):
    if doc.dt == 'Item':
        transfer_entry(doc, method)

def delete(doc, method=None):
    if doc.dt == 'Item':
        transfer_entry(doc, method)

def after_rename(doc, old, method=None):
    print(f"Custom Field renamed from {old} to {doc.name}")
    transfer_entry(doc, method='Update')