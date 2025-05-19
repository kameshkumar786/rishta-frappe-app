import frappe
import random
from frappe import _
from datetime import datetime
import json
import base64
from frappe.utils import get_files_path, get_site_name, now
import requests
from frappe.utils.password import check_password, get_password_reset_limit


@frappe.whitelist(allow_guest=True)
def register_user():
    try:
        payload = frappe.form_dict

        required_fields = ["dob", "email", "gender", "mobile"]
        for field in required_fields:
            if field not in payload or not payload[field]:
                frappe.throw(f"{field} is required.")

        if not validate_email(payload['email']):
            frappe.throw("Invalid email format.")

        if not validate_mobile(payload['mobile']):
            frappe.throw("Invalid mobile number format.")

        if frappe.db.exists("User", {"email": payload['email']}):
            frappe.throw("Email already exists in User.")

        if frappe.db.exists("User", {"mobile_no": payload['mobile']}):
            frappe.throw("Mobile number already exists in User.")

        if frappe.db.exists("Rishta Profile", {"email": payload['email']}):
            frappe.throw("Email already exists in Rishta Profile.")

        if frappe.db.exists("Rishta Profile", {"mobile": payload['mobile']}):
            frappe.throw("Mobile number already exists in Rishta Profile.")

        # user = frappe.get_doc({
        #     "doctype": "User",
        #     "email": payload['email'],
        #     "first_name": payload['full_name'],
        #     "mobile_no": payload['mobile'],
        #     "enabled": 1,
        #     # "new_password": "default_password" 
        # })
        # user.insert(ignore_permissions=True)

        # Create a new Rishta Profile
        rishta_profile = frappe.get_doc({
            "doctype": "Rishta Profile",
            "dob": payload['dob'],
            "email": payload['email'],
            "first_name": payload['first_name'],
            "middle_name": payload['middle_name'] if payload['middle_name'] else '' ,
            "last_name": payload['last_name'] if payload['last_name'] else '',
            "gender": payload['gender'],
            "mobile_number": payload['mobile']
            
        })
        rishta_profile.insert(ignore_permissions=True)
        random_otp = random.randint(100000, 999999) 
        otp = frappe.get_doc({
            "doctype": "Rishta OTP Auth",
            "email": payload['email'],
            "otp": random_otp,
            "mobile_no": payload['mobile'],
            "enabled":0
           
        })
        otp.insert(ignore_permissions=True)
        frappe.db.commit()

        frappe.response.message = {
            'status': True,
            "data":rishta_profile,
            'message': "Profile Created Successfully"
        }

    except Exception as e:
        frappe.error_log("error","{e}")
        frappe.response.message = {
            'status': False,
            'message': str(e)
        }

@frappe.whitelist(allow_guest=True)
def validate_otp():
    try:
        payload = frappe.form_dict
        if 'email' not in payload and 'mobile_no' not in payload:
            frappe.throw("Either email or mobile number is required.")
        if 'otp' not in payload:
            frappe.throw("OTP is required.")

        if 'email' in payload:
            key = 'email'
            value = payload['email']
        else:
            key = 'mobile_no'
            value = payload['mobile_no']

        # Fetch the OTP record
        otp_record = frappe.get_all("Rishta OTP Auth", filters={key: value}, fields=["otp"])

        if not otp_record:
            frappe.throw("No OTP record found for the provided email or mobile number.")

        # Compare the provided OTP with the stored OTP
        stored_otp = otp_record[0].otp
        if stored_otp != payload['otp']:
            frappe.throw("Invalid OTP.")

        # If OTP is valid, you can proceed with further actions (e.g., logging in the user)
        # Here you can add logic to log in the user or mark the OTP as used

        # Optionally, delete the OTP record after successful validation
        frappe.delete_doc("Rishta OTP Auth", otp_record[0].name)
        userm = frappe.db.get_all('User', filters={key: value}, fields=['*'])
        user_email = userm[0].name
        # try:
        #     check_password(user_email, pwd)
        # except Exception as e:
        #     frappe.local.response["message"] = {
        #         "status": False,
        #         "message": "User Password  Is Not Correct",
        #     }
        #     return

        api_key, api_secret = generate_keys(user_email)
        # frappe.local.login_manager.user = user_email
        # frappe.local.login_manager.post_login()
        # profile_data = frappe.db.get_all('Rishta Profile', filters={'user_id': user_email}, fields=['*'])
        # if profile_data :
        frappe.local.response["message"] = {
            "status": True,
            "message": "OTP validated successfully.",
            "data":{
            "api_key": api_key,
            "api_secret": api_secret,
            # "first_name": userm[0].first_name
            }
        }
        return  

        frappe.response.message = {
            'status': True,
            'message': "OTP validated successfully."
        }

    except Exception as e:
        frappe.response.message = {
            'status': False,
            'message': str(e)
        }

@frappe.whitelist()
def get_doctype_images(doctype, docname, is_private):
    attachments = frappe.db.get_all("File",
        fields=["attached_to_name", "file_name", "file_url", "is_private"],
        filters={"attached_to_name": docname, "attached_to_doctype": doctype}
    )
    resp = []
    for attachment in attachments:
        # file_path = site_path + attachment["file_url"]
        x = get_files_path(attachment['file_name'], is_private=is_private)
        with open(x, "rb") as f:
            # encoded_string = base64.b64encode(image_file.read())
            img_content = f.read()
            img_base64 = base64.b64encode(img_content).decode()
            img_base64 = 'data:image/jpeg;base64,' + img_base64
        resp.append({"image": img_base64})

    return resp

@frappe.whitelist()
def generate_keys(user):
    user_details = frappe.get_doc("User", user)
    api_secret = frappe.generate_hash(length=15)
    
    if not user_details.api_key:
        api_key = frappe.generate_hash(length=15)
        user_details.api_key = api_key
    
    user_details.api_secret = api_secret

    user_details.flags.ignore_permissions = True
    user_details.save(ignore_permissions = True)
    frappe.db.commit()
    
    return user_details.api_key, api_secret


@frappe.whitelist(allow_guest=True)
def login_user(usr, pwd):

    if not usr or not pwd:
        frappe.local.response["message"] = {
            "status": False,
            "message": "invalid inputs"
        }
        return
    user_exist = frappe.db.exists("User",{'email': usr})
    if user_exist :
        userm = frappe.db.get_all('User', filters={'email': usr}, fields=['*'])
        user_email = userm[0].name
        try:
            check_password(user_email, pwd)
        except Exception as e:
            frappe.local.response["message"] = {
                "status": False,
                "message": "User Password  Is Not Correct",
            }
            return



        api_key, api_secret = generate_keys(user_email)
        # frappe.local.login_manager.user = user_email
        # frappe.local.login_manager.post_login()
        profile_data = frappe.db.get_all('Rishta Profile', filters={'user_id': user_email}, fields=['*'])
        if profile_data :
            frappe.local.response["message"] = {
                "status": True,
                "message": "User Already Exists",
                "data":{
                "api_key": api_key,
                "api_secret": api_secret,
                "first_name": userm[0].first_name,
                "profile_data":profile_data
                }
            }
            return 
        else:
            frappe.local.response["message"] = {
                "status": True,
                "message": "No Profile Found",
                "data":{
                "api_key": api_key,
                "api_secret": api_secret,
                "first_name": userm[0].first_name
                }
            }
            return        
    else:
        frappe.local.response["message"] = {
            "status": False,
            "message": "User Not Exists"
        }
        return


@frappe.whitelist()
def upload_file_in_doctype(datas, filename, docname, doctype):
   for data in datas:
        try:
            filename_ext = f'/home/frappe/frappe-bench/sites/rishtavishta.com/private/files/{filename}.png'
            base64data = data.replace('data:image/jpeg;base64,', '')
            imgdata = base64.b64decode(base64data)
            with open(filename_ext, 'wb') as file:
                file.write(imgdata)

            doc = frappe.get_doc(
                {
                    "file_name": f'{filename}.png',
                    "is_private": 1,
                    "file_url": f'/private/files/{filename}.png',
                    "attached_to_doctype": doctype,
                    "attached_to_name": docname,
                    "doctype": "File",
                }
            )
            doc.flags.ignore_permissions = True
            doc.insert()
            frappe.db.commit()
            return doc.file_url

        except Exception as e:
            frappe.log_error('ng_write_file', str(e))
            return e

@frappe.whitelist(allow_guest=True)
def get_rishta_profiles(page=1, page_size=10):
    try:
        page = int(page)
        page_size = int(page_size)
        start = (page - 1) * page_size

        profiles = frappe.get_all("Rishta Profile",
            fields=[
                "name", "full_name", "gender", "dob", "caste", "religion",
                "marital_status", "education", "occupation", "location_preference"
            ],
            limit_start=start,
            limit_page_length=page_size,
            order_by="creation desc"
        )

        for profile in profiles:
            image = frappe.db.get_value("File", {"attached_to_doctype": "Rishta Profile", "attached_to_name": profile.name}, "file_url")
            profile["image_url"] = image if image else ""

        return {
            "status": "success",
            "message": f"Fetched {len(profiles)} profiles",
            "data": profiles
        }

    except Exception as e:
        frappe.log_error("get_rishta_profiles", f"{e}")
        return {
            "status": "error",
            "message": str(e)
        }


def validate_email(email):
    # Simple email validation
    import re
    return re.match(r"[^@]+@[^@]+\.[^@]+", email) is not None

def validate_mobile(mobile):
    # Simple mobile number validation (10 digits)
    return mobile.isdigit() and len(mobile) == 10