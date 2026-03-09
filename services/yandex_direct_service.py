"""
Yandex Direct API v5 — Service Layer
Управление рекламными кампаниями через API
Docs: https://yandex.ru/dev/direct/doc/ref-v5/concepts/about.html
"""
import requests
import os
from datetime import datetime, timedelta


API_URL = "https://api.direct.yandex.com/json/v5/"
SANDBOX_URL = "https://api-sandbox.direct.yandex.com/json/v5/"


class YandexDirectService:
    def __init__(self):
        self.token = os.getenv("YANDEX_DIRECT_TOKEN", "")
        self.client_id = os.getenv("YANDEX_DIRECT_CLIENT_ID", "")
        self.use_sandbox = os.getenv("YANDEX_DIRECT_SANDBOX", "false").lower() == "true"

    @property
    def base_url(self):
        return SANDBOX_URL if self.use_sandbox else API_URL

    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept-Language": "ru",
            "Content-Type": "application/json",
        }

    def _request(self, service, method, params=None):
        """Generic API v5 request"""
        if not self.token:
            return {"error": "YANDEX_DIRECT_TOKEN not configured"}

        url = f"{self.base_url}{service}"
        body = {"method": method}
        if params:
            body["params"] = params

        try:
            resp = requests.post(url, json=body, headers=self.headers, timeout=30)
            data = resp.json()
            if "error" in data:
                return {"error": f"{data['error'].get('error_string', 'Unknown')}: {data['error'].get('error_detail', '')}"}
            return data.get("result", data)
        except requests.exceptions.Timeout:
            return {"error": "API timeout (30s)"}
        except Exception as e:
            return {"error": str(e)}

    # ==================== CAMPAIGNS ====================

    def get_campaigns(self):
        """Get all campaigns with basic stats"""
        result = self._request("campaigns", "get", {
            "SelectionCriteria": {},
            "FieldNames": [
                "Id", "Name", "Status", "State", "Type",
                "StartDate", "DailyBudget", "Statistics"
            ],
        })
        if "error" in result:
            return result

        campaigns = result.get("Campaigns", [])
        return {"campaigns": campaigns}

    def get_campaign_stats(self, date_from=None, date_to=None):
        """Get campaign statistics via Reports service"""
        if not date_from:
            date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not date_to:
            date_to = datetime.now().strftime("%Y-%m-%d")

        # Reports API uses a different endpoint and headers
        url = f"{self.base_url}reports"
        headers = {
            **self.headers,
            "processingMode": "auto",
            "returnMoneyInMicros": "false",
            "skipReportHeader": "true",
            "skipReportSummary": "true",
        }
        body = {
            "params": {
                "SelectionCriteria": {
                    "DateFrom": date_from,
                    "DateTo": date_to,
                },
                "FieldNames": [
                    "CampaignName", "CampaignId",
                    "Impressions", "Clicks", "Ctr",
                    "Cost", "AvgCpc", "Conversions"
                ],
                "ReportName": f"stats_{date_from}_{date_to}_{datetime.now().timestamp():.0f}",
                "ReportType": "CAMPAIGN_PERFORMANCE_REPORT",
                "DateRangeType": "CUSTOM_DATE",
                "Format": "TSV",
                "IncludeVAT": "YES",
            }
        }

        try:
            resp = requests.post(url, json=body, headers=headers, timeout=60)

            # 201 = report in queue, 202 = building
            if resp.status_code in (201, 202):
                return {"status": "building", "retry_after": 5}

            if resp.status_code != 200:
                return {"error": f"Report API error {resp.status_code}: {resp.text[:200]}"}

            # Parse TSV response
            lines = resp.text.strip().split("\n")
            if len(lines) < 2:
                return {"stats": [], "totals": _empty_totals()}

            header = lines[0].split("\t")
            stats = []
            totals = {
                "impressions": 0, "clicks": 0, "cost": 0.0, "conversions": 0
            }

            for line in lines[1:]:
                cols = line.split("\t")
                if len(cols) < len(header):
                    continue
                row = dict(zip(header, cols))
                entry = {
                    "campaign_name": row.get("CampaignName", ""),
                    "campaign_id": row.get("CampaignId", ""),
                    "impressions": _int(row.get("Impressions", "0")),
                    "clicks": _int(row.get("Clicks", "0")),
                    "ctr": _float(row.get("Ctr", "0")),
                    "cost": _float(row.get("Cost", "0")),
                    "avg_cpc": _float(row.get("AvgCpc", "0")),
                    "conversions": _int(row.get("Conversions", "0")),
                }
                stats.append(entry)
                totals["impressions"] += entry["impressions"]
                totals["clicks"] += entry["clicks"]
                totals["cost"] += entry["cost"]
                totals["conversions"] += entry["conversions"]

            totals["ctr"] = round(totals["clicks"] / totals["impressions"] * 100, 2) if totals["impressions"] else 0
            totals["avg_cpc"] = round(totals["cost"] / totals["clicks"], 2) if totals["clicks"] else 0

            return {"stats": stats, "totals": totals}

        except requests.exceptions.Timeout:
            return {"error": "Report API timeout"}
        except Exception as e:
            return {"error": str(e)}

    def get_search_queries(self, date_from=None, date_to=None):
        """Search queries: what users typed -> which keyword matched"""
        if not date_from:
            date_from = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        if not date_to:
            date_to = datetime.now().strftime("%Y-%m-%d")

        url = f"{self.base_url}reports"
        headers = {
            **self.headers,
            "processingMode": "auto",
            "returnMoneyInMicros": "false",
            "skipReportHeader": "true",
            "skipReportSummary": "true",
        }
        body = {
            "params": {
                "SelectionCriteria": {
                    "DateFrom": date_from,
                    "DateTo": date_to,
                },
                "FieldNames": [
                    "Date", "Query", "CriterionType", "Criterion",
                    "CampaignName", "Impressions", "Clicks", "Cost",
                    "AvgCpc", "Bounces"
                ],
                "ReportName": f"sq_{date_from}_{date_to}_{datetime.now().timestamp():.0f}",
                "ReportType": "SEARCH_QUERY_PERFORMANCE_REPORT",
                "DateRangeType": "CUSTOM_DATE",
                "Format": "TSV",
                "IncludeVAT": "YES",
            }
        }

        try:
            import time as _time
            resp = None
            for _attempt in range(6):
                resp = requests.post(url, json=body, headers=headers, timeout=60)
                if resp.status_code == 200:
                    break
                elif resp.status_code in (201, 202):
                    wait = int(resp.headers.get('retryIn', 2))
                    _time.sleep(min(wait + 1, 15))
                else:
                    return {"error": f"Report API error {resp.status_code}: {resp.text[:300]}"}

            if not resp or resp.status_code != 200:
                return {"error": "Report is still building, try again later"}

            lines = resp.text.strip().split("\n")
            if len(lines) < 2:
                return {"queries": []}

            header = lines[0].split("\t")
            queries = []

            type_names = {
                "KEYWORD": "ключевик",
                "AUTOTARGETING": "автотаргет",
                "AUDIENCE_TARGET": "аудитория",
                "DYNAMIC_TEXT_AD_TARGET": "динамич.",
            }

            for line in lines[1:]:
                cols = line.split("\t")
                if len(cols) < len(header):
                    continue
                row = dict(zip(header, cols))
                clicks = _int(row.get("Clicks", "0"))
                impressions = _int(row.get("Impressions", "0"))
                queries.append({
                    "date": row.get("Date", ""),
                    "query": row.get("Query", ""),
                    "criterion_type": type_names.get(
                        row.get("CriterionType", ""), row.get("CriterionType", "")),
                    "keyword": row.get("Criterion", ""),
                    "campaign": row.get("CampaignName", ""),
                    "impressions": impressions,
                    "clicks": clicks,
                    "cost": _float(row.get("Cost", "0")),
                    "avg_cpc": _float(row.get("AvgCpc", "0")),
                    "bounces": _int(row.get("Bounces", "0")),
                    "bounce_rate": round(
                        _int(row.get("Bounces", "0")) / clicks * 100, 1
                    ) if clicks > 0 else 0,
                })

            # Sort by clicks desc
            queries.sort(key=lambda x: x["clicks"], reverse=True)
            return {"queries": queries, "total": len(queries)}

        except requests.exceptions.Timeout:
            return {"error": "Report API timeout"}
        except Exception as e:
            return {"error": str(e)}

    def suspend_campaign(self, campaign_id):
        """Pause a campaign"""
        return self._request("campaigns", "suspend", {
            "SelectionCriteria": {"Ids": [int(campaign_id)]}
        })

    def resume_campaign(self, campaign_id):
        """Resume a campaign"""
        return self._request("campaigns", "resume", {
            "SelectionCriteria": {"Ids": [int(campaign_id)]}
        })

    # ==================== ADS ====================

    def get_ads(self, campaign_ids=None):
        """Get ads, optionally filtered by campaign"""
        criteria = {}
        if campaign_ids:
            criteria["CampaignIds"] = [int(c) for c in campaign_ids]

        result = self._request("ads", "get", {
            "SelectionCriteria": criteria,
            "FieldNames": ["Id", "CampaignId", "State", "Status", "Type"],
            "TextAdFieldNames": ["Title", "Title2", "Text", "Href", "Mobile"],
        })
        if "error" in result:
            return result

        return {"ads": result.get("Ads", [])}

    # ==================== KEYWORDS ====================

    def get_keywords(self, campaign_ids=None):
        """Get keywords for campaigns"""
        # First get ad group IDs for the campaigns
        if campaign_ids:
            groups_result = self._request("adgroups", "get", {
                "SelectionCriteria": {"CampaignIds": [int(c) for c in campaign_ids]},
                "FieldNames": ["Id", "CampaignId", "Name"],
            })
            if "error" in groups_result:
                return groups_result
            group_ids = [g["Id"] for g in groups_result.get("AdGroups", [])]
            if not group_ids:
                return {"keywords": []}
            criteria = {"AdGroupIds": group_ids}
        else:
            criteria = {}

        result = self._request("keywords", "get", {
            "SelectionCriteria": criteria,
            "FieldNames": [
                "Id", "Keyword", "AdGroupId", "CampaignId",
                "Status", "State", "Bid",
            ],
        })
        if "error" in result:
            return result

        return {"keywords": result.get("Keywords", [])}

    # ==================== ACCOUNT ====================

    def get_account_balance(self):
        """Get account balance and currency"""
        # Use Campaigns service to infer — or use Dictionaries
        # Simpler: return account info from a lightweight call
        result = self._request("campaigns", "get", {
            "SelectionCriteria": {},
            "FieldNames": ["Id", "Funds"],
        })
        if "error" in result:
            return result

        campaigns = result.get("Campaigns", [])
        if not campaigns:
            return {"balance": 0, "currency": "RUB"}

        # Sum shared account funds if available
        funds = campaigns[0].get("Funds", {})
        shared = funds.get("SharedAccountFunds", {})
        return {
            "balance": _float(str(shared.get("Spend", 0))),
            "currency": "RUB",
        }

    def is_configured(self):
        """Check if token is set"""
        return bool(self.token)


# ==================== Helpers ====================

def _int(val):
    try:
        return int(val.replace("--", "0"))
    except (ValueError, AttributeError):
        return 0

def _float(val):
    try:
        return round(float(val.replace("--", "0")), 2)
    except (ValueError, AttributeError):
        return 0.0

def _empty_totals():
    return {"impressions": 0, "clicks": 0, "ctr": 0, "cost": 0, "avg_cpc": 0, "conversions": 0}


# Singleton
yandex_direct_service = YandexDirectService()
