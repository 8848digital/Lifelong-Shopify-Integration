# Copyright (c) 2025, 8848digital and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
from lifelong_shopify_integration.lifelong_shopify_integration.utils.doc_events.utility_functions import sync_between_servers_with_name


class SyncStatusLog(Document):
	pass


def insert_after(self, method=None):
    sync_between_servers_with_name(self.name)

