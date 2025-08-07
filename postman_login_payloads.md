# Universal Login & First-Time Sign-In API Payloads

## 1. First-Time Sign-In (Request OTP)
**POST** `http://127.0.0.1:5000/auth/first-time-signin`
- Body: `form-data`
  - `email`: user_or_staff_email@example.com

---

## 2. OTP Verification
**POST** `http://127.0.0.1:5000/auth/otp_verification`
- Body: `form-data`
  - `otp`: 123456   *(replace with OTP received in email)*

---

## 3. Set Password
**POST** `http://127.0.0.1:5000/auth/set_password`
- Body: `form-data`
  - `password`: MyNewPassword@123

---

## 4. Login
**POST** `http://127.0.0.1:5000/auth/login`
- Body: `form-data`
  - `email`: user_or_staff_email@example.com
  - `password`: MyNewPassword@123

---

**Notes:**
- Use the same email for all steps.
- Password must be at least 8 characters, include letters, numbers, and special characters.
- The OTP is sent to your email after step 1.
