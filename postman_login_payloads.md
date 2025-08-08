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

## 5. Clerk: Add Member (Pending Approval)
**POST** `http://127.0.0.1:5000/clerk/api/add-member`
- Body: `form-data`
  - `name`: John Doe
  - `kgid`: 123456
  - `phone`: 9876543210
  - `email`: johndoe@example.com
  - `pan_aadhar`: ABCDE1234F
  - `salary`: 50000
  - `organization_name`: VTU
  - `address`: 123 Main St, City
  - `otp`: 123456  *(from email)*
  - `photo`: [choose file]
  - `signature`: [choose file]

---

## 6. Manager: Approve Member
**POST** `http://127.0.0.1:5000/manager/approve-member`
- Body: `form-data`
  - `email`: johndoe@example.com

---

## 7. Manager: Reject Member
**POST** `http://127.0.0.1:5000/manager/reject-member`
- Body: `form-data`
  - `email`: johndoe@example.com

---

**Notes:**
- When a member is added, their status is `pending` and they cannot log in until approved by a manager.
- On approval or rejection, the member receives an email notification.
- Only members with `status: approved` can log in or complete first-time sign-in.
- Use the same email for all steps.
- Password must be at least 8 characters, include letters, numbers, and special characters.
- The OTP is sent to your email after step 1.
