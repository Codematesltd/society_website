-- 1) add staff_phone to loans
ALTER TABLE public.loans
  ADD COLUMN IF NOT EXISTS staff_phone text;

-- 2) ensure loan_records.loan_id can store the LN... string
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'loan_records' AND column_name = 'loan_id'
  ) THEN
    ALTER TABLE public.loan_records ADD COLUMN loan_id text;
  ELSE
    IF (SELECT data_type FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'loan_records' AND column_name = 'loan_id') <> 'text'
    THEN
      EXECUTE 'ALTER TABLE public.loan_records ALTER COLUMN loan_id TYPE text USING loan_id::text';
    END IF;
  END IF;
END
$$;

-- 3) index to speed surety lookups
CREATE INDEX IF NOT EXISTS idx_sureties_surety_customer_id ON public.sureties (surety_customer_id);

-- optional: index active flag + surety_customer_id composite (if you query both)
CREATE INDEX IF NOT EXISTS idx_sureties_customer_active ON public.sureties (surety_customer_id) WHERE active = true;
