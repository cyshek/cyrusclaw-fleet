import smtplib
try:
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:\n        s.login('cyshekari@gmail.com', 'yjse lddd mhan gbpe')\n        print('SMTP OK - logged in')\nexcept Exception as e:\n    print(f'SMTP FAIL: {e}')
