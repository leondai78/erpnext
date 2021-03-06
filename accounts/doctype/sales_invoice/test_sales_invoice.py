import webnotes
import unittest

class TestSalesInvoice(unittest.TestCase):
	def make(self):
		w = webnotes.bean(webnotes.copy_doclist(test_records[0]))
		w.insert()
		w.submit()
		return w

	def test_outstanding(self):
		w = self.make()
		self.assertEquals(w.doc.outstanding_amount, w.doc.grand_total)
		
	def test_payment(self):
		w = self.make()
		from accounts.doctype.journal_voucher.test_journal_voucher \
			import test_records as jv_test_records
			
		jv = webnotes.bean(webnotes.copy_doclist(jv_test_records[0]))
		jv.doclist[1].against_invoice = w.doc.name
		jv.insert()
		jv.submit()
		
		self.assertEquals(webnotes.conn.get_value("Sales Invoice", w.doc.name, "outstanding_amount"),
			161.8)
	
		jv.cancel()
		self.assertEquals(webnotes.conn.get_value("Sales Invoice", w.doc.name, "outstanding_amount"),
			561.8)
			
	def test_time_log_batch(self):
		tlb = webnotes.bean("Time Log Batch", "_T-Time Log Batch-00001")
		tlb.submit()
		
		si = webnotes.bean(webnotes.copy_doclist(test_records[0]))
		si.doclist[1].time_log_batch = "_T-Time Log Batch-00001"
		si.insert()
		si.submit()
		
		self.assertEquals(webnotes.conn.get_value("Time Log Batch", "_T-Time Log Batch-00001",
		 	"status"), "Billed")

		self.assertEquals(webnotes.conn.get_value("Time Log", "_T-Time Log-00001", "status"), 
			"Billed")

		si.cancel()

		self.assertEquals(webnotes.conn.get_value("Time Log Batch", "_T-Time Log Batch-00001", 
			"status"), "Submitted")

		self.assertEquals(webnotes.conn.get_value("Time Log", "_T-Time Log-00001", "status"), 
			"Batched for Billing")
			
	def test_sales_invoice_gl_entry_without_aii(self):
		webnotes.defaults.set_global_default("auto_inventory_accounting", 0)
		
		si = webnotes.bean(webnotes.copy_doclist(test_records[1]))
		si.insert()
		si.submit()
		
		gl_entries = webnotes.conn.sql("""select account, debit, credit
			from `tabGL Entry` where voucher_type='Sales Invoice' and voucher_no=%s
			order by account asc""", si.doc.name, as_dict=1)
		self.assertTrue(gl_entries)
		
		expected_values = sorted([
			[si.doc.debit_to, 630.0, 0.0],
			[test_records[1][1]["income_account"], 0.0, 500.0],
			[test_records[1][2]["account_head"], 0.0, 80.0],
			[test_records[1][3]["account_head"], 0.0, 50.0],
		])
		
		for i, gle in enumerate(gl_entries):
			self.assertEquals(expected_values[i][0], gle.account)
			self.assertEquals(expected_values[i][1], gle.debit)
			self.assertEquals(expected_values[i][2], gle.credit)
			
		# cancel
		si.cancel()
		
		gle_count = webnotes.conn.sql("""select count(name) from `tabGL Entry` 
			where voucher_type='Sales Invoice' and voucher_no=%s 
			and ifnull(is_cancelled, 'No') = 'Yes'
			order by account asc""", si.doc.name)
		
		self.assertEquals(gle_count[0][0], 8)
		
	def test_sales_invoice_gl_entry_with_aii_delivery_note(self):
		webnotes.conn.sql("delete from `tabStock Ledger Entry`")
		
		webnotes.defaults.set_global_default("auto_inventory_accounting", 1)
		
		self._insert_purchase_receipt()
		dn = self._insert_delivery_note()
		
		si_against_dn = webnotes.copy_doclist(test_records[1])
		si_against_dn[1]["delivery_note"] = dn.doc.name
		si_against_dn[1]["dn_detail"] = dn.doclist[1].name
		si = webnotes.bean(si_against_dn)		
		si.insert()
		
		si.submit()
		
		gl_entries = webnotes.conn.sql("""select account, debit, credit
			from `tabGL Entry` where voucher_type='Sales Invoice' and voucher_no=%s
			order by account asc""", si.doc.name, as_dict=1)
		self.assertTrue(gl_entries)
		
		expected_values = sorted([
			[si.doc.debit_to, 630.0, 0.0],
			[test_records[1][1]["income_account"], 0.0, 500.0],
			[test_records[1][2]["account_head"], 0.0, 80.0],
			[test_records[1][3]["account_head"], 0.0, 50.0],
			["Stock Delivered But Not Billed - _TC", 0.0, 375.0],
			[test_records[1][1]["expense_account"], 375.0, 0.0]
		])
		for i, gle in enumerate(gl_entries):
			self.assertEquals(expected_values[i][0], gle.account)
			self.assertEquals(expected_values[i][1], gle.debit)
			self.assertEquals(expected_values[i][2], gle.credit)
			
		si.cancel()
		gl_entries = webnotes.conn.sql("""select account, debit, credit
			from `tabGL Entry` where voucher_type='Sales Invoice' and voucher_no=%s
			and ifnull(is_cancelled, 'No') = 'No' 
			order by account asc, name asc""", si.doc.name, as_dict=1)
			
		expected_values = sorted([
			[si.doc.debit_to, 630.0, 0.0],
			[si.doc.debit_to, 0.0, 630.0],
			[test_records[1][1]["income_account"], 0.0, 500.0],
			[test_records[1][1]["income_account"], 500.0, 0.0],
			[test_records[1][2]["account_head"], 0.0, 80.0],
			[test_records[1][2]["account_head"], 80.0, 0.0],
			[test_records[1][3]["account_head"], 0.0, 50.0],
			[test_records[1][3]["account_head"], 50.0, 0.0],
			["Stock Delivered But Not Billed - _TC", 0.0, 375.0],
			["Stock Delivered But Not Billed - _TC", 375.0, 0.0],
			[test_records[1][1]["expense_account"], 375.0, 0.0],
			[test_records[1][1]["expense_account"], 0.0, 375.0]
			
		])
		for i, gle in enumerate(gl_entries):
			self.assertEquals(expected_values[i][0], gle.account)
			self.assertEquals(expected_values[i][1], gle.debit)
			self.assertEquals(expected_values[i][2], gle.credit)
			
		webnotes.defaults.set_global_default("auto_inventory_accounting", 0)
		
	def test_pos_gl_entry_with_aii(self):
		webnotes.conn.sql("delete from `tabStock Ledger Entry`")
		webnotes.defaults.set_global_default("auto_inventory_accounting", 1)
		
		self._insert_purchase_receipt()
		self._insert_pos_settings()
		
		pos = webnotes.copy_doclist(test_records[1])
		pos[0]["is_pos"] = 1
		pos[0]["update_stock"] = 1
		pos[0]["posting_time"] = "12:05"
		pos[0]["cash_bank_account"] = "_Test Account Bank Account - _TC"
		pos[0]["paid_amount"] = 600.0

		si = webnotes.bean(pos)
		si.insert()
		si.submit()
		
		# check stock ledger entries
		sle = webnotes.conn.sql("""select * from `tabStock Ledger Entry` 
			where voucher_type = 'Sales Invoice' and voucher_no = %s""", si.doc.name, as_dict=1)[0]
		self.assertTrue(sle)
		self.assertEquals([sle.item_code, sle.warehouse, sle.actual_qty], 
			["_Test Item", "_Test Warehouse", -5.0])
		
		# check gl entries
		stock_in_hand_account = webnotes.conn.get_value("Company", "_Test Company", 
			"stock_in_hand_account")
		
		gl_entries = webnotes.conn.sql("""select account, debit, credit
			from `tabGL Entry` where voucher_type='Sales Invoice' and voucher_no=%s
			order by account asc, debit asc""", si.doc.name, as_dict=1)
		self.assertTrue(gl_entries)
		
		expected_gl_entries = sorted([
			[si.doc.debit_to, 630.0, 0.0],
			[test_records[1][1]["income_account"], 0.0, 500.0],
			[test_records[1][2]["account_head"], 0.0, 80.0],
			[test_records[1][3]["account_head"], 0.0, 50.0],
			[stock_in_hand_account, 0.0, 375.0],
			[test_records[1][1]["expense_account"], 375.0, 0.0],
			[si.doc.debit_to, 0.0, 600.0],
			["_Test Account Bank Account - _TC", 600.0, 0.0]
		])
		for i, gle in enumerate(gl_entries):
			self.assertEquals(expected_gl_entries[i][0], gle.account)
			self.assertEquals(expected_gl_entries[i][1], gle.debit)
			self.assertEquals(expected_gl_entries[i][2], gle.credit)
		
		# cancel
		si.cancel()
		gl_count = webnotes.conn.sql("""select count(name)
			from `tabGL Entry` where voucher_type='Sales Invoice' and voucher_no=%s
			and ifnull(is_cancelled, 'No') = 'Yes' 
			order by account asc, name asc""", si.doc.name)
		
		self.assertEquals(gl_count[0][0], 16)
			
		webnotes.defaults.set_global_default("auto_inventory_accounting", 0)
		
	def test_sales_invoice_gl_entry_with_aii_no_item_code(self):		
		webnotes.defaults.set_global_default("auto_inventory_accounting", 1)
				
		si_copy = webnotes.copy_doclist(test_records[1])
		si_copy[1]["item_code"] = None
		si = webnotes.bean(si_copy)		
		si.insert()
		si.submit()
		
		gl_entries = webnotes.conn.sql("""select account, debit, credit
			from `tabGL Entry` where voucher_type='Sales Invoice' and voucher_no=%s
			order by account asc""", si.doc.name, as_dict=1)
		self.assertTrue(gl_entries)
		
		expected_values = sorted([
			[si.doc.debit_to, 630.0, 0.0],
			[test_records[1][1]["income_account"], 0.0, 500.0],
			[test_records[1][2]["account_head"], 0.0, 80.0],
			[test_records[1][3]["account_head"], 0.0, 50.0],
		])
		for i, gle in enumerate(gl_entries):
			self.assertEquals(expected_values[i][0], gle.account)
			self.assertEquals(expected_values[i][1], gle.debit)
			self.assertEquals(expected_values[i][2], gle.credit)
				
		webnotes.defaults.set_global_default("auto_inventory_accounting", 0)
	
	def test_sales_invoice_gl_entry_with_aii_non_stock_item(self):		
		webnotes.defaults.set_global_default("auto_inventory_accounting", 1)
		
		si_copy = webnotes.copy_doclist(test_records[1])
		si_copy[1]["item_code"] = "_Test Non Stock Item"
		si = webnotes.bean(si_copy)
		si.insert()
		si.submit()
		
		gl_entries = webnotes.conn.sql("""select account, debit, credit
			from `tabGL Entry` where voucher_type='Sales Invoice' and voucher_no=%s
			order by account asc""", si.doc.name, as_dict=1)
		self.assertTrue(gl_entries)
		
		expected_values = sorted([
			[si.doc.debit_to, 630.0, 0.0],
			[test_records[1][1]["income_account"], 0.0, 500.0],
			[test_records[1][2]["account_head"], 0.0, 80.0],
			[test_records[1][3]["account_head"], 0.0, 50.0],
		])
		for i, gle in enumerate(gl_entries):
			self.assertEquals(expected_values[i][0], gle.account)
			self.assertEquals(expected_values[i][1], gle.debit)
			self.assertEquals(expected_values[i][2], gle.credit)
				
		webnotes.defaults.set_global_default("auto_inventory_accounting", 0)
		
		
		
	def _insert_purchase_receipt(self):
		from stock.doctype.purchase_receipt.test_purchase_receipt import test_records \
			as pr_test_records
		pr = webnotes.bean(copy=pr_test_records[0])
		pr.run_method("calculate_taxes_and_totals")
		pr.insert()
		pr.submit()
		
	def _insert_delivery_note(self):
		from stock.doctype.delivery_note.test_delivery_note import test_records \
			as dn_test_records
		dn = webnotes.bean(copy=dn_test_records[0])
		dn.insert()
		dn.submit()
		return dn
		
	def _insert_pos_settings(self):
		ps = webnotes.bean([
			{
				"cash_bank_account": "_Test Account Bank Account - _TC", 
				"company": "_Test Company", 
				"conversion_rate": 1.0, 
				"cost_center": "_Test Cost Center - _TC", 
				"currency": "INR", 
				"doctype": "POS Setting", 
				"income_account": "_Test Account Bank Account - _TC", 
				"price_list_name": "_Test Price List", 
				"territory": "_Test Territory", 
				"warehouse": "_Test Warehouse"
			}
		])
		ps.insert()
		
test_dependencies = ["Journal Voucher", "POS Setting"]

test_records = [
	[
		{
			"naming_series": "_T-Sales Invoice-",
			"company": "_Test Company", 
			"conversion_rate": 1.0, 
			"currency": "INR", 
			"debit_to": "_Test Customer - _TC",
			"customer": "_Test Customer",
			"customer_name": "_Test Customer",
			"doctype": "Sales Invoice", 
			"due_date": "2013-01-23", 
			"fiscal_year": "_Test Fiscal Year 2013", 
			"grand_total": 561.8, 
			"grand_total_export": 561.8, 
			"net_total": 500.0, 
			"plc_conversion_rate": 1.0, 
			"posting_date": "2013-01-23", 
			"price_list_currency": "INR", 
			"price_list_name": "_Test Price List", 
			"territory": "_Test Territory"
		}, 
		{
			"amount": 500.0, 
			"basic_rate": 500.0, 
			"description": "138-CMS Shoe", 
			"doctype": "Sales Invoice Item", 
			"export_amount": 500.0, 
			"export_rate": 500.0, 
			"income_account": "Sales - _TC",
			"cost_center": "_Test Cost Center - _TC",
			"item_name": "138-CMS Shoe", 
			"parentfield": "entries",
			"qty": 1.0
		}, 
		{
			"account_head": "_Test Account VAT - _TC", 
			"charge_type": "On Net Total", 
			"description": "VAT", 
			"doctype": "Sales Taxes and Charges", 
			"parentfield": "other_charges",
			"tax_amount": 30.0,
		}, 
		{
			"account_head": "_Test Account Service Tax - _TC", 
			"charge_type": "On Net Total", 
			"description": "Service Tax", 
			"doctype": "Sales Taxes and Charges", 
			"parentfield": "other_charges",
			"tax_amount": 31.8,
		},
		{
			"parentfield": "sales_team",
			"doctype": "Sales Team",
			"sales_person": "_Test Sales Person 1",
			"allocated_percentage": 65.5,
		},
		{
			"parentfield": "sales_team",
			"doctype": "Sales Team",
			"sales_person": "_Test Sales Person 2",
			"allocated_percentage": 34.5,
		},
	],
	[
		{
			"naming_series": "_T-Sales Invoice-",
			"company": "_Test Company", 
			"conversion_rate": 1.0, 
			"currency": "INR", 
			"debit_to": "_Test Customer - _TC",
			"customer": "_Test Customer",
			"customer_name": "_Test Customer",
			"doctype": "Sales Invoice", 
			"due_date": "2013-01-23", 
			"fiscal_year": "_Test Fiscal Year 2013", 
			"grand_total": 630.0, 
			"grand_total_export": 630.0, 
			"net_total": 500.0, 
			"plc_conversion_rate": 1.0, 
			"posting_date": "2013-03-07", 
			"price_list_currency": "INR", 
			"price_list_name": "_Test Price List", 
			"territory": "_Test Territory"
		}, 
		{
			"item_code": "_Test Item",
			"item_name": "_Test Item", 
			"description": "_Test Item", 
			"doctype": "Sales Invoice Item", 
			"parentfield": "entries",
			"qty": 5.0,
			"basic_rate": 500.0,
			"amount": 500.0, 
			"export_rate": 500.0, 
			"export_amount": 500.0, 
			"income_account": "Sales - _TC",
			"expense_account": "_Test Account Cost for Goods Sold - _TC",
			"cost_center": "_Test Cost Center - _TC",
		}, 
		{
			"account_head": "_Test Account VAT - _TC", 
			"charge_type": "On Net Total", 
			"description": "VAT", 
			"doctype": "Sales Taxes and Charges", 
			"parentfield": "other_charges",
			"tax_amount": 80.0,
		}, 
		{
			"account_head": "_Test Account Service Tax - _TC", 
			"charge_type": "On Net Total", 
			"description": "Service Tax", 
			"doctype": "Sales Taxes and Charges", 
			"parentfield": "other_charges",
			"tax_amount": 50.0,
		}
	],
]