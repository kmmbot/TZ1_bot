import requests
import hmac
import hashlib

url = "http://192.168.214.133/api/v1/billing/users/search"
salt = "12345"
secret = "d6538f988734083acdb091ca5d7f0c6992643458657a932f1dd0feb664ed239e0acb38aa58396074aeaa63e736f545e969687fa6c42e160c3e140e410a6fa12e"
sign = hmac.new(secret.encode(), salt.encode(), hashlib.sha512).hexdigest()

payload = {
    'field': 'numdogovor',
    'operator': '=',
    'value': '1234',
    'sign': sign,
    'salt': salt
}

# Заголовки запроса
headers = {}

# Выполняем запрос
response = requests.request("POST", url, headers=headers, data=payload)

data = response.json()

if data['success'] and 'data' in data and len(data['data']) > 0:
    phone_number = data['data'][0]['address']
    print(data)