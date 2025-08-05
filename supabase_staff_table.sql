CREATE TABLE staff (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text NOT NULL UNIQUE,
    otp text,                                -- OTP stored here
    name text NOT NULL DEFAULT '',           -- default empty string
    kgid text NOT NULL DEFAULT '',
    phone text NOT NULL DEFAULT '',
    pan_aadhar text NOT NULL DEFAULT '',
    organization_name text NOT NULL DEFAULT '',
    address text NOT NULL DEFAULT '',
    photo_url text NOT NULL DEFAULT '',
    signature_url text NOT NULL DEFAULT '',
    created_at timestamp with time zone DEFAULT timezone('utc', now())
);
