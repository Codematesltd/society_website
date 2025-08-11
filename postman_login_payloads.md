# API Testing Workflow (Postman Steps)

---

## 1. Manager Adds Staff (Send OTP to Staff Email)
**POST** `http://127.0.0.1:5000/manager/add-staff/send-otp`
- Body: `form-data`
  - `email`: staff_email@example.com

---

## 2. Staff Registration (with OTP)
**POST** `http://127.0.0.1:5000/manager/add-staff`
- Body: `form-data`
  - `name`: Jane Smith
  - `kgid`: 654321
  - `phone`: 9876543211
  - `email`: staff_email@example.com
  - `aadhar_no`: 432143214321
  - `pan_no`: ZXCVB9876L
  - `organization_name`: VTU
  - `address`: 456 Main St, City
  - `otp`: [OTP received in staff email]
  - `photo`: [choose file]
  - `signature`: [choose file]

---

## 3. Staff Adds Member (Send OTP to Member Email)
**POST** `http://127.0.0.1:5000/staff/api/add-member/send-otp`
- Body: `form-data`
  - `email`: member_email@example.com

---

## 4. Member Registration (with OTP)
**POST** `http://127.0.0.1:5000/staff/api/add-member`
- Body: `form-data`
  - `name`: John Doe
  - `kgid`: 123456
  - `phone`: 9876543210
  - `email`: member_email@example.com
  - `aadhar_no`: 123412341234
  - `pan_no`: ABCDE1234F
  - `salary`: 50000
  - `organization_name`: VTU
  - `address`: 123 Main St, City
  - `otp`: [OTP received in member email]
  - `photo`: [choose file]
  - `signature`: [choose file]

---

## 5. First-Time Sign-In (Staff or Member) - Request OTP
**POST** `http://127.0.0.1:5000/auth/first-time-signin`
- Body: `form-data`
  - `email`: staff_email@example.com` or `member_email@example.com

---

## 6. OTP Verification (Staff or Member)
**POST** `http://127.0.0.1:5000/auth/otp_verification`
- Body: `form-data`
  - `otp`: [OTP received in email]

---

## 7. Set Password (Staff or Member)
**POST** `http://127.0.0.1:5000/auth/set_password`
- Body: `form-data`
  - `password`: MyNewPassword@123

---

## 8. Login (Staff or Member)
**POST** `http://127.0.0.1:5000/auth/login`
- Body: `form-data`
  - `email`: staff_email@example.com` or `member_email@example.com
  - `password`: MyNewPassword@123

---

## 9. Manager Approves Member
**POST** `http://127.0.0.1:5000/manager/approve-member`
- Body: `form-data`
  - `email`: member_email@example.com

---

## 10. Manager Rejects Member
**POST** `http://127.0.0.1:5000/manager/reject-member`
- Body: `form-data`
  - `email`: member_email@example.com

---

## 11. Unblock Member (by Manager)
**POST** `http://127.0.0.1:5000/manager/unblock-member`
- Body: `form-data`
  - `email`: member_email@example.com

---

## 12. Unblock Member (by Staff)
**POST** `http://127.0.0.1:5000/staff/api/unblock-member`
- Body: `form-data`
  - `email`: member_email@example.com

---

## 13. Unblock Staff (by Manager)
**POST** `http://127.0.0.1:5000/manager/unblock-staff`
- Body: `form-data`
  - `email`: staff_email@example.com

---

## 14. Forgot Password (Staff or Member)
**POST** `http://127.0.0.1:5000/auth/forgot_password`
- Body: `form-data`
  - `email`: staff_email@example.com or member_email@example.com

---

## 15. Reset Password (Staff or Member)
**POST** `http://127.0.0.1:5000/auth/reset_password?token=[token from email]`
- Body: `form-data`
  - `password`: MyNewPassword@123

---

**Notes:**
- For every registration, use the OTP received in the respective email.
- Only approved members can log in and complete first-time sign-in.
- Passwords must be at least 8 characters, include letters, numbers, and special characters.
- Use the same email for all steps for each user.
- Attach files for `photo` and `signature` fields where required.
- If you need to test dashboards, use GET requests to `/staff/dashboard`, `/members/dashboard`, etc.
