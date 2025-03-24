from flask import Flask, request
import requests
import json
import os
from datetime import datetime, timedelta

app = Flask(__name__)

PAGE_ACCESS_TOKEN = "EAAJF5d7eApwBO1fZBwDFrZCf1n2dj7LvWZCrXcJi58T3PCI99lRvRGvmcAebwaVLZBQHKOropGLwlgLnlZBrILZAepwNFE55YFJZAt4zvRNrEW2C0pbFzABo4cmr2QOkYOfamlBRaynnI78hATERZBU8nOTs5apZCVA13hpkMOHNoqma5Q6YE3vy3ZChjjVf08xfq6jAZDZD"
VERIFY_TOKEN = "20102010"
data_file_path = 'djezzy_data.json'

def load_user_data():
    if os.path.exists(data_file_path):
        with open(data_file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    return {}

def save_user_data(data):
    with open(data_file_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4)

def send_message(sender_id, message_text):
    url = f"https://graph.facebook.com/v22.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": sender_id},
        "message": {"text": message_text}
    }
    headers = {"Content-Type": "application/json"}
    requests.post(url, json=payload, headers=headers)

def send_otp(msisdn):
    url = 'https://apim.djezzy.dz/oauth2/registration'
    payload = f'msisdn={msisdn}&client_id=6E6CwTkp8H1CyQxraPmcEJPQ7xka&scope=smsotp'
    headers = {
        'User-Agent': 'Djezzy/2.6.7',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    try:
        response = requests.post(url, data=payload, headers=headers)
        return response.status_code == 200
    except requests.RequestException:
        return False

def verify_and_activate(msisdn, otp, sender_id):
    url = 'https://apim.djezzy.dz/oauth2/token'
    payload = f'otp={otp}&mobileNumber={msisdn}&scope=openid&client_id=6E6CwTkp8H1CyQxraPmcEJPQ7xka&client_secret=MVpXHW_ImuMsxKIwrJpoVVMHjRsa&grant_type=mobile'
    headers = {
        'User-Agent': 'Djezzy/2.6.7',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    try:
        response = requests.post(url, data=payload, headers=headers)
        if response.status_code == 200:
            tokens = response.json()
            user_data = load_user_data()
            user_data[sender_id] = {
                'msisdn': msisdn,
                'access_token': tokens['access_token'],
                'last_applied': None
            }
            save_user_data(user_data)
            return apply_gift(sender_id, msisdn, tokens['access_token'])
        return False
    except requests.RequestException:
        return False

def apply_gift(sender_id, msisdn, access_token):
    user_data = load_user_data()
    if datetime.now() - datetime.fromisoformat(user_data.get(sender_id, {}).get('last_applied', '2000-01-01')) < timedelta(days=1):
        send_message(sender_id, "⚠️ الرجاء الانتظار 24 ساعة قبل تفعيل هدية جديدة.")
        return False

    url = f'https://apim.djezzy.dz/djezzy-api/api/v1/subscribers/{msisdn}/subscription-product'
    payload = {
        'data': {
            'id': 'GIFTWALKWIN',
            'type': 'products',
            'meta': {'services': {'steps': 10000, 'code': 'GIFTWALKWIN1GO', 'id': 'WALKWIN'}}
        }
    }
    headers = {
        'User-Agent': 'Djezzy/2.6.7',
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {access_token}'
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.json()['message'].startswith('the subscription to the product'):
            send_message(sender_id, "🎉 تم تفعيل الهدية بنجاح: GIFTWALKWIN1GO!")
            user_data[sender_id]['last_applied'] = datetime.now().isoformat()
            save_user_data(user_data)
            return True
        else:
            send_message(sender_id, "⚠️ فشل تفعيل الهدية.")
            return False
    except requests.RequestException:
        send_message(sender_id, "⚠️ حدث خطأ أثناء تفعيل الهدية.")
        return False

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get('hub.verify_token') == VERIFY_TOKEN:
            return request.args.get('hub.challenge')
        return "Verification failed", 403

    if request.method == 'POST':
        data = request.json
        if 'entry' in data and 'messaging' in data['entry'][0]:
            for event in data['entry'][0]['messaging']:
                sender_id = event['sender']['id']
                user_data = load_user_data()

                if 'message' in event and 'text' in event['message'] and sender_id not in user_data:
                    send_message(sender_id, "👋 مرحبًا! أرسل رقم هاتف Djezzy الخاص بك (مثال: 0771234567) للبدء.")

                elif 'message' in event and 'text' in event['message']:
                    text = event['message']['text']
                    step = user_data.get(sender_id, {}).get('step', 'phone')

                    if step == 'phone' and text.startswith('07') and len(text) == 10:
                        msisdn = '213' + text[1:]
                        if send_otp(msisdn):
                            send_message(sender_id, "🔢 تم إرسال رمز OTP إلى رقمك. أدخل الرمز الذي تلقيته:")
                            user_data[sender_id] = {'msisdn': msisdn, 'step': 'otp'}
                            save_user_data(user_data)
                        else:
                            send_message(sender_id, "⚠️ فشل إرسال OTP. حاول مرة أخرى.")

                    elif step == 'otp':
                        if verify_and_activate(user_data[sender_id]['msisdn'], text, sender_id):
                            send_message(sender_id, "✅ تم التحقق وتفعيل الهدية بنجاح!")
                            user_data[sender_id]['step'] = 'done'
                            save_user_data(user_data)
                        else:
                            send_message(sender_id, "⚠️ رمز OTP غير صحيح. أدخل الرمز الصحيح.")

                    elif step == 'done':
                        send_message(sender_id, "🎁 لقد تم تفعيل الهدية بالفعل. يمكنك المحاولة مرة أخرى بعد 24 ساعة.")

            return "EVENT_RECEIVED", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
