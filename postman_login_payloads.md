# Universal Login & First-Time Sign-In API Payloads

## 1. First-Time Sign-In (Request OTP)
**POST** `/auth/first-time-signin`
- Body: `form-data`
  - `email`: user_or_staff_email@example.com

---

## 2. OTP Verification
**POST** `/auth/otp_verification`
- Body: `form-data`
  - `otp`: 123456   *(replace with OTP received in email)*

---

## 3. Set Password
**POST** `/auth/set_password`
- Body: `form-data`
  - `password`: MyNewPassword@123

---

## 4. Login
**POST** `/auth/login`
- Body: `form-data`
  - `email`: user_or_staff_email@example.com
  - `password`: MyNewPassword@123

---

**Notes:**
- Use the same email for all steps.
- Password must be at least 8 characters, include letters, numbers, and special characters.
- The OTP is sent to your email after step 1.
