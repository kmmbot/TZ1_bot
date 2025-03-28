import requests, hmac, hashlib, mysql.connector, uvicorn
from fastapi import FastAPI, Request

app = FastAPI()
url = "http://192.168.214.133/api/v1/billing/users/search"
salt = "12345"
secret = "d6538f988734083acdb091ca5d7f0c6992643458657a932f1dd0feb664ed239e0acb38aa58396074aeaa63e736f545e969687fa6c42e160c3e140e410a6fa12e"
sign = hmac.new(secret.encode(), salt.encode(), hashlib.sha512).hexdigest()


def send_message(name, speed, cost):
    payload = {
            "name": name,
            "speed": speed,
            "cost": cost
        }
    print(payload)
    response = requests.post("http://localhost:8000", json=payload)

    if response.status_code == 200:
        print('Данные успешно отправлены')
    else:
        print(response)

    return

@app.post("/")
async def receive_data(request: Request):
    data = await request.json()
    gid = data.get("gid", "unknown")

    connection = mysql.connector.connect(
            host='192.168.214.133',  # IP-адрес виртуальной машины
            port=3306,  # Порт базы данных
            user='kmm',  # Имя пользователя
            password='12345',  # Пароль
            database='mikbill'  # Имя базы данных
        )



    cursor = connection.cursor()

    query = f"SELECT packet, speed_rate, fixed_cost FROM packets WHERE gid = {gid}"
    cursor.execute(query)
    info_packet = cursor.fetchall()
    print(info_packet)
    name = info_packet[0][0]
    speed = round(info_packet[0][1] / 1024)
    cost = info_packet[0][2]

    send_message(name, speed, cost)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5001)