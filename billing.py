import hmac
import hashlib
import requests

url = "https://192.168.214.130/api/v1/billing/users/search"
salt = "123456"
secret_key = "d6538f988734083acdb091ca5d7f0c6992643458657a932f1dd0feb664ed239e0acb38aa58396074aeaa63e736f545e969687fa6c42e160c3e140e410a6fa12e"

sign = hmac.new(secret_key.encode(), salt.encode(), hashlib.sha512).hexdigest()

payload={'field': 'uid',
'operator': '=',
'value': '7',
'sign': sign,
'salt': salt}
files=[

]
headers = {}

response = requests.request("POST", url, headers=headers, data=payload, files=files, verify=False)

print(response.text)
