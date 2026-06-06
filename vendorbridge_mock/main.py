from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import datetime
import hashlib
import json
import models
from models import get_db

app = FastAPI(title="VendorBridge Mock App")

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Mock session state for demo (simulating logged in user)
# Default is None to force redirecting to login page first.
current_user_id = None

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def get_current_user(db: Session = Depends(get_db)):
    if current_user_id is None:
        return None
    return db.query(models.User).filter(models.User.id == current_user_id).first()

def log_activity(db: Session, category: str, action: str, details: str, model_name: str, record_id: int):
    log = models.ActivityLog(
        category=category,
        action=action,
        details=details,
        model_name=model_name,
        record_id=record_id,
        timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    db.add(log)
    db.commit()

@app.on_event("startup")
def startup_event():
    db = models.SessionLocal()
    
    # 1. Create a default procurement officer user if none exists
    if db.query(models.User).count() == 0:
        default_officer = models.User(
            first_name="Procurement",
            last_name="Officer",
            email="officer@vendorbridge.com",
            phone="+91 98765 43210",
            password_hash=hash_password("password"),
            role="officer",
            country="India"
        )
        db.add(default_officer)
        db.commit()

    # 2. Seed Vendors
    if db.query(models.Vendor).count() == 0:
        vendor1 = models.Vendor(
            company_name="Infra Supplies Pvt Ltd",
            contact_name="Rohan Sharma",
            email="rohan@infrasupplies.com",
            phone="+91 98111 22233",
            address="405 Corporate Hub, Bandra East, Mumbai, Maharashtra - 400051",
            gst_number="27AABCU9603R1ZM",
            state="Maharashtra",
            rating=4.8,
            status="approved"
        )
        vendor2 = models.Vendor(
            company_name="Global Logistics Corp",
            contact_name="Anita Patel",
            email="sales@globallogistics.com",
            phone="+91 79111 22233",
            address="12 Logistics Park, GIDC, Ahmedabad, Gujarat - 380001",
            gst_number="24ABCDE1234F1Z8",
            state="Gujarat",
            rating=4.2,
            status="approved"
        )
        vendor3 = models.Vendor(
            company_name="Acme IT Solutions",
            contact_name="Vijay Kumar",
            email="contact@acmeitsolutions.com",
            phone="+91 80111 22233",
            address="88 Electronic City Phase 1, Bangalore, Karnataka - 560100",
            gst_number="29AABCU4567A1Z2",
            state="Karnataka",
            rating=4.5,
            status="approved"
        )
        vendor4 = models.Vendor(
            company_name="Standard Paper & Packaging",
            contact_name="Sanjay Shah",
            email="sanjay@standardpaper.com",
            phone="+91 22111 22233",
            address="15 Industrial Area, Thane, Maharashtra - 400604",
            gst_number="27BBBBB1111A1Z0",
            state="Maharashtra",
            rating=3.5,
            status="pending"
        )
        vendor5 = models.Vendor(
            company_name="Blocked Trading Inc",
            contact_name="Rahul Gupta",
            email="rahul@blockedtrading.com",
            phone="+91 11111 22233",
            address="Plot 56, Sector 4, Gandhinagar, Gujarat - 382010",
            gst_number="24CCCCC2222B1Z1",
            state="Gujarat",
            rating=2.1,
            status="blocked"
        )
        db.add_all([vendor1, vendor2, vendor3, vendor4, vendor5])
        db.commit()

    # 3. Seed RFQs and Line Items
    if db.query(models.RFQ).count() == 0:
        # Fetch seeded vendors to link
        vendors = db.query(models.Vendor).all()
        v1, v2, v3 = vendors[0], vendors[1], vendors[2]
        
        # RFQ 1: Office Furniture Sourcing (Status: Compared)
        rfq1 = models.RFQ(
            title="Office Furniture Sourcing Q2",
            description="Procurement of modular desks and high-back mesh office chairs for BKC headquarters expansion.",
            category="Furniture",
            priority="high",
            deadline="2026-06-30",
            status="compared"
        )
        db.add(rfq1)
        db.commit()
        
        # RFQ 1 lines
        l1 = models.RFQLine(rfq_id=rfq1.id, description="Ergonomic Standing Desk (Dual Motor)", quantity=10.0, uom="Units")
        l2 = models.RFQLine(rfq_id=rfq1.id, description="High-Back Ergonomic Mesh Chair", quantity=25.0, uom="Units")
        db.add_all([l1, l2])
        db.commit()

        # Bid 1: Vendor 1 (Cheapest)
        bid1 = models.Bid(
            rfq_id=rfq1.id, vendor_id=v1.id, discount_percent=5.0, discount_amount=9000.0,
            delivery_days=7, notes="Standard 1 year comprehensive warranty included.",
            amount=180000.0, tax_amount=32400.0, total_amount=203400.0, status="submitted", is_selected=False
        )
        db.add(bid1)
        db.commit()
        
        bl1_1 = models.BidLine(bid_id=bid1.id, rfq_line_id=l1.id, unit_price=8000.0, gst_rate=18.0, subtotal=80000.0)
        bl1_2 = models.BidLine(bid_id=bid1.id, rfq_line_id=l2.id, unit_price=4000.0, gst_rate=18.0, subtotal=100000.0)
        db.add_all([bl1_1, bl1_2])
        db.commit()

        # Bid 2: Vendor 3
        bid2 = models.Bid(
            rfq_id=rfq1.id, vendor_id=v3.id, discount_percent=0.0, discount_amount=0.0,
            delivery_days=10, notes="2 years warranty on mechanical components.",
            amount=195000.0, tax_amount=35100.0, total_amount=230100.0, status="submitted", is_selected=False
        )
        db.add(bid2)
        db.commit()
        
        bl2_1 = models.BidLine(bid_id=bid2.id, rfq_line_id=l1.id, unit_price=9000.0, gst_rate=18.0, subtotal=90000.0)
        bl2_2 = models.BidLine(bid_id=bid2.id, rfq_line_id=l2.id, unit_price=4200.0, gst_rate=18.0, subtotal=105000.0)
        db.add_all([bl2_1, bl2_2])
        db.commit()

        # RFQ 2: Developer Laptops Sourcing (Status: PO Created)
        rfq2 = models.RFQ(
            title="Developer Laptops Sourcing",
            description="Sourcing high-performance workstation laptops for developer hires. Min: 32GB RAM, 1TB NVMe, Intel i7 or equivalent.",
            category="IT Hardware",
            priority="critical",
            deadline="2026-07-15",
            status="po_created"
        )
        db.add(rfq2)
        db.commit()
        
        l3 = models.RFQLine(rfq_id=rfq2.id, description="Core i7 Workstation Laptop (32GB RAM / 1TB SSD)", quantity=15.0, uom="Units")
        db.add(l3)
        db.commit()

        # Selected Bid: Vendor 3
        bid3 = models.Bid(
            rfq_id=rfq2.id, vendor_id=v3.id, discount_percent=2.0, discount_amount=30000.0,
            delivery_days=5, notes="Pre-loaded with corporate OS image.",
            amount=1500000.0, tax_amount=270000.0, total_amount=1740000.0, status="selected", is_selected=True
        )
        db.add(bid3)
        db.commit()
        
        bl3 = models.BidLine(bid_id=bid3.id, rfq_line_id=l3.id, unit_price=100000.0, gst_rate=18.0, subtotal=1500000.0)
        db.add(bl3)
        db.commit()

        # Approval Request for RFQ 2 (Approved)
        approval2 = models.ApprovalRequest(
            rfq_id=rfq2.id, bid_id=bid3.id, approver="Sourcing Head", level=2, status="approved",
            remarks="Approved: pricing fits current departmental hardware allocation.",
            created_at=(datetime.datetime.now() - datetime.timedelta(days=5)).strftime("%Y-%m-%d %H:%M")
        )
        db.add(approval2)
        db.commit()

        # Purchase Order for RFQ 2 (Status: Confirmed)
        po2 = models.PurchaseOrder(
            rfq_id=rfq2.id, bid_id=bid3.id, vendor_id=v3.id,
            amount_untaxed=1470000.0, amount_tax=264600.0, amount_total=1734600.0,
            status="confirmed", date_order=(datetime.date.today() - datetime.timedelta(days=4)).strftime("%Y-%m-%d")
        )
        db.add(po2)
        db.commit()

        # Invoice for PO 2
        inv2 = models.Invoice(
            purchase_order_id=po2.id, vendor_id=v3.id,
            amount_untaxed=1470000.0, gst_type="igst", cgst_amount=0.0, sgst_amount=0.0,
            igst_amount=264600.0, tax_amount=264600.0, amount_total=1734600.0,
            status="sent", invoice_date=(datetime.date.today() - datetime.timedelta(days=2)).strftime("%Y-%m-%d"),
            due_date=(datetime.date.today() + datetime.timedelta(days=28)).strftime("%Y-%m-%d")
        )
        db.add(inv2)
        db.commit()

        # RFQ 3: Stationery & Warehouse supplies (Status: Open)
        rfq3 = models.RFQ(
            title="Warehouse Consumables & Packing Tape",
            description="Procurement of bulk carton packing tape and shipping label rolls for regional warehouses.",
            category="Stationery",
            priority="normal",
            deadline="2026-06-25",
            status="open"
        )
        db.add(rfq3)
        db.commit()
        
        l4 = models.RFQLine(rfq_id=rfq3.id, description="Heavy Duty Packing Tape (2-inch width)", quantity=100.0, uom="Boxes")
        l5 = models.RFQLine(rfq_id=rfq3.id, description="Thermal Barcode Shipping Labels", quantity=50.0, uom="Boxes")
        db.add_all([l4, l5])
        db.commit()

        # 4. Seed Activity Logs
        log_activity(db, "rfq", "RFQ published", "RFQ-0003 Sourcing for Warehouse Consumables published to 5 suppliers.", "RFQ", rfq3.id)
        log_activity(db, "purchase_order", "PO Created", "Purchase Order PO-0001 generated for Acme IT Solutions.", "PurchaseOrder", po2.id)
        log_activity(db, "approval", "Approval approved", "Sourcing Head approved Bid-0003 costing ₹17.34L.", "ApprovalRequest", approval2.id)
        log_activity(db, "quotation", "Quotation submitted", "Acme IT Solutions submitted pricing for Developer Laptops Sourcing.", "Bid", bid3.id)
        log_activity(db, "quotation", "Quotation submitted", "Infra Supplies Pvt Ltd submitted pricing for Office Furniture Sourcing.", "Bid", bid1.id)
        log_activity(db, "quotation", "Quotation submitted", "Acme IT Solutions submitted pricing for Office Furniture Sourcing.", "Bid", bid2.id)
        log_activity(db, "vendor", "Vendor approved", "Acme IT Solutions supplier profile verified and approved.", "Vendor", v3.id)
        log_activity(db, "vendor", "Vendor registered", "Standard Paper & Packaging registered. Verification pending.", "Vendor", v1.id)
        
    db.close()

# ── AUTHENTICATION ROUTES ──

@app.get("/", response_class=RedirectResponse)
async def read_root():
    if current_user_id:
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/login", status_code=302)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"no_sidebar": True, "error": None})

@app.post("/api/login")
async def api_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    global current_user_id
    # Look up user
    user = db.query(models.User).filter(models.User.email == username).first()
    if user and user.password_hash == hash_password(password):
        current_user_id = user.id
        return RedirectResponse(url="/dashboard", status_code=302)
    
    return templates.TemplateResponse(request, "login.html", {
        "no_sidebar": True,
        "error": "Invalid email address or password combination."
    })

@app.get("/vendor/signup", response_class=RedirectResponse)
async def redirect_signup():
    return RedirectResponse(url="/signup", status_code=302)

@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse(request, "signup.html", {"no_sidebar": True})

@app.post("/api/signup")
async def api_signup(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    role: str = Form("officer"),
    country: str = Form("India"),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    global current_user_id
    
    # Check if user already exists
    existing = db.query(models.User).filter(models.User.email == email).first()
    if existing:
        return templates.TemplateResponse(request, "signup.html", {
            "no_sidebar": True,
            "error": "An account with this email address already exists."
        })
        
    user = models.User(
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        role=role,
        country=country,
        password_hash=hash_password(password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    current_user_id = user.id
    
    # Write audit log
    log_activity(db, "vendor", "User registered", f"New account created for {first_name} {last_name} ({role}).", "User", user.id)
    
    return RedirectResponse(url="/dashboard", status_code=302)

@app.get("/logout")
async def logout():
    global current_user_id
    current_user_id = None
    return RedirectResponse(url="/login", status_code=302)

# ── DASHBOARD ──

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, db: Session = Depends(get_db)):
    if not current_user_id:
        return RedirectResponse(url="/login", status_code=302)
        
    # Sourcing Stats counts
    active_rfqs = db.query(models.RFQ).filter(models.RFQ.status == 'open').count()
    pending_approvals = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.status == 'pending').count()
    active_vendors = db.query(models.Vendor).filter(models.Vendor.status == 'approved').count()
    
    # Sum spend of done and confirmed POs
    pos = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.status.in_(['confirmed', 'done'])).all()
    total_spend = sum(po.amount_total for po in pos)
    
    recent_pos = db.query(models.PurchaseOrder).order_by(models.PurchaseOrder.id.desc()).limit(5).all()
    
    # Mock data for Chart.js
    chart_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    chart_data = [120000, 240000, 180000, 480000, 230000, float(total_spend)]
    
    return templates.TemplateResponse(request, "dashboard.html", {
        "active_page": "dashboard",
        "active_rfqs": active_rfqs,
        "pending_approvals": pending_approvals,
        "total_spend": total_spend,
        "active_vendors": active_vendors,
        "recent_pos": recent_pos,
        "chart_labels": chart_labels,
        "chart_data": chart_data
    })

# ── VENDORS ──

@app.get("/vendors", response_class=HTMLResponse)
async def vendors_page(request: Request, status: str = "all", search: str = "", db: Session = Depends(get_db)):
    if not current_user_id:
        return RedirectResponse(url="/login", status_code=302)
        
    query = db.query(models.Vendor)
    
    if status != "all":
        query = query.filter(models.Vendor.status == status)
        
    if search:
        search_like = f"%{search}%"
        query = query.filter(
            (models.Vendor.company_name.like(search_like)) |
            (models.Vendor.contact_name.like(search_like)) |
            (models.Vendor.gst_number.like(search_like)) |
            (models.Vendor.email.like(search_like))
        )
        
    vendors = query.all()
    
    return templates.TemplateResponse(request, "vendors.html", {
        "active_page": "vendors",
        "vendors": vendors,
        "current_status": status,
        "search_query": search
    })

@app.get("/vendors/new", response_class=HTMLResponse)
async def vendors_new_form(request: Request):
    if not current_user_id:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(request, "vendor_form.html", {"active_page": "vendors", "vendor": None})

@app.post("/api/vendors")
async def api_create_vendor(
    company_name: str = Form(...),
    contact_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    gst_number: str = Form(...),
    state: str = Form("Maharashtra"),
    address: str = Form(...),
    db: Session = Depends(get_db)
):
    if not current_user_id:
        return RedirectResponse(url="/login", status_code=302)
        
    vendor = models.Vendor(
        company_name=company_name,
        contact_name=contact_name,
        email=email,
        phone=phone,
        gst_number=gst_number,
        state=state,
        address=address,
        status="approved" # Auto approved for demo ease
    )
    db.add(vendor)
    db.commit()
    
    log_activity(db, "vendor", "Vendor created", f"Supplier profile registered manually: {company_name}.", "Vendor", vendor.id)
    return RedirectResponse(url="/vendors", status_code=302)

@app.get("/vendors/edit/{id}", response_class=HTMLResponse)
async def edit_vendor_form(request: Request, id: int, db: Session = Depends(get_db)):
    if not current_user_id:
        return RedirectResponse(url="/login", status_code=302)
    vendor = db.query(models.Vendor).filter(models.Vendor.id == id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return templates.TemplateResponse(request, "vendor_form.html", {"active_page": "vendors", "vendor": vendor})

@app.post("/api/vendors/{id}/edit")
async def api_edit_vendor(
    id: int,
    company_name: str = Form(...),
    contact_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    gst_number: str = Form(...),
    state: str = Form("Maharashtra"),
    address: str = Form(...),
    status: str = Form(...),
    rating: float = Form(5.0),
    db: Session = Depends(get_db)
):
    if not current_user_id:
        return RedirectResponse(url="/login", status_code=302)
    vendor = db.query(models.Vendor).filter(models.Vendor.id == id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
        
    vendor.company_name = company_name
    vendor.contact_name = contact_name
    vendor.email = email
    vendor.phone = phone
    vendor.gst_number = gst_number
    vendor.state = state
    vendor.address = address
    vendor.status = status
    vendor.rating = rating
    
    db.commit()
    log_activity(db, "vendor", "Vendor updated", f"Modified supplier profile settings: {company_name}.", "Vendor", vendor.id)
    return RedirectResponse(url="/vendors", status_code=302)

@app.post("/api/vendors/{id}/approve")
async def api_approve_vendor(id: int, db: Session = Depends(get_db)):
    if not current_user_id:
        return RedirectResponse(url="/login", status_code=302)
    vendor = db.query(models.Vendor).filter(models.Vendor.id == id).first()
    if vendor:
        vendor.status = "approved"
        db.commit()
        log_activity(db, "vendor", "Vendor approved", f"Registration verified and approved: {vendor.company_name}.", "Vendor", vendor.id)
    return RedirectResponse(url="/vendors", status_code=302)

@app.post("/api/vendors/{id}/block")
async def api_block_vendor(id: int, db: Session = Depends(get_db)):
    if not current_user_id:
        return RedirectResponse(url="/login", status_code=302)
    vendor = db.query(models.Vendor).filter(models.Vendor.id == id).first()
    if vendor:
        vendor.status = "blocked"
        db.commit()
        log_activity(db, "vendor", "Vendor blocked", f"Supplier profile flagged and blocked: {vendor.company_name}.", "Vendor", vendor.id)
    return RedirectResponse(url="/vendors", status_code=302)

# ── RFQS ──

@app.get("/rfqs", response_class=HTMLResponse)
async def rfqs_page(
    request: Request, 
    search: str = "", 
    category: str = "", 
    status: str = "", 
    db: Session = Depends(get_db)
):
    if not current_user_id:
        return RedirectResponse(url="/login", status_code=302)
        
    query = db.query(models.RFQ)
    
    if search:
        query = query.filter(models.RFQ.title.like(f"%{search}%"))
    if category:
        query = query.filter(models.RFQ.category == category)
    if status:
        query = query.filter(models.RFQ.status == status)
        
    rfqs = query.all()
    
    return templates.TemplateResponse(request, "rfq_list.html", {
        "active_page": "rfqs",
        "rfqs": rfqs,
        "search_query": search,
        "category_filter": category,
        "status_filter": status
    })

# Backward compatibility route for user signup logic
@app.get("/vendor/rfq", response_class=RedirectResponse)
async def redirect_rfq():
    return RedirectResponse(url="/rfqs", status_code=302)

@app.get("/rfqs/new", response_class=HTMLResponse)
async def rfq_create_wizard(request: Request, db: Session = Depends(get_db)):
    if not current_user_id:
        return RedirectResponse(url="/login", status_code=302)
    approved_vendors = db.query(models.Vendor).filter(models.Vendor.status == 'approved').all()
    return templates.TemplateResponse(request, "rfq_create.html", {
        "active_page": "rfqs",
        "approved_vendors": approved_vendors
    })

@app.post("/api/rfqs")
async def api_create_rfq(
    request: Request,
    title: str = Form(...),
    category: str = Form(...),
    deadline: str = Form(...),
    priority: str = Form(...),
    description: str = Form(...),
    status: str = Form("open"), # 'draft' or 'open'
    db: Session = Depends(get_db)
):
    if not current_user_id:
        return RedirectResponse(url="/login", status_code=302)
        
    rfq = models.RFQ(
        title=title,
        description=description,
        category=category,
        priority=priority,
        deadline=deadline,
        status=status
    )
    db.add(rfq)
    db.commit()
    db.refresh(rfq)
    
    # Process line items from form arrays
    form_data = await request.form()
    descriptions = form_data.getlist("line_description[]")
    quantities = form_data.getlist("line_quantity[]")
    uoms = form_data.getlist("line_uom[]")
    
    for i in range(len(descriptions)):
        if descriptions[i].strip():
            qty = float(quantities[i]) if i < len(quantities) else 1.0
            uom = uoms[i] if i < len(uoms) else "Units"
            line = models.RFQLine(
                rfq_id=rfq.id,
                description=descriptions[i],
                quantity=qty,
                uom=uom
            )
            db.add(line)
    
    db.commit()
    
    log_activity(db, "rfq", "RFQ published" if status == "open" else "RFQ draft saved", 
                 f"Created RFQ-{rfq.id:04d}: {title}.", "RFQ", rfq.id)
                 
    return RedirectResponse(url="/rfqs", status_code=302)

@app.get("/rfqs/{id}", response_class=HTMLResponse)
async def rfq_detail_page(request: Request, id: int, db: Session = Depends(get_db)):
    if not current_user_id:
        return RedirectResponse(url="/login", status_code=302)
    rfq = db.query(models.RFQ).filter(models.RFQ.id == id).first()
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
        
    # Get all approved vendors so we can submit on their behalf
    vendors = db.query(models.Vendor).filter(models.Vendor.status == 'approved').all()
    
    return templates.TemplateResponse(request, "rfq_detail.html", {
        "active_page": "rfqs",
        "rfq": rfq,
        "vendors": vendors
    })

# Backward compatibility route
@app.get("/vendor/rfq/{rfq_id}", response_class=RedirectResponse)
async def redirect_rfq_detail(rfq_id: int):
    return RedirectResponse(url=f"/rfqs/{rfq_id}", status_code=302)

# ── QUOTATIONS ──

@app.get("/quotations", response_class=HTMLResponse)
async def quotations_list_redirect():
    # Show open RFQs with bids or redirect to /rfqs to filter bids
    return RedirectResponse(url="/rfqs?status=open", status_code=302)

@app.get("/quotations/submit/{rfq_id}", response_class=HTMLResponse)
async def quotation_submit_form(request: Request, rfq_id: int, db: Session = Depends(get_db)):
    if not current_user_id:
        return RedirectResponse(url="/login", status_code=302)
    rfq = db.query(models.RFQ).filter(models.RFQ.id == rfq_id).first()
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    vendors = db.query(models.Vendor).filter(models.Vendor.status == 'approved').all()
    return templates.TemplateResponse(request, "quotation_submit.html", {
        "active_page": "rfqs",
        "rfq": rfq,
        "vendors": vendors
    })

@app.post("/api/quotations")
async def api_create_quotation(
    request: Request,
    rfq_id: int = Form(...),
    vendor_id: int = Form(...),
    delivery_days: int = Form(7),
    notes: str = Form(""),
    amount: float = Form(...),
    tax_amount: float = Form(...),
    discount_percent: float = Form(0.0),
    total_amount: float = Form(...),
    db: Session = Depends(get_db)
):
    if not current_user_id:
        return RedirectResponse(url="/login", status_code=302)
        
    form_data = await request.form()
    rfq_line_ids = form_data.getlist("rfq_line_id[]")
    unit_prices = form_data.getlist("unit_price[]")
    gst_rates = form_data.getlist("gst_rate[]")
    
    # Calculate discount amount
    disc_amount = amount * (discount_percent / 100.0)
    
    # Create Bid/Quotation
    bid = models.Bid(
        rfq_id=rfq_id,
        vendor_id=vendor_id,
        discount_percent=discount_percent,
        discount_amount=disc_amount,
        delivery_days=delivery_days,
        notes=notes,
        amount=amount,
        tax_amount=tax_amount,
        total_amount=total_amount,
        status="submitted"
    )
    db.add(bid)
    db.commit()
    db.refresh(bid)
    
    # Save Bid Lines
    for i in range(len(rfq_line_ids)):
        line_id = int(rfq_line_ids[i])
        price = float(unit_prices[i])
        gst = float(gst_rates[i])
        
        # Get RFQ line qty
        rfq_line = db.query(models.RFQLine).filter(models.RFQLine.id == line_id).first()
        qty = rfq_line.quantity if rfq_line else 1.0
        
        bid_line = models.BidLine(
            bid_id=bid.id,
            rfq_line_id=line_id,
            unit_price=price,
            gst_rate=gst,
            subtotal=(price * qty)
        )
        db.add(bid_line)
        
    db.commit()
    
    # Log Sourcing Activity
    vendor = db.query(models.Vendor).filter(models.Vendor.id == vendor_id).first()
    vendor_name = vendor.company_name if vendor else "Supplier"
    log_activity(db, "quotation", "Quotation recorded", 
                 f"Recorded quotation from {vendor_name} for RFQ-{rfq_id:04d} totaling ₹{total_amount:,.2f}.", 
                 "Bid", bid.id)
                 
    return RedirectResponse(url=f"/rfqs/{rfq_id}", status_code=302)

@app.get("/quotations/compare/{rfq_id}", response_class=HTMLResponse)
async def quotation_compare_matrix(request: Request, rfq_id: int, db: Session = Depends(get_db)):
    if not current_user_id:
        return RedirectResponse(url="/login", status_code=302)
    rfq = db.query(models.RFQ).filter(models.RFQ.id == rfq_id).first()
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
        
    bids = db.query(models.Bid).filter(models.Bid.rfq_id == rfq_id).all()
    if len(bids) == 0:
        raise HTTPException(status_code=400, detail="No quotations received to compare.")
        
    # Find lowest bid
    lowest_bid = min(bids, key=lambda b: b.total_amount)
    lowest_bid_id = lowest_bid.id if lowest_bid else None
    
    # Mark RFQ as compared if open
    if rfq.status == "open":
        rfq.status = "compared"
        db.commit()
        log_activity(db, "quotation", "Comparison matrix viewed", f"Performed comparison matrix check on RFQ-{rfq.id:04d}.", "RFQ", rfq.id)
        
    return templates.TemplateResponse(request, "quotation_compare.html", {
        "active_page": "rfqs",
        "rfq": rfq,
        "bids": bids,
        "lowest_bid_id": lowest_bid_id
    })

@app.post("/api/quotations/{bid_id}/select")
async def api_select_bid(bid_id: int, db: Session = Depends(get_db)):
    if not current_user_id:
        return RedirectResponse(url="/login", status_code=302)
        
    bid = db.query(models.Bid).filter(models.Bid.id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=404, detail="Quotation not found")
        
    # Set all other bids for this RFQ as not selected
    db.query(models.Bid).filter(models.Bid.rfq_id == bid.rfq_id).update({
        models.Bid.is_selected: False,
        models.Bid.status: "submitted"
    })
    
    # Select this bid
    bid.is_selected = True
    bid.status = "selected"
    
    # Set RFQ status to pending_approval
    rfq = db.query(models.RFQ).filter(models.RFQ.id == bid.rfq_id).first()
    rfq.status = "pending_approval"
    
    # Initiate Approval workflow request
    approval = models.ApprovalRequest(
        rfq_id=rfq.id,
        bid_id=bid.id,
        approver="Finance Controller", # Demo flow level 2
        level=2,
        status="pending"
    )
    db.add(approval)
    db.commit()
    
    log_activity(db, "approval", "Approval workflow initiated", 
                 f"Sourcing selected {bid.vendor.company_name} for RFQ-{rfq.id:04d}. Sent to Finance Controller.", 
                 "ApprovalRequest", approval.id)
                 
    return RedirectResponse(url="/approvals", status_code=302)

# ── APPROVAL WORKFLOWS ──

@app.get("/approvals", response_class=HTMLResponse)
async def approvals_page(request: Request, db: Session = Depends(get_db)):
    if not current_user_id:
        return RedirectResponse(url="/login", status_code=302)
    approvals = db.query(models.ApprovalRequest).order_by(models.ApprovalRequest.id.desc()).all()
    return templates.TemplateResponse(request, "approvals_list.html", {
        "active_page": "approvals",
        "approvals": approvals
    })

@app.get("/approvals/{id}", response_class=HTMLResponse)
async def approval_detail_page(request: Request, id: int, db: Session = Depends(get_db)):
    if not current_user_id:
        return RedirectResponse(url="/login", status_code=302)
    approval = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.id == id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return templates.TemplateResponse(request, "approval.html", {
        "active_page": "approvals",
        "approval": approval
    })

@app.post("/api/approvals/{id}/action")
async def api_approval_action(
    id: int,
    action: str = Form(...), # 'approve' or 'reject'
    remarks: str = Form(""),
    db: Session = Depends(get_db)
):
    if not current_user_id:
        return RedirectResponse(url="/login", status_code=302)
        
    approval = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.id == id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")
        
    if action == "approve":
        approval.status = "approved"
        approval.remarks = remarks
        
        # Set RFQ status to approved
        rfq = approval.rfq
        rfq.status = "approved"
        
        # Generate PO automatically
        bid = approval.bid
        po = models.PurchaseOrder(
            rfq_id=rfq.id,
            bid_id=bid.id,
            vendor_id=bid.vendor_id,
            amount_untaxed=bid.amount - bid.discount_amount,
            amount_tax=bid.tax_amount,
            amount_total=bid.total_amount,
            status="confirmed" # Confirmed on creation
        )
        db.add(po)
        db.commit()
        db.refresh(po)
        
        # Generate Invoice for the PO
        # Split GST types for interstate vs local
        gst_type = "cgst_sgst"
        cgst = 0.0
        sgst = 0.0
        igst = 0.0
        
        # Sourcing BKC in MH
        if bid.vendor.state != "Maharashtra":
            gst_type = "igst"
            igst = po.amount_tax
        else:
            cgst = po.amount_tax / 2.0
            sgst = po.amount_tax / 2.0
            
        invoice = models.Invoice(
            purchase_order_id=po.id,
            vendor_id=bid.vendor_id,
            amount_untaxed=po.amount_untaxed,
            gst_type=gst_type,
            cgst_amount=cgst,
            sgst_amount=sgst,
            igst_amount=igst,
            tax_amount=po.amount_tax,
            amount_total=po.amount_total,
            status="sent",
            due_date=(datetime.date.today() + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        )
        db.add(invoice)
        
        # Set RFQ to po_created
        rfq.status = "po_created"
        db.commit()
        
        log_activity(db, "approval", "Proposal approved", f"Approved recommendation for RFQ-{rfq.id:04d} Sourcing: {remarks}", "ApprovalRequest", approval.id)
        log_activity(db, "purchase_order", "PO Confirmed", f"PO-{po.id:04d} auto-generated for {bid.vendor.company_name} following workflow clearance.", "PurchaseOrder", po.id)
        
    else:
        approval.status = "rejected"
        approval.remarks = remarks
        
        # Reset RFQ status back to compared
        rfq = approval.rfq
        rfq.status = "compared"
        
        # Mark selected bid back to submitted
        bid = approval.bid
        bid.status = "submitted"
        bid.is_selected = False
        db.commit()
        
        log_activity(db, "approval", "Proposal rejected", f"Rejected sourcing recommendation for RFQ-{rfq.id:04d}: {remarks}", "ApprovalRequest", approval.id)
        
    return RedirectResponse(url="/approvals", status_code=302)

# ── PURCHASE ORDERS & INVOICES ──

@app.get("/purchase-orders", response_class=HTMLResponse)
async def purchase_orders_page(request: Request, db: Session = Depends(get_db)):
    if not current_user_id:
        return RedirectResponse(url="/login", status_code=302)
    pos = db.query(models.PurchaseOrder).order_by(models.PurchaseOrder.id.desc()).all()
    return templates.TemplateResponse(request, "purchase_orders_list.html", {
        "active_page": "purchase_orders",
        "purchase_orders": pos
    })

@app.get("/purchase-orders/{id}", response_class=HTMLResponse)
async def purchase_order_detail_page(request: Request, id: int, db: Session = Depends(get_db)):
    if not current_user_id:
        return RedirectResponse(url="/login", status_code=302)
    po = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.id == id).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
        
    # Get associated Invoice
    invoice = db.query(models.Invoice).filter(models.Invoice.purchase_order_id == po.id).first()
    
    return templates.TemplateResponse(request, "po_invoice.html", {
        "active_page": "purchase_orders",
        "po": po,
        "invoice": invoice
    })

@app.post("/api/purchase-orders/{id}/pay")
async def api_pay_invoice(id: int, db: Session = Depends(get_db)):
    if not current_user_id:
        return RedirectResponse(url="/login", status_code=302)
    po = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.id == id).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
        
    invoice = db.query(models.Invoice).filter(models.Invoice.purchase_order_id == po.id).first()
    if invoice:
        invoice.status = "paid"
        po.status = "done" # Complete PO
        db.commit()
        log_activity(db, "invoice", "Invoice paid", f"Cleared payment for INV-{invoice.id:04d} totaling ₹{invoice.amount_total:,.2f}.", "Invoice", invoice.id)
        
    return RedirectResponse(url=f"/purchase-orders/{po.id}", status_code=302)

@app.get("/invoices", response_class=HTMLResponse)
async def invoices_page(request: Request, db: Session = Depends(get_db)):
    if not current_user_id:
        return RedirectResponse(url="/login", status_code=302)
    invoices = db.query(models.Invoice).order_by(models.Invoice.id.desc()).all()
    return templates.TemplateResponse(request, "invoices_list.html", {
        "active_page": "invoices",
        "invoices": invoices
    })

# ── AUDIT LOGS ──

@app.get("/activity", response_class=HTMLResponse)
async def activity_logs_page(request: Request, category: str = "all", db: Session = Depends(get_db)):
    if not current_user_id:
        return RedirectResponse(url="/login", status_code=302)
        
    query = db.query(models.ActivityLog)
    if category != "all":
        query = query.filter(models.ActivityLog.category == category)
        
    logs = query.order_by(models.ActivityLog.id.desc()).all()
    
    return templates.TemplateResponse(request, "activity.html", {
        "active_page": "activity",
        "logs": logs,
        "current_category": category
    })

# ── REPORTS & ANALYTICS ──

@app.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request, db: Session = Depends(get_db)):
    if not current_user_id:
        return RedirectResponse(url="/login", status_code=302)
        
    # Aggregate sourcing values
    active_vendors = db.query(models.Vendor).filter(models.Vendor.status == 'approved').count()
    pending_invoices = db.query(models.Invoice).filter(models.Invoice.status != 'paid').count()
    
    # Grand spend
    pos = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.status.in_(['confirmed', 'done'])).all()
    total_spend = sum(po.amount_total for po in pos)
    
    # Calculate ratios per category
    categories = ["IT Hardware", "Furniture", "Stationery", "Logistics"]
    category_spend = {cat: 0.0 for cat in categories}
    for po in pos:
        cat = po.rfq.category
        if cat in category_spend:
            category_spend[cat] += po.amount_total
        else:
            category_spend[cat] = po.amount_total
            
    # Fill in defaults if empty
    if total_spend == 0:
        total_spend = 1240000.0
        category_spend = {
            "IT Hardware": 480000.0,
            "Furniture": 320000.0,
            "Stationery": 210000.0,
            "Logistics": 230000.0
        }
        
    # Get top vendors spend list
    vendors = db.query(models.Vendor).filter(models.Vendor.status == 'approved').all()
    top_vendors = []
    for vendor in vendors:
        v_pos = db.query(models.PurchaseOrder).filter(
            models.PurchaseOrder.vendor_id == vendor.id,
            models.PurchaseOrder.status.in_(['confirmed', 'done'])
        ).all()
        v_spend = sum(po.amount_total for po in v_pos)
        if len(v_pos) > 0:
            top_vendors.append({
                "vendor": vendor,
                "order_count": len(v_pos),
                "total_spend": v_spend
            })
            
    # Default top vendors if DB is cold
    if not top_vendors:
        for idx, vendor in enumerate(vendors[:3]):
            top_vendors.append({
                "vendor": vendor,
                "order_count": 5 - idx,
                "total_spend": 700000.0 / (idx + 1)
            })
            
    top_vendors = sorted(top_vendors, key=lambda x: x["total_spend"], reverse=True)
    
    # Chart data
    chart_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    chart_data = [120000, 240000, 180000, 480000, 230000, float(total_spend)]
    
    return templates.TemplateResponse(request, "reports.html", {
        "active_page": "reports",
        "total_spend": total_spend,
        "active_vendors": active_vendors,
        "pending_invoices": pending_invoices,
        "category_spend": category_spend,
        "top_vendors": top_vendors,
        "chart_labels": chart_labels,
        "chart_data": chart_data
    })
