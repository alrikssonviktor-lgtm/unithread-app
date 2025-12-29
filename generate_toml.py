import json

try:
    with open("service_account.json", "r") as f:
        data = json.load(f)

    print("\nKopiera allt nedanför denna linje och klistra in i Streamlit Secrets:\n")
    print("-" * 50)
    print("[gcp_service_account]")
    for key, value in data.items():
        # json.dumps ser till att specialtecken (som nya rader i nyckeln) hanteras rätt
        print(f'{key} = {json.dumps(value)}')
    print("-" * 50)
    print("\n")

except FileNotFoundError:
    print("Kunde inte hitta service_account.json")
