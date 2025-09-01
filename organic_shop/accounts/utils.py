from decimal import Decimal
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from django.http import HttpResponse
from django.utils import timezone


def format_currency(value):
    return f"₹{Decimal(value):.2f}"


def generate_invoice(order):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Invoice_{order.id}.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    # Header
    p.setFont("Helvetica-Bold", 16)
    p.drawString(220, height - 50, "INVOICE")

    p.setFont("Helvetica", 12)
    p.drawString(50, height - 100, f"Invoice ID: {order.id}")
    p.drawString(50, height - 120, f"Date: {timezone.now().strftime('%d-%m-%Y %H:%M')}")
    p.drawString(50, height - 140, f"Customer: {order.user.username}")
    p.drawString(50, height - 160, f"Email: {order.user.email}")

    # Table header
    y = height - 200
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Product")
    p.drawString(250, y, "Quantity")
    p.drawString(350, y, "Price")
    p.drawString(450, y, "Total")

    # Items
    p.setFont("Helvetica", 12)
    y -= 20
    for item in order.items.all():
        if y < 120:  # Page break
            p.showPage()
            p.setFont("Helvetica", 12)
            y = height - 100

        product_name = item.product.name if item.product else "Deleted Product"
        if item.variant:
            product_name += f" ({item.variant_display})"

        p.drawString(50, y, product_name[:40])  # truncate if too long
        p.drawString(250, y, str(item.quantity))
        p.drawString(350, y, format_currency(item.price))
        p.drawString(450, y, format_currency(item.total))
        y -= 20

    # Totals section
    subtotal = order.get_subtotal
    discount = order.get_discount_amount
    grand_total = order.total_price

    y -= 20
    p.setFont("Helvetica-Bold", 12)
    p.drawString(350, y, "Subtotal:")
    p.drawString(450, y, format_currency(subtotal))

    if order.promo_code:
        y -= 20
        p.setFont("Helvetica", 12)
        p.drawString(350, y, f"Promo ({order.promo_code.code}):")
        p.drawString(450, y, f"-{format_currency(discount)}")

    y -= 25
    p.setFont("Helvetica-Bold", 12)
    p.drawString(350, y, "Grand Total:")
    p.drawString(450, y, format_currency(grand_total))

    # Footer
    y -= 40
    p.setFont("Helvetica-Oblique", 10)
    p.drawString(50, 50, "Thank you for your order!")

    p.showPage()
    p.save()
    return response
