from src.tools import duck_search
import re

def clean_body(text: str) -> str:
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Remove URLs
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    # Remove markdown links
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)
    # Remove unwanted special characters while keeping common punctuation
    text = re.sub(r"[^\w\s.,!?;:%₹$€£'\"()\-–—/]", " ", text)
    return text.strip()


q = "UPI charge above 2000"
# result = duck_search(q,5)
result = [{'title': 'UPI Charges Explained: Will you pay a fee for Rs 2,000+ UPI ...', 'href': 'https://economictimes.indiatimes.com/news/new-updates/upi-charges-explained-will-you-pay-a-fee-for-rs-2000-upi-payments-government-clarifies-what-users-need-to-know/articleshow/134251814.cms', 'body': 'Sep 15, 2026 · UPI Payment Charges Rules: Ordinary UPI users will not pay transaction fees for payments above Rs 2,000. Person-to-person UPI transactions will remain completely free, regardless of the amount transferred. Payments to merchants up to Rs 2,000 will also continue to be free of charge.'}, {'title': 'UPI Charges Above ₹2,000 Explained: Who Pays MDR? - INDmoney', 'href': 'https://www.indmoney.com/blog/stocks/upi-charges-above-2000-explained', 'body': 'Sep 16, 2026 · UPI MDR above ₹2,000 explained simply. See who pays the charge, how much merchants bear on ₹10,000 to ₹1 lakh payments, how broker funding is treated and what it means for users, Paytm, MobiKwik and banks.'}, {'title': 'UPI Charges Up To ₹2,000: New Government Rules Effective ...', 'href': 'https://taxgst.in/upi-charges/', 'body': 'Sep 15, 2026 · India bars bank charges on UPI payments up to ₹2,000. Latest rules, examples, deadlines & expert insights for Indian taxpayers.'}, {'title': 'UPI से ₹2,000 तक पेमेंट पर नहीं लगेगा चार्ज, इससे ज्यादा पर ...', 'href': 'https://hindi.oneindia.com/news/india/upi-2000-payment-charge-rupay-debit-card-fees-mdr-above-2000-payment-govt-10-questions-answers-1648821.html', 'body': 'Sep 15, 2026 · UPI ₹2,000 Payment Charge को लेकर सरकार ने स्थिति साफ कर दी है। ₹2,000 तक के यूपीआई पेमेंट और RuPay डेबिट कार्ड पेमेंट पर फीस नहीं लगेगी। जानें                            ₹2,000 से ...'}, {'title': 'UPI Charges Above ₹2,000: New 0.4% Rule Explained (Oct 2026)', 'href': 'https://upichargess.com/news/upi-charges-above-2000', 'body': 'Sep 16, 2026 · Charges on UPI above ₹2,000 explained: 0.4% MDR on specified merchant payments, capped at ₹300, from October 15, 2026. Consumers pay nothing extra.'}]

new_result = []
for i in result:
    body = i["body"]
    new_result.append(body)


ans = [clean_body(b) for b in new_result]
print(new_result)
print("=======================================")
print(ans)