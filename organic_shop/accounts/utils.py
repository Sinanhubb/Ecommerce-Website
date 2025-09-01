from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from django.http import HttpResponse
from django.utils import timezone

def generate_invoice(order):
    # Create HTTP response with PDF headers
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Invoice_{order.id}.pdf"'

    # Create PDF
    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    # Header
    p.setFont("Helvetica-Bold", 16)
    p.drawString(200, height - 50, "INVOICE")

    # Order Info
    p.setFont("Helvetica", 12)
    p.drawString(50, height - 100, f"Invoice ID: {order.id}")
    p.drawString(50, height - 120, f"Date: {timezone.now().strftime('%d-%m-%Y %H:%M')}")
    p.drawString(50, height - 140, f"Customer: {order.user.username}")
    p.drawString(50, height - 160, f"Email: {order.user.email}")

    # Table Header
    y = height - 200
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Product")
    p.drawString(250, y, "Quantity")
    p.drawString(350, y, "Price")
    p.drawString(450, y, "Total")

    # Table Content
    p.setFont("Helvetica", 12)
    y -= 20
    total_amount = 0
    for item in order.items.all():
    # Product / Variant name
      if item.variant:
        product_name = f"{item.variant.product.name} ({item.variant_display})"
      else:
        product_name = item.product.name if item.product else "Deleted Product"

    # Draw row
    p.drawString(50, y, product_name)
    p.drawString(250, y, str(item.quantity))
    p.drawString(350, y, f"₹{item.price}")
    line_total = item.total
    p.drawString(450, y, f"₹{line_total}")
    total_amount += line_total
    y -= 20


    # Final Total
    p.setFont("Helvetica-Bold", 12)
    p.drawString(350, y - 20, "Grand Total:")
    p.drawString(450, y - 20, f"₹{total_amount}")

    # Footer
    p.setFont("Helvetica-Oblique", 10)
    p.drawString(50, 50, "Thank you for shopping with us!")

    # Save PDF
    p.showPage()
    p.save()
    return response
