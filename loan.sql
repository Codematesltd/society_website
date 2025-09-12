create table public.loan_records (
  id uuid not null default gen_random_uuid (),
  loan_id text not null,
  repayment_date date null,
  repayment_amount numeric null,
  outstanding_balance numeric null,
  status text not null default 'active'::text,
  interest_amount numeric null,
  principal_amount numeric null,
  remaining_principal_amount numeric null, -- New column to track remaining principal after each repayment
  constraint loan_records_pkey primary key (id)
) TABLESPACE pg_default;

create table public.loans (
  id uuid not null default gen_random_uuid (),
  loan_id text null,
  customer_id text not null,
  loan_type text not null,
  loan_amount numeric not null,
  interest_rate numeric not null,
  loan_term_months integer not null,
  purpose_of_loan text null,
  purpose_of_emergency_loan text null,
  status text not null default 'pending'::text,
  rejection_reason text null,
  created_at timestamp with time zone null default now(),
  staff_email text null,
  staff_name text null,
  staff_photo_url text null,
  staff_signature_url text null,
  staff_phone text null,
  constraint loans_pkey primary key (id),
  constraint loans_loan_id_key unique (loan_id)
) TABLESPACE pg_default;