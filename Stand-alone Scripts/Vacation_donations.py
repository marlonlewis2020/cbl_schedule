import requests
import BAPI
import base64

vacation_donations = {
    # 253: -1,
    # 633: -1,
    # 491: -2,
    # 630: -2,
    # 552: -1,
    # 568: -1,
    # 673: -2,
    # 432: -1,
    # 530: -1,
    # 265: -2,
    # 236: -1,
    # 480: -1,
    # 216: -1,
    # 330: -1,
    # 407: -1,
    # 488: -1,
    # 221: -2,
    # 615: -2,
    # 646: -1,
    # 275: -1,
    # 215: -2,
    # 234: -3,
    # 122: -1,
}

KEY = BAPI.KEY
AUTHORIZATION = f"Basic {base64.b64encode(KEY.encode('utf-8')).decode('utf-8')}"
HEADERS = {
    "accept": "application/json",
    "content-type": "application/json",
    "authorization": AUTHORIZATION,
}

for eeid, amount in vacation_donations.items():
    if amount < 0:
        url = f"https://cbljm.bamboohr.com/api/v1/employees/{eeid}/time_off/balance_adjustment"
        print(f"Posting balance adjustment for Employee ID: {eeid}, Amount: {amount}")
        print(f"URL: {url}")
        payload = { "date": "2026-11-04",
                "timeOffTypeId": 83,
                "amount": amount,
                "note": "Vacation donation for October 2026."
                }
        response = requests.put(url, json=payload, headers=HEADERS)
        print(f"Employee ID: {eeid}, Response: {response.status_code}, {response.text}")

