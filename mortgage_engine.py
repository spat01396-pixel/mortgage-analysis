import pandas as pd


class MortgageCalculator:
    def __init__(
        self,
        price,
        loan_amount,
        annual_rate,
        tenure_years,
        prepayment_rules=None,
        variable_rates=None,
    ):
        self.price = price
        self.loan_amount = loan_amount
        self.annual_rate = annual_rate
        self.tenure_years = tenure_years
        # Each rule: {"start_year": int, "stop_year": int|None, "type": "fixed"|"percent", "amount": float, "pct": float}
        self.prepayment_rules = prepayment_rules or []
        # Each rule: {"year": int, "rate": float, "new_tenure_years": float|None}
        # "year" is the year from which the new rate (and optionally new remaining
        # tenure) applies — i.e. a remortgage / rate-change event. "new_tenure_years",
        # if given, resets the remaining loan term from that point (e.g. remortgaging
        # onto a fresh 20-year term). If omitted, the EMI is recalculated to keep
        # paying the loan off on its previously implied schedule.
        self.variable_rates = variable_rates or []

        self.total_months = tenure_years * 12
        self.ltv = self.loan_amount / self.price

    # -------------------------
    # Rate handling
    # -------------------------
    def _get_active_rate_rule(self, month):
        """Return the variable_rates rule in effect for this month, or None."""
        year = (month - 1) // 12 + 1
        applicable = [r for r in self.variable_rates if r["year"] <= year]
        if not applicable:
            return None
        return max(applicable, key=lambda r: r["year"])

    def get_rate_for_month(self, month):
        rule = self._get_active_rate_rule(month)
        if rule:
            return rule["rate"] / 100 / 12
        return self.annual_rate / 100 / 12

    # -------------------------
    # Prepayment for a given year
    # -------------------------
    def get_prepayment_for_year(self, year, balance):
        """Return the prepayment amount due at end of `year` given current `balance`."""
        total = 0.0
        for rule in self.prepayment_rules:
            start = rule.get("start_year", 1) or 1
            stop = rule.get("stop_year")  # None = no end
            if year < start:
                continue
            if stop is not None and year > stop:
                continue
            if rule.get("type") == "percent":
                total += balance * (rule.get("pct", 0) / 100)
            else:
                total += rule.get("amount", 0)
        return total

    # -------------------------
    # EMI (base, at origination)
    # -------------------------
    def calculate_emi(self, balance=None, rate=None, months=None):
        P = balance if balance else self.loan_amount
        r = (rate if rate else self.annual_rate) / 100 / 12
        n = months if months else self.total_months
        if r == 0:
            return P / n
        return P * (r * (1 + r) ** n) / ((1 + r) ** n - 1)

    # -------------------------
    # EMI recalc at a given month (used on rate change / remortgage)
    # -------------------------
    def _simulate_remaining_balance(
        self, start_month, balance, r_monthly, remaining_months, emi
    ):
        """Project the balance forward `remaining_months` at a fixed EMI/rate,
        applying any prepayment rules along the way (used to solve for the EMI
        that actually clears the balance by the target month)."""
        bal = balance
        for i in range(remaining_months):
            month = start_month + i
            interest = bal * r_monthly
            principal = emi - interest
            bal -= principal
            if month % 12 == 0:
                year = month // 12
                prepay = self.get_prepayment_for_year(year, bal)
                bal -= prepay
        return bal

    def _closed_form_emi(self, balance, r_monthly, remaining_months):
        if remaining_months <= 0:
            remaining_months = 1
        if r_monthly == 0:
            return balance / remaining_months
        return (
            balance
            * (r_monthly * (1 + r_monthly) ** remaining_months)
            / ((1 + r_monthly) ** remaining_months - 1)
        )

    def _solve_emi(self, month, balance, r_monthly, remaining_months):
        """Find the EMI that pays off `balance` in exactly `remaining_months`,
        taking into account any prepayment rules that will fire along the way.
        Falls back to the closed-form annuity formula when there are no
        prepayment rules."""
        if remaining_months <= 0:
            remaining_months = 1

        if not self.prepayment_rules:
            return self._closed_form_emi(balance, r_monthly, remaining_months)

        # Bisection search for the EMI that drives the simulated ending
        # balance to (approximately) zero, given known future prepayments.
        lo, hi = 0.0, max(
            balance / remaining_months, balance * (r_monthly + 0.0001) + 1
        )
        for _ in range(60):
            end_balance = self._simulate_remaining_balance(
                month, balance, r_monthly, remaining_months, hi
            )
            if end_balance <= 0:
                break
            hi *= 2
        for _ in range(80):
            mid = (lo + hi) / 2
            end_balance = self._simulate_remaining_balance(
                month, balance, r_monthly, remaining_months, mid
            )
            if end_balance > 0:
                lo = mid
            else:
                hi = mid
        return hi

    def _project_payoff_month(
        self, start_month, balance, r_monthly, emi, hard_cap=2400
    ):
        """Simulate forward at a fixed EMI/rate (applying prepayment rules)
        to find the month the loan would naturally be paid off on its
        current trajectory. Used so that a rate change which doesn't specify
        an explicit new tenure preserves the payoff date implied by
        prepayments already made, rather than snapping back to the loan's
        original full term."""
        bal = balance
        month = start_month
        while month <= hard_cap:
            interest = bal * r_monthly
            principal = emi - interest
            bal -= principal
            if month % 12 == 0:
                year = month // 12
                prepay = self.get_prepayment_for_year(year, bal)
                bal -= prepay
            if bal <= 0:
                return month
            month += 1
        return hard_cap

    def get_emi_for_month(self, month, balance):
        """Kept for backwards compatibility — recalculates EMI assuming the
        loan stays on its originally implied payoff month."""
        r_monthly = self.get_rate_for_month(month)
        remaining_months = self.total_months - month + 1
        return self._solve_emi(month, balance, r_monthly, remaining_months)

    # -------------------------
    # Schedule
    # -------------------------
    def generate_schedule(self):
        balance = self.loan_amount
        current_payoff_month = self.total_months
        last_rule_year = None
        # Standard fixed starting EMI — a plain amortization over the original
        # term, just like a normal mortgage payment. Any prepayments are
        # voluntary extras on top of this and are what naturally shorten the
        # payoff; they should NOT be "priced in" to this starting EMI.
        current_emi = self._closed_form_emi(
            balance, self.annual_rate / 100 / 12, current_payoff_month
        )
        current_rate = self.annual_rate / 100 / 12

        schedule = []
        month = 1
        # Generous safety cap so a remortgage onto a much longer term (or a
        # pathological input) can't spin the loop forever.
        max_extension = max(
            [
                int(r.get("new_tenure_years") or 0) * 12 + r["year"] * 12
                for r in self.variable_rates
            ],
            default=0,
        )
        max_months = max(self.total_months, max_extension) + 1200

        while month <= max_months:
            rule = self._get_active_rate_rule(month)
            rule_year = rule["year"] if rule else None
            r = (rule["rate"] / 100 / 12) if rule else (self.annual_rate / 100 / 12)

            if rule_year != last_rule_year:
                # A new rate rule has just taken effect — this is a rate
                # change or remortgage event, so recalculate the EMI.
                last_rule_year = rule_year
                if rule and rule.get("new_tenure_years"):
                    # Explicit remortgage onto a fresh term.
                    current_payoff_month = (
                        month - 1 + int(rule["new_tenure_years"]) * 12
                    )
                elif not self.prepayment_rules:
                    # No prepayments in play, so there's no accelerated
                    # trajectory to preserve — keep targeting the loan's
                    # original maturity exactly (avoids compounding
                    # floating-point drift from repeated projection).
                    current_payoff_month = self.total_months
                else:
                    # No explicit new term: preserve the payoff date implied
                    # by the loan's current trajectory (including any
                    # prepayments already accelerating it), rather than
                    # resetting back to the original full tenure.
                    current_payoff_month = self._project_payoff_month(
                        month, balance, current_rate, current_emi
                    )
                remaining_months = current_payoff_month - month + 1
                current_emi = self._solve_emi(month, balance, r, remaining_months)
                current_rate = r

            interest = balance * r
            principal = current_emi - interest
            balance -= principal

            prepay = 0.0
            if month % 12 == 0 and balance > 0:
                prepay = self.get_prepayment_for_year(month // 12, balance)
                balance -= prepay
                balance = max(balance, 0)

            schedule.append(
                {
                    "Month": month,
                    "Year": (month - 1) // 12 + 1,
                    "EMI": current_emi,
                    "Balance": max(balance, 0),
                    "Interest Paid": interest,
                    "Principal Paid": principal,
                    "Prepayment": prepay,
                }
            )

            if balance <= 0:
                break

            month += 1

        return pd.DataFrame(schedule)

    # -------------------------
    # Summary
    # -------------------------
    def summary(self):
        df = self.generate_schedule()
        return {
            "emi": df["EMI"].iloc[0],
            "total_interest": df["Interest Paid"].sum(),
            "payoff_years": df["Month"].iloc[-1] / 12,
            "schedule": df,
        }

    # -------------------------
    # Helper: balance at year
    # -------------------------
    def get_balance_at_year(self, year):
        df = self.generate_schedule()
        if year <= df["Year"].max():
            return df[df["Year"] == year].iloc[-1]["Balance"]
        return 0

    # -------------------------
    # Rental snapshot WITH growth
    # -------------------------
    def rental_analysis(
        self, rent, tax, maint, vacancy, year, tax_mode="uk", rent_growth=0
    ):
        df = self.generate_schedule()
        balance = self.get_balance_at_year(year)
        annual_rent = rent * ((1 + rent_growth / 100) ** (year - 1)) * 12
        costs = annual_rent * (maint + vacancy) / 100
        interest = (
            df[df["Year"] == year]["Interest Paid"].sum()
            if year in df["Year"].values
            else 0
        )

        if tax_mode == "simple":
            taxable = annual_rent - costs - interest
            tax_paid = max(taxable, 0) * tax / 100
        elif tax_mode == "uk":
            taxable = annual_rent - costs
            gross_tax = taxable * tax / 100
            credit = interest * 0.2
            tax_paid = max(gross_tax - credit, 0)
        else:
            tax_paid = annual_rent * tax / 100

        net = annual_rent - costs - tax_paid
        monthly_emi = (
            df[df["Year"] == year]["EMI"].mean() if year in df["Year"].values else 0
        )

        return {
            "remaining_balance": balance,
            "tax_paid": tax_paid,
            "net_cashflow": (net / 12) - monthly_emi,
        }

    # -------------------------
    # Rental trend WITH growth
    # -------------------------
    def rental_cashflow_over_time(
        self, rent, tax, maint, start_year, tax_mode="uk", rent_growth=0
    ):
        df = self.generate_schedule()
        results = []
        max_year = max(self.tenure_years, int(df["Year"].max()))

        for year in range(start_year, max_year + 1):
            annual_rent = rent * ((1 + rent_growth / 100) ** (year - start_year)) * 12
            costs = annual_rent * maint / 100
            interest = (
                df[df["Year"] == year]["Interest Paid"].sum()
                if year in df["Year"].values
                else 0
            )

            if tax_mode == "simple":
                taxable = annual_rent - costs - interest
                tax_paid = max(taxable, 0) * tax / 100
            elif tax_mode == "uk":
                taxable = annual_rent - costs
                gross_tax = taxable * tax / 100
                tax_paid = max(gross_tax - interest * 0.2, 0)
            else:
                tax_paid = annual_rent * tax / 100

            net = annual_rent - costs - tax_paid
            monthly_emi = (
                df[df["Year"] == year]["EMI"].mean() if year in df["Year"].values else 0
            )

            results.append({"Year": year, "Net Cashflow": (net / 12) - monthly_emi})

        return pd.DataFrame(results)

    # -------------------------
    # EMI chart data
    # -------------------------
    def get_emi_chart_data(self):
        df = self.generate_schedule()
        segments = []
        prev_rate = None
        seg_start = 1

        for _, row in df.iterrows():
            month = int(row["Month"])
            r_annual = self.get_rate_for_month(month) * 12 * 100
            if prev_rate is None:
                prev_rate = r_annual
                seg_start = month
            elif abs(r_annual - prev_rate) > 1e-9:
                segments.append((seg_start, month - 1, prev_rate))
                seg_start = month
                prev_rate = r_annual

        segments.append((seg_start, int(df["Month"].iloc[-1]), prev_rate))
        return df, segments

    # -------------------------
    # Selling analysis
    # -------------------------
    def selling_analysis(self, year, price_change, inflation, selling_costs):
        df = self.generate_schedule()
        df_valid = df[df["Year"] <= year]
        balance = (
            df_valid.iloc[-1]["Balance"] if not df_valid.empty else self.loan_amount
        )
        interest_paid = df_valid["Interest Paid"].sum()

        sale_price = self.price * ((1 + price_change / 100) ** year)
        inflation_adj_sale_price = sale_price / ((1 + inflation / 100) ** year)
        proceeds = sale_price - balance - selling_costs

        gain = sale_price - self.price - selling_costs
        real_gain = inflation_adj_sale_price - self.price - selling_costs
        fin_gain = gain - interest_paid
        fin_real_gain = real_gain - interest_paid

        return {
            "sale_price": sale_price,
            "remaining_balance": balance,
            "interest_paid": interest_paid,
            "proceeds": proceeds,
            "inflation_adj_sale_price": inflation_adj_sale_price,
            "gain": gain,
            "real_gain": real_gain,
            "fin_gain": fin_gain,
            "fin_real_gain": fin_real_gain,
        }
