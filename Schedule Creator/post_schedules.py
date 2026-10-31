'''
CBL schedules are posted to the BambooHR API using this script. 
The script uses the requests library to send POST requests with schedule payloads defined in the schedules module (schedules.py). 
The API key is retrieved from the BAPI module and encoded in base64 for authorization. 
The script prints the response status and text for each schedule posted.
'''
import requests, base64, schedules, BAPI

URL = "https://cbljm.bamboohr.com/api/v1/scheduling/shifts"
KEY = BAPI.KEY
AUTHORIZATION = f"Basic {base64.b64encode(KEY.encode('utf-8')).decode('utf-8')}"
HEADERS = {
    "accept": "application/json",
    "content-type": "application/json",
    "authorization": AUTHORIZATION,
}

PAYLOADS = schedules.PAYLOADS

def post_schedules():
    for index, payload in enumerate(PAYLOADS, start=1):
        print(f"Posting schedule {index}/{len(PAYLOADS)}: {payload['scheduleId']} {payload['start']} employees={payload['employeeIds']}")
        response = requests.post(URL, headers=HEADERS, json=payload)
        print(f"Response: {response.status_code} - {response.text}\n")
        print(f"{index}/{len(PAYLOADS)} posted: {payload['scheduleId']} {payload['start']} employees={payload['employeeIds']}")

if __name__ == "__main__":
    post_schedules()