CREATE TABLE loans (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id text UNIQUE,
    customer_id text NOT NULL,
    loan_type text NOT NULL, -- 'normal' or 'emergency'
    loan_amount numeric NOT NULL,
    interest_rate numeric NOT NULL,
    loan_term_months integer NOT NULL,
    purpose_of_loan text,
    purpose_of_emergency_loan text,
    status text NOT NULL DEFAULT 'pending',
    rejection_reason text,
    created_at timestamp with time zone DEFAULT now()
);

CREATE TABLE sureties (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id uuid NOT NULL REFERENCES loans(id) ON DELETE CASCADE,
    surety_customer_id text NOT NULL,
    surety_name text NOT NULL,
    surety_mobile text NOT NULL,
    surety_signature_url text,
    surety_photo_url text,
    active boolean NOT NULL DEFAULT true
);

CREATE TABLE loan_records (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id text NOT NULL,
    repayment_date date,
    repayment_amount numeric,
    outstanding_balance numeric,
    status text NOT NULL DEFAULT 'active'
);
