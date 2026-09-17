from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from ..spec import Arguments, Site, Task, ToolSpec


class ListRecords(Arguments):
    query: str = ""
    after: date | None = None
    before: date | None = None
    status: str | None = None
    customer: str | None = None
    document_type: str | None = None
    limit: int = Field(default=50, ge=1, le=500)

    @model_validator(mode="after")
    def ordered_dates(self):
        if self.after and self.before and self.after > self.before:
            raise ValueError("after must not follow before")
        return self


class Record(Arguments):
    record: str = Field(
        min_length=1, description="Unique document number, customer identity, or expense identity"
    )


class Customer(Arguments):
    name: str = Field(min_length=1)
    email: str | None = None
    tax_id: str | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    country: str | None = None
    notes: str | None = None


class UpdateCustomer(Customer):
    existing_customer: str = Field(min_length=1)


class Line(Arguments):
    description: str = Field(min_length=1)
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    vat: Literal["included", "excluded", "exempt"] = "excluded"


class Payment(Arguments):
    method: str = Field(
        min_length=1, description="UI payment method, e.g. bank transfer, cash or credit card"
    )
    amount: Decimal = Field(gt=0)
    date: date
    reference: str | None = None


class Document(Arguments):
    document_type: Literal[
        "invoice",
        "tax_invoice",
        "receipt",
        "invoice_receipt",
        "quote",
        "proforma",
        "credit_note",
        "delivery_note",
    ]
    customer: str = Field(min_length=1)
    date: date
    currency: str = "ILS"
    language: Literal["he", "en"] = "he"
    items: list[Line] = Field(min_length=1)
    payments: list[Payment] = Field(default_factory=list)
    notes: str | None = None
    related_document: str | None = None

    @model_validator(mode="after")
    def payment_required(self):
        if self.document_type in {"receipt", "invoice_receipt"} and not self.payments:
            raise ValueError("Receipt documents require actual payment details")
        if self.document_type == "credit_note" and not self.related_document:
            raise ValueError("credit_note requires related_document")
        return self


class Expense(Arguments):
    supplier: str = Field(min_length=1)
    date: date
    amount: Decimal = Field(gt=0)
    currency: str = "ILS"
    category: str | None = None
    description: str | None = None
    attachment: str | None = Field(default=None, description="Previously uploaded file name")


class Report(Arguments):
    report: str = Field(
        min_length=1,
        description="Report name visible in Morning, e.g. income, expenses, customer balance",
    )
    after: date
    before: date
    download: bool = True

    @model_validator(mode="after")
    def ordered_dates(self):
        if self.after > self.before:
            raise ValueError("after must not follow before")
        return self


class SendDocument(Record):
    email: str = Field(min_length=1)


def fields(data, prefix=""):
    """Offer every exact scalar as a Jev choice, including repeated line-item fields."""
    output = {}
    for key, value in data.items() if isinstance(data, dict) else enumerate(data):
        name = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, (dict, list)):
            output.update(fields(value, name))
        elif value is not None:
            output[name] = str(value)
    return output


def task(args, goal, *, uploads=None):
    data = args.model_dump(mode="json", exclude_none=True)
    return Task(
        f"{goal}\nExact caller data: {data}\nVerify the resulting page or saved record. Stop if a required field is absent; do not invent tax or payment data.",
        fields(data),
        uploads or {},
        max_steps=100,
    )


def listing(kind):
    return lambda a: task(
        a,
        f"List/search {kind}. Apply all supplied date, status, customer, type and text filters. Capture each page of matching rows before pagination, up to limit or end; report observed numbers, dates, names, amounts, currencies and statuses. Do not change records.",
    )


SITE = Site(
    name="morning",
    start_url="https://app.greeninvoice.co.il/",
    domains=(
        "greeninvoice.co.il",
        "morning.co.il",
        "morning.co",
        "accounts.google.com",
        "content.googleapis.com",
    ),
    guidance="Morning (חשבונית ירוקה / Green Invoice) business app; Hebrew and English interfaces. מסמכים=documents, לקוחות=customers, הוצאות=expenses, דוחות=reports, טיוטה=draft, הפקה=issue, קבלה=receipt, חשבונית מס=tax invoice. Choose the exact requested business when multiple businesses appear; stop if unspecified and ambiguous. Monetary amounts, VAT and payments must come from tool arguments. Never issue a document when asked to draft. Issued accounting documents may be irreversible: do not issue duplicates after uncertainty. Use UI downloads for PDFs and exports.",
    tools=(
        ToolSpec(
            "morning_list_documents",
            "Find documents/invoices/receipts/quotes by dates, customer, type, status or query.",
            ListRecords,
            listing("documents"),
            True,
        ),
        ToolSpec(
            "morning_read_document",
            "Open a document and return its visible details and line items.",
            Record,
            lambda a: task(
                a,
                "Open the uniquely identified document. Capture full details, all line items, totals, VAT, payment and status.",
            ),
            True,
        ),
        ToolSpec(
            "morning_download_document",
            "Download the original document PDF to the isolated file store.",
            Record,
            lambda a: task(
                a, "Open the unique document and download its PDF. Wait for the download."
            ),
        ),
        ToolSpec(
            "morning_create_draft",
            "Create a draft invoice, receipt, quote or other document with exact line items and payment data.",
            Document,
            lambda a: task(
                a,
                "Create a new document as a DRAFT only. Enter all line items/payment details and verify the saved draft. Never issue or email it.",
            ),
        ),
        ToolSpec(
            "morning_issue_document",
            "Issue an existing uniquely identified draft. This may be irreversible; call only when issuance is intended.",
            Record,
            lambda a: task(
                a,
                "Open the exact existing draft, issue it once, and verify the assigned document number and issued status. Do not email unless separately requested.",
            ),
        ),
        ToolSpec(
            "morning_send_document",
            "Email an existing document to the supplied recipient.",
            SendDocument,
            lambda a: task(
                a,
                "Open the existing document and email it once to the exact provided email address. Verify sent status.",
            ),
        ),
        ToolSpec(
            "morning_list_customers",
            "Search/list customers with visible contact and balance details.",
            ListRecords,
            listing("customers"),
            True,
        ),
        ToolSpec(
            "morning_read_customer",
            "Read one customer's details, documents and balance.",
            Record,
            lambda a: task(
                a,
                "Open the unique customer and capture contact details, balance and document history. Do not modify.",
            ),
            True,
        ),
        ToolSpec(
            "morning_create_customer",
            "Create a customer from exact supplied details.",
            Customer,
            lambda a: task(
                a,
                "Create the customer once. Check for an existing matching tax ID/email first and stop on duplicate. Save and verify.",
            ),
        ),
        ToolSpec(
            "morning_update_customer",
            "Update the supplied fields of an existing customer.",
            UpdateCustomer,
            lambda a: task(
                a, "Find existing_customer uniquely. Update only supplied fields, save and verify."
            ),
        ),
        ToolSpec(
            "morning_list_expenses",
            "Search/list expenses by timeframe and filters.",
            ListRecords,
            listing("expenses"),
            True,
        ),
        ToolSpec(
            "morning_record_expense",
            "Record an expense with an optional uploaded receipt.",
            Expense,
            lambda a: task(
                a,
                "Record this expense exactly once, attach the supplied receipt if any, save and verify.",
                uploads={a.attachment: a.attachment} if a.attachment else {},
            ),
        ),
        ToolSpec(
            "morning_report",
            "Open a named report for a date range and optionally download its export.",
            Report,
            lambda a: task(
                a,
                "Open the requested report and apply the exact date range. Capture totals and rows; download its export if requested. Do not alter business records.",
            ),
            True,
        ),
    ),
)
