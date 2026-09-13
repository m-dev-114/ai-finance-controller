"""
Builds a downloadable example settlement + bank CSV pair, sized and shaped
to exercise every pattern the investigation agent knows how to reason
about, via the actual import path rather than direct DB seeding.
"""
import io
import csv
import random
import datetime as dt

RAZORPAY_FEE_RATE = 0.02
GST_ON_FEE_RATE = 0.18

random.seed(7)


def _fee_tax(amount):
    fee = round(amount * RAZORPAY_FEE_RATE, 2)
    tax = round(fee * GST_ON_FEE_RATE, 2)
    return fee, tax


def build_example_csvs(n_transactions: int = 40):
    base_date = dt.datetime(2026, 8, 1)
    settlement_rows = []
    bank_rows = []

    txns = []
    for i in range(n_transactions):
        created = base_date + dt.timedelta(hours=random.randint(0, 24 * 6), minutes=random.randint(0, 59))
        amount = round(random.uniform(200, 12000), 2)
        fee, tax = _fee_tax(amount)
        txns.append({
            "id": f"txn_ex_{i:04d}",
            "customer_id": f"cust_{2000 + random.randint(0, 40)}",
            "amount": amount, "fee": fee, "tax": tax,
            "created_at": created, "status": "captured",
        })

    # a couple of refunds and a failed attempt, sprinkled in
    txns[3]["status"] = "refunded"
    txns[3]["refund_delay_days"] = 9
    txns.append({
        "id": "txn_ex_failed_01", "customer_id": txns[7]["customer_id"],
        "amount": txns[7]["amount"], "fee": 0, "tax": 0,
        "created_at": txns[7]["created_at"] - dt.timedelta(minutes=4),
        "status": "failed",
    })

    # group captured txns into daily batches, T+2 settlement lag
    by_day = {}
    for t in txns:
        if t["status"] != "captured":
            continue
        by_day.setdefault(t["created_at"].date(), []).append(t)

    double_fee_ids = {2, 9}       # clean pattern -> should auto-clear
    unexplained_ids = {14}         # no clean pattern -> needs review

    batch_seq = 0
    for day, day_txns in sorted(by_day.items()):
        batch_seq += 1
        utr = f"utr_EX{batch_seq:03d}"
        settlement_date = dt.datetime.combine(day, dt.time()) + dt.timedelta(days=2)
        batch_total = 0.0

        for t in day_txns:
            idx = int(t["id"].split("_")[-1]) if t["id"].split("_")[-1].isdigit() else -1
            net = round(t["amount"] - t["fee"] - t["tax"], 2)
            if idx in double_fee_ids:
                net = round(net - t["fee"], 2)
            elif idx in unexplained_ids:
                net = round(net - random.uniform(5, 20), 2)
            batch_total += net
            settlement_rows.append({
                "transaction_id": t["id"], "customer_id": t["customer_id"],
                "amount": t["amount"], "fee": t["fee"], "tax": t["tax"],
                "currency": "INR", "status": "captured",
                "created_at": t["created_at"].isoformat(),
                "settlement_utr": utr, "settled_net_amount": net,
                "settlement_date": settlement_date.isoformat(),
            })

        # one batch takes a known bank-charge-slab shortfall (auto-clears)
        if batch_seq == 3:
            bank_rows.append({
                "value_date": settlement_date.isoformat(),
                "amount": round(batch_total - 25.0, 2),
                "utr_reference": utr, "narrative": "RAZORPAY SETTLEMENT (bank chg)",
            })
        else:
            bank_rows.append({
                "value_date": settlement_date.isoformat(),
                "amount": round(batch_total, 2),
                "utr_reference": utr, "narrative": "RAZORPAY SETTLEMENT",
            })

    for t in txns:
        if t["status"] == "refunded":
            settlement_rows.append({
                "transaction_id": t["id"], "customer_id": t["customer_id"],
                "amount": t["amount"], "fee": t["fee"], "tax": t["tax"],
                "currency": "INR", "status": "refunded",
                "created_at": t["created_at"].isoformat(),
                "settlement_utr": "", "settled_net_amount": "", "settlement_date": "",
            })
        elif t["status"] == "failed":
            settlement_rows.append({
                "transaction_id": t["id"], "customer_id": t["customer_id"],
                "amount": t["amount"], "fee": 0, "tax": 0,
                "currency": "INR", "status": "failed",
                "created_at": t["created_at"].isoformat(),
                "settlement_utr": "", "settled_net_amount": "", "settlement_date": "",
            })

    settlement_buf = io.StringIO()
    fieldnames = [
        "transaction_id", "customer_id", "amount", "fee", "tax", "currency",
        "status", "created_at", "settlement_utr", "settled_net_amount", "settlement_date",
    ]
    writer = csv.DictWriter(settlement_buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(settlement_rows)

    bank_buf = io.StringIO()
    bank_writer = csv.DictWriter(bank_buf, fieldnames=["value_date", "amount", "utr_reference", "narrative"])
    bank_writer.writeheader()
    bank_writer.writerows(bank_rows)

    return settlement_buf.getvalue(), bank_buf.getvalue()
