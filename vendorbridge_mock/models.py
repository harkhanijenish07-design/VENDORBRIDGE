from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Boolean, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
import datetime

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String)
    last_name = Column(String)
    email = Column(String, unique=True, index=True)
    phone = Column(String)
    password_hash = Column(String)
    role = Column(String, default="officer")  # admin, officer
    country = Column(String, default="India")


class Vendor(Base):
    __tablename__ = 'vendors'
    
    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String, index=True)
    contact_name = Column(String)
    email = Column(String, unique=True, index=True)
    phone = Column(String)
    address = Column(String)
    gst_number = Column(String)
    state = Column(String, default="Maharashtra")  # Maharashtra or other (for CGST/SGST vs IGST split)
    rating = Column(Float, default=5.0)
    status = Column(String, default="pending")  # pending, approved, rejected, blocked
    
    bids = relationship("Bid", back_populates="vendor")
    purchase_orders = relationship("PurchaseOrder", back_populates="vendor")
    invoices = relationship("Invoice", back_populates="vendor")


class RFQ(Base):
    __tablename__ = 'rfqs'
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text)
    category = Column(String, default="IT Hardware")  # Stationery, IT Hardware, Furniture
    priority = Column(String, default="normal")  # low, normal, high, critical
    deadline = Column(String)
    status = Column(String, default="open")  # open, compared, pending_approval, approved, po_created, closed, cancelled
    
    line_ids = relationship("RFQLine", back_populates="rfq", cascade="all, delete-orphan")
    bids = relationship("Bid", back_populates="rfq")
    approval_requests = relationship("ApprovalRequest", back_populates="rfq")
    purchase_orders = relationship("PurchaseOrder", back_populates="rfq")


class RFQLine(Base):
    __tablename__ = 'rfq_lines'
    
    id = Column(Integer, primary_key=True)
    rfq_id = Column(Integer, ForeignKey('rfqs.id'))
    description = Column(String)
    quantity = Column(Float, default=1.0)
    uom = Column(String, default="Units")
    
    rfq = relationship("RFQ", back_populates="line_ids")
    bid_lines = relationship("BidLine", back_populates="rfq_line", cascade="all, delete-orphan")


class Bid(Base):
    __tablename__ = 'bids'
    
    id = Column(Integer, primary_key=True, index=True)
    rfq_id = Column(Integer, ForeignKey('rfqs.id'))
    vendor_id = Column(Integer, ForeignKey('vendors.id'))
    discount_percent = Column(Float, default=0.0)
    discount_amount = Column(Float, default=0.0)
    delivery_days = Column(Integer, default=7)
    notes = Column(Text)
    amount = Column(Float, default=0.0)  # Untaxed total (sum of unit_price * qty)
    tax_amount = Column(Float, default=0.0)
    total_amount = Column(Float, default=0.0)  # Grand total including tax
    status = Column(String, default="submitted")  # submitted, selected, rejected
    is_selected = Column(Boolean, default=False)
    
    rfq = relationship("RFQ", back_populates="bids")
    vendor = relationship("Vendor", back_populates="bids")
    line_ids = relationship("BidLine", back_populates="bid", cascade="all, delete-orphan")
    approval_requests = relationship("ApprovalRequest", back_populates="bid")
    purchase_orders = relationship("PurchaseOrder", back_populates="bid")


class BidLine(Base):
    __tablename__ = 'bid_lines'
    
    id = Column(Integer, primary_key=True)
    bid_id = Column(Integer, ForeignKey('bids.id'))
    rfq_line_id = Column(Integer, ForeignKey('rfq_lines.id'))
    unit_price = Column(Float, default=0.0)
    gst_rate = Column(Float, default=18.0)  # 0, 5, 12, 18, 28
    subtotal = Column(Float, default=0.0)  # unit_price * quantity
    
    bid = relationship("Bid", back_populates="line_ids")
    rfq_line = relationship("RFQLine", back_populates="bid_lines")


class ApprovalRequest(Base):
    __tablename__ = 'approval_requests'
    
    id = Column(Integer, primary_key=True, index=True)
    rfq_id = Column(Integer, ForeignKey('rfqs.id'))
    bid_id = Column(Integer, ForeignKey('bids.id'))
    approver = Column(String, default="Procurement Manager")
    remarks = Column(Text, default="")
    level = Column(Integer, default=1)  # 1-level or 2-level approvals
    status = Column(String, default="pending")  # pending, approved, rejected
    created_at = Column(String, default=lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))

    rfq = relationship("RFQ", back_populates="approval_requests")
    bid = relationship("Bid", back_populates="approval_requests")


class PurchaseOrder(Base):
    __tablename__ = 'purchase_orders'
    
    id = Column(Integer, primary_key=True, index=True)
    rfq_id = Column(Integer, ForeignKey('rfqs.id'))
    bid_id = Column(Integer, ForeignKey('bids.id'))
    vendor_id = Column(Integer, ForeignKey('vendors.id'))
    amount_untaxed = Column(Float, default=0.0)
    amount_tax = Column(Float, default=0.0)
    amount_total = Column(Float, default=0.0)
    status = Column(String, default="draft")  # draft, confirmed, done, cancelled
    date_order = Column(String, default=lambda: datetime.date.today().strftime("%Y-%m-%d"))
    
    rfq = relationship("RFQ", back_populates="purchase_orders")
    bid = relationship("Bid", back_populates="purchase_orders")
    vendor = relationship("Vendor", back_populates="purchase_orders")
    invoices = relationship("Invoice", back_populates="purchase_order")


class Invoice(Base):
    __tablename__ = 'invoices'
    
    id = Column(Integer, primary_key=True, index=True)
    purchase_order_id = Column(Integer, ForeignKey('purchase_orders.id'))
    vendor_id = Column(Integer, ForeignKey('vendors.id'))
    amount_untaxed = Column(Float, default=0.0)
    gst_type = Column(String, default="cgst_sgst")  # cgst_sgst, igst
    cgst_amount = Column(Float, default=0.0)
    sgst_amount = Column(Float, default=0.0)
    igst_amount = Column(Float, default=0.0)
    tax_amount = Column(Float, default=0.0)
    amount_total = Column(Float, default=0.0)
    status = Column(String, default="draft")  # draft, sent, paid, cancelled
    invoice_date = Column(String, default=lambda: datetime.date.today().strftime("%Y-%m-%d"))
    due_date = Column(String)

    purchase_order = relationship("PurchaseOrder", back_populates="invoices")
    vendor = relationship("Vendor", back_populates="invoices")


class ActivityLog(Base):
    __tablename__ = 'activity_logs'
    
    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String)
    record_id = Column(Integer)
    record_name = Column(String)
    action = Column(String)
    category = Column(String)  # rfq, quotation, approval, invoice, vendor, purchase_order
    details = Column(Text)
    timestamp = Column(String, default=lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


# Database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./vendorbridge_mock.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Recreate all tables
Base.metadata.create_all(bind=engine)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
