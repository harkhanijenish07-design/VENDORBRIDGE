<<<<<<< HEAD
# VendorBridge 🚀

**VendorBridge** is a complete procurement and vendor management system built to simplify how organizations interact with suppliers. It connects internal procurement teams with external vendors through a smooth, automated workflow—from raising RFQs to generating purchase orders and invoices.

This repository includes two main parts:

* **`vendorbridge/`** → The production-ready ERP module built for **Odoo 17**
* **`vendorbridge_mock/`** → A FastAPI-based demo app that showcases the full workflow with a simple UI and sample data

---

## 📁 Project Structure

```
├── vendorbridge/                # Odoo 17 ERP module
│   ├── models/                  # Business logic (RFQ, Bid, PO, Invoice, etc.)
│   ├── views/                   # Backend UI (forms, lists, menus)
│   ├── security/                # Roles and access rules
│   ├── data/                    # Email templates and sequences
│   └── static/                  # Portal assets
│
├── vendorbridge_mock/           # FastAPI demo application
│   ├── templates/               # HTML pages (Jinja2)
│   ├── static/                  # CSS, JS, images
│   ├── main.py                  # App entry point and routes
│   ├── models.py                # Database schema (SQLite)
│   ├── requirements.txt         # Dependencies
│   └── vendorbridge_mock.db     # Preloaded demo database
│
└── README.md
```

---

## ✨ Features

VendorBridge focuses on making procurement simple, transparent, and automated:

* **Vendor Registration & Approval**
  Vendors can sign up through a portal. Procurement teams review and approve them based on details like GSTIN and location.

* **RFQ Creation (3-Step Process)**
  Easily create RFQs with item details, attachments, and selected vendors.

* **Vendor Bidding Portal**
  Vendors can submit quotations with pricing, taxes, discounts, and delivery timelines.

* **Quotation Comparison**
  Compare multiple bids side-by-side with automatic highlighting of the best price.

* **Approval Workflow**
  Multi-level approval system based on purchase value thresholds.

* **Automatic PO & Invoice Generation**
  Approved RFQs generate Purchase Orders, which in turn create draft invoices with correct tax handling.

* **Analytics Dashboard**
  Visual insights like monthly spend, category breakdown, and vendor performance.

* **Audit Logs**
  Every action is tracked for full transparency.

---

## 🚀 Running the Demo (FastAPI App)

### Prerequisites

* Python **3.10 or higher**

### Setup

```bash
cd vendorbridge_mock
```

Create and activate a virtual environment (if not already done):

```bash
python -m venv venv
```

Activate it:

* **Windows**

```bash
venv\Scripts\activate
```

* **macOS/Linux**

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

### Start the Server

```bash
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Open your browser and go to:

```
http://127.0.0.1:8000
```

---

### Demo Login

* **Username:** [officer@vendorbridge.com](mailto:officer@vendorbridge.com)
* **Password:** password

---

## 🛠️ Installing the Odoo Module

To use VendorBridge inside Odoo 17:

1. Copy the `vendorbridge` folder into your Odoo `custom_addons` directory
2. Add the path to `addons_path` in your `odoo.conf`
3. Restart the Odoo server
4. Enable **Developer Mode**
5. Go to **Apps → Update Apps List**
6. Search for **VendorBridge** and install it

---

## 👥 User Roles

* **Vendors (Portal Users)**
  Can view RFQs and submit bids

* **Procurement Officers**
  Create RFQs, manage vendors, and compare bids

* **Managers / Approvers**
  Review and approve procurement requests

* **Administrators**
  Full system access and configuration control

---

## 📄 License

This project is open-source and available under the **MIT License**.

---

## 💡 Final Note

This project is designed to demonstrate a complete procurement workflow—from vendor onboarding to final invoicing—both as a real ERP module and as an easy-to-run demo app.

Feel free to explore, modify, and build on top of it 🚀
=======
# VENDORBRIDGE
An end-to-end ERP procurement and vendor management system built for Odoo 17, featuring automated RFQ wizards, portal bid submission, side-by-side quotation comparison, dynamic multi-level approvals, tax-compliant invoice auto-generation, and Chart.js analytics dashboard (includes a FastAPI mock application for live testing).
>>>>>>> 9b2ec2ba1a9ae4456b976c3b981480abbe7f3e15
